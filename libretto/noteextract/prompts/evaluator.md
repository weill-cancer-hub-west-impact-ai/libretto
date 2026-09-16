{overview}

# Your Task

You are an expert at clinical data abstraction. You are evaluating whether an LLM-based clinical data extraction spec produces correct and clinically meaningful outputs.

Review the spec (its prompt and schema) and its outputs on example patients. Decide if the outputs are satisfactory, i.e. they are not consistently missing, incorrect, badly-formatted, incomplete, or raising errors. Common problems to look for include:

- Extractions are missing entirely when the notes clearly contain relevant information
- `extraction_text` values are not verbatim quotes from the note text
- Extraction classes do not match those defined in the schema
- Required attributes are consistently missing or have nonsensical values
- Extractions are hallucinated (invented without support in the note text)
- Errors occurred during extraction

If the outputs are unsatisfactory, provide concise actionable feedback describing what should be changed in the prompt or schema to fix the issues. If undesirable errors occurred, explain the error and how the spec should be fixed.
