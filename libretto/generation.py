"""Shared generation utilities used by all spec executor types."""

import re
import json
import random
import logging
from pathlib import Path
from typing import Any, Literal, Optional, Callable, AsyncIterator, Tuple, Any, TypedDict
import asyncio
import traceback

from lab_llm import LLMApi
from pydantic import BaseModel, Field

from .types import Project, Patient, NoteExtraction, ExtractionSpec
from .prompt_format import format_note_preview
from .source_database import DEFAULT_NOTE_METADATA_QUERY, DEFAULT_NOTE_TEXT_QUERY, SourceDatabase

logger = logging.getLogger(__name__)

class EvaluationResult(BaseModel):
    satisfactory: bool
    feedback: Optional[str] = Field(
        None,
        description="Feedback string if outputs are not satisfactory; null if satisfactory",
    )

class UserQuestion(BaseModel):
    question: str = Field(description="the question to ask")
    answer_choices: list[str] = Field(
        description="list of possible answer choices (do not include an 'Other' choice, this will be added automatically)"
    )

class SpecGeneratorResult(TypedDict):
    questions: Optional[list[dict]]
    spec: Optional[ExtractionSpec]
    response_message: Optional[str]
    message_history: list[dict[str, Any]]


class SpecGenerator:
    """
    Handles generating and optionally evaluating a specification. Subclasses
    handle the specifics of each specification executor.

    Subclasses should override the constructor providing the default_prompt (if applicable).
    They should also implement one or more generate_* methods that call the 
    generate() or generate_and_evaluate() base methods.
    """
    def __init__(self, llm_api: LLMApi, project: Project, default_prompt: Optional[str] = None):
        self.llm_api = llm_api
        self.project = project
        self.default_prompt = default_prompt

    def call_llm_with_structured_output(
        self,
        messages: list[dict[str, Any]],
        response_format: type[BaseModel],
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Call LLM with structured output and fallback regex JSON parsing.

        Handles the repeated pattern across specs.py of calling llm_api.run() with a
        response_format, then falling back to regex extraction if the model returns a
        plain string instead of a structured object.

        Args:
            llm_api: LLMApi instance.
            messages: Fully assembled chat messages (system + user).
            response_format: Pydantic model class for structured output.
            model: Optional model ID override.

        Returns:
            model_dump() dict of the parsed response.

        Raises:
            ValueError: If the response cannot be parsed as JSON.
        """
        print("Calling LLM with messages:", messages)
        response = self.llm_api.run(
            messages=messages,
            response_format=response_format,
            model=model,
        )
        print("LLM response:", response)

        if isinstance(response, str):
            clean = re.sub(r'```(?:json)?\s*', '', response)
            clean = re.sub(r'```', '', clean).strip()
            match = re.search(r'\{.*\}\s*$', clean, re.DOTALL)
            if not match:
                raise ValueError(f"LLM returned response without parseable JSON: {response[:300]}")
            response = response_format.model_validate_json(match.group())

        return response.model_dump()

    @property
    def generate_system_prompt(self) -> str:
        raise NotImplementedError("Subclasses must provide a generate_system_prompt")
    
    def create_initial_messages(
        self,
        spec_section_content: Any,
        spec_section_header: str,
        prompt: str,
        example_patient_ids: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        system_prompt_path: Path to the system prompt file. The file may contain
            ``{key}`` placeholders; pass ``system_prompt_format_vars`` to hydrate them.
        spec_section_content: Dict (or any JSON-serialisable value) describing the
            current state of the spec for the model. Serialised as JSON in the initial
            message. If a dict, its ``example_patient_ids`` key (if present) is used
            to select patients for the data overview.
        spec_section_header: Human-readable heading for the spec section, e.g.
            ``"Current Chart Abstraction Plan"``.
        """
        messages: list[dict[str, Any]] = []

        effective_prompt = prompt or self.default_prompt or "Generate a spec for the provided information."

        source_db = SourceDatabase(connection_string=self.project["source_connection"])
        query_spec = {
            "note_metadata_query": self.project.get("note_metadata_query") or DEFAULT_NOTE_METADATA_QUERY,
            "note_text_query": self.project.get("note_text_query") or DEFAULT_NOTE_TEXT_QUERY,
        }
        metadata = source_db.get_note_metadata(query_spec)

        if example_patient_ids:
            sample_notes = source_db.get_notes(query_spec, patient_ids=example_patient_ids)
        else:
            sample_notes = source_db.get_notes(query_spec, note_limit=100)

        data_overview = format_note_preview(metadata, sample_notes)

        spec_section_text = (
            json.dumps(spec_section_content, indent=2)
            if not isinstance(spec_section_content, str)
            else spec_section_content
        )

        initial_message = (
            "# Patient Data Overview\n\n{data_overview}\n\n"
            "# {section_header}\n\n{spec_section}\n\n"
            "# User Instruction\n\n{prompt}"
        ).format(
            data_overview=data_overview,
            section_header=spec_section_header,
            spec_section=spec_section_text,
            prompt=effective_prompt,
        )
        messages.append({"role": "user", "content": initial_message})

        print("INITIAL LENGTH:", len(messages), messages[0]['role'])
        return messages

    def generate(
        self,
        response_format: type[BaseModel],
        message_history: list[dict[str, Any]] = [],
        prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> tuple[dict[str, Any], Optional[str], list[dict[str, Any]]]:
        """
        Generic spec generation engine.

        If provided, appends the new prompt as the next user message.

        The response_format must include a ``questions`` field (list or None). When 
        ``questions`` is non-empty the caller should surface them to the user instead 
        of interpreting the spec output.

        Args:
            response_format: Pydantic model class for structured output. Must have a
                ``questions`` field (Optional[list]) and a ``response_message`` field.
            message_history: Prior assistant/user messages for multi-turn continuations.
                Omit or pass ``[]`` for the first turn.
            prompt: User instruction to append. If omitted on the first turn, falls back
                to ``default_prompt``.
            model: Optional model ID override passed to the LLM.

        Returns:
            ``(response_dict, updated_message_history)``

            * ``response_dict`` — model_dump() of the parsed LLM response.
            * ``updated_message_history`` — the full message list (excluding system
            message) to pass back for the next turn.

        Raises:
            ValueError: If the LLM response cannot be parsed as valid JSON, or if
                message_history contains an invalid message object.
        """
        messages = [{"role": "system", "content": self.generate_system_prompt}]
        if message_history:
            for message in message_history:
                if isinstance(message, dict) and message.get("role") in ("user", "assistant", "system") and message.get("content"):
                    messages.append(message)
                else:
                    raise ValueError(f"Invalid message object in message_history: {message!r}")
            if prompt:
                messages.append({"role": "user", "content": prompt})

        response = self.call_llm_with_structured_output(messages, response_format, model=model)

        updated_history = [*messages[1:], {"role": "assistant", "content": json.dumps(response)}]
        return response, updated_history

    def execute_spec(
        self,
        spec_content: dict[str, Any],
        patient: Patient
    ) -> list[NoteExtraction]:
        raise NotImplementedError("Subclasses must implement execute_spec")
        
    def test_run_spec(
        self,
        spec_content: dict[str, Any]
    ) -> str:
        """
        Run a spec on example patients and return formatted output text.

        Uses spec_content.get('example_patient_ids') if set; otherwise randomly samples
        up to 3 patients from the first 50 in the source database.

        Args:
            spec_content: Spec content dict (executor-specific fields).
            spec_executor: Which executor to dispatch to.
            project: Project with source_connection and note query settings.
            llm_api: LLMApi instance

        Returns:
            Formatted string of JSON results plus any error descriptions.
        """
        source_db = SourceDatabase(connection_string=self.project['source_connection'])
        query_spec = {
            "note_metadata_query": self.project.get("note_metadata_query") or DEFAULT_NOTE_METADATA_QUERY,
            "note_text_query": self.project.get("note_text_query") or DEFAULT_NOTE_TEXT_QUERY,
        }

        patient_ids = spec_content.get("example_patient_ids") or None
        if patient_ids:
            patients = source_db.get_notes(query_spec, patient_ids=patient_ids)
        else:
            all_patients = source_db.get_notes(query_spec, note_limit=50)
            patients = random.sample(all_patients, min(3, len(all_patients)))

        def _run(patient):
            return self.execute_spec(spec_content, patient)

        results = []
        error_description = None
        for patient in patients[:3]:
            try:
                output = _run(patient)
                results.append({"patient_id": patient["id"], "outputs": output})
            except Exception as e:
                error_description = f"Error running spec on patient {patient['id']}: {e}"
                traceback.print_exc()
                break

        outputs_text = json.dumps(results, indent=2) if results else "No outputs produced."
        error_text = f"\n\nErrors encountered:\n{error_description}" if error_description else ""
        return f"{outputs_text}{error_text}"

    @property
    def evaluate_system_prompt(self) -> str:
        raise NotImplementedError("Subclasses must provide evaluate_prompt if using")

    def evaluate_spec(
        self,
        spec_content: dict[str, Any],
        test_run_output: str,
        model: str | None = None
    ) -> tuple[bool, Optional[str]]:
        """
        Ask an LLM to evaluate spec outputs and return (satisfactory, feedback).

        Args:
            spec_content: Full spec content dict.
            test_run_output: Formatted string from test_run_spec().
            llm_api: LLMApi instance.
            evaluator_prompt_path: Path to the evaluator system prompt file.
            overview_prompt_path: Path to the implementation overview file (injected as {overview}).

        Returns:
            (satisfactory, feedback) — feedback is None when satisfactory is True.
        """
        
        spec_summary = json.dumps(spec_content, indent=2)

        messages = [
            {"role": "system", "content": self.evaluate_system_prompt},
            {
                "role": "user",
                "content": (
                    f"# Spec\n\n{spec_summary}\n\n"
                    f"# Outputs on Example Patients\n\n{test_run_output}\n\n"
                    "Are these outputs satisfactory? If not, what should be improved?"
                ),
            },
        ]

        try:
            response = self.call_llm_with_structured_output(messages, EvaluationResult, model=model)
            logger.info("Evaluator response: %s", response)
            return response["satisfactory"], response.get("feedback")
        except Exception as e:
            logger.warning("Evaluator LLM call failed: %s", e)
            return True, None


    async def generate_and_evaluate(
        self,
        response_model: type[BaseModel],
        initial_message_history: list[dict],
        evaluate_max_passes: int,
        response_to_spec_fn: Callable[[Any], dict] | None,
        prompt: str | None = None,
        model: str | None = None
    ) -> AsyncIterator[Tuple[str, Any]]:
        """
        Shared SSE event generator for all three executor types.

        generate_fn(message_history, initial) returns a coroutine yielding
        (response_dict, response_message, updated_message_history).
        initial=True on the first call (prompt is active); initial=False on
        refinement passes (feedback has been appended to message_history instead).

        response_to_spec_fn(response) converts a response dict to the saved
        ExtractionSpec dict.

        evaluate_max_passes: maximum number of generate→test→evaluate cycles.
        """
        try:
            yield ("status", {"message": "Generating..."})

            current_message_history = [{"role": "system", "content": self.generate_system_prompt}, *initial_message_history]
            evaluation_result = None
            
            for pass_num in range(evaluate_max_passes):
                response, current_message_history = await asyncio.to_thread(
                    self.generate,
                    response_model,
                    current_message_history,
                    prompt if pass_num == 0 else None,
                    model,
                )

                if response.get("questions"):
                    yield ("result", {"questions": response["questions"], "message_history": current_message_history})
                    return

                current_response = response

                spec_content = response_to_spec_fn(current_response)
                if not spec_content:
                    raise ValueError(f"The LLM returned the following with no spec: {current_response.get('response_message')}")
                spec_content = spec_content.get("content", {})
                print("Returned spec content:", spec_content)

                if pass_num == evaluate_max_passes - 1:
                    break

                yield ("status", {"message": f"Running spec on example patients (try {pass_num + 1}/{evaluate_max_passes})..."})
                test_run_output = await asyncio.to_thread(
                    self.test_run_spec, spec_content
                )

                yield ("status", {"message": f"Evaluating the example results (try {pass_num + 1}/{evaluate_max_passes})..."})
                satisfactory, feedback = await asyncio.to_thread(
                    self.evaluate_spec,
                    spec_content,
                    test_run_output,
                    model
                )

                if satisfactory:
                    evaluation_result = {"satisfactory": True, "passes": pass_num + 1}
                    break

                feedback_message = f"The output was evaluated and found to be unsatisfactory.\n\nFeedback:\n{feedback}"
                yield ("status", {"message": f"Refining based on feedback (pass {pass_num + 2}/{evaluate_max_passes})..."})

                current_message_history = [
                    *current_message_history,
                    {"role": "user", "content": feedback_message},
                ]

            yield ("result", {
                "response": response,
                "message_history": current_message_history[1:],
                "evaluation": evaluation_result,
            })

        except Exception as e:
            traceback.print_exc()
            yield ("error", {"detail": str(e)})
