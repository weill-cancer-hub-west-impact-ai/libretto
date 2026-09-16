import os
import langextract as lx
from langextract.providers.gemini import GeminiLanguageModel
import re

AIHUB_BASE = "https://aihubapi.stanfordhealthcare.org/azure-openai"
AIHUB_API_VERSION = "2025-04-01-preview"

def _aihub_row(deployment_id: str, max_input_tokens: int, max_output_tokens: int, fence_output: bool, out_token_key: str) -> dict:
    return {
        "type": "aihub",
        "model_id": deployment_id,
        "base_url": f"{AIHUB_BASE}/deployments/{deployment_id}/chat/completions",
        "api_version": AIHUB_API_VERSION,
        "max_input_tokens": max_input_tokens,
        "max_output_tokens": max_output_tokens,
        "fence_output": fence_output,
        "out_token_key": out_token_key
    }


# (deployment_id, max_input_tokens, max_output_tokens) — limits are approximate caps for client-side checks
_AIHUB_SPECS: list[tuple[str, int, int]] = [
    ("chat", 128_000, 8_192, True, "max_completion_tokens"),
    ("deepseek-r1", 128_000, 32_768, True, "max_tokens"),
    ("gpt-4o", 128_000, 16_384, True, "max_completion_tokens"),
    ("gpt-4-1", 1_047_576, 32_768, True, "max_completion_tokens"),
    ("gpt-4-1-mini", 1_047_576, 32_768, True, "max_completion_tokens"),
    ("gpt-4-1-mini-low-threshold-policy", 1_047_576, 32_768, True, "max_completion_tokens"),
    ("gpt-4-1-mini-high-threshold-policy", 1_047_576, 32_768, True, "max_completion_tokens"),
    ("gpt-4-1-nano", 1_047_576, 32_768, True, "max_completion_tokens"),
    ("gpt-5", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-mini", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-nano", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-1", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-2", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-2-high-threshold-policy", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-4", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-4-high-threshold-policy", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-4-mini", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-4-mini-high-threshold-policy", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-4-nano", 270_000, 128_000, True, "max_completion_tokens"),
    ("gpt-5-4-nano-high-threshold-policy", 270_000, 128_000, True, "max_completion_tokens"),
    ("grok-3", 128_000, 16_384, True, "max_completion_tokens"),
    ("grok-3-mini", 128_000, 16_384, True, "max_completion_tokens"),
    ("o1", 200_000, 100_000, True, "max_completion_tokens"),
    ("o3", 200_000, 100_000, True, "max_completion_tokens"),
    ("o3-mini", 200_000, 100_000, True, "max_completion_tokens"),
    ("o4-mini", 200_000, 100_000, True, "max_completion_tokens"),
    ("phi-4-mini-instruct", 128_000, 16_384, True, "max_completion_tokens"),
]

LX_MODEL_REGISTRY = {
    f"aihub:{dep}": _aihub_row(dep, mi, mo, fo, otk) for dep, mi, mo, fo, otk in _AIHUB_SPECS
}

LX_MODEL_REGISTRY.update({
    # Vertex AI models
    "nero:gemini-2.0-flash": {
        "model_id": "gemini-2.0-flash",
        "type": "vertex",
        "max_input_tokens": 1_048_576,
        "max_output_tokens": 8_192 - 1_024,
        "fence_output": True,
        "out_token_key": "max_output_tokens"
    },
    "nero:gemini-2.5-pro": {
        "model_id": "gemini-2.5-pro",
        "type": "vertex",
        "max_input_tokens": 1_048_576,
        "max_output_tokens": 65_535 - 1_024,
        "fence_output": True,
        "out_token_key": "max_output_tokens"
    },
    "nero:gemini-2.5-flash": {
        "model_id": "gemini-2.5-flash",
        "type": "vertex",
        "max_input_tokens": 1_048_576,
        "max_output_tokens": 65_535 - 1_024,
        "fence_output": True,
        "out_token_key": "max_output_tokens"
    },
    "nero:gemini-2.5-flash-lite": {
        "model_id": "gemini-2.5-flash-lite",
        "type": "vertex",
        "max_input_tokens": 1_048_576,
        "max_output_tokens": 65_535 - 1_024,
        "fence_output": True,
        "out_token_key": "max_output_tokens"
    },
    # Vertex AI Claude models
    "vertex-claude:claude-opus-4-6": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 32_000,
        "fence_output": True,
        "out_token_key": "max_tokens",
    },
    "vertex-claude:claude-sonnet-4-6": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 32_000,
        "fence_output": True,
        "out_token_key": "max_tokens",
    },
    "vertex-claude:claude-haiku-4-5@20251001": {
        "max_input_tokens": 200_000,
        "max_output_tokens": 8_096,
        "fence_output": True,
        "out_token_key": "max_tokens",
    },
})

