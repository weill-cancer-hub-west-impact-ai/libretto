import pandas as pd
from typing import Any

from .extract import run_extraction
from .prepare_task import load_examples_from_config, create_note_dataframe, map_note_positions
from ..json_sanitize import convert_to_native_types
from ..types import Patient, NoteExtraction
import os

def prepare_config_for_extraction(content: dict[str, Any], model_id: str | None = None) -> dict[str, Any]:
    """Prepare extraction config from noteextract content with model ID from environment."""
    model_id = model_id or (content.get("model_args") or {}).get("model_id") or os.getenv("EXTRACTION_MODEL_ID")
    assert model_id is not None, "No model_id provided, specify in spec['model_args']['model_id'] or EXTRACTION_MODEL_ID environment variable"
    return {
        **content,
        "model_args": {
            **(content.get("model_args") or {}),
            "model_id": model_id,
            "combine_notes": True,
            "extraction_passes": 1,
            "resolver_params": {
                "enable_fuzzy_alignment": False
            }
        }
    }

def run_noteextract(patient: Patient, spec_content: dict[str, Any], model_id: str | None = None) -> list[NoteExtraction]:
    """
    Run noteextract on a single patient and return a list of NoteExtraction dicts.

    This is the per-patient logic extracted from run_noteextract_and_store in worker/worker.py.
    With combine_notes=True (the default for this executor), create_note_dataframe produces
    one row per patient, so the loop always processes exactly one note row.

    Args:
        patient: Patient dict with id, notes, and metadata.
        spec_content: Spec content dict including prompt, schema, examples, and model_args.
        model_id: Model ID to use (replaces the one in model_args if present).

    Returns:
        List of NoteExtraction dicts with citations attached.
    """
    config = prepare_config_for_extraction(spec_content, model_id=model_id)
    prompt = f"{config['prompt']}\n\nSchema:\n{config['schema']}"
    examples = load_examples_from_config(config, None)

    notes_data, position_mappings = create_note_dataframe([patient], config)

    extractions_out: list[NoteExtraction] = []

    for _, note_row in notes_data.iterrows():
        note_text = note_row["note_text"]
        patient_id = note_row["patient_id"]
        note_id = note_row["note_id"]

        extractions, _ = run_extraction(note_text, prompt, examples, config)

        for extraction in extractions:
            extraction["patient_id"] = patient_id

        if position_mappings is not None:
            extractions = map_note_positions(extractions, position_mappings)

        for e in extractions:
            extractions_out.append({
                **e,
                "citations": [{
                    "note_id": e.get('note_id') or note_id or None,
                    "quote": e["extraction_text"],
                    "char_interval": {
                        "start_pos": e.get("start_pos"),
                        "end_pos": e.get("end_pos"),
                    },
                }],
            })

    return convert_to_native_types(extractions_out)
