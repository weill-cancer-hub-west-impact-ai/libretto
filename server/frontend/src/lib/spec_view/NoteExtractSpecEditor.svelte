<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';
  import {
    faXmark,
    faUndo,
    faSave,
    faMagicWandSparkles,
    faPlay,
    faComment,
    faPencil
  } from '@fortawesome/free-solid-svg-icons';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import SpecGenerationView from './SpecGenerationView.svelte';
  import ExamplePatientSelectionDialog from './generation_dialogs/ExamplePatientSelectionDialog.svelte';
  import type {
    ExtractionSpec,
    GenerationMessage,
    NoteExtractSpecContent
  } from '$lib/extraction_types';
  import CodeMirror from 'svelte-codemirror-editor';
  import { markdown } from '@codemirror/lang-markdown';
  import { json } from '@codemirror/lang-json';
  import { v4 as uuid } from 'uuid';
  import { areObjectsEqual } from '$lib/utils/utils';
  import { specs } from '$lib/stores/data';
  import CommentView from '$lib/shared/CommentView.svelte';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';
  import { consumeGenerationResponse } from '$lib/utils/sseGeneration';
  import QuestionAnswerDialog from './generation_dialogs/QuestionAnswerDialog.svelte';
  import type { BuildWorkflowQuestion } from './types';

  export let selectedSpec: ExtractionSpec;

  /** Whether a save is currently in-flight (controlled by parent). */
  export let saving: boolean = false;

  const dispatch = createEventDispatcher();

  let generating: boolean = false;
  let generationProgressMessage: string | undefined = undefined;
  let generationPaneVisible: boolean = false;
  let generationPrompt: string = '';
  let generationExplanation: string = '';
  let generationError: string = '';
  let commentView: CommentView;

  let examplePatientIds: string[] = [];
  let examplePatientDialogOpen: boolean = false;

  // Q&A dialog state
  let qaDialogOpen = false;
  let qaQuestions: BuildWorkflowQuestion[] = [];
  let qaHistory: GenerationMessage[] = [];

  // Form fields
  let editedSpecName: string = '';
  let editedPrompt: string = '';
  let editedSchema: string = '';
  let editedExamples: string = '';
  let remainingSpecFields: any = undefined;

  // Expose the current edited name so the sidebar can show it for unsaved new specs.
  export let newSpecName: string = '';
  $: newSpecName = editedSpecName;

  // Update form fields when selectedSpec changes
  $: if (selectedSpec) {
    let content = selectedSpec.content as NoteExtractSpecContent;
    editedSpecName = selectedSpec.name;
    editedPrompt = content.prompt;
    editedSchema = content.schema;
    editedExamples = JSON.stringify(content.examples, null, 2);
    remainingSpecFields = {
      model_args: content.model_args,
      note_metadata_query: content.note_metadata_query,
      note_text_query: content.note_text_query
    };
    examplePatientIds = content.example_patient_ids ?? [];
  }

  // Expose unsaved-changes state to parent via bind:hasChanges
  export let hasChanges: boolean = false;
  $: hasChanges =
    !!selectedSpec &&
    (editedSpecName !== selectedSpec.name ||
      editedPrompt !== (selectedSpec.content as NoteExtractSpecContent).prompt ||
      editedSchema !== (selectedSpec.content as NoteExtractSpecContent).schema ||
      editedExamples !==
        JSON.stringify((selectedSpec.content as NoteExtractSpecContent).examples, null, 2) ||
      !areObjectsEqual(
        examplePatientIds,
        (selectedSpec.content as NoteExtractSpecContent).example_patient_ids ?? []
      ) ||
      !$specs?.find((s) => areObjectsEqual(s, selectedSpec)));

  async function handleSave() {
    if (!selectedSpec) return;

    let parsedExamples;
    try {
      parsedExamples = JSON.parse(editedExamples);
      if (!Array.isArray(parsedExamples)) {
        alert('Examples must be a JSON array.');
        return;
      }
    } catch (error) {
      alert('Invalid JSON in examples field.');
      return;
    }

    let newID = selectedSpec.is_current ? selectedSpec.id : uuid();
    saving = true;
    try {
      const response = await authenticatedFetch(`/api/projects/${$projectID}/specs/${newID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: newID,
          name: newID != selectedSpec.id ? makeNewName(editedSpecName) : editedSpecName,
          executor: 'noteextract',
          content: {
            ...(remainingSpecFields ?? {}),
            prompt: editedPrompt,
            schema: editedSchema,
            examples: parsedExamples,
            example_patient_ids: examplePatientIds.length > 0 ? examplePatientIds : undefined
          }
        })
      });

      if (!response.ok) {
        console.error('Failed to save spec');
        alert('Failed to save specification. Please try again.');
      } else {
        const savedID = (await response.json()).spec_id;
        dispatch('saved', { newSelectedID: savedID });
      }
    } catch (error) {
      console.error('Error saving spec:', error);
      alert('Error saving specification. Please try again.');
    } finally {
      saving = false;
    }
  }

  async function handleExtract() {
    if (!selectedSpec) return;

    if (hasChanges) {
      dispatch('extractAfterRefresh');
      await handleSave();
    } else {
      dispatch('extract', { spec: selectedSpec });
    }
  }

  function makeNewName(baseName: string): string {
    let newName = baseName;
    if (!!$specs && $specs.find((s) => s.name == newName)) {
      let idx = 2;
      while ($specs.find((s) => s.name == newName + ` ${idx}`)) idx++;
      newName += ` ${idx}`;
    }
    return newName;
  }

  function handleRevert() {
    if (!selectedSpec) return;
    let content = selectedSpec.content as NoteExtractSpecContent;
    editedSpecName = selectedSpec.name;
    editedPrompt = content.prompt;
    editedSchema = content.schema;
    editedExamples = JSON.stringify(content.examples, null, 2);
    examplePatientIds = content.example_patient_ids ?? [];
  }

  function handleExamplePatientConfirm(event: CustomEvent<{ patientIds: string[] }>) {
    examplePatientIds = event.detail.patientIds;
    examplePatientDialogOpen = false;
  }

  function _generationBody(prompt?: string, answers?: string[], evaluate: boolean = false): any {
    // Build request body — include prior Q&A history and this round's answers if present
    let parsedExamples;
    try {
      parsedExamples = JSON.parse(editedExamples);
      if (!Array.isArray(parsedExamples)) {
        parsedExamples = [];
      }
    } catch (error) {
      alert('Invalid JSON in examples field.');
      parsedExamples = [];
    }
    let requestBody: any = {
      spec_draft: {
        ...(remainingSpecFields ?? {}),
        prompt: editedPrompt,
        schema: editedSchema,
        examples: parsedExamples,
        example_patient_ids: examplePatientIds.length > 0 ? examplePatientIds : undefined
      },
      ...(prompt ? { prompt } : {}),
      message_history: qaHistory,
      evaluate
    };
    if (answers) {
      requestBody.message_history = [
        ...requestBody.message_history,
        {
          role: 'user',
          content:
            'The user has answered your questions:\n\n' +
            answers.join('\n') +
            '\n\nUse these answers to ask further questions or create the spec.'
        }
      ];
    }
    return requestBody;
  }

  async function handleGenerateSubmit(prompt?: string, answers?: string[]) {
    if (!selectedSpec) return;

    generating = true;
    generationProgressMessage = 'Generating specification...';
    generationError = '';

    try {
      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/specs/${selectedSpec.id}/generate_noteextract`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(_generationBody(prompt, answers, examplePatientIds.length > 0))
        }
      );

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ detail: 'Failed to generate specification' }));
        throw new Error(errorData.detail || 'Failed to generate specification');
      }

      const result = await consumeGenerationResponse(response, (msg) => {
        generationProgressMessage = msg;
      });

      if (result.questions) {
        qaDialogOpen = true;
        qaQuestions = result.questions;
        qaHistory = result.message_history;
        generationExplanation = '';
        return;
      }

      generationPaneVisible = false;
      generationExplanation = result.response_message;
      dispatch('saved', { newSelectedID: result.spec?.id ?? null });
      generationPrompt = '';
    } catch (error) {
      console.error('Error generating spec:', error);
      generationError =
        error instanceof Error
          ? error.message
          : 'Failed to generate specification. Please try again.';
      generating = false;
    } finally {
      generating = false;
      generationProgressMessage = undefined;
    }
  }

  function handleQASubmit(event: CustomEvent<{ answers: string[] }>) {
    qaDialogOpen = false;
    handleGenerateSubmit(undefined, event.detail.answers);
  }

  function handleQACancel() {
    qaDialogOpen = false;
    qaHistory = [];
    qaQuestions = [];
  }