try:
    from lab_llm import LLMApi, wrap_completion_function, CachingCompletion
    from lab_llm.versa import make_versa_openai_completion, make_versa_claude_completion
    import asyncio
    import os
    import litellm

    litellm.drop_params = True
    
    VERSA_REGEX = r"^versa:(.*)$"

    @lx.providers.registry.register(VERSA_REGEX)
    class VersaLanguageModel(lx.inference.BaseLanguageModel):
        """
        Custom LangExtract language model that uses the UCSF LLMApi (https://github.com/jjfenglab/llm-api) 
        instead of direct OpenAI calls.
        """

        def __init__(self, model_id: str = 'versa:azure/gpt-4.1-mini-2025-04-14', **kwargs):
            # Separate actual model name from prefix
            if model_id.startswith('versa:'):
                self.model_id = model_id[6:]
            else:
                self.model_id = model_id

            self.organization = None
            self.format_type = kwargs.get("format_type", lx.data.FormatType.JSON)
            self.temperature = kwargs.get("temperature", 0.0)
            self.max_workers = kwargs.get("max_workers", 10)
            self.max_completion_tokens = kwargs.get("max_tokens")
            self._extra_kwargs = kwargs

            # Use provided LLMApi instance
            if "anthropic" in model_id:
                completion = make_versa_claude_completion()
                self.model_kwargs = {"effort": "low"}
            else:
                completion = make_versa_openai_completion()
                self.model_kwargs = {"reasoning_effort": "low"}

            if cache_path := os.getenv("LLM_CACHE_DB"):
                cache = CachingCompletion(cache_path)
            else:
                cache = None
            self.api_client = LLMApi(wrap_completion_function(completion,
                                                              cache=cache,
                                                              model=self.model_id))

        def infer(self, batch_prompts, **kwargs):
            """
            Run inference on a batch of prompts using our LLMApi.
            """
            for res in asyncio.run(self.api_client.run_batch(batch_prompts, **self.model_kwargs)):
                yield [lx.core.types.ScoredOutput(score=1.0, output=res)]

except:
    pass

