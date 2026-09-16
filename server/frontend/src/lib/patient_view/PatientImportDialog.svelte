<script lang="ts">
  import { createEventDispatcher, getContext } from 'svelte';
  import Fa from 'svelte-fa';
  import { faXmark, faPlus, faTrash } from '@fortawesome/free-solid-svg-icons';
  import CodeMirror from 'svelte-codemirror-editor';
  import { markdown } from '@codemirror/lang-markdown';
  import type { Patient, Note } from '../extraction_types';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';
  import { error } from '@sveltejs/kit';

  export let isOpen: boolean = false;

  const dispatch = createEventDispatcher();

  let patientId = '';
  let notes: { id: string; text: string; date: string }[] = [{ id: '', text: '', date: '' }];
  let importing = false;
  let errorMessage = '';

  // Generate note IDs based on patient ID
  $: {
    notes = notes.map((note, index) => ({
      ...note,
      id: patientId ? `${patientId}_note_${index + 1}` : ''
    }));
  }

  function addNote() {
    notes = [...notes, { id: '', text: '', date: '' }];
  }

  function removeNote(index: number) {
    if (notes.length > 1) {
      notes = notes.filter((_, i) => i !== index);
    }
  }

  function updateNoteText(index: number, text: string) {
    notes = notes.map((note, i) => (i === index ? { ...note, text } : note));
  }

  function updateNoteDate(index: number, date: string) {
    notes = notes.map((note, i) => (i === index ? { ...note, date } : note));
  }

  async function handleImport() {
    if (!patientId.trim()) {
      errorMessage = 'Patient ID is required.';
      return;
    }
    if (patientId.toLocaleLowerCase() == 'test') {
      errorMessage = "The patient ID 'test' is not allowed.";
      return;
    }

    if (notes.some((note) => !note.text.trim())) {
      errorMessage = 'All notes must have content.';
      return;
    }

    importing = true;
    errorMessage = '';

    try {
      // Prepare patient data
      const patientData: Patient[] = [
        {
          id: patientId.trim(),
          notes: notes.map((note, index) => ({
            id: note.id,
            metadata: {},
            note_text: note.text.trim(),
            date: note.date.trim() || undefined
          })),
          metadata: {},
          note_count: notes.length,
          earliest_note_date: null,
          latest_note_date: null
        }
      ];

      const response = await authenticatedFetch(`/api/projects/${$projectID}/patients`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ patients: patientData })
      });

      if (response.ok) {
        const result = await response.json();
        dispatch('success', { patientIds: result.patient_ids || [patientId] });
        handleClose();
      } else {
        const errorData = await response.json();
        errorMessage = errorData.error || 'Import failed. Please try again.';
      }
    } catch (error) {
      console.error('Import error:', error);
      errorMessage = 'Import failed. Please check your connection and try again.';
    } finally {
      importing = false;
    }
  }

  function handleClose() {
    patientId = '';
    notes = [{ id: '', text: '', date: '' }];
    errorMessage = '';
    importing = false;
    dispatch('close');
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      handleClose();
      event.stopPropagation();
      event.preventDefault();
    }
  }

  // Validation
  $: isValid = patientId.trim() && notes.every((note) => note.text.trim());
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
  <!-- Modal backdrop -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    on:click={handleBackdropClick}
    on:keydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    tabindex="-1"
  >
    <!-- Modal content -->
    <div class="mx-4 flex max-h-3/4 w-full max-w-4xl flex-col rounded-lg bg-white py-4 shadow-xl">
      <!-- Header -->
      <div class="mx-6 mb-4 flex shrink-0 items-center justify-between">
        <h2 id="modal-title" class="text-lg font-bold text-gray-900">Enter Patient Details</h2>
        <button
          on:click={handleClose}
          class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close modal"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <!-- Content -->
      <div class="min-h-0 flex-auto space-y-4 overflow-auto px-6">
        <!-- Patient ID -->
        <div class="shrink-0">
          <label for="patient-id" class="mb-2 block text-sm font-semibold text-gray-700 uppercase">
            Patient ID <span class="text-red-500">*</span>
          </label>
          <input
            id="patient-id"
            bind:value={patientId}
            type="text"
            placeholder="Enter patient ID (e.g., patient_001)"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            disabled={importing}
          />
        </div>

        <!-- Notes Section -->
        <div class="mb-2 flex items-center justify-between">
          <label class="block text-sm font-semibold text-gray-700 uppercase">
            Notes <span class="text-red-500">*</span>
          </label>
          <button
            on:click={addNote}
            class="rounded-md bg-gray-200 px-3 py-1 text-sm text-gray-900 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={importing}
          >
            <Fa icon={faPlus} class="mr-2 inline" />
            Note
          </button>
        </div>

        <!-- Notes List -->
        <div class="space-y-3">
          {#each notes as note, index (index)}
            <div class="mb-3 flex items-center gap-2">
              {#if notes.length > 1}
                <button
                  on:click={() => removeNote(index)}
                  class="rounded-lg p-1 text-gray-500 hover:opacity-50 disabled:cursor-not-allowed disabled:opacity-30"
                  disabled={importing}
                  aria-label="Remove note"
                >
                  <Fa icon={faTrash} class="h-4 w-4" />
                </button>
              {/if}
              <div class="text-sm font-medium text-gray-700">
                Note {index + 1}
                {#if note.id}
                  <span class="ml-2 text-xs text-gray-500">ID: {note.id}</span>
                {/if}
              </div>
            </div>

            <!-- Date input -->
            <div class="mb-3">
              <label for="note-date-{index}" class="mb-1 block text-xs font-medium text-gray-700">
                Date (optional)
              </label>
              <input
                id="note-date-{index}"
                bind:value={note.date}
                on:input={(e) => updateNoteDate(index, e.currentTarget.value)}
                type="text"
                placeholder="YYYY-MM-DD"
                class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                disabled={importing}
              />
            </div>

            <div class="h-48">
              <CodeMirror
                bind:value={note.text}
                onchange={(val) => updateNoteText(index, val)}
                extensions={[markdown()]}
                placeholder="Enter note text here..."
                class="h-full rounded-lg border border-gray-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
            </div>
          {/each}
        </div>
      </div>
      <!-- Error message -->
      {#if errorMessage}
        <div class="mx-6 shrink-0 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {errorMessage}
        </div>
      {/if}

      <!-- Actions -->
      <div class="mx-6 flex shrink-0 justify-end space-x-3 pt-4">
        <button
          on:click={handleImport}
          disabled={!isValid || importing}
          class="btn-primary btn-big"
        >
          {importing ? 'Importing...' : 'Import Patient'}
        </button>
      </div>
    </div>
  </div>
{/if}
