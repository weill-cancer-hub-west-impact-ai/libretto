"""NoteExtract spec generation."""

import logging
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional, Tuple, TypedDict, NotRequired

from lab_llm import LLMApi
from pydantic import BaseModel

from ..types import Patient, NoteExtraction, Project, ExtractionSpec
from ..source_database import DEFAULT_NOTE_METADATA_QUERY, DEFAULT_NOTE_TEXT_QUERY
from ..generation import SpecGenerator, UserQuestion, SpecGeneratorResult
from .run import run_noteextract

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ExampleAttribute(BaseModel):
    key: str
    value: str


class ExampleExtraction(BaseModel):
    extraction_class: str
    extraction_text: str
    attributes: List[ExampleAttribute]


class ExampleData(BaseModel):
    text: str
    extractions: List[ExampleExtraction]

class NoteExtractOptionalSpecContent(TypedDict):
    example_patient_ids: NotRequired[Optional[list[str]]]
    prompt: NotRequired[Optional[str]]
    schema: NotRequired[Optional[str]]
    examples: NotRequired[Optional[List[ExampleData]]]


class GeneratedNoteExtractSpec(BaseModel):
    """LLM-generated spec before conversion to ExtractionSpec format."""
    name: str
    prompt: str
    schema: str
    examples: List[ExampleData]

    @staticmethod
    def to_spec(spec_dict: dict[str, Any], note_metadata_query: str, note_text_query: str, example_patient_ids: Optional[list[str]]) -> ExtractionSpec:
        """Convert a GeneratedNoteExtractSpec dict to an ExtractionSpec with executor/content format."""
        def _attrs_to_dict(attributes):
            if isinstance(attributes, dict):
                return attributes
            if isinstance(attributes, list):
                return {att["key"]: att["value"] for att in attributes if isinstance(att, dict) and "key" in att}
            return {}

        examples = [
            {**example, "extractions": [
                {**ex, "attributes": _attrs_to_dict(ex.get("attributes", {}))}
                for ex in example.get("extractions") or []
            ]}
            for example in spec_dict.get("examples") or []
        ]
        return {
            "name": spec_dict["name"],
            "executor": "noteextract",
            "content": {
                "prompt": spec_dict["prompt"],
                "schema": spec_dict["schema"],
                "examples": examples,
                "note_metadata_query": note_metadata_query,
                "note_text_query": note_text_query,
                "model_args": spec_dict.get("model_args", {}),
                "example_patient_ids": example_patient_ids
            },
        }

    @staticmethod
    def to_generation_spec(spec: ExtractionSpec) -> dict[str, Any]:
        """Convert an ExtractionSpec back to GeneratedNoteExtractSpec shape for LLM editing."""
        def _dict_to_attrs(attributes):
            return [{"key": key, "value": value} for key, value in attributes.items()]

        content = spec.get("content") or {}
        return {
            "name": spec.get("name"),
            "prompt": content.get("prompt"),
            "schema": content.get("schema"),
            "examples": [
                {**example, "extractions": [
                    {**ex, "attributes": _dict_to_attrs(ex.get("attributes", {}))}
                    for ex in example.get("extractions") or []
                ]}
                for example in content.get("examples") or []
            ],
        }


class _GenerateNoteExtractSpecResult(BaseModel):
    questions: Optional[List[UserQuestion]] = None
    response_message: Optional[str] = None
    spec: Optional[GeneratedNoteExtractSpec] = None


