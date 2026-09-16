"""
Helper module to read and validate configs, and produce a dataframe of formatted notes.
"""
import pandas as pd
from typing import List, Dict, Tuple, Optional, Iterable
from pathlib import Path
import langextract as lx
import json
import logging
from ..types import Patient

LOGGER = logging.getLogger()

def format_notes(notes: pd.DataFrame, combine: bool = False) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """
    Takes a list of Patient objects (each of which has a list of notes) as input.

    Returns a tuple (formatted_notes, mapping), where formatted_notes is a new
    dataframe with the columns "patient_id", "note_id", and "note_text",
    and note_text contains transformed text. If combine is True, then mapping will
    be a dataframe containing the positions of each source note in the
    transformed text. Pass this dataframe with a list of extractions
    to map_note_positions to separate the extractions by source note.
    """
    formatted_data = []
    mapping_data = []
    has_patient_metadata = "patient_metadata" in notes.columns
    has_note_metadata = "note_metadata" in notes.columns

    if combine:
        # Group by patient and combine notes
        for patient_id, group in notes.groupby("patient_id"):
            combined_text = ""
            if has_patient_metadata:
                patient_metadata = group.iloc[0]['patient_metadata']
                combined_text = f"# Patient\n{patient_metadata}\n\n"

            # Add each note with metadata
            for _, row in group.iterrows():
                note_start = len(combined_text)
                if has_note_metadata:
                    prefix = f"## Note {row['note_date'] or ''}\n\n### Metadata\n{row['note_metadata']}\n\n###Text\n\n"
                else:
                    prefix = f"## Note {row['note_date'] or ''}\n\n### Text\n\n"
                note_section = prefix + row['note_text'] + "\n\n"
                combined_text += note_section

                mapping_data.append({
                    "patient_id": patient_id,
                    "note_id": row['note_id'],
                    "start_pos": note_start,
                    "text_start_pos": note_start + len(prefix),
                    "end_pos": len(combined_text)
                })

            formatted_data.append({
                'patient_id': patient_id,
                'note_id': pd.NA,  # Combined notes don't have a single note_id
                'note_text': combined_text
            })
    else:
        # Format each note individually
        formatted_data = []

        for _, row in notes.iterrows():
            parts = []
            if has_patient_metadata:
                parts.append(f"# Patient\n{row['patient_metadata']}")
            if has_note_metadata:
                parts.append(f"## Note {row['note_date'] or ''}\n\n### Metadata\n{row['note_metadata']}\n\n### Text")
            prefix = "\n\n".join(parts) + "\n" if parts else ""
            formatted_text = prefix + row['note_text']

            formatted_data.append({
                'patient_id': row['patient_id'],
                'note_id': row['note_id'],
                'note_text': formatted_text
            })
            mapping_data.append({
                "patient_id": row['patient_id'],
                "note_id": row['note_id'],
                "start_pos": 0,
                "text_start_pos": len(prefix),
                "end_pos": len(formatted_text)
            })


    formatted_df = pd.DataFrame(formatted_data)
    mapping_df = pd.DataFrame(mapping_data)
    return formatted_df, mapping_df


