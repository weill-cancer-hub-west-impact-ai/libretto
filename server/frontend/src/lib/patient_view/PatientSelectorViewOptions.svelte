<script lang="ts">
  import {
    faChevronDown,
    faChevronUp,
    faPlus,
    faTrash,
    faXmark
  } from '@fortawesome/free-solid-svg-icons';
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';

  const dispatch = createEventDispatcher();

  export let viewTypes: { name: string; value: string }[] = [
    { name: 'Number of Notes', value: 'note_count' },
    { name: 'Number of Extractions', value: 'extraction_count' },
    { name: 'Earliest Note Date', value: 'earliest_date' },
    { name: 'Latest Note Date', value: 'latest_date' },
    { name: 'Patient Metadata Field', value: 'metadata_field' }
  ];
  export let selectedViewType: string = viewTypes[0]?.value || '';
  export let metadataFieldName: string = '';
  export let metadataFields: { name: string; type: string }[] = [];
  export let filterTag: string | null = null;
  export let allTags: string[] = [];
  export let extractionStatusFilter: string = 'all';
  export let specForExtractionStatus: string | undefined = undefined;
  export let showExtractionFilter: boolean = false;

  // Advanced filters
  export let showAdvancedFilters: boolean = false;
  export let extractionSpecs: any = {};
  export let advancedFiltersExpanded: boolean = false;
  export let metadataFilters: any[] = [];
  export let extractionFilters: any[] = [];

  function handleViewTypeChange(newType: string) {
    selectedViewType = newType;
    dispatch('viewTypeChange', { viewType: newType });
  }

  function handleMetadataFieldChange(field: string) {
    metadataFieldName = field;
    dispatch('metadataFieldChange', { field });
  }

  function handleTagFilterChange(tag: string | null) {
    filterTag = tag;
    dispatch('tagFilterChange', { tag });
  }

  function handleExtractionStatusFilterChange(status: string) {
    extractionStatusFilter = status;
    dispatch('extractionStatusFilterChange', { status });
  }

  function toggleAdvancedFilters() {
    advancedFiltersExpanded = !advancedFiltersExpanded;
    dispatch('advancedFiltersToggle', { expanded: advancedFiltersExpanded });
  }

  function addMetadataFilter() {
    const newFilter = {
      field: '',
      operator: 'eq',
      value: ''
    };
    metadataFilters = [...metadataFilters, newFilter];
    dispatch('metadataFiltersChange', { filters: metadataFilters });
  }

  function removeMetadataFilter(index: number) {
    metadataFilters = metadataFilters.filter((_, i) => i !== index);
    dispatch('metadataFiltersChange', { filters: metadataFilters });
  }

  function updateMetadataFilter(index: number, field: string, value: any) {
    metadataFilters[index] = { ...metadataFilters[index], [field]: value };
    console.log('updated filters:', metadataFilters);
    dispatch('metadataFiltersChange', { filters: metadataFilters });
  }

  function addExtractionFilter() {
    const newFilter = {
      spec_id: '',
      extraction_class: '',
      attribute: '',
      operator: 'exists',
      value: ''
    };
    extractionFilters = [...extractionFilters, newFilter];
    dispatch('extractionFiltersChange', { filters: extractionFilters });
  }

  function removeExtractionFilter(index: number) {
    extractionFilters = extractionFilters.filter((_, i) => i !== index);
    dispatch('extractionFiltersChange', { filters: extractionFilters });
  }

  function updateExtractionFilter(index: number, field: string, value: any) {
    extractionFilters[index] = { ...extractionFilters[index], [field]: value };
    dispatch('extractionFiltersChange', { filters: extractionFilters });
  }

  function clearAllFilters() {
    metadataFilters = [];
    extractionFilters = [];
    dispatch('metadataFiltersChange', { filters: metadataFilters });
    dispatch('extractionFiltersChange', { filters: extractionFilters });
  }

  // Reactive statements
  $: availableSpecIds = Object.keys(extractionSpecs);
</script>

