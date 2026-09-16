"""Unified LLM client abstraction.

Provides a common interface for different LLM backends (securellm, Azure OpenAI,
OpenAI) so that callers don't need to know which provider is in use.

Usage::

    from src.llm_client import create_llm_client

    client = create_llm_client()  # auto-detects from env vars
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.3,
    )
    print(response["choices"][0]["message"]["content"])
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class CompletionsAPI(ABC):
    """Minimal chat-completions interface returning OpenAI-format dicts."""

    @abstractmethod
    def create(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a chat completion.

        Returns a dict with at least::

            {"choices": [{"message": {"role": "assistant", "content": "...", "tool_calls": [...]}}]}
        """


class ChatAPI:
    """Namespace so callers can write ``client.chat.completions.create(...)``."""

    def __init__(self, completions: CompletionsAPI):
        self.completions = completions


class LLMClient(ABC):
    """Base class for all LLM backends."""

    chat: ChatAPI

    def ping(self, model: str | None = None) -> bool:
        """Send a trivial request to verify connectivity. Returns True on success."""
        try:
            self.chat.completions.create(
                model=model or self.default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False

    @property
    def default_model(self) -> str:
        """Sensible default model for quick health checks."""
        return "gpt-4.1-mini"

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider label (e.g. 'securellm', 'azure', 'openai')."""


# ---------------------------------------------------------------------------
# SecureLLM backend
# ---------------------------------------------------------------------------

class _SecureLLMCompletions(CompletionsAPI):

    def __init__(self, inner_client: Any):
        self._inner = inner_client

    def create(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        return self._inner.chat.completions.create(model=model, messages=messages, **kwargs)


class SecureLLMClient(LLMClient):
    """Wraps ``securellm.Client``."""

    def __init__(self, api_key: str | None = None):
        try:
            from securellm import Client  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "securellm is not installed. Install it with: "
                "uv sync --extra securellm  (or pip install securellm)"
            ) from exc
        inner = Client(api_key=api_key)
        self.chat = ChatAPI(_SecureLLMCompletions(inner))

    @property
    def default_model(self) -> str:
        return "nero:gemini-2.5-flash-lite"

    @property
    def provider_name(self) -> str:
        return "securellm"


# ---------------------------------------------------------------------------
# Azure OpenAI backend
# ---------------------------------------------------------------------------

class _AzureCompletions(CompletionsAPI):

    def __init__(self, inner_client: Any):
        self._inner = inner_client

    def create(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        response = self._inner.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
        return _openai_response_to_dict(response)


class AzureOpenAIClient(LLMClient):
    """Wraps ``openai.AzureOpenAI``.

    Required env vars (or constructor args):
      - AZURE_OPENAI_API_KEY
      - AZURE_OPENAI_ENDPOINT
      - AZURE_OPENAI_API_VERSION  (defaults to 2024-12-01-preview)
      - AZURE_OPENAI_DEPLOYMENT   (used as default model)
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        api_version: str | None = None,
        deployment: str | None = None,
    ):
        from openai import AzureOpenAI  # type: ignore[import-untyped]

        self._deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
        inner = AzureOpenAI(
            api_key=api_key or os.environ.get("AZURE_OPENAI_API_KEY"),
            azure_endpoint=endpoint or os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=api_version or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        self.chat = ChatAPI(_AzureCompletions(inner))

    @property
    def default_model(self) -> str:
        return self._deployment

    @property
    def provider_name(self) -> str:
        return "azure"


# ---------------------------------------------------------------------------
# OpenAI backend (direct)
# ---------------------------------------------------------------------------

class _OpenAICompletions(CompletionsAPI):

    def __init__(self, inner_client: Any):
        self._inner = inner_client

    def create(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        response = self._inner.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
        return _openai_response_to_dict(response)


class OpenAIClient(LLMClient):
    """Wraps ``openai.OpenAI`` for direct OpenAI API access.

    Required env vars (or constructor args):
      - OPENAI_API_KEY
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        from openai import OpenAI  # type: ignore[import-untyped]

        inner = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
        )
        self.chat = ChatAPI(_OpenAICompletions(inner))

    @property
    def provider_name(self) -> str:
        return "openai"


class _VersaCompletions(CompletionsAPI):
    def __init__(self):
        try:
            from lab_llm.versa import make_versa_openai_completion, make_versa_claude_completion
            if os.getenv("VERSA_API_KEY"):
                self.openai_completion = make_versa_openai_completion()
            else:
                self.openai_completion = None
            if os.getenv("AWS_ACCESS_KEY_ID"):
                self.claude_completion = make_versa_claude_completion()
            else:
                self.claude_completion = None
        except ImportError:
            raise ImportError(f"The lab_llm package is not installed. Please install it from https://github.com/jjfenglab/llm-api.")

    def create(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        model = model.replace("versa:", "")
        if "anthropic" in model:
            if self.claude_completion is None:
                raise ValueError("Attempted to use Anthropic through Versa API without credentials. AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required.")
            return self.claude_completion(model, messages=messages, **kwargs)
        if self.openai_completion is None:
            raise ValueError("Attempted to use Azure OpenAI through Versa API without credentials. VERSA_API_KEY is required.")
        return self.openai_completion(model, messages=messages, **kwargs)


class VersaClient(LLMClient):
    """
    Wraps the Versa API using lab_llm.
    """
    def __init__(self, **kwargs):
        self.chat = ChatAPI(_VersaCompletions())

    @property
    def default_model(self):
        return "versa:azure/gpt-4.1-mini-2025-04-14"
    
    @property
    def provider_name(self):
        return "versa"

class _LiteLLMCompletions(CompletionsAPI):
    def __init__(self):
        try:
            import litellm
            self.completion = litellm.completion
        except ImportError:
            raise ImportError(f"The litellm package is not installed. Please run `pip install litellm`")

    def create(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        model = model.replace("litellm:", "")
        return self.completion(model, messages=messages, **kwargs)


class LiteLLMClient(LLMClient):
    """
    Wraps the LiteLLM API for access to any LLM provider, open-source models, etc.
    """
    def __init__(self, **kwargs):
        self.chat = ChatAPI(_LiteLLMCompletions())

    @property
    def default_model(self):
        return "litellm:hosted_vllm/qwen3.8-27b"
    
    @property
    def provider_name(self):
        return "litellm"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _openai_response_to_dict(response: Any) -> dict[str, Any]:
    """Convert an ``openai`` library ChatCompletion object to a plain dict.

    The ``openai>=1.0`` library returns Pydantic models. securellm returns
    plain dicts. We normalize to dicts so the caller code is provider-agnostic.
    """
    if isinstance(response, dict):
        return response

    choices = []
    for choice in response.choices:
        msg: dict[str, Any] = {
            "role": choice.message.role,
            "content": choice.message.content,
        }
        if choice.message.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]
        choices.append({
            "index": choice.index,
            "message": msg,
            "finish_reason": choice.finish_reason,
        })

    result: dict[str, Any] = {"choices": choices}
    if hasattr(response, "usage") and response.usage:
        result["usage"] = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    return result


# ---------------------------------------------------------------------------
# Google / Vertex AI backend (detected via GOOGLE_CLOUD_PROJECT)
# ---------------------------------------------------------------------------

class _GoogleMessage:
    def __init__(self, d):
        self.role = d.get("role", "assistant")
        self.content = d.get("content", "")
        self.tool_calls = d.get("tool_calls")

    def model_dump(self):
        return {"role": self.role, "content": self.content, "tool_calls": self.tool_calls}

    def __iter__(self):
        yield "role", self.role
        yield "content", self.content
        if self.tool_calls:
            yield "tool_calls", self.tool_calls

class _GoogleChoice:
    def __init__(self, d):
        self.message = _GoogleMessage(d.get("message", {}))
        self.finish_reason = d.get("finish_reason", "stop")
        self.index = d.get("index", 0)

class _GoogleResponse:
    def __init__(self, d):
        self.choices = [_GoogleChoice(c) for c in d.get("choices", [])]
        self.model = d.get("model", "")

class _GoogleCompletions(CompletionsAPI):

    def __init__(self, inner_client: Any):
        self._inner = inner_client

    def create(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        response = self._inner.chat.completions.create(model=model, messages=messages, **kwargs)
        if isinstance(response, dict):
            return _GoogleResponse(response)
        return response



class GoogleLLMClient(LLMClient):
    """Uses SecureLLMClient's GoogleProvider via GOOGLE_CLOUD_PROJECT credentials.

    No API key is needed — authentication is handled by Application Default
    Credentials (GOOGLE_APPLICATION_CREDENTIALS or gcloud ADC).
    The model is read from EXTRACTION_MODEL_ID, falling back to gemini-2.5-flash-lite.
    """

    def __init__(self, model_id: str | None = None, **kwargs: Any):
        try:
            from securellm import Client  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "securellm is not installed. Install it with: pip install ./secure-llm"
            ) from exc
        inner = Client(api_key=None)
        self.chat = ChatAPI(_GoogleCompletions(inner))
        raw = model_id or os.environ.get("EXTRACTION_MODEL_ID", "nero:gemini-2.5-flash-lite")
        self._model_id = raw.strip('"').strip("'")

    @property
    def default_model(self) -> str:
        return self._model_id

    @property
    def provider_name(self) -> str:
        return "google"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDER_ORDER = [
    ("versa", "VERSA_API_KEY"),
    ("versa", "AWS_ACCESS_KEY_ID"),
    ("securellm", "VAULT_SECRET_KEY"),
    ("securellm", "AI_HUB_API_KEY"),
    ("google", "GOOGLE_CLOUD_PROJECT"),
    ("azure", "AZURE_OPENAI_ENDPOINT"),
    ("openai", "OPENAI_API_KEY"),
]


def create_llm_client(
    provider: str | None = None,
    **kwargs: Any,
) -> LLMClient:
    """Create an LLM client, auto-detecting the provider from env vars.

    Args:
        provider: Force a specific provider ('securellm', 'azure', 'openai', 'google').
                  If None, picks the first one whose required env var is set.
        **kwargs: Passed to the provider constructor.

    Returns:
        An ``LLMClient`` instance.

    Raises:
        RuntimeError: If no provider could be auto-detected.
        ValueError:  If an unknown provider name is given.
    """
    if provider is None:
        for name, env_var in _PROVIDER_ORDER:
            if os.environ.get(env_var):
                provider = name
                break

    if provider is None:
        available = ", ".join(f"{name} ({var})" for name, var in _PROVIDER_ORDER)
        raise RuntimeError(
            f"No LLM provider detected. Set one of: {available}"
        )

    if provider == "versa":
        return VersaClient(**kwargs)
    if provider == "securellm":
        return SecureLLMClient(**kwargs)
    if provider == "google":
        return GoogleLLMClient(**kwargs)
    if provider == "azure":
        return AzureOpenAIClient(**kwargs)
    if provider == "openai":
        return OpenAIClient(**kwargs)
    if provider == "litellm":
        return LiteLLMClient(**kwargs)

    raise ValueError(f"Unknown LLM provider: {provider!r}. Use 'versa', 'securellm', 'google', 'azure', 'openai', or 'litellm'.")
