<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  export let selectedFilter: { type?: string; feedback?: string };
  export let selectedSort: string;
  export let availableClasses: string[];
  export let isNoteView: boolean; // true when viewing a specific note, false for patient-level view

  function handleTypeFilterChange(newType: string) {
    selectedFilter = { ...selectedFilter, type: newType === 'All' ? undefined : newType };
  }

  function handleFeedbackFilterChange(newFeedback: string) {
    selectedFilter = {
      ...selectedFilter,
      feedback: newFeedback === 'All' ? undefined : newFeedback
    };
  }

  function handleSortChange(newSort: string) {
    selectedSort = newSort;
  }
</script>

<div class="bg-white">
  <!-- Filter Section -->
  <div class="border-b border-gray-100 px-4 py-3">
    <div class="mb-2 text-sm font-medium text-gray-700">Filter Extraction/Response Types</div>
    <div class="space-y-1">
      <!-- All option -->
      <label class="flex cursor-pointer items-center space-x-2">
        <input
          type="radio"
          checked={!selectedFilter.type}
          value="All"
          class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          on:change={() => handleTypeFilterChange('All')}
        />
        <span class="text-sm text-gray-900">All</span>
      </label>

      <!-- Available classes -->
      {#each availableClasses as className}
        <label class="flex cursor-pointer items-center space-x-2">
          <input
            type="radio"
            checked={selectedFilter.type === className}
            value={className}
            class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            on:change={() => handleTypeFilterChange(className)}
          />
          <span class="text-sm text-gray-900">{className}</span>
        </label>
      {/each}
    </div>
  </div>

  <!-- Feedback Filter Section -->
  <div class="border-b border-gray-100 px-4 py-3">
    <div class="mb-2 text-sm font-medium text-gray-700">Filter by Feedback</div>
    <div class="space-y-1">
      <!-- All feedback option -->
      <label class="flex cursor-pointer items-center space-x-2">
        <input
          type="radio"
          checked={!selectedFilter.feedback}
          value="All"
          class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          on:change={() => handleFeedbackFilterChange('All')}
        />
        <span class="text-sm text-gray-900">All</span>
      </label>

      <!-- Reviewed option -->
      <label class="flex cursor-pointer items-center space-x-2">
        <input
          type="radio"
          checked={selectedFilter.feedback === 'Reviewed'}
          value="Reviewed"
          class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          on:change={() => handleFeedbackFilterChange('Reviewed')}
        />
        <span class="text-sm text-gray-900">Reviewed</span>
      </label>

      <!-- Unreviewed option -->
      <label class="flex cursor-pointer items-center space-x-2">
        <input
          type="radio"
          checked={selectedFilter.feedback === 'Unreviewed'}
          value="Unreviewed"
          class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
          on:change={() => handleFeedbackFilterChange('Unreviewed')}
        />
        <span class="text-sm text-gray-900">Unreviewed</span>
      </label>
    </div>
  </div>

  <!-- Sort Section -->
  <div>
    <div class="px-4 py-3">
      <div class="mb-2 text-sm font-medium text-gray-700">Sort By</div>
      <div class="space-y-1">
        <!-- Text Order (only in note view) -->
        {#if isNoteView}
          <label class="flex cursor-pointer items-center space-x-2">
            <input
              type="radio"
              bind:group={selectedSort}
              value="Text Order"
              class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
              on:change={() => handleSortChange('Text Order')}
            />
            <span class="text-sm text-gray-900">Text Order</span>
          </label>
        {:else}
          <!-- Note Order (only in patient view) -->
          <label class="flex cursor-pointer items-center space-x-2">
            <input
              type="radio"
              bind:group={selectedSort}
              value="Note Order"
              class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
              on:change={() => handleSortChange('Note Order')}
            />
            <span class="text-sm text-gray-900">Note Order</span>
          </label>
        {/if}

        <!-- Type option -->
        <label class="flex cursor-pointer items-center space-x-2">
          <input
            type="radio"
            bind:group={selectedSort}
            value="Type"
            class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            on:change={() => handleSortChange('Type')}
          />
          <span class="text-sm text-gray-900">Type</span>
        </label>
      </div>
    </div>
  </div>
</div>
