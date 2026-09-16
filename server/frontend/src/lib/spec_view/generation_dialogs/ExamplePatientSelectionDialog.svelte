<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';
  import { faXmark, faShuffle, faCheck } from '@fortawesome/free-solid-svg-icons';
  import PatientSelector from '$lib/patient_view/PatientSelector.svelte';
  import PatientView from '$lib/patient_view/PatientView.svelte';
  import { loadPatients } from '$lib/stores/data';
  import type { ExtractionSpec, Patient } from '$lib/extraction_types';
  import ResizablePanel from '$lib/utils/ResizablePanel.svelte';

  export let isOpen: boolean = false;
  export let selectedSpec: ExtractionSpec | null = null;

  const dispatch = createEventDispatcher<{
    confirm: { patientIds: string[] };
    cancel: void;
  }>();

  // The IDs the user has checked/multi-selected in PatientSelector
  export let selectedPatientIds: string[] = [];

  // The patient the user is currently previewing in PatientView
  let previewPatient: Patient | null = null;
  let previewNoteID: string | null = null;

  // All loaded patients (needed for random selection)
  let allPatients: Patient[] = [];
  let loadingPatients = false;
  let patientsFetched = false;

  $: if (isOpen && !patientsFetched && !loadingPatients) {
    loadingPatients = true;
    loadPatients(null).then((p) => {
      allPatients = p ?? [];
      loadingPatients = false;
      patientsFetched = true;
    });
  }

  // Reset state when dialog opens
  $: if (isOpen) {
    previewPatient = null;
    previewNoteID = null;
  }

  function handleSelectRandom() {
    if (allPatients.length === 0) return;
    const shuffled = [...allPatients].sort(() => Math.random() - 0.5);
    selectedPatientIds = shuffled.slice(0, Math.min(3, shuffled.length)).map((p) => p.id);
  }

  function handleConfirm() {
    dispatch('confirm', { patientIds: [...selectedPatientIds] });
  }

  function handleCancel() {
    dispatch('cancel');
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      handleCancel();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      handleCancel();
      event.stopPropagation();
      event.preventDefault();
    }
  }

  // When a patient is single-clicked in PatientSelector, preview it in PatientView
  function handlePatientSelect(event: CustomEvent<{ patient: Patient | null }>) {
    previewPatient = event.detail.patient;
    previewNoteID = null;
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    on:click={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    aria-labelledby="example-patients-modal-title"
    tabindex="-1"
  >
    <div
      class="mx-4 flex w-full flex-col rounded-lg bg-white shadow-xl"
      style="width: min(90vw, 1100px); height: min(85vh, 800px);"
    >
      <!-- Header -->
      <div class="flex shrink-0 items-center justify-between px-6 py-4">
        <div>
          <h2 id="example-patients-modal-title" class="text-lg font-bold text-stone-900">
            Select Example Patients
          </h2>
          <p class="mt-0.5 text-sm text-stone-500">
            Select patient examples to help the AI create your specification and evaluate it once
            created.
          </p>
        </div>
        <button
          on:click={handleCancel}
          class="rounded-lg p-2 text-stone-500 hover:bg-stone-100 hover:text-stone-700"
          aria-label="Close"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <!-- Body: patient list on the left, patient detail on the right -->
      <div class="flex min-h-0 flex-auto overflow-hidden">
        <!-- Left panel: PatientSelector for browsing + multi-select -->
        <ResizablePanel height="100%" rightResizable minWidth={160} maxWidth="80%" width={320}>
          <PatientSelector
            {selectedSpec}
            showHeader={false}
            multiSelectOnly={false}
            editable={false}
            bind:selectedPatientIds
            on:select={handlePatientSelect}
          />
        </ResizablePanel>

        <!-- Right panel: PatientView for previewing the clicked patient -->
        <div class="flex min-w-0 flex-auto flex-col overflow-hidden">
          {#if previewPatient}
            <PatientView
              showEditControls={false}
              selectedPatient={previewPatient}
              bind:noteID={previewNoteID}
              extractionSpecs={[]}
              {selectedSpec}
              showPatientSelector={false}
            />
          {:else}
            <div class="flex h-full items-center justify-center text-stone-500">
              <div class="text-center">
                <div class="text-sm">Click a patient to preview their notes</div>
              </div>
            </div>
          {/if}
        </div>
      </div>

      <!-- Footer -->
      <div class="flex shrink-0 items-center justify-between px-6 py-4">
        <div class="flex items-center gap-3">
          <button
            on:click={handleSelectRandom}
            disabled={allPatients.length === 0}
            class="btn btn-secondary"
            title="Select 3 random patients"
          >
            <Fa icon={faShuffle} class="mr-2 inline" />
            Random
          </button>
          {#if selectedPatientIds.length > 0}
            <span class="text-sm text-stone-500">
              {selectedPatientIds.length}
              {selectedPatientIds.length === 1 ? 'patient' : 'patients'} selected
            </span>
          {/if}
        </div>
        <div class="flex items-center gap-3">
          <button on:click={handleCancel} class="btn btn-secondary"> Cancel </button>
          <button
            on:click={handleConfirm}
            disabled={selectedPatientIds.length > 5}
            class="btn btn-primary"
            title={selectedPatientIds.length > 5
              ? 'Cannot attach more than 5 patients'
              : 'Attach these patients'}
          >
            {#if selectedPatientIds.length == 0}
              Skip
            {:else}
              Attach {selectedPatientIds.length > 0
                ? `${selectedPatientIds.length} `
                : ''}{selectedPatientIds.length === 1 ? 'Patient' : 'Patients'}
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