class NoteExtractSpecGenerator(SpecGenerator):
    """Spec generator for the noteextract executor."""

    def __init__(
        self,
        llm_api: LLMApi,
        project: Project,
        prompts_dir: Optional[Path] = None,
        model: Optional[str] = None,
    ):
        super().__init__(llm_api, project)
        self._prompts_dir = prompts_dir or _PROMPTS_DIR
        self.model = model

    def execute_spec(
        self,
        spec_content: dict[str, Any],
        patient: Patient,
    ) -> list[NoteExtraction]:
        return run_noteextract(patient, spec_content)

    @property
    def generate_system_prompt(self) -> str:
        overview_path = self._prompts_dir / "overview.md"
        with overview_path.open() as f:
            overview = f.read()
        with (self._prompts_dir / "generate_spec.md").open() as f:
            system_prompt = f.read().format(overview=overview)
        return system_prompt

    @property
    def evaluate_system_prompt(self) -> str:
        evaluator_path = self._prompts_dir / "evaluator.md"
        overview_path = self._prompts_dir / "overview.md"
        with overview_path.open() as f:
            overview = f.read()
        with evaluator_path.open() as f:
            return f.read().format(overview=overview)

    def _initial_messages(self, 
                          prompt: str, 
                          spec_draft: NoteExtractOptionalSpecContent | None = None, 
                          existing_spec: ExtractionSpec | None = None) -> list[dict[str, Any]]:
        existing_content = (existing_spec or {}).get("content") or {}
        spec_section_content: dict[str, Any] = {
            "name": (existing_spec or {}).get("name"),
            "prompt": (spec_draft or {}).get("prompt") or existing_content.get("prompt"),
            "schema": (spec_draft or {}).get("schema") or existing_content.get("schema"),
            "examples": (spec_draft or {}).get("examples") or existing_content.get("examples"),
        }
        spec_section_header = "Existing Spec Draft"

        example_ids = (spec_draft or {}).get("example_patient_ids")
        if example_ids is None:
            example_ids = existing_content.get("example_patient_ids")

        return self.create_initial_messages(
            spec_section_content=spec_section_content,
            spec_section_header=spec_section_header,
            prompt=prompt or "Generate a clinically meaningful extraction specification given the provided patient data.",
            example_patient_ids=example_ids,
        )

    def _build_spec_object(self, response: dict, spec_draft: Optional[NoteExtractOptionalSpecContent] = None, existing_spec: Optional[dict] = None) -> ExtractionSpec:
        """Build a full ExtractionSpec dict from a NoteExtract generate_spec response."""
        if spec := response.get("spec"):
            example_ids = (spec_draft or {}).get("example_patient_ids")
            if example_ids is None:
                example_ids = (existing_spec or {}).get("content", {}).get("example_patient_ids")

            note_metadata_query = self.project.get("note_metadata_query") or DEFAULT_NOTE_METADATA_QUERY
            note_text_query = self.project.get("note_text_query") or DEFAULT_NOTE_TEXT_QUERY
            spec = GeneratedNoteExtractSpec.to_spec(response["spec"], 
                                                    note_metadata_query, 
                                                    note_text_query,
                                                    example_ids)

            return spec

    def generate_spec(
        self,
        message_history: list[dict[str, Any]] = [],
        prompt: Optional[str] = None,
        spec_draft: Optional[NoteExtractOptionalSpecContent] = None,
        existing_spec: Optional[ExtractionSpec] = None
    ) -> SpecGeneratorResult:
        """
        Generate or update a prompt-only spec.

        On the first turn (empty message_history), builds the initial structured
        message from the patient data overview, existing spec context, and prompt.
        Subsequent turns continue multi-turn via message_history.

        Returns:
            dictionary with (questions, spec, response_message, message_history)

            Either questions or spec will be non-null.
        """
        if not message_history:
            message_history = self._initial_messages(prompt, spec_draft=spec_draft, existing_spec=existing_spec)
            prompt = None

        response, updated_history = self.generate(
            _GenerateNoteExtractSpecResult, message_history, prompt=prompt, model=self.model
        )

        if questions := response.get("questions"):
            return {
                "questions": questions, 
                "spec": None, 
                "response_message": None, 
                "message_history": updated_history
            }

        return {
            "questions": None, 
            "spec": self._build_spec_object(response, spec_draft, existing_spec), 
            "response_message": response.get("response_message"), 
            "message_history": updated_history
        }

    async def generate_and_evaluate_spec(
        self,
        message_history: list[dict[str, Any]] = [],
        prompt: Optional[str] = None,
        spec_draft: Optional[NoteExtractOptionalSpecContent] = None,
        existing_spec: Optional[ExtractionSpec] = None,
        evaluate_max_passes: int = 2
    ) -> AsyncIterator[Tuple[str, Any]]:
        """
        Generate and iteratively evaluate a prompt-only spec via SSE events.

        Yields (event_type, data) tuples. When event_type is "result", the data
        dictionary will contain "spec", "response_message", "evaluation", and
        "message_history".
        """
        if not message_history:
            message_history = self._initial_messages(prompt, spec_draft=spec_draft, existing_spec=existing_spec)
            prompt = None

        print("Message history:", message_history)
        async for event in self.generate_and_evaluate(
            response_model=_GenerateNoteExtractSpecResult,
            initial_message_history=message_history,
            evaluate_max_passes=evaluate_max_passes,
            response_to_spec_fn=lambda response: self._build_spec_object(response, spec_draft=spec_draft, existing_spec=existing_spec),
            prompt=prompt,
            model=self.model,
        ):
            if event[0] == "result" and "response" in event[1]:
                response = event[1]["response"]
                yield (event[0], {
                    "spec": self._build_spec_object(response, spec_draft, existing_spec),
                    "response_message": response.get("response_message"),
                    "evaluation": event[1].get("evaluation"),
                    "message_history": event[1].get("message_history"),
                })
            else:
                yield event
