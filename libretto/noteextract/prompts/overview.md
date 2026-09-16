# NoteExtract Extraction Spec

A NoteExtract spec drives an LLM-based extraction pipeline that reads individual clinical notes and produces structured **extractions** from them. Each extraction identifies a specific piece of clinical information mentioned in the note.

The specification you will generate should define how to extract structured information from medical notes and patient records. It should include:

- name: A human-readable name for the extraction spec. The name should use spaces (not underscores or hyphens) and be in title case.
- prompt: The main instruction to guide LLM extraction
- schema: A plain-text description of the possible extractions and their attributes. List the name of each extraction that the model should output along with a description of what each extraction represents. Each extraction will be associated with a verbatim quote from the text. Enumerate the attributes that the extraction model should attach to each extraction in addition to the quote. Do not describe any specific data structure. Refer to extraction classes as fields and extraction text as quotes; do not use the terms "extraction class" or "extraction text".
  Example schema:
  ```
  - Extract a field `onset_date`, containing the following attributes: `date` (the precise date of onset in YYYY-MM-DD format), and `detail` (descriptive text if needed)
  - Extract the field `treatment` containing attributes `start_date`, `end_date` (both in YYYY-MM-DD format) and `detail` (indicating which treatment was given)
  - The field `recommendation` should have the attributes `date` (the date of the recommendation in YYYY-MM-DD format) and `detail` (what the provider recommendation was).
  ```
- examples: List of 1-3 example notes and extraction results. The extractions must contain a "text" field with a minimal note example (at least
  two sentences), and an "extractions" field with one or more extractions containing the fields "extraction_class", "extraction_text", and "attributes".
  The extractions must be in the same order as they appear in the text, and the extraction_text value MUST be verbatim from the text. Here is what each
  example should look like. Do NOT include any other fields in the extraction objects. All examples must have at least two extractions associated with them.
  ```json
  {
    "text": "# Patient Information\nDOB: 2001-06-14\nCurrent Status: Alive\nSex: Male\nGender Identity: Male\nEthnicity: Not Hispanic or Latino\nPrimary Race: White\n\n# Prior Visits\n15 prior visits, including:\n- Dermatology\n- Neurology\n- Oncology\n\n# Note\n\nNote Date: 2022-03-15\n\nHISTORY OF PRESENT ILLNESS:\nPatient is a 20-year-old male diagnosed with NF1 at 18 months of age. He presents for routine follow-up.\n\nCURRENT MEDICATIONS:\nCurrently taking gabapentin 300mg TID for neuropathic pain, started in January 2021.\n\nASSESSMENT AND PLAN:\nPatient is stable. Continue current gabapentin regimen. Recommend annual MRI brain to monitor for optic gliomas.\n",
    "extractions": [
      {
        "extraction_class": "onset_date",
        "extraction_text": "diagnosed with NF1 at 18 months of age",
        "attributes": [
          {"key": "detail", "value": "18 months of age"},
          {"key": "date", "value": "2002-12-14"}
        ]
      },
      {
        "extraction_class": "treatment",
        "extraction_text": "gabapentin 300mg TID for neuropathic pain",
        "attributes": {
          {"key": "type", "value": "medication"},
          {"key": "detail", "value": "gabapentin"},
          {"key": "start_date", "value": "2021-01-01"},
          {"key": "end_date", "value": "ONGOING"}
        }
      },
      {
        "extraction_class": "recommendation",
        "extraction_text": "Recommend annual MRI brain to monitor for optic gliomas",
        "attributes": {
            {"key": "detail", "value": "MRI brain"},
            {"key": "date", "value": "2022-03-15"}
        }
      }
    ]
  }
  ```

The results of running a NoteExtract spec on a patient are a list of `NoteExtraction` objects, each with the following fields:

```python
class NoteExtraction(TypedDict):
    # The extraction class name (matches a class defined in the schema)
    extraction_class: str
    # Verbatim quote from the note that supports this extraction
    extraction_text: str
    # Attributes attached to this extraction (schema-defined keys and values)
    attributes: dict[str, str]
    # Citation indicating which note the extraction came from
    citations: list[SourceCitation]
```

Each patient's output is a list of `NoteExtraction` objects spanning all their notes. If the spec is working correctly, the extraction classes should match those defined in the schema, the `extraction_text` should be a verbatim snippet from the note, and the attributes should be populated with the expected keys and reasonable values. Note that the prompt and schema are plain-text, while the examples are JSON-formatted.
