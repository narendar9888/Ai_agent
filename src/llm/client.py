"""LLM client for foundation model interaction with strict environment variable compliance."""

import json
import os
from typing import Any, Dict, Optional
from openai import OpenAI

from ..config.settings import LLMConfig


TupleDict = tuple[Dict[str, Any], int]


class LLMClientError(Exception):
    """Raised when LLM invocation fails or API key is missing."""
    pass


class LLMClient:
    """
    Client for interacting with foundation models.
    Reads credentials from os.environ['AI_API_KEY'] as required by PS Section 32.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()

        # PS Section 32: Primary credential is AI_API_KEY
        api_key = (
            self.config.api_key
            or os.environ.get("AI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )

        self.api_key = api_key
        self.base_url = self.config.base_url or os.environ.get("AI_API_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        self.model_name = self.config.model_name or os.environ.get("AI_MODEL_NAME", "gpt-4o")

        self._client: Optional[OpenAI] = None
        if self.api_key:
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self._client = OpenAI(**client_kwargs)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def require_configured(self):
        if not self.is_configured:
            raise LLMClientError(
                "Missing AI_API_KEY environment variable.\n"
                "Please export your API key according to PS Section 32:\n"
                "  export AI_API_KEY=\"<YOUR_API_KEY>\"\n"
            )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calls the foundation model and returns parsed text/JSON response and token counts."""
        self.require_configured()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        try:
            response = self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            content = choice.message.content or ""
            usage = response.usage

            prompt_tokens = usage.prompt_tokens if usage else len(user_prompt) // 4
            completion_tokens = usage.completion_tokens if usage else len(content) // 4
            total_tokens = usage.total_tokens if usage else (prompt_tokens + completion_tokens)

            return {
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
        except Exception as e:
            raise LLMClientError(f"LLM API request failed: {str(e)}") from e

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> TupleDict:
        """Invokes LLM and safely extracts a JSON object."""
        resp = self.complete(system_prompt, user_prompt, temperature=temperature)
        raw_text = resp["content"].strip()

        # Handle markdown fences
        if "```json" in raw_text:
            raw_text = raw_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            data = json.loads(raw_text)
            return data, resp["total_tokens"]
        except json.JSONDecodeError as jde:
            # Fallback regex extraction for {}
            import re
            m = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0)), resp["total_tokens"]
                except Exception:
                    pass
            raise LLMClientError(f"Could not parse valid JSON from LLM response: {raw_text[:200]}") from jde