def map_note_positions(extractions: List[Dict], mapping: pd.DataFrame) -> List[Dict]:
    """
    Takes a list of extractions, each of which contains fields "patient_id" and "start_pos"
    corresponding to a span of text within a piece of text containing multiple notes; and a
    mapping of note IDs to start positions in the text. Maps each extraction to the note it
    came from and returns an updated list of extractions with the note_id set, with all values 
    preserved and the start and end positions shifted to those of the note.
    """
    results = []

    for extraction in extractions:
        start_pos = extraction.get('start_pos')
        end_pos = extraction.get('end_pos')

        # Skip extractions without position information (these will be patient-level)
        if start_pos is None or end_pos is None:
            results.append(extraction)
            continue

        possible_notes = mapping[(mapping['patient_id'] == extraction['patient_id']) & 
                                 (start_pos >= mapping['start_pos']) & 
                                 (end_pos <= mapping['end_pos'])]
        if note_id := extraction.get("note_id"):
            possible_notes = possible_notes[possible_notes['note_id'] == note_id]
        if not len(possible_notes):
            results.append(extraction)
            continue

        target_row = possible_notes.sort_values("start_pos").iloc[0]
        # Create a copy of the extraction with adjusted positions
        if start_pos >= target_row['text_start_pos']:
            results.append({
                **extraction,
                "note_id": target_row['note_id'],
                'start_pos': start_pos - target_row['text_start_pos'],
                'end_pos': end_pos - target_row['text_start_pos']
            })
        else:
            # The extraction was from the metadata - no applicable text span
            results.append({
                **extraction,
                "note_id": target_row['note_id'],
                'start_pos': None,
                'end_pos': None
            })

    return results

def parse_config(path: Path, config_dir: str) -> Tuple[dict, str, list[lx.data.ExampleData]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    # Validate required config fields
    if not config.get("name"):
        raise ValueError("Config must include 'name'")
    if not config.get("prompt"):
        raise ValueError("Config must include 'prompt'")
    if not config.get("schema"):
        raise ValueError("Config must include 'schema'")

    # Build prompt
    prompt = f"{config['prompt']}\n\nSchema:\n{config['schema']}"

    # Load examples
    examples = load_examples_from_config(config, config_dir)
    if not examples:
        LOGGER.warning("No usable examples found; proceeding without few-shot guidance.")

    return config, prompt, examples

def load_examples_from_config(config: dict, config_dir: Optional[Path] = None) -> list[lx.data.ExampleData]:
    from .examples_utils import build_examples

    examples_raw = config.get("examples", [])

    if isinstance(examples_raw, str):
        excel_path = Path(examples_raw)
        if config_dir and not excel_path.is_absolute():
            excel_path = config_dir / excel_path
        df = pd.read_excel(excel_path)
        return build_examples(df)

    examples: list[lx.data.ExampleData] = []
    for item in examples_raw:
        text_source = str(item.get("text", "")).strip()
        if not text_source:
            continue

        text = text_source
        extractions_raw = item.get("extractions", [])
        extractions: list[lx.data.Extraction] = []
        for extraction in extractions_raw:
            extraction_class = str(extraction.get("extraction_class", "")).strip()
            extraction_text = str(extraction.get("extraction_text", "")).strip()
            if not extraction_class or not extraction_text:
                continue
            attrs = extraction.get("attributes") or {}
            cleaned_attrs = {
                str(k).strip(): str(v).strip()
                for k, v in attrs.items()
                if v is not None and str(v).strip()
            }
            extractions.append(
                lx.data.Extraction(
                    extraction_class=extraction_class,
                    extraction_text=extraction_text,
                    attributes=cleaned_attrs,
                )
            )
        examples.append(lx.data.ExampleData(text=text, extractions=extractions))
    return examples


def iter_note_files(path: Path) -> Iterable[Path]:
    if path.is_dir():
        yield from sorted(p for p in path.iterdir() if p.is_file())
    elif path.is_file():
        yield path
    else:
        raise ValueError(f"Path {path} does not exist.")


def create_note_dataframe(patients: List[Patient], config: dict) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """Returns formatted notes and optionally mapping data for position tracking."""
    notes_data = [
        {
            "patient_id": patient['id'],
            "patient_metadata": patient.get('metadata'),
            "note_id": note['id'],
            "note_metadata": note.get('metadata'),
            "note_date": note.get('date'),
            "note_text": note['note_text']
        }
        for patient in patients
        for note in patient['notes']
    ]
    notes_df = pd.DataFrame(notes_data).sort_values("note_date")
    combine_notes = config.get("model_args", {}).get("combine_notes", False)
    return format_notes(notes_df, combine=combine_notes)

