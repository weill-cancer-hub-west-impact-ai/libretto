<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  export let disabled: boolean = false;

  // Download options state
  let selectedScope: 'patient' | 'all' = 'all';
  let selectedFormat: 'csv' | 'json' = 'csv';

  function handleDownload() {
    const patientId = selectedScope === 'patient' ? 'current' : null;
    const csv = selectedFormat === 'csv';

    dispatch('download', {
      patientId,
      csv
    });
  }
</script>

<div class="pointer-events-auto bg-white">
  <!-- Patient Scope Section -->
  <div class="border-b border-gray-100 px-4 py-3">
    <div class="mb-2 text-xs text-gray-500">Download model outputs and feedback for:</div>
    <div class="space-y-1">
      <label class="flex cursor-pointer items-center space-x-2">
        <input
          type="radio"
          bind:group={selectedScope}
          value="all"
          class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          {disabled}
        />
        <span class="text-sm text-gray-900">All Patients</span>
      </label>
      <label class="flex cursor-pointer items-center space-x-2">
        <input
          type="radio"
          bind:group={selectedScope}
          value="patient"
          class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          {disabled}
        />
        <span class="text-sm text-gray-900">This Patient</span>
      </label>
    </div>
  </div>

  <!-- Format Section -->
  <div class="border-b border-gray-100 px-4 py-3">
    <div class="mb-2 text-sm font-medium text-gray-700">Format</div>
    <div class="space-y-1">
      <label class="flex cursor-pointer items-center space-x-2">
        <input
          type="radio"
          bind:group={selectedFormat}
          value="csv"
          class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          {disabled}
        />
        <span class="text-sm text-gray-900">CSV</span>
      </label>

      <label class="flex cursor-pointer items-center space-x-2">
        <input
          type="radio"
          bind:group={selectedFormat}
          value="json"
          class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          {disabled}
        />
        <span class="text-sm text-gray-900">JSON</span>
      </label>
    </div>
  </div>

  <!-- Download Button -->
  <div class="px-4 py-3">
    <button class="btn btn-primary w-full" {disabled} on:click={handleDownload}> Download </button>
  </div>
</div>