try:
    import litellm
    litellm.drop_params = True

    # This is needed to address a bug in LiteLLM (unresolved as of 8/31/2026, see https://github.com/BerriAI/litellm/pull/38388)
    # where an empty list of tools throws an error in OpenAI-like APIs
    def fake_tool(arg: str) -> str:
        """Do not call this tool. It exists to make sure the API runs correctly."""
        return "The fake tool doesn't return results. Proceed with the task you were previously given."

    fake_tools = [
        {
            "type": "function",
            "function": {
                "name": "fake_tool",
                "description": "Do not call this tool. It exists to make sure the API runs correctly.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "arg": {
                            "type": "string",
                            "description": "A fake argument",
                        },
                    },
                    "required": ["arg"],
                },
            },
        }
    ]

    LITELLM_REGEX = r"^litellm:(.*)$"

    @lx.providers.registry.register(LITELLM_REGEX)
    class LiteLLMLanguageModel(lx.inference.BaseLanguageModel):
        """
        Custom LangExtract language model that calls into LiteLLM, allowing for local LLM
        calls.
        """

        def __init__(self, model_id: str = 'litellm:hosted_vllm/qwen3.8-27b', **kwargs):
            # Separate actual model name from prefix
            if model_id.startswith('litellm:'):
                self.model_id = model_id[8:]
            else:
                self.model_id = model_id

            self.organization = None
            self.format_type = kwargs.get("format_type", lx.data.FormatType.JSON)
            self.temperature = kwargs.get("temperature", 0.0)
            self.max_workers = kwargs.get("max_workers", 10)
            self.max_completion_tokens = kwargs.get("max_tokens")
            self._extra_kwargs = kwargs

            self.completion = litellm.completion
            
            try:
                from lab_llm import LLMApi
            except:
                self.api_client = None
            else:
                if cache_path := os.getenv("LLM_CACHE_DB"):
                    cache = CachingCompletion(cache_path)
                else:
                    cache = None
                self.api_client = LLMApi(wrap_completion_function(self.completion,
                                                                cache=cache,
                                                                model=self.model_id))
                

        def infer(self, batch_prompts, **kwargs):
            """
            Run inference on a batch of prompts using our LLMApi.
            """
            if self.api_client is not None:
                for res in asyncio.run(self.api_client.run_batch(batch_prompts, enable_thinking=False, reasoning_effort="low", tools=[fake_tool])):
                    yield [lx.core.types.ScoredOutput(score=1.0, output=res)]
            else:
                for prompt in batch_prompts:
                    message = None
                    inputs = [{"role": "user", "content": prompt}]
                    tries = 0
                    while message is None:
                        tries += 1
                        if tries == 10:
                            message = ""
                            break
                        response = self.completion(model=self.model_id, messages=inputs, tools=fake_tools, enable_thinking=False, reasoning_effort="low", **self._extra_kwargs)
                        if response.tool_calls:
                            inputs.append({"role": "tool", "content": "The fake tool returned no output. Please resume your task."})
                        else:
                            message = response.choices[0].message.content
                    yield [lx.core.types.ScoredOutput(score=1.0, output=message)]

except:
    pass

try:
    from anthropic import AnthropicVertex
    import concurrent.futures as _futures

    @lx.providers.registry.register(r"^vertex-claude:", priority=100)
    class VertexClaudeLanguageModel(lx.inference.BaseLanguageModel):
        """LangExtract provider for Claude models on Vertex AI."""

        def __init__(self, model_id: str = "vertex-claude:claude-sonnet-4-6", **kwargs):
            actual_model_id = model_id[len("vertex-claude:"):]
            project = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not project:
                raise ValueError("GOOGLE_CLOUD_PROJECT must be set for Vertex AI Claude models.")
            location = os.getenv("ANTHROPIC_VERTEX_LOCATION", "global")
            self.model_id = actual_model_id
            self.temperature = kwargs.get("temperature", 0.0)
            self.max_tokens = int(kwargs.get("max_tokens", 8_096))
            self.timeout = kwargs.get("timeout", 120)
            self.max_workers = kwargs.get("max_workers", 10)
            self.format_type = lx.data.FormatType.JSON
            self._client = AnthropicVertex(project_id=project, region=location)
            super().__init__()
            self._extra_kwargs = kwargs

        @property
        def requires_fence_output(self) -> bool:
            return True

        def _process_single_prompt(
            self, prompt: str, max_tokens: int, temperature: float, timeout: float
        ) -> lx.core.types.ScoredOutput:
            response = self._client.messages.create(
                model=self.model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            return lx.core.types.ScoredOutput(score=1.0, output=response.content[0].text)

        def infer(self, batch_prompts, **kwargs):
            merged = self.merge_kwargs(kwargs)
            temperature = float(merged.get("temperature", self.temperature))
            max_tokens = int(merged.get("max_tokens", self.max_tokens))
            timeout = float(merged.get("timeout", self.timeout))

            if len(batch_prompts) > 1 and self.max_workers > 1:
                with _futures.ThreadPoolExecutor(
                    max_workers=min(self.max_workers, len(batch_prompts))
                ) as executor:
                    fs = [
                        executor.submit(self._process_single_prompt, p, max_tokens, temperature, timeout)
                        for p in batch_prompts
                    ]
                    for f in fs:
                        yield [f.result()]
            else:
                for prompt in batch_prompts:
                    yield [self._process_single_prompt(prompt, max_tokens, temperature, timeout)]

except Exception:
    pass

try:
    from securellm.providers.langextract_provider import SecureGPTExtract

    for _pattern in (r"^apim:", r"^nero:", r"^aihub:"):
        lx.providers.registry.register(_pattern, priority=50)(SecureGPTExtract)

except ImportError:
    pass