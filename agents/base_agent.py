import logging
from typing import Optional, Tuple, Type, TypeVar

from pydantic import BaseModel
from langchain_openai import AzureChatOpenAI

import warnings

from config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BaseAgent")

T = TypeVar("T", bound=BaseModel)


class BaseAgent:
    """
    Foundational base agent providing isolated Azure OpenAI execution wrapper,
    token utilization audit tracking, and runtime error isolation.
    """
    def __init__(self):
        settings = get_settings()

        self.llm = AzureChatOpenAI(
            azure_deployment=settings.azure_openai_chat_deployment_name,
            api_version=settings.openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            temperature=settings.llm_temperature,
            max_retries=3
        )

        self.token_alert_threshold = settings.token_alert_threshold

    def call_llm_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T]
    ) -> Tuple[Optional[T], dict]:
        token_metadata = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

        try:
            structured_llm = self.llm.with_structured_output(
                response_model,
                include_raw=True
            )

            messages = [
                ("system", system_prompt),
                ("user", user_prompt)
            ]

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*PydanticSerializationUnexpectedValue.*",
                    category=UserWarning
                )
                warnings.filterwarnings(
                    "ignore",
                    message=".*Expected.*got.*",
                    category=UserWarning
                )
                response = structured_llm.invoke(messages)

            parsed_output = response.get("parsed")
            raw_message = response.get("raw")

            if raw_message:
                # Primary path: usage_metadata on AIMessage (LangChain structured output)
                usage_meta = getattr(raw_message, "usage_metadata", None)
                if usage_meta:
                    token_metadata["prompt_tokens"] = usage_meta.get("input_tokens", 0)
                    token_metadata["completion_tokens"] = usage_meta.get("output_tokens", 0)
                    token_metadata["total_tokens"] = usage_meta.get("total_tokens", 0)
                else:
                    # Fallback: some LangChain versions still populate response_metadata
                    resp_meta = getattr(raw_message, "response_metadata", {})
                    usage = resp_meta.get("token_usage", {})
                    token_metadata["prompt_tokens"] = usage.get("prompt_tokens", 0)
                    token_metadata["completion_tokens"] = usage.get("completion_tokens", 0)
                    token_metadata["total_tokens"] = usage.get("total_tokens", 0)

            parsing_error = response.get("parsing_error")
            if parsing_error:
                logger.error(f"Structured output parsing error: {parsing_error}")
                return None, token_metadata

            if token_metadata["total_tokens"] >= self.token_alert_threshold:
                logger.critical(
                    f"CRITICAL TOKEN BREACH: {token_metadata['total_tokens']} tokens consumed. "
                    f"Threshold is {self.token_alert_threshold}."
                )
            else:
                logger.info(f"Execution call completed. Tokens consumed: {token_metadata['total_tokens']}.")

            return parsed_output, token_metadata

        except Exception as e:
            logger.error(f"Runtime error during LLM execution: {str(e)}")
            return None, token_metadata