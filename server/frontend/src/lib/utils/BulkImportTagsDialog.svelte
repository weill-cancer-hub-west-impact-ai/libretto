<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';
  import { faXmark } from '@fortawesome/free-solid-svg-icons';

  export let isOpen: boolean = false;
  export let allTags: string[] = [];

  const dispatch = createEventDispatcher<{
    close: void;
    import: { patientIds: string[]; tag: string };
  }>();

  let patientIdsText = '';
  let tag = '';
  let errorMessage = '';

  $: isValid = patientIdsText.trim().length > 0 && tag.trim().length > 0;

  $: parsedIds = patientIdsText
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  function handleImport() {
    if (parsedIds.length === 0) {
      errorMessage = 'Enter at least one patient ID.';
      return;
    }
    if (!tag.trim()) {
      errorMessage = 'Enter a tag name.';
      return;
    }
    dispatch('import', { patientIds: parsedIds, tag: tag.trim() });
    handleClose();
  }

  function handleClose() {
    patientIdsText = '';
    tag = '';
    errorMessage = '';
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
    aria-labelledby="bulk-import-tags-title"
    tabindex="-1"
  >
    <!-- Modal content -->
    <div class="mx-4 flex w-full max-w-lg flex-col rounded-lg bg-white py-4 shadow-xl">
      <!-- Header -->
      <div class="mx-6 mb-4 flex shrink-0 items-center justify-between">
        <h2 id="bulk-import-tags-title" class="text-lg font-bold text-gray-900">Import Tags</h2>
        <button
          on:click={handleClose}
          class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close modal"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <!-- Content -->
      <div class="min-h-0 flex-auto space-y-4 px-6">
        <!-- Patient IDs -->
        <div>
          <label
            for="bulk-patient-ids"
            class="mb-1 block text-sm font-semibold text-gray-700 uppercase"
          >
            Patient IDs <span class="text-red-500">*</span>
          </label>
          <p class="mb-2 text-xs text-gray-500">
            Enter patient IDs separated by commas or newlines.
          </p>
          <textarea
            id="bulk-patient-ids"
            bind:value={patientIdsText}
            rows="6"
            placeholder={'patient_001, patient_002'}
            class="w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm focus:border-sky-500 focus:ring-1 focus:ring-sky-500 focus:outline-none"
          ></textarea>
          {#if parsedIds.length > 0}
            <p class="mt-1 text-xs text-gray-500">
              {parsedIds.length} patient{parsedIds.length === 1 ? '' : 's'} identified
            </p>
          {/if}
        </div>

        <!-- Tag -->
        <div>
          <label for="bulk-tag" class="mb-1 block text-sm font-semibold text-gray-700 uppercase">
            Tag <span class="text-red-500">*</span>
          </label>
          <input
            id="bulk-tag"
            bind:value={tag}
            type="text"
            placeholder="Enter tag name"
            list="bulk-tag-suggestions"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-1 focus:ring-sky-500 focus:outline-none"
          />
          {#if allTags.length > 0}
            <datalist id="bulk-tag-suggestions">
              {#each allTags as existingTag}
                <option value={existingTag} />
              {/each}
            </datalist>
          {/if}
        </div>
      </div>

      <!-- Error message -->
      {#if errorMessage}
        <div class="mx-6 mt-4 shrink-0 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {errorMessage}
        </div>
      {/if}

      <!-- Actions -->
      <div class="mx-6 flex shrink-0 justify-end space-x-3 pt-4">
        <button on:click={handleClose} class="btn btn-secondary"> Cancel </button>
        <button on:click={handleImport} disabled={!isValid} class="btn btn-primary">
          Import Tags
        </button>
      </div>
    </div>
  </div>
{/if}
