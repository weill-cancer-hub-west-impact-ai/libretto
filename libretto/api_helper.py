from typing import Optional, Unpack, Any
from lab_llm import LLMApi, VersaOpenAI, CachingCompletion, ErrorTracker, wrap_completion_function, DefaultParameters, CompletionKwargs, CompletionFunction
from lab_llm.versa import make_versa_openai_completion
from .llm_client import create_llm_client
from dotenv import load_dotenv
import os
import logging
from .types import Project, project_environment

import litellm
litellm.drop_params = True

def setup_llm_api(project: Optional[Project] = None, model_name: str | None = None) -> LLMApi:
    """Set up the LLMApi instance. If model_name is given in the format '<provider>:<model>', uses it to determine the provider."""
    load_dotenv()

    if model_name is not None and ':' in model_name:
        provider = model_name.split(':')[0]
    else:
        provider = None

    # Alternate code using public LLMs:
    # completion_func = litellm.completion
    # Or, specify your default parameters such as api_key, api_base, etc.:
    # completion_func = DefaultParameters(litellm.completion, api_base=..., model=...)
    if project:
        # Use environment variables from the project to create the client
        with project_environment(project):
            client = create_llm_client(provider=provider)
        # Ensure that project environment is always set
        def completion_func(model: str, messages: list[dict[str, Any]], **kwargs: Unpack[CompletionKwargs]):
            with project_environment(project):
                return client.chat.completions.create(model, messages, **kwargs)
    else:
        client = create_llm_client(provider=provider)
        completion_func = client.chat.completions.create


    completion = wrap_completion_function(completion_func,
                                          cache=CachingCompletion(os.getenv("LLM_CACHE_DB", "./llm_cache.db")),
                                          error_tracker=ErrorTracker(logging.getLogger()),
                                          model=client.default_model) # replace with a different model name if not using Versa

    # Create API instance
    return LLMApi(completion, track_usage=True)