<div class="pointer-events-auto max-h-96 overflow-y-auto bg-white">
  <!-- View Type Section -->
  <div class="border-b border-gray-100 px-4 py-3">
    <div class="mb-2 text-sm font-medium text-gray-700">Show in Patient List</div>
    <div class="space-y-1">
      {#each viewTypes as viewType}
        <label class="flex cursor-pointer items-center space-x-2">
          <input
            type="radio"
            checked={selectedViewType === viewType.value}
            value={viewType.value}
            class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            on:change={() => handleViewTypeChange(viewType.value)}
          />
          <span class="text-sm text-gray-900">{viewType.name}</span>
        </label>
      {/each}

      <!-- Metadata field dropdown (shown when metadata_field is selected) -->
      {#if selectedViewType === 'metadata_field'}
        <div class="mt-2 ml-6">
          {#if metadataFields.length > 0}
            <select
              bind:value={metadataFieldName}
              class="flat-select w-full"
              on:change={() => handleMetadataFieldChange(metadataFieldName)}
            >
              <option value="" disabled selected={metadataFieldName === ''}>Select field...</option>
              {#each metadataFields as field}
                <option value={field.name}>{field.name}</option>
              {/each}
            </select>
          {:else}
            <div class="text-xs text-gray-500 italic">No metadata fields available</div>
          {/if}
        </div>
      {/if}
    </div>
  </div>

  <!-- Tag Filter Section -->
  {#if allTags.length > 0}
    <div class="border-b border-gray-100 px-4 py-3">
      <div class="mb-2 text-sm font-medium text-gray-700">Filter by Tag</div>
      <div class="space-y-1">
        <!-- All tags option -->
        <label class="flex cursor-pointer items-center space-x-2">
          <input
            type="radio"
            checked={filterTag === null}
            value="All"
            class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            on:change={() => handleTagFilterChange(null)}
          />
          <span class="text-sm text-gray-900">All</span>
        </label>

        <!-- Individual tags -->
        {#each allTags as tag}
          <label class="flex cursor-pointer items-center space-x-2">
            <input
              type="radio"
              checked={filterTag === tag}
              value={tag}
              class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
              on:change={() => handleTagFilterChange(tag)}
            />
            <span class="text-sm text-gray-900">{tag}</span>
          </label>
        {/each}
      </div>
    </div>
  {/if}

  {#if showExtractionFilter}
    <!-- Extraction Status Filter Section -->
    <div class="border-b border-gray-100 px-4 py-3">
      <div class="mb-2 text-sm font-medium text-gray-700">
        Filter by Extraction Spec
        {#if !!specForExtractionStatus}<br />
          <span class="text-xs font-normal">{specForExtractionStatus}</span>{/if}
      </div>
      <div class="space-y-1">
        <label class="flex cursor-pointer items-center space-x-2">
          <input
            type="radio"
            checked={extractionStatusFilter === 'all'}
            value="all"
            class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            on:change={() => handleExtractionStatusFilterChange('all')}
          />
          <span class="text-sm text-gray-900">All</span>
        </label>
        <label class="flex cursor-pointer items-center space-x-2">
          <input
            type="radio"
            checked={extractionStatusFilter === 'run'}
            value="run"
            class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            on:change={() => handleExtractionStatusFilterChange('run')}
          />
          <span class="text-sm text-gray-900">Extraction Run</span>
        </label>
        <label class="flex cursor-pointer items-center space-x-2">
          <input
            type="radio"
            checked={extractionStatusFilter === 'not_run'}
            value="not_run"
            class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
            on:change={() => handleExtractionStatusFilterChange('not_run')}
          />
          <span class="text-sm text-gray-900">Extraction Not Run</span>
        </label>
      </div>
    </div>
  {/if}

  <!-- Advanced Filters Section -->
  {#if showAdvancedFilters}
    <div class="border-b border-gray-100 py-3">
      <div class="mx-2 mb-2 flex items-center gap-2">
        <button
          class="block flex-auto rounded-md bg-transparent px-2 py-1 text-left text-sm font-medium text-gray-700 hover:bg-stone-100"
          on:click={toggleAdvancedFilters}
        >
          <Fa icon={advancedFiltersExpanded ? faChevronUp : faChevronDown} class="mr-2 inline" />
          Advanced Filters
        </button>
        {#if metadataFilters.length > 0 || extractionFilters.length > 0}
          <button
            type="button"
            class="btn-icon-small mr-2"
            on:click|stopPropagation={clearAllFilters}
          >
            <Fa icon={faTrash} />
          </button>
        {/if}
      </div>

      {#if advancedFiltersExpanded}
        <!-- Metadata Filters -->
        <div class="mb-4 px-4">
          <div class="mb-2 flex items-center justify-between">
            <span class="text-sm font-medium text-gray-600">Metadata Filters</span>
            <button type="button" class="btn-icon-small" on:click={addMetadataFilter}>
              <Fa icon={faPlus} />
            </button>
          </div>

          {#if metadataFilters.length > 0}
            {@const currentMetadataField = metadataFields.find((m) => m.name == metadataFieldName)}
            <div class="space-y-2">
              {#each metadataFilters as filter, index}
                <div class="rounded border border-stone-400 bg-stone-100 p-2">
                  <div class="space-y-2">
                    <!-- Field Input -->
                    <div class="flex w-full items-center gap-2">
                      <select
                        bind:value={filter.field}
                        class="flat-select flex-auto"
                        on:change={() => updateMetadataFilter(index, 'field', filter.field)}
                      >
                        <option value="" disabled selected={metadataFieldName === ''}
                          >Select field...</option
                        >
                        {#each metadataFields as field}
                          <option value={field.name}>{field.name}</option>
                        {/each}
                      </select>
                      <!-- Remove Button -->
                      <button
                        type="button"
                        class="btn-icon-small"
                        on:click={() => removeMetadataFilter(index)}
                      >
                        <Fa icon={faXmark} />
                      </button>
                    </div>

                    <select
                      bind:value={filter.operator}
                      on:change={() => updateMetadataFilter(index, 'operator', filter.operator)}
                      class="flat-select w-full"
                    >
                      <option value="eq">Equals</option>
                      {#if currentMetadataField?.type == 'string'}
                        <option value="contains">Contains</option>
                      {/if}
                      {#if currentMetadataField?.type == 'number'}
                        <option value="lt">Less Than</option>
                        <option value="gt">Greater Than</option>
                        <option value="lte">≤</option>
                        <option value="gte">≥</option>
                      {/if}
                      <option value="exists">Exists</option>
                    </select>

                    {#if filter.operator === 'exists'}
                      <input
                        type="text"
                        value="(field exists)"
                        disabled
                        class="w-full rounded border border-gray-300 bg-gray-100 px-2 py-1 text-xs text-gray-500"
                      />
                    {:else if currentMetadataField?.type == 'boolean'}
                      <div class="flex w-full gap-2">
                        <button
                          type="button"
                          class="flex-1 rounded px-2 py-1 text-xs transition-all duration-150 {filter.operator ===
                          'exists'
                            ? 'bg-stone-700 font-semibold text-white shadow-sm'
                            : 'text-stone-600 hover:bg-stone-300'}"
                          on:click={() => updateMetadataFilter(index, 'value', false)}
                        >
                          False
                        </button>
                        <button
                          type="button"
                          class="flex-1 rounded px-2 py-1 text-xs transition-all duration-150 {filter.operator !==
                          'exists'
                            ? 'bg-stone-700 font-semibold text-white shadow-sm'
                            : 'text-stone-600 hover:bg-stone-300'}"
                          on:click={() => updateMetadataFilter(index, 'value', true)}
                        >
                          True
                        </button>
                      </div>
                    {:else}
                      <input
                        type="text"
                        placeholder="Value"
                        bind:value={filter.value}
                        on:input={() => updateMetadataFilter(index, 'value', filter.value)}
                        class="w-full rounded border border-gray-300 bg-white px-2 py-1 text-xs"
                      />
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Extraction Filters -->
        <div class="mb-4 px-4">
          <div class="mb-2 flex items-center justify-between">
            <span class="text-sm font-medium text-gray-600">Extraction Filters</span>
            <button type="button" class="btn-icon-small" on:click={addExtractionFilter}>
              <Fa icon={faPlus} />
            </button>
          </div>

          {#if extractionFilters.length > 0}
            <div class="w-full space-y-2">
              {#each extractionFilters as filter, index}
                <div class="w-full rounded border border-stone-400 bg-stone-100 p-2">
                  <div class="mb-2 w-full space-y-2">
                    <!-- Spec Selection -->
                    <div class="flex w-full items-center gap-2">
                      <select
                        bind:value={filter.spec_id}
                        on:change={() => updateExtractionFilter(index, 'spec_id', filter.spec_id)}
                        class="flat-select w-0 flex-auto shrink"
                      >
                        <option value="">Select Spec...</option>
                        {#each availableSpecIds as specId}
                          <option value={specId}>{extractionSpecs[specId]?.name || specId}</option>
                        {/each}
                      </select>
                      <button
                        type="button"
                        class="btn-icon-small"
                        on:click={() => removeExtractionFilter(index)}
                      >
                        <Fa icon={faXmark} />
                      </button>
                    </div>

                    <!-- Class Selection -->
                    <select
                      bind:value={filter.extraction_class}
                      on:change={() =>
                        updateExtractionFilter(index, 'extraction_class', filter.extraction_class)}
                      class="flat-select w-full"
                      disabled={!filter.spec_id}
                    >
                      <option value="">Select Class...</option>
                      {#if filter.spec_id && extractionSpecs[filter.spec_id]?.classes}
                        {#each Object.keys(extractionSpecs[filter.spec_id].classes) as className}
                          <option value={className}>{className}</option>
                        {/each}
                      {/if}
                    </select>

                    <!-- Filter Mode Segment Control -->
                    <div class="mb-2 flex w-full gap-2">
                      <button
                        type="button"
                        class="flex-1 rounded px-3 py-1 text-sm transition-all duration-150 {filter.operator ===
                        'exists'
                          ? 'bg-stone-700 font-semibold text-white shadow-sm'
                          : 'text-stone-600 hover:bg-stone-300'}"
                        on:click={() => updateExtractionFilter(index, 'operator', 'exists')}
                      >
                        Class Exists
                      </button>
                      <button
                        type="button"
                        class="flex-1 rounded px-3 py-1 text-sm transition-all duration-150 {filter.operator !==
                        'exists'
                          ? 'bg-stone-700 font-semibold text-white shadow-sm'
                          : 'text-stone-600 hover:bg-stone-300'}"
                        on:click={() => {
                          if (filter.operator === 'exists') {
                            updateExtractionFilter(index, 'operator', 'eq');
                          }
                        }}
                      >
                        Attribute Value
                      </button>
                    </div>

                    {#if filter.operator !== 'exists'}
                      <select
                        bind:value={filter.attribute}
                        on:change={() =>
                          updateExtractionFilter(index, 'attribute', filter.attribute)}
                        class="flat-select w-full"
                        disabled={!filter.extraction_class}
                      >
                        <option value="">Select Attribute...</option>
                        {#if filter.spec_id && filter.extraction_class && extractionSpecs[filter.spec_id]?.classes[filter.extraction_class]?.attributes}
                          {#each extractionSpecs[filter.spec_id].classes[filter.extraction_class].attributes as attr}
                            <option value={attr}>{attr}</option>
                          {/each}
                        {/if}
                      </select>
                      <select
                        bind:value={filter.operator}
                        on:change={() => updateExtractionFilter(index, 'operator', filter.operator)}
                        class="flat-select w-full"
                      >
                        <option value="eq">Equals</option>
                        <option value="contains">Contains</option>
                        <option value="lt">Less Than</option>
                        <option value="gt">Greater Than</option>
                        <option value="lte">≤</option>
                        <option value="gte">≥</option>
                      </select>

                      <input
                        type="text"
                        placeholder="Value"
                        bind:value={filter.value}
                        on:input={() => updateExtractionFilter(index, 'value', filter.value)}
                        class="w-full rounded border border-gray-300 bg-white px-2 py-1 text-xs"
                      />
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>
