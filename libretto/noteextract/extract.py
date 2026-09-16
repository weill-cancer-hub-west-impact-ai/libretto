from __future__ import annotations

import json
import logging
import os
import re
import pandas as pd
from pathlib import Path
from typing import Iterable, Sequence, Any, Optional, Tuple
import sys
from bloatectomy import bloatectomy

import langextract as lx

from .model_providers import LX_MODEL_REGISTRY

def resolve_model_id(config: dict) -> str:
    model_args = config.get("model_args", {})

    # First try model_args for model specification
    if "model_id" in model_args:
        return model_args["model_id"]

    # Fallback to old config format for backwards compatibility
    model_name = str(config.get("model_name", "")).strip()
    entry_type = str(config.get("entry_type", "")).strip()
    if model_name and ":" in model_name:
        return model_name
    if model_name and entry_type:
        return f"{entry_type}:{model_name}"

    return model_name or os.getenv("LX_MODEL", "apim:o3-mini")

def serialize_raw_response(response: object) -> str:
    if hasattr(response, "model_dump_json"):
        try:
            return response.model_dump_json(indent=2)
        except TypeError:
            return response.model_dump_json()
    if hasattr(response, "json"):
        try:
            return response.json()
        except TypeError:
            return response.json(indent=2)
    try:
        return json.dumps(response, default=str, indent=2)
    except TypeError:
        return str(response)

def reduce_note_redundancy(combined_text: str) -> Tuple[str, dict[int, int]]:
    """
    Use bloatectomy to remove redundant chunks of text. Returns the deduplicated
    text as well as a mapping of points in the cut text and the positions they map to in
    the original text.
    """
    bloat = bloatectomy(combined_text, style='highlight', output="str", regex1=r'((?<!:)\s*\n+)')
    result_text = ""
    cut_points = {}
    for token, token_pos in zip(bloat.tokens, bloat.token_positions):
        if token.startswith("<mark>"):
            continue
        cut_points[len(result_text)] = token_pos
        result_text += token + "\n"
    return result_text, cut_points

def backconvert_char_interval(start_pos: int, end_pos: int, cut_points: dict[int, int]) -> Tuple[int, int]:
    """
    Converts the char interval from the truncated text into the original text using the cut points.
    """
    last_cut_point = max((k for k in cut_points.keys() if k <= start_pos), default=None)
    if last_cut_point is None:
        return start_pos, end_pos
    return start_pos - last_cut_point + cut_points[last_cut_point], end_pos - last_cut_point + cut_points[last_cut_point]

def run_extraction(
    note_text: str,
    prompt: str,
    examples: Sequence[lx.data.ExampleData],
    config: dict,
    schema_attributes: Sequence[str] | None = None,
) -> tuple[list[dict], str]:
    model_id = resolve_model_id(config)
    model_config = LX_MODEL_REGISTRY.get(model_id, {})

    model_args = config.get("model_args", {})
    max_char_buffer = int(model_args.get("max_char_buffer", config.get("max_char_buffer", int(os.getenv("LX_MAX_BUF", "6000")))))
    extraction_passes = int(model_args.get("extraction_passes", config.get("extraction_passes", 3)))

    # Merge model args with defaults
    language_model_params = {
        "temperature": 0.0,
        "max_tokens": 400,
        "timeout": int(os.getenv("LX_TIMEOUT", "120")),
    }

    # Update with config-specific language model params (backwards compatibility)
    if "language_model_params" in config:
        language_model_params.update(config["language_model_params"])

    # Update with model_args
    language_model_params.update(model_args)

    # API key resolution
    api_key = (
        model_args.get("api_key")
        or config.get("api_key")
        or os.getenv("APIM_API_KEY")
        or os.getenv("LX_API_KEY")
        or os.getenv("VAULT_SECRET_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("AZURE_OPENAI_API_KEY")
        or os.getenv("AIHUB_API_KEY")
    )
    if api_key and "api_key" not in language_model_params:
        language_model_params["api_key"] = api_key

    output_token_key = model_config.get("out_token_key", "max_tokens")
    for token_key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
        if token_key != output_token_key:
            language_model_params.pop(token_key, None)
    language_model_params[output_token_key] = model_config.get("max_output_tokens", 60000)

    dedup_note_text, dedup_mappings = reduce_note_redundancy(note_text)
    if len(dedup_note_text) < len(note_text):
        print(f"Reduction in note length from {len(note_text)} to {len(dedup_note_text)} ({(len(note_text) - len(dedup_note_text)) / len(note_text):.1%})")
    response = lx.extract(
        text_or_documents=dedup_note_text,
        model_id=model_id,
        prompt_description=prompt,
        examples=examples,
        extraction_passes=extraction_passes,
        max_char_buffer=max_char_buffer,
        language_model_params=language_model_params,
        fence_output=model_config.get("fence_output", False),
        debug=bool(config.get("debug", False)),
        resolver_params={"fence_output": model_config.get("fence_output", False)},
    )
    raw_output = serialize_raw_response(response)
    output = []
    for extraction in response.extractions or []:
        attrs = dict(extraction.attributes or {})
        if schema_attributes:
            for attr in schema_attributes:
                if attr not in attrs or attrs[attr] is None or not str(attrs[attr]).strip():
                    attrs[attr] = "Not found"
        cleaned = {
            key: str(value).strip()
            for key, value in attrs.items()
            if value is not None and str(value).strip()
        }
        if extraction.char_interval:
            char_interval = backconvert_char_interval(extraction.char_interval.start_pos, extraction.char_interval.end_pos, dedup_mappings)
        else:
            char_interval = (None, None)
        output.append(
            {
                "extraction_class": extraction.extraction_class,
                "extraction_text": extraction.extraction_text,
                "start_pos": char_interval[0],
                "end_pos": char_interval[1],
                "attributes": cleaned,
            }
        )
    return output, raw_output
