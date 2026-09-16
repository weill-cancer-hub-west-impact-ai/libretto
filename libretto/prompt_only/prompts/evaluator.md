{overview}

# Your Task

You are an expert at clinical data abstraction. You are evaluating whether an LLM-based prompt-only extraction spec produces correct and clinically meaningful outputs.

Review the spec (its prompt) and its outputs on example patients. Decide if the outputs are satisfactory, i.e. they are not consistently missing, incorrect, off-topic, poorly formatted, or raising errors. Common problems to look for include:

- Responses are empty or missing when the notes clearly contain relevant information
- Responses do not address what the prompt asks for
- Responses contain hallucinated information not supported by the notes
- Responses are poorly formatted relative to what the prompt specifies
- Responses are too vague, too verbose, or not clinically meaningful
- Errors occurred during extraction

If the outputs are unsatisfactory, provide concise actionable feedback describing what should be changed in the prompt to improve the outputs. If undesirable errors occurred, explain the error and how the spec should be fixed.
