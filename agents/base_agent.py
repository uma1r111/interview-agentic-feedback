import os
import logging
from typing import Type, TypeVar, Optional, Tuple
from pydantic import BaseModel
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv

# Load environmental variables from root .env file
load_dotenv()

# Setup structured logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BaseAgent")

# Context threshold boundary rule
TOKEN_ALERT_THRESHOLD = 80000

T = TypeVar("T", bound=BaseModel)

class BaseAgent:
    """
    Foundational base agent providing isolated Azure OpenAI execution wrapper,
    token utilization audit tracking, and runtime error isolation.
    """
    def __init__(self):
        # 1. Deduce credentials and settings from environment variables
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_version = os.getenv("OPENAI_API_VERSION")
        deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")

        if not all([api_key, endpoint, api_version, deployment_name]):
            raise ValueError(
                "Missing core Azure OpenAI configuration environment variables. "
                "Ensure .env contains AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, "
                "OPENAI_API_VERSION, and AZURE_OPENAI_CHAT_DEPLOYMENT_NAME."
            )

        # 2. Instantiate isolated AzureChatOpenAI client framework
        self.llm = AzureChatOpenAI(
            azure_deployment=deployment_name,
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
            temperature=0.1,  # Low variance for strict analytical criteria matching
            max_retries=3     # Self-contained retry logic
        )

    def call_llm_structured(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        response_model: Type[T]
    ) -> Tuple[Optional[T], dict]:
        """
        Executes a call against Azure OpenAI forcing compliance with a Pydantic model response.
        Tracks precise token tracking telemetry metadata per call invocation block.
        
        Returns:
            Tuple[Optional[PydanticInstance], TokenMetadataDict]
        """
        token_metadata = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        try:
            # Enforce structured validation layout at the native LLM api border
            structured_llm = self.llm.with_structured_output(response_model)
            
            # Formulate structured message payload arrays
            messages = [
                ("system", system_prompt),
                ("user", user_prompt)
            ]
            
            # Invoke generation
            response = structured_llm.invoke(messages)
            
            # Extract runtime token utilization telemetry out of the execution response block
            if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
                usage = response.response_metadata["token_usage"]
                token_metadata["prompt_tokens"] = usage.get("prompt_tokens", 0)
                token_metadata["completion_tokens"] = usage.get("completion_tokens", 0)
                token_metadata["total_tokens"] = usage.get("total_tokens", 0)
            
            # Enforce context boundary rules monitoring
            if token_metadata["total_tokens"] >= TOKEN_ALERT_THRESHOLD:
                logger.critical(
                    f"CRITICAL TOKEN BREACH WARNING: Single execution call consumed "
                    f"{token_metadata['total_tokens']} tokens! Boundary safety threshold rule is set to {TOKEN_ALERT_THRESHOLD}."
                )
            else:
                logger.info(f"Execution call completed successfully. Tokens consumed: {token_metadata['total_tokens']}.")

            return response, token_metadata

        except Exception as e:
            logger.error(f"Isolated Runtime Error caught during LLM generation execution step: {str(e)}")
            return None, token_metadata