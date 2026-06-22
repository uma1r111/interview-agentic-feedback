import time
import uuid
import logging
from collections import defaultdict
from contextvars import ContextVar
from typing import Optional
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

# Set up logging for the middleware
logger = logging.getLogger("API_Middleware")

# Global contextvar to hold token usages for the current request/thread context
token_tracker_var: ContextVar[Optional[dict]] = ContextVar("token_tracker_var", default=None)

# Simple thread-safe memory storage for tracking request timestamps per client IP
rate_limit_store = defaultdict(list)


class BestPracticeLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that profiles all HTTP requests, generates unique Request IDs,
    measures execution duration, and attaches them to response headers.
    Bypasses the '/health' endpoint to avoid spamming system logs.
    """
    async def dispatch(self, request: Request, call_next):
        # Bypass health check to prevent log pollution from keep-alive health checks
        if request.url.path == "/health":
            return await call_next(request)

        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Save request ID in request state so route handlers can read it if needed
        request.state.request_id = request_id
        
        logger.info(f"[{request_id}] Incoming {request.method} request to {request.url.path}")
        
        try:
            response = await call_next(request)
            
            process_time = time.time() - start_time
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"
            
            logger.info(f"[{request_id}] Completed in {process_time:.4f}s with status {response.status_code}")
            return response
            
        except Exception as exc:
            process_time = time.time() - start_time
            logger.error(f"[{request_id}] Failed after {process_time:.4f}s. Error: {str(exc)}")
            raise exc


class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware that blocks uploads that are too large (limit set to 10MB)
    on POST and PUT requests to prevent memory/disk exhaustion attacks.
    """
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT"):
            content_length = request.headers.get("content-length")
            if content_length:
                max_bytes = 10 * 1024 * 1024  # 10 Megabytes limit
                if int(content_length) > max_bytes:
                    logger.warning(
                        f"Blocked upload from {request.client.host if request.client else 'unknown'}: "
                        f"{content_length} bytes exceeds 10MB limit."
                    )
                    return Response(
                        content="File too large. Maximum size allowed is 10MB.",
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                    )
                    
        return await call_next(request)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Middleware that limits the number of write operations a client IP can make.
    GET requests are never rate-limited (they are cheap reads).
    - '/health': Bypassed completely.
    - Routes containing '/evaluate' (POST): Strict limit of 5 requests per minute.
    - All other POST/PATCH/DELETE routes: 30 requests per minute.
    """
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Bypass health checks and all GET requests entirely —
        # GET is a read operation and should never be blocked.
        if path == "/health" or request.method == "GET":
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Decide limit based on the route
        # /evaluate triggers expensive LLM pipelines — strict limit
        if "/evaluate" in path:
            limit = 5
            window = 60
        else:
            # Other write operations (create candidate, upload files, patch decision)
            limit = 30
            window = 60

        # Build a unique key per IP + route type so evaluate and upload
        # limits don't share the same bucket
        bucket_key = f"{client_ip}:evaluate" if "/evaluate" in path else client_ip

        # Retrieve request history for this bucket
        timestamps = rate_limit_store[bucket_key]

        # Slide the window: discard timestamps older than the window
        timestamps = [t for t in timestamps if current_time - t < window]
        rate_limit_store[bucket_key] = timestamps

        if len(timestamps) >= limit:
            logger.warning(
                f"Rate limit exceeded for IP {client_ip} on {request.method} {path}. "
                f"Limit: {limit} requests per {window}s."
            )
            return Response(
                content=f"Rate limit exceeded. Maximum allowed is {limit} write requests per minute.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Record the current request timestamp
        timestamps.append(current_time)
        return await call_next(request)


class AITokenCostTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that tracks AI tokens and calculates the dollar cost of Azure OpenAI
    calls made during the lifecycle of the request.
    """
    async def dispatch(self, request: Request, call_next):
        # Initialize token tracker dictionary
        tracker = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0
        }
        
        # Set the token tracker in the ContextVar for this request's context
        token = token_tracker_var.set(tracker)
        
        try:
            response = await call_next(request)
            
            # Post-request processing: calculate cost
            # Pricing for Azure OpenAI (gpt-4o default):
            # $5.00 per 1M input tokens, $15.00 per 1M output tokens
            prompt_cost = (tracker["prompt_tokens"] / 1_000_000) * 5.0
            completion_cost = (tracker["completion_tokens"] / 1_000_000) * 15.0
            total_cost = prompt_cost + completion_cost
            tracker["cost"] = total_cost
            
            # Inject cost/token metrics as headers if any LLM calls were made
            if tracker["total_tokens"] > 0:
                response.headers["X-AI-Tokens-Input"] = str(tracker["prompt_tokens"])
                response.headers["X-AI-Tokens-Output"] = str(tracker["completion_tokens"])
                response.headers["X-AI-Cost"] = f"${total_cost:.5f}"
                
                logger.info(
                    f"Request {request.url.path} consumed {tracker['total_tokens']} LLM tokens. "
                    f"Estimated Cost: ${total_cost:.5f}"
                )
                
            return response
            
        finally:
            # Clean up ContextVar
            token_tracker_var.reset(token)
