<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { ExtractionSpec } from '../extraction_types';
  import Fa from 'svelte-fa';
  import { faXmark } from '@fortawesome/free-solid-svg-icons';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import SpecificationListView from '$lib/shared/SpecificationListView.svelte';

  export let extractionSpecs: ExtractionSpec[] = [];
  export let isOpen: boolean = false;

  const dispatch = createEventDispatcher();

  export let selectedSpec: ExtractionSpec | null = null;
  export let fetchFilteredSpecs: (() => Promise<ExtractionSpec[]>) | undefined = undefined;

  let filterAvailableModels: boolean = false;
  let filteredSpecs: ExtractionSpec[] = [];
  let loadingSpecs: boolean = false;

  // Reactive statement to fetch filtered prompts when toggle changes
  $: if (isOpen && filterAvailableModels && fetchFilteredSpecs) {
    loadingSpecs = true;
    fetchFilteredSpecs()
      .then((filtered) => {
        filteredSpecs = filtered;
        loadingSpecs = false;
      })
      .catch((err) => {
        console.error('Error loading prompts:', err);
        loadingSpecs = false;
      });
  }

  // Use filtered models/prompts if filtering is enabled, otherwise use all
  $: displayedSpecs = filterAvailableModels ? filteredSpecs : extractionSpecs;

  // Reset selections if they are no longer available in filtered lists
  $: if (!!selectedSpec && !loadingSpecs && !displayedSpecs.find((p) => p.id == selectedSpec!.id)) {
    selectedSpec = displayedSpecs.length > 0 ? displayedSpecs[0] : null;
  }

  function handleSpecSelect(event: CustomEvent) {
    selectedSpec = event.detail.spec;
    dispatch('select', { spec: selectedSpec! });
    handleClose();
  }

  function handleClose() {
    dispatch('close');
  }

  function handleNewSpec() {
    dispatch('createSpec');
  }

  function handleEditSpec(spec: ExtractionSpec) {
    dispatch('editSpec', { spec });
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
      class="mx-4 flex max-h-3/4 w-full max-w-4xl flex-col gap-4 rounded-lg bg-white px-6 py-4 shadow-xl"
    >
      <!-- Header -->
      <div class="flex shrink-0 items-center justify-between">
        <h2 id="modal-title" class="text-lg font-bold text-gray-900">Select Extraction Spec</h2>
        <button
          on:click={handleClose}
          class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close modal"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <!-- Content -->
      <div class="flex min-h-0 flex-auto gap-4">
        <!-- Spec Selection -->
        <div class="flex flex-1 flex-col">
          <div class="min-h-0 flex-auto overflow-y-auto">
            <SpecificationListView
              specs={displayedSpecs}
              {selectedSpec}
              showEditButton={true}
              showNewButton={false}
              on:select={handleSpecSelect}
              on:editSpec={(e) => handleEditSpec(e.detail.spec)}
              on:new={handleNewSpec}
            />
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}