</script>

<QuestionAnswerDialog
  isOpen={qaDialogOpen}
  questions={qaQuestions}
  on:submit={handleQASubmit}
  on:cancel={handleQACancel}
/>

<ExamplePatientSelectionDialog
  selectedPatientIds={examplePatientIds}
  isOpen={examplePatientDialogOpen}
  {selectedSpec}
  on:confirm={handleExamplePatientConfirm}
  on:cancel={() => (examplePatientDialogOpen = false)}
/>

{#if generating}
  <LoadingView text={generationProgressMessage ?? 'Generating specification...'} />
{:else}
  <div class="flex h-full flex-auto flex-col">
    <!-- Action Buttons -->
    <div class="flex shrink-0 items-center justify-between px-4 py-4">
      <div class="flex items-center space-x-4">
        <button
          on:click={() => (generationPaneVisible = !generationPaneVisible)}
          class="btn inline-flex items-center gap-2 {generationPaneVisible
            ? 'btn-ai-secondary'
            : 'btn-ai-primary'}"
        >
          {#if generationPaneVisible}
            <Fa icon={faXmark} class="h-4 w-4" /> Hide
          {:else}
            <Fa icon={faMagicWandSparkles} class="h-4 w-4" /> Generate
          {/if}
        </button>
      </div>

      <div class="flex items-center space-x-2">
        <button
          on:click={() => commentView?.createNewComment()}
          class="btn-icon"
          title="View and add comments for this specification"
        >
          <Fa icon={faComment} />
        </button>
        <button
          on:click={handleRevert}
          disabled={!hasChanges}
          class="btn btn-tertiary inline-flex cursor-pointer items-center gap-2"
        >
          <Fa icon={faUndo} class="h-4 w-4" />
          Revert
        </button>
        <button
          on:click={handleSave}
          disabled={!hasChanges || saving}
          class="btn btn-primary inline-flex cursor-pointer items-center gap-2"
        >
          <Fa icon={faSave} class="h-4 w-4" />
          {saving ? 'Saving...' : selectedSpec?.is_current ? 'Save' : 'Save as Copy'}
        </button>
        <button
          on:click={handleExtract}
          disabled={saving}
          class="btn btn-primary inline-flex cursor-pointer items-center gap-2"
        >
          <Fa icon={faPlay} class="h-4 w-4" />
          {hasChanges ? 'Save and Extract...' : 'Extract...'}
        </button>
      </div>
    </div>

    <!-- Generation View -->
    <div class="px-4">
      <SpecGenerationView
        {selectedSpec}
        bind:generationPaneVisible
        bind:generationPrompt
        bind:generationExplanation
        bind:generationError
        {generating}
        on:generate={(e) => handleGenerateSubmit(e.detail.prompt.trim())}
      />
      {#if generationPaneVisible}
        <!-- Example patients -->
        {#if examplePatientIds.length > 0}
          <div class="mt-1 text-sm text-stone-500">
            The AI will reference these example patient(s) when developing the spec:
            {#each examplePatientIds as id, i (i)}
              <a
                class="cursor-pointer font-semibold text-sky-600 hover:opacity-50"
                href={null}
                on:click={() => dispatch('selectPatient', { patientID: id })}>{id}</a
              >{i < examplePatientIds.length - 1 ? ', ' : ''}
            {/each}
            <button
              on:click={() => (examplePatientDialogOpen = true)}
              class="btn-icon-small ml-1"
              title="Change example patients"
              aria-label="Change example patients"
            >
              <Fa icon={faPencil} />
            </button>
            <button
              on:click={() => (examplePatientIds = [])}
              class="btn-icon-small ml-1"
              title="Clear example patients"
              aria-label="Clear example patients"
            >
              <Fa icon={faXmark} />
            </button>
          </div>
        {:else}
          <div class="mt-1">
            <button
              on:click={() => (examplePatientDialogOpen = true)}
              class="btn-small btn-secondary"
            >
              Example Patients
            </button>
            <span class="ml-2 text-sm text-stone-400">
              Examples help the AI tailor and evaluate the specification.
            </span>
          </div>
        {/if}
      {/if}
    </div>

    <div class="min-h-0 flex-auto overflow-auto px-4 py-4">
      <!-- Spec Comments -->
      <CommentView entityType="spec" entityId={selectedSpec.id} bind:this={commentView} />

      <div class="space-y-4 rounded-lg border-2 border-stone-300/50 p-4 shadow-lg">
        <!-- Specification Name -->
        <div>
          <label for="spec-name" class="mb-1 block text-sm font-bold uppercase">
            Specification Name
          </label>
          <input
            id="spec-name"
            type="text"
            bind:value={editedSpecName}
            class="w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            placeholder="Enter specification name"
          />
        </div>

        <!-- Prompt -->
        <div>
          <div class="mb-1 text-sm font-bold uppercase">
            Prompt
            <span class="ml-2 font-normal text-stone-500 normal-case">
              Overall instructions to the model.
            </span>
          </div>
          <CodeMirror
            class="max-h-48 w-full overflow-auto rounded-md border border-stone-300"
            bind:value={editedPrompt}
            lineWrapping
            lang={markdown()}
          />
        </div>

        <!-- Schema -->
        <div>
          <div class="mb-1 text-sm font-bold uppercase">
            Schema
            <span class="ml-2 font-normal text-stone-500 normal-case">
              Describe in text the structure for the extractions you expect, including possible
              extraction classes and attributes.
            </span>
          </div>
          <CodeMirror
            class="max-h-48 w-full overflow-auto rounded-md border border-stone-300"
            bind:value={editedSchema}
            lineWrapping
            lang={markdown()}
          />
        </div>

        <!-- Examples -->
        <div>
          <div class="mb-1 text-sm font-bold uppercase">
            Examples
            <span class="ml-2 font-normal text-stone-500 normal-case">
              JSON array of example inputs and expected outputs to guide the model.
            </span>
          </div>
          <CodeMirror
            class="max-h-48 w-full overflow-auto rounded-md border border-stone-300"
            bind:value={editedExamples}
            lineWrapping
            lang={json()}
          />
        </div>
      </div>
      <div class="my-2 text-xs text-stone-500">
        This specification was created for <strong>NoteExtract</strong>: it uses the LangExtract
        algorithm to extract information over chunked sections of notes. NoteExtract specifications
        require a prompt, schema, and examples.
      </div>
    </div>
  </div>
{/if}

<style>
  :global(.cm-editor) {
    height: 100%;
  }

  :global(.cm-activeLine) {
    background: transparent !important;
  }
  :global(.cm-focused .cm-activeLine) {
    background: rgba(100, 100, 100, 0.1) !important;
  }
</style>
