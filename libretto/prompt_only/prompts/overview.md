# Clinical Information Extraction Specification

Clinical information extraction specifications drive an LLM-based pipeline, applying a single free-form prompt to clinical notes and returning a natural-language response. The output is a list of extractions, each associated with a value, optionally attributes, and one or more citations from the text.

The spec has one main component:

- **prompt**: Clear instructions telling the extraction model what information to identify, summarize, or extract from each note. The prompt specifies the desired output format and content.

Optionally, the spec may also specify:

- **combine_notes**: Whether to concatenate multiple notes for a patient into a single input (up to a maximum character length), rather than processing each note independently.
- **max_chunk_size**: The maximum number of characters per input chunk when combining notes.

Design a spec such that each response directly addresses the prompt instruction, is appropriately detailed and structured, and draws on relevant information from the corresponding note(s).
