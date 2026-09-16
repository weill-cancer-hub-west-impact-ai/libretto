"""Prompt-only spec generation."""

import logging
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional, Tuple, TypedDict, NotRequired

from lab_llm import LLMApi
from pydantic import BaseModel

from ..types import Patient, NoteExtraction, Project, ExtractionSpec
from ..generation import SpecGenerator, UserQuestion, SpecGeneratorResult
from .run import run_prompt_only

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PromptOnlyOptionalSpecContent(TypedDict):
    example_patient_ids: NotRequired[Optional[list[str]]]
    prompt: NotRequired[Optional[str]]
    
class _GeneratedPromptOnlySpec(BaseModel):
    name: str
    prompt: str

class _GeneratePromptOnlySpecResult(BaseModel):
    questions: Optional[List[UserQuestion]] = None
    response_message: Optional[str] = None
    spec: Optional[_GeneratedPromptOnlySpec] = None

class PromptOnlySpecGenerator(SpecGenerator):
    """Spec generator for the prompt_only executor."""

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
        return run_prompt_only(patient, spec_content["prompt"], self.llm_api)

    @property
    def generate_system_prompt(self):
        generate_path = self._prompts_dir / "generate_spec.md"
        overview_path = self._prompts_dir / "overview.md"
        with overview_path.open() as f:
            overview = f.read()
        with generate_path.open() as f:
            return f.read().format(overview=overview)
        
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
                          spec_draft: PromptOnlyOptionalSpecContent | None = None, 
                          existing_spec: ExtractionSpec | None = None) -> list[dict[str, Any]]:
        existing_content = (existing_spec or {}).get("content") or {}
        spec_section_content: dict[str, Any] = {
            "name": (existing_spec or {}).get("name"),
            "prompt": (spec_draft or {}).get("prompt") or existing_content.get("prompt"),
        }
        spec_section_header = "Existing Spec Draft"

        example_ids = (spec_draft or {}).get("example_patient_ids")
        if example_ids is None:
            example_ids = existing_content.get("example_patient_ids")

        return self.create_initial_messages(
            spec_section_content=spec_section_content,
            spec_section_header=spec_section_header,
            prompt=prompt or "Generate a clinically meaningful extraction specification given the provided patient data.",
            example_patient_ids=example_ids
        )

    def _build_spec_object(self, response: dict, spec_draft: Optional[PromptOnlyOptionalSpecContent] = None, existing_spec: Optional[dict] = None) -> ExtractionSpec:
        """Build a full ExtractionSpec dict from a prompt_only generate_spec response."""
        if spec := response.get("spec"):
            
            example_ids = (spec_draft or {}).get("example_patient_ids")
            if example_ids is None:
                example_ids = (existing_spec or {}).get("content", {}).get("example_patient_ids")

            response_spec = {"name": spec.get("name"),
                             "executor": "prompt_only",
                             **(existing_spec or {}), 
                             "content": {
                                "prompt": spec.get("prompt") or (spec_draft or {}).get("prompt"),
                                "example_patient_ids": example_ids
                             }, "project_id": self.project["id"]}
            return response_spec


    # ------------------------------------------------------------------
    # Public generation methods
    # ------------------------------------------------------------------

    def generate_spec(
        self,
        message_history: list[dict[str, Any]] = [],
        prompt: Optional[str] = None,
        spec_draft: Optional[PromptOnlyOptionalSpecContent] = None,
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
            _GeneratePromptOnlySpecResult, message_history, prompt=prompt, model=self.model
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
        spec_draft: Optional[PromptOnlyOptionalSpecContent] = None,
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

        async for event in self.generate_and_evaluate(
            response_model=_GeneratePromptOnlySpecResult,
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
