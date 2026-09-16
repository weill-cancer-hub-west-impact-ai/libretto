<script lang="ts">
  import type { ExtractionSpec } from '$lib/extraction_types';
  import { createEventDispatcher } from 'svelte';
  import SpecificationListView from '$lib/shared/SpecificationListView.svelte';
  import Fa from 'svelte-fa';
  import { faCopy, faDownload, faTrash, faUpload } from '@fortawesome/free-solid-svg-icons';

  const dispatch = createEventDispatcher();

  export let specs: ExtractionSpec[] | null = [];
  export let selectedSpec: ExtractionSpec | null = null;
  export let newSpecName: string | null = null;

  function handleSelect(event: CustomEvent) {
    dispatch('select', event.detail);
  }

  function handleNew() {
    dispatch('new');
  }

  export let uploading: boolean = false;
  let fileInput: HTMLInputElement;

  function handleUploadClick() {
    fileInput?.click();
  }

  $: if (!uploading && !!fileInput) fileInput.value = '';
</script>

<div class="flex h-full w-full flex-auto flex-col">
  <!-- Header + Action Buttons -->
  <div class="flex shrink-0 items-center px-4 py-4">
    <h2 id="modal-title" class="flex-auto text-lg font-bold text-stone-900">Specifications</h2>
    <button
      on:click={handleUploadClick}
      disabled={uploading}
      class="btn-icon"
      title="Import a specification from a JSON file"
    >
      <Fa icon={faUpload} class="h-4 w-4" />
    </button>
    <button
      on:click={() => dispatch('download')}
      class="btn-icon"
      title="Download the saved version of this specification as a JSON file"
    >
      <Fa icon={faDownload} class="h-4 w-4" />
    </button>
    <button on:click={() => dispatch('delete')} class="btn-icon" title="Delete this specification">
      <Fa icon={faTrash} class="h-4 w-4" />
    </button>
    <button
      on:click={() => dispatch('duplicate')}
      class="btn-icon"
      title="Duplicate this specification"
    >
      <Fa icon={faCopy} class="h-4 w-4" />
    </button>
    <!-- Hidden file input for uploading specs -->
    <input
      bind:this={fileInput}
      type="file"
      accept=".json"
      on:change={(e) =>
        dispatch('upload', { file: ((e.target as HTMLInputElement).files ?? [null])[0] })}
      style="display: none;"
    />
  </div>

  <div class="min-h-0 w-full flex-auto overflow-y-auto px-4">
    <SpecificationListView
      specs={specs ?? []}
      {newSpecName}
      {selectedSpec}
      showNewButton={true}
      on:select={handleSelect}
      on:new={handleNew}
    />
  </div>
</div>
