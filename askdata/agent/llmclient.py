"""Wraps OpenAI-compatible model calls used by the SQL agent."""

from openai import OpenAI

from askdata.core.config import LoadSettings
from askdata.core.errors import ModelError


class LlmClient:
    """Calls an OpenAI-compatible chat completion endpoint."""

    def __init__(self, settings=None):
        self.settings = settings or LoadSettings()

    def Complete(self, prompt):
        """Sends one prompt and returns the model text response."""
        if not self.settings.modelApiKey: raise ModelError("MODEL_API_KEY is required for model calls")
        try:
            client = OpenAI(api_key=self.settings.modelApiKey, base_url=self.settings.modelBaseUrl)
            response = client.chat.completions.create(model=self.settings.modelName, messages=[{"role": "user", "content": prompt}], temperature=0)
            return response.choices[0].message.content.strip()
        except Exception as error:
            raise ModelError(f"Model call failed: {error}") from error

    def Chat(self, messages, tools=None):
        """Sends messages with optional tool definitions. Returns the raw message for ReAct loop processing."""
        if not self.settings.modelApiKey: raise ModelError("MODEL_API_KEY is required for model calls")
        try:
            client = OpenAI(api_key=self.settings.modelApiKey, base_url=self.settings.modelBaseUrl)
            kwargs = {"model": self.settings.modelName, "messages": messages, "temperature": 0}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception as error:
            raise ModelError(f"Model call failed: {error}") from error
