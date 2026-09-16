import re
import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from lab_llm import LLMApi
from ..types import Patient, NoteExtraction, TextRange, ExtractionCitation
from ..text_matching import reduce_note_redundancy, format_notes_batch

logger = logging.getLogger(__name__)


class ExtractionAttribute(BaseModel):
    key: str
    value: str

class ExtractionItem(BaseModel):
    extraction_class: str = Field(description="Short name for the type of extraction")
    value: str = Field(description="The response for this extraction")
    attributes: list[ExtractionAttribute] = Field([], description="Optional key-value pairs adding information to the extraction value")
    quotes: list[str] = Field([], description="Verbatim quotes from the source text justifying this extraction")


class PromptOnlyOutput(BaseModel):
    extractions: list[ExtractionItem]


def _find_quote_in_note(quote: str, note_text: str) -> Optional[TextRange]:
    if not quote:
        return None
    m = re.search(re.escape(quote), note_text, flags=re.IGNORECASE)
    if m:
        return {"start_pos": m.start(), "end_pos": m.end()}
    return None


def _parse_llm_response(llm_response, note_id_for_log: str, patient_id_for_log) -> Optional[PromptOnlyOutput]:
    try:
        if isinstance(llm_response, str):
            clean = re.sub(r'```(?:json)?\s*|\s*```', '', llm_response).strip()
            m = re.search(r'\{.*\}', clean, re.DOTALL)
            if not m:
                raise ValueError(f"Unparseable LLM response: {llm_response[:200]}")
            return PromptOnlyOutput.model_validate_json(m.group())
        return llm_response
    except Exception as e:
        logger.warning(f"Error processing note {note_id_for_log} for patient {patient_id_for_log}: {e}")
        return None


def run_prompt_only(
    patient: Patient,
    prompt: str,
    api: LLMApi,
    model_id: str | None = None,
    combine_notes: bool = False,
    max_chunk_size: int = 100000,
) -> list[NoteExtraction]:
    """
    Run a free-text prompt against patient notes and return extractions.

    When combine_notes is False (default), the prompt is run against each note
    individually. When combine_notes is True, notes are first deduplicated using
    bloatectomy and then combined into batches of at most max_chunk_size characters,
    with one LLM call per batch.

    The LLM is asked to return a structured list of extractions, each with a class,
    value, optional attributes, and optional verbatim quotes. Quotes are mapped back
    to char intervals in the source note via case-insensitive exact string matching.

    Args:
        patient: Patient dict with a "notes" list
        prompt: Free-text extraction prompt written by the user
        api: LLMApi instance for calling the LLM
        model_id: Optional model identifier to pass to the API
        combine_notes: If True, combine all notes into batched inputs before calling LLM
        max_chunk_size: Maximum characters per LLM call when combine_notes is True

    Returns:
        Flat list of NoteExtraction dicts across all notes
    """
    results: list[NoteExtraction] = []
    api_args = {"model": model_id} if model_id else {}

    if combine_notes:
        deduped_patient = reduce_note_redundancy(patient)
        notes = deduped_patient.get("notes", [])
        # Build a map from note id to original note for quote matching
        original_notes_by_id = {n["id"]: n for n in patient.get("notes", [])}

        processed = 0
        while processed < len(notes):
            notes_text, id_map = format_notes_batch(notes[processed:], max_chunk_size, id_offset=processed)
            batch_size = len(id_map)
            processed += batch_size

            combined_prompt = f"{prompt}\n\nNotes:\n{notes_text}"
            raw_response = api.run(
                [{"role": "user", "content": combined_prompt}],
                response_format=PromptOnlyOutput,
                **api_args
            )
            llm_response = _parse_llm_response(raw_response, f"batch(offset={processed - batch_size})", patient.get("id"))

            if llm_response is None:
                continue

            # Build lookup of original note objects for the notes in this batch
            batch_note_ids = list(id_map.values())
            batch_original_notes = {nid: original_notes_by_id[nid] for nid in batch_note_ids if nid in original_notes_by_id}

            for item in llm_response.extractions:
                citations: list[ExtractionCitation] = []
                for q in item.quotes:
                    matched = False
                    for orig_note_id, note_obj in batch_original_notes.items():
                        interval = _find_quote_in_note(q, note_obj.get("note_text") or "")
                        if interval:
                            citations.append({"note_id": orig_note_id, "quote": q, "char_interval": interval})
                            matched = True
                            break
                    if not matched:
                        citations.append({"note_id": None, "quote": q, "char_interval": None})
                if not citations:
                    citations = [{"note_id": None, "quote": None, "char_interval": None}]

                results.append({
                    "extraction_class": item.extraction_class,
                    "attributes": {"value": item.value, **{attr.key: attr.value for attr in item.attributes}},
                    "citations": citations
                })

        return results

    # Per-note mode (default)
    for note in patient.get("notes", []):
        note_id = note.get("id")
        note_text = note.get("note_text") or ""

        combined_prompt = f"{prompt}\n\nNote:\n{note_text}"

        raw_response = api.run(
            [{"role": "user", "content": combined_prompt}],
            response_format=PromptOnlyOutput,
            **api_args
        )
        llm_response = _parse_llm_response(raw_response, note_id, patient.get("id"))

        if llm_response is None:
            continue

        for item in llm_response.extractions:
            citations: list[ExtractionCitation] = [
                {
                    "note_id": note_id,
                    "quote": q,
                    "char_interval": _find_quote_in_note(q, note_text)
                }
                for q in item.quotes
            ] or [{"note_id": note_id, "quote": None, "char_interval": None}]

            results.append({
                "extraction_class": item.extraction_class,
                "attributes": {"value": item.value, **{attr.key: attr.value for attr in item.attributes}},
                "citations": citations
            })

    return results
