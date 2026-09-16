import re
import json
from bloatectomy import bloatectomy
from .types import Patient, Note, ExtractionCitation, SourceCitation
import logging

logger = logging.getLogger()

REDUNDANCY_INDICATOR = ' ... '
REDUNDANCY_PATTERN = r'[\s\\]*\\.\\.\\.[\s\\]*' # escaped to find in escaped verbatim quote

def reduce_note_redundancy(patient: Patient) -> Patient:
    """
    Use bloatectomy to remove redundant chunks of text while preserving separate note objects.
    """
    combined_text = []
    for note in patient['notes']:
        combined_text.append(f"<!< {note['id']} >!>\n" + note['note_text'])
    combined_text = '\n\n'.join(combined_text)
    combined_text = re.sub('\n{2,}', '\n\n', combined_text)
    combined_text = re.sub('[-=]{3,}', '---', combined_text)
    combined_text = re.sub('[*]{3,}', '***', combined_text)
    bloat = bloatectomy(combined_text, output="str", regex1=r'((?<!:)\s*\n+)', protected_regex=r'(?:<!< .*? >!>)|(?:.*:$)')
    shortened_text = re.sub(r'(<mark>.*?</mark>\s*)+', REDUNDANCY_INDICATOR, '\n'.join(bloat.tokens), flags=re.MULTILINE)
    shortened_notes = [x.strip() for x in re.split(r'<!< .* >!>', shortened_text, flags=re.MULTILINE) if x.strip()]
    if len(shortened_notes) != len(patient['notes']):
        print(shortened_notes)
        print(len(shortened_notes), len(patient['notes']))
        print("Lengths don't match, returning original data")
        return patient
    return {**patient, 'notes': [{**n, 'note_text': shortened_notes[i]} for i, n in enumerate(patient['notes']) if shortened_notes[i]]}

def map_citations_in_shortened_text(citations: list[SourceCitation], shortened_patient: Patient, original_patient: Patient) -> list[SourceCitation]:
    """
    Produces a set of converted citations by finding any occurrences of
    a redundancy indicator in the text and expanding them so that the
    quote matches the original patient text.
    """
    updated_citations: list[SourceCitation] = []
    for citation in citations:
        original_note = next((n for n in original_patient["notes"] if n["id"] == citation["note_id"]), None)
        if not original_note:
            logger.warning(f"Citation with no matching note ID ({citation})")
            continue
        shortened_note = next((n for n in shortened_patient["notes"] if n["id"] == citation["note_id"]), None)
        if not shortened_note or REDUNDANCY_INDICATOR not in shortened_note["note_text"]:
            updated_citations.append(citation)
            continue

        pattern = re.sub(REDUNDANCY_PATTERN, r".*?", re.escape(citation['verbatim_quote']))
        if match := re.search(pattern, original_note["note_text"], flags=re.DOTALL | re.IGNORECASE):
            updated_citations.append({
                **citation,
                "verbatim_quote": match.group(0)
            })
        else:
            updated_citations.append(citation)
    return updated_citations

def get_extraction_citation(source_citation: SourceCitation, patient: Patient) -> ExtractionCitation:
    """
    Converts a citation from the LLM to one with a specific position in the text.
    """
    original_note = next((n for n in patient["notes"] if n["id"] == source_citation["note_id"]), None)
    if not original_note:
        logger.warning(f"Citation with no matching note ID ({source_citation})")
        return {"note_id": None, "quote": source_citation["verbatim_quote"], "char_interval": {"start_pos": None, "end_pos": None}}
    pattern = re.escape(source_citation["verbatim_quote"]).replace("\\\n", r"\s*")
    if match := re.search(pattern, original_note["note_text"], flags=re.IGNORECASE | re.MULTILINE):
        return {
            "note_id": source_citation["note_id"],
            "quote": source_citation["verbatim_quote"],
            "char_interval": {"start_pos": match.start(), "end_pos": match.end()}
        }
    return {
        "note_id": source_citation["note_id"],
        "quote": source_citation["verbatim_quote"],
        "char_interval": {"start_pos": None, "end_pos": None}
    }

def format_notes_batch(
    notes: list[Note],
    max_chars: int,
    id_offset: int = 0,
) -> tuple[str, dict[int, str]]:
    """
    Build a text block of patient notes fitting within max_chars, and a mapping
    from the monotonic integer IDs used in the text back to the original note IDs.

    Notes are added one at a time in order; the batch stops before adding a note
    that would push the total over max_chars (a single note that already exceeds
    max_chars is still included as the sole entry so the batch is never empty).

    Returns:
        (notes_text, id_map) where id_map maps integer_id -> original_note_id
        and integer IDs start from id_offset + 1.
    """
    id_map: dict[int, str] = {}
    note_blocks: list[str] = []
    total_chars = 0

    for note in notes:
        int_id = id_offset + len(id_map) + 1
        date_str = note.get("date") or note.get("metadata", {}).get("Date") or "unknown date"
        metadata = {k: v for k, v in note.get("metadata", {}).items() if k != "Date"}
        header_parts = [f"Note ID: {int_id}", f"Date: {date_str}"]
        if metadata:
            header_parts.append(f"Metadata: {json.dumps(metadata)}")
        header = " | ".join(header_parts)
        body = (note.get("note_text") or "").strip()
        block = f"--- {header} ---\n{body}\n"

        # Always include at least one note even if it exceeds max_chars alone
        if note_blocks and max_chars and total_chars + len(block) > max_chars:
            break

        id_map[int_id] = note["id"]
        note_blocks.append(block)
        total_chars += len(block)

    notes_text = "\n".join(note_blocks)
    return notes_text, id_map


if __name__ == '__main__':
    test_patient: Patient = {
        "id": 1234,
        "notes": [
            {
                "id": 1,
                "note_text": "Blah blah blah.\n\nA B C D E.\n\nBlah blah blah."
            },
            {
                "id": 2,
                "note_text": "A B C\nBlah blah blah.\n\nA B C D E.\n\nHello 123."
            }
        ]
    }
    deduplicated = reduce_note_redundancy(test_patient)
    print(deduplicated)
    print(map_citations_in_shortened_text([{
        "note_id": 1,
        "verbatim_quote": "A B C"
    }, {
        "note_id": 2,
        "verbatim_quote": "C\n...\nHello"
    }], deduplicated, test_patient))
