<script lang="ts">
  import { createEventDispatcher, getContext } from 'svelte';
  import type { ExtractionSpec, Patient } from '$lib/extraction_types';
  import Fa from 'svelte-fa';
  import { faPlay, faXmark } from '@fortawesome/free-solid-svg-icons';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import TableView from '$lib/utils/TableView.svelte';
  import SpecificationListView from '$lib/shared/SpecificationListView.svelte';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';
  import PatientSelector from '$lib/patient_view/PatientSelector.svelte';

  export let isOpen: boolean = false;

  const dispatch = createEventDispatcher();

  let extractionSpecs: ExtractionSpec[] = [];
  export let selectedSpec: ExtractionSpec | null = null;
  export let selectedPatientIDs: string[] = [];
  let loading: boolean = false;

  $: canCreate = selectedSpec !== null && selectedPatientIDs.length > 0;

  // Load data when modal opens
  $: if (isOpen) {
    loadData();
  }

  async function loadData() {
    loading = true;
    try {
      const specsResponse = await authenticatedFetch(`/api/projects/${$projectID}/specs`);

      if (specsResponse.ok) {
        extractionSpecs = await specsResponse.json();
        // Only auto-select first spec if no spec is already selected
        if (!selectedSpec && extractionSpecs.length > 0) {
          selectedSpec = extractionSpecs[0];
        }
      }
    } catch (error) {
      console.error('Error loading specs:', error);
    } finally {
      loading = false;
    }
  }

  function handleSpecSelect(event: CustomEvent) {
    selectedSpec = event.detail.spec;
  }

  async function handleCreate() {
    if (!canCreate) return;

    try {
      const response = await authenticatedFetch(`/api/projects/${$projectID}/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          specID: selectedSpec!.id,
          patientIDs: selectedPatientIDs,
          overwrite: true
        })
      });

      if (response.ok) {
        const task = await response.json();
        dispatch('created', { task });
        handleClose();
      } else {
        console.error('Failed to create task');
        alert('Failed to create task. Is the extraction service running?');
        handleClose();
      }
    } catch (error) {
      console.error('Error creating task:', error);
    }
  }

  function handleClose() {
    dispatch('close');
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  }

  function handleNewSpec() {
    dispatch('createSpec');
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      handleClose();
      event.stopPropagation();
      event.preventDefault();
    }
  }
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
    <div
      class="mx-4 flex max-h-3/4 w-full max-w-5xl flex-col gap-4 rounded-lg bg-white px-6 py-4 shadow-xl"
    >
      <!-- Header -->
      <div class="flex shrink-0 items-center justify-between">
        <h2 id="modal-title" class="text-lg font-bold text-gray-900">Start Extraction</h2>
        <button
          on:click={handleClose}
          class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close modal"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <!-- Content -->
      <div class="flex min-h-0 flex-auto">
        {#if loading}
          <LoadingView text="Loading specifications..." />
        {:else}
          {@const currentSpecs = extractionSpecs.filter((s) => s.is_current ?? false)}
          <!-- Spec Selection -->
          <div class="mr-4 flex w-1/3 min-w-48 flex-col">
            <h3 class="mb-2 shrink-0 font-semibold text-gray-900">
              Specification <span class="ml-2 text-sm font-normal text-gray-400"
                >{currentSpecs.length} spec{currentSpecs.length != 1 ? 's' : ''}</span
              >
            </h3>
            <div class="min-h-0 flex-auto overflow-y-auto">
              <SpecificationListView
                specs={extractionSpecs}
                {selectedSpec}
                showEditButton={true}
                showNewButton={true}
                on:select={handleSpecSelect}
                on:editSpec
                on:new={handleNewSpec}
              />
            </div>
          </div>

          <!-- Patient Selection -->
          <div class="flex flex-auto flex-col">
            <div class="mb-2 flex w-full shrink-0 items-center justify-between">
              <h3 class="font-semibold text-gray-900">
                Patients <span class="ml-2 text-sm font-normal text-gray-400"
                  >Extract on: {selectedPatientIDs.length} patient{selectedPatientIDs.length != 1
                    ? 's'
                    : ''}</span
                >
              </h3>
              <button
                on:click={() => dispatch('editPatients')}
                class="rounded-md bg-gray-200 px-3 py-1 text-sm text-gray-900 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
                title="Add or delete patients"
              >
                Edit...
              </button>
            </div>

            <div class="min-h-0 w-full flex-auto">
              <PatientSelector
                showHeader={false}
                multiSelectOnly
                defaultSelectAll
                {selectedSpec}
                bind:selectedPatientIds={selectedPatientIDs}
                editable={false}
              />
            </div>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="flex shrink-0 items-center justify-end">
        <!-- Skip processed checkbox -->
        <!-- <label class="flex items-center text-sm text-gray-700">
          <input
            type="checkbox"
            bind:checked={skipProcessedNotes}
            class="mr-2 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          Skip already-processed notes
        </label> -->

        <button on:click={handleCreate} disabled={!canCreate} class="btn-big btn-primary">
          <Fa icon={faPlay} class="mr-2 inline" /> Run
        </button>
      </div>
    </div>
  </div>
{/if}
