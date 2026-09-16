<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';
  import {
    faSort,
    faSortUp,
    faSortDown,
    faSearch,
    faAngleLeft,
    faAngleRight,
    faTag,
    faTrash,
    faFilter,
    faAnglesLeft,
    faAnglesRight
  } from '@fortawesome/free-solid-svg-icons';
  import ActionMenuButton from './ActionMenuButton.svelte';
  import TagEditMenu from './TagEditMenu.svelte';
  import BulkImportTagsDialog from './BulkImportTagsDialog.svelte';

  // Generic item interface
  type TableItem = {
    id: string;
    name: string;
    description?: string;
    value?: string | number;
    tags?: string[];
  };

  // Props
  export let items: TableItem[] = [];
  export let nameColumnTitle: string = 'Name';
  export let valueColumnTitle: string = 'Value';
  export let fixedHeight: boolean = false;
  export let height: string = '400px';
  export let itemsPerPage: number = 10;
  export let selectedItemId: string | null = null;
  export let selectedItemIds: string[] | null = null; // if allowMultiselect
  export let allowSearch: boolean = true;
  export let allowMultiselect: boolean = false;
  export let allowSingleSelect: boolean = true;
  export let allowTags: boolean = false;
  export let allowDelete: boolean = false;
  export let filterTag: string | null = null; // Made bindable for parent control
  export let searchFunction: ((query: string, searchTarget?: string) => Promise<string[]>) | null =
    null;
  export let searchQuery: string = '';
  export let searchTargets: { name: string; value: string }[] = [];
  export let selectedSearchTarget: string = '';
  export let secondaryBackground: boolean = false;

  // Internal state
  let currentPage: number = 0;
  let bulkImportTagsOpen: boolean = false;
  export let sortBy: 'name' | 'value' | null = null;
  export let sortDirection: 'asc' | 'desc' = 'asc';
  let searchFilteredIds: string[] | null = null;
  let searchResultQuery: string = ''; // search term that was used to produce the current results
  let isSearching: boolean = false;
  let searchExpanded: boolean = false;

  const dispatch = createEventDispatcher<{
    select: { item: TableItem | null };
    tag: { items: TableItem[]; tag: string; include: boolean };
    delete: { ids: string[] };
    filterTag: { filterTag: string | null };
    bulkImportTags: { patientIds: string[]; tag: string };
  }>();

  // Check if any items have values to determine if we should show the value column
  $: hasValues = items.some(
    (item) => item.value !== undefined && item.value !== null && item.value !== ''
  );

  // Initialize selected search target with first option
  $: if (searchTargets.length > 0 && !selectedSearchTarget) {
    selectedSearchTarget = searchTargets[0].value;
  }

  // Handle external search function
  function runSearch() {
    searchFilteredIds = null;
    if (searchFunction && searchQuery) {
      isSearching = true;
      let query = searchQuery;
      searchFunction(searchQuery, selectedSearchTarget)
        .then((ids) => {
          if (query == searchQuery) {
            searchFilteredIds = ids;
            searchResultQuery = query;
          }
          isSearching = false;
        })
        .catch(() => {
          searchFilteredIds = [];
          searchResultQuery = '';
          isSearching = false;
        });
    } else if (!searchQuery) {
      searchFilteredIds = [];
      isSearching = false;
      searchResultQuery = '';
    }
  }

  // Filter items based on search query
  $: filteredItems = items.filter((item) => {
    if (filterTag != null && !item.tags?.includes(filterTag)) return false;

    // If using external search function and we have a search query
    if (searchFunction && searchQuery && searchQuery == searchResultQuery) {
      // Only show items that are in the search results (if search has completed)
      return searchFilteredIds != null ? searchFilteredIds.includes(item.id) : !isSearching;
    }

    // Default local search behavior
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    const nameMatch = item.name.toLowerCase().includes(query);
    const descriptionMatch = item.description?.toLowerCase().includes(query) || false;
    return nameMatch || descriptionMatch;
  });

  // Sort filtered items
  $: sortedItems = [...filteredItems].sort((a, b) => {
    if (!sortBy) return 0;

    let aVal: string | number;
    let bVal: string | number;

    if (sortBy === 'name') {
      aVal = a.name.toLowerCase();
      bVal = b.name.toLowerCase();
    } else {
      aVal = a.value || '';
      bVal = b.value || '';

      // Try to parse as numbers for numeric sorting
      const aNum = Number(String(aVal));
      const bNum = Number(String(bVal));
      if (!isNaN(aNum) && !isNaN(bNum)) {
        aVal = aNum;
        bVal = bNum;
      } else {
        aVal = String(aVal).toLowerCase();
        bVal = String(bVal).toLowerCase();
      }
    }

    if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  // Paginate sorted items
  $: totalPages = Math.ceil(sortedItems.length / itemsPerPage);
  $: paginatedItems = sortedItems.slice(
    currentPage * itemsPerPage,
    (currentPage + 1) * itemsPerPage
  );

  // Reset pagination when search query or sort changes
  $: (sortedItems,
    (() => {
      currentPage = 0;
    })());

  // Collect all unique tags from items
  $: allTags = [...new Set(items.flatMap((item) => item.tags || []))].sort();

  // Check if all filtered items are selected
  $: allFilteredSelected =
    allowMultiselect &&
    paginatedItems.length > 0 &&
    paginatedItems.every((item) => (selectedItemIds ?? []).includes(item.id));

  // Check if some but not all filtered items are selected
  $: someFilteredSelected =
    allowMultiselect &&
    paginatedItems.length > 0 &&
    paginatedItems.some((item) => (selectedItemIds ?? []).includes(item.id)) &&
    !allFilteredSelected;

  // remove filtered-out items from selection
  $: if (!!selectedItemIds && selectedItemIds.length > 0 && filteredItems.length > 0) {
    let filteredIDs = new Set(filteredItems.map((item) => item.id));
    selectedItemIds = selectedItemIds.filter((id) => filteredIDs.has(id));
  }
  $: if (!!selectedItemId) {
    let idx = sortedItems.findIndex((el) => el.id == selectedItemId);
    if (idx < 0) handleItemSelect(null);
  }

  // reset tags if tag no longer exists
  $: if (!!filterTag && !allTags.includes(filterTag)) {
    filterTag = null;
    dispatch('filterTag', { filterTag });
  }

  function handleSort(column: 'name' | 'value') {
    if (sortBy === column) {
      if (sortDirection == 'asc') sortDirection = 'desc';
      else if (sortDirection == 'desc') sortBy = null;
    } else {
      sortBy = column;
      sortDirection = 'asc';
    }
  }

  function handleMultiselect(item: TableItem) {
    if (!selectedItemIds) selectedItemIds = [];
    if (selectedItemIds.includes(item.id)) {
      let idx = selectedItemIds.indexOf(item.id);
      selectedItemIds = [...selectedItemIds.slice(0, idx), ...selectedItemIds.slice(idx + 1)];
    } else {
      selectedItemIds = [...selectedItemIds, item.id];
    }
  }

  function handleItemSelect(item: TableItem | null) {
    selectedItemId = item?.id ?? null;
    dispatch('select', { item });
  }

  function handleSelectAll() {
    let newItems = new Set(selectedItemIds ?? []);
    if (allFilteredSelected) {
      // Deselect all filtered items
      filteredItems.forEach((item) => newItems.delete(item.id));
    } else {
      // Select all filtered items
      filteredItems.forEach((item) => newItems.add(item.id));
    }
    selectedItemIds = Array.from(newItems);
  }

  function handleTagToggle(tag: string, include: boolean, itemsToUpdate: any[]) {
    if (itemsToUpdate.length === 0) return;

    const updatedItems = itemsToUpdate.map((item) => {
      const itemTags = item.tags || [];
      let newTags: string[];

      if (!include) {
        // Remove tag
        newTags = itemTags.filter((t: any) => t !== tag);
      } else {
        // Add tag
        newTags = [...itemTags.filter((t: any) => t !== tag), tag];
      }

      return { ...item, tags: newTags };
    });

    // Update the original items array
    const updatedItemsMap = new Map(updatedItems.map((item) => [item.id, item]));
    items = items.map((item) => updatedItemsMap.get(item.id) || item);

    dispatch('tag', { items: itemsToUpdate, tag, include });
  }

  function getSortIcon(column: 'name' | 'value', sortCol: string | null, sortDir: string) {
    if (sortCol !== column) return faSort;
    return sortDir === 'asc' ? faSortUp : faSortDown;
  }

  function goToPage(page: number) {
    currentPage = Math.max(0, Math.min(page, totalPages - 1));
  }

  function handleDelete() {
    const idsToDelete = allowMultiselect
      ? (selectedItemIds ?? [])
      : selectedItemId
        ? [selectedItemId]
        : [];

    if (idsToDelete.length > 0) {
      dispatch('delete', { ids: idsToDelete });
    }
  }
</script>

<div
  class="flex w-full flex-col {fixedHeight ? '' : 'h-full'}"
  style={height != null ? `height: ${height}` : ''}
>
  <div class="mx-4 mb-2 flex shrink-0 items-center gap-2">
    {#if searchExpanded && allowSearch}
      <!-- Expanded search bar -->
      <button
        class="btn-icon"
        title="Close search"
        on:click={() => {
          searchExpanded = false;
          searchQuery = '';
        }}
      >
        <Fa icon={faAngleLeft} />
      </button>
      {#if searchTargets.length > 0 && searchFunction}
        <!-- Search target dropdown -->
        <select bind:value={selectedSearchTarget} class="flat-select" on:change={runSearch}>
          {#each searchTargets as target}
            <option value={target.value}>{target.name}</option>
          {/each}
        </select>
      {/if}
      <div class="relative flex-grow">
        <Fa
          icon={faSearch}
          class="absolute top-1/2 left-3 -translate-y-1/2 transform text-xs text-gray-400"
        />
        <input
          type="text"
          bind:value={searchQuery}
          placeholder={searchFunction ? 'Search and press Enter' : 'Search...'}
          class="w-full rounded-md border border-gray-300 py-1 pr-2 pl-8 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500 {isSearching
            ? 'opacity-50'
            : ''}"
          disabled={isSearching}
          on:change={searchFunction ? runSearch : null}
        />
        {#if isSearching}
          <div class="absolute top-1/2 right-3 -translate-y-1/2 transform">
            <div
              class="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-sky-500"
            ></div>
          </div>
        {/if}
      </div>
    {:else}
      <!-- Normal top row with buttons -->
      <div class="flex items-center gap-2">
        <!-- Search button -->
        {#if allowSearch}
          <button class="btn-icon" title="Search" on:click={() => (searchExpanded = true)}>
            <Fa icon={faSearch} />
          </button>
        {/if}
        <!-- View Options Menu Slot -->
        <slot name="viewOptionsMenu" />
      </div>
      <div class="flex-auto"></div>
    {/if}
    <div class="flex items-center gap-2">
      {#if allowDelete && (selectedItemIds ?? []).length > 0}
        <button
          class="btn-small btn-danger inline-flex items-center gap-1"
          title="Delete selected items"
          on:click={handleDelete}
        >
          <Fa icon={faTrash} class="mr-2 inline h-3 w-3" />
          Delete
        </button>
      {/if}
      {#if allowTags}
        {#if (selectedItemIds ?? []).length > 0}
          {@const allItems =
            (selectedItemIds ?? []).length > 0
              ? filteredItems.filter((item) => selectedItemIds?.includes(item.id))
              : selectedItemId != null
                ? [filteredItems.find((item) => item.id == selectedItemId)].filter((i) => !!i)
                : []}
          <ActionMenuButton
            buttonClass="inline-flex cursor-pointer items-center gap-1 btn-small btn-secondary"
            buttonTitle="Tag selected items"
            menuWidth={200}
            align="right"
          >
            {#snippet buttonContent()}
              <Fa icon={faTag} class="mr-2 inline h-3 w-3" />
              Add/Remove Tags
            {/snippet}
            {#snippet options(dismiss: () => void)}
              <TagEditMenu items={allItems} {allTags} onTagToggle={handleTagToggle} />
            {/snippet}
          </ActionMenuButton>
        {:else}
          <button
            class="btn-small btn-secondary inline-flex cursor-pointer items-center gap-1"
            title="Import tags for a list of patients"
            on:click={() => (bulkImportTagsOpen = true)}
          >
            <Fa icon={faTag} class="mr-2 inline h-3 w-3" />
            Import Tags...
          </button>
        {/if}
      {/if}
    </div>
  </div>

  <!-- Table Container -->
  <div class="flex-grow overflow-auto rounded" class:min-h-0={fixedHeight}>
    <div class="relative">
      <!-- Sticky Header -->
      <div
        class="sticky top-0 z-10 mx-4 border-b border-stone-300/50 {secondaryBackground
          ? 'bg-stone-50'
          : 'bg-white'}"
      >
        <div class="flex min-h-8">
          <!-- Checkbox Column Header (only if multiselect is enabled) -->
          {#if allowMultiselect}
            <div class="flex w-10 items-center justify-center px-2 py-3">
              <input
                type="checkbox"
                checked={allFilteredSelected}
                indeterminate={someFilteredSelected}
                on:click|stopPropagation={() => {}}
                on:change={handleSelectAll}
                class="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
              />
            </div>
          {/if}

          <!-- Name Column Header -->
          <button
            class="flex flex-grow items-center justify-between px-4 py-3 text-left text-sm font-medium text-gray-800 hover:opacity-50 focus:ring-2 focus:ring-sky-500 focus:outline-none focus:ring-inset"
            on:click={() => handleSort('name')}
          >
            <span>{nameColumnTitle}</span>
            <Fa
              icon={getSortIcon('name', sortBy, sortDirection)}
              class="ml-2 text-xs text-gray-500"
            />
          </button>

          <!-- Value Column Header (only if items have values) -->
          {#if hasValues}
            <button
              class="flex min-w-32 items-center justify-between px-4 py-3 text-right text-sm font-medium text-gray-800 hover:opacity-50 focus:ring-2 focus:ring-sky-500 focus:outline-none focus:ring-inset"
              on:click={() => handleSort('value')}
            >
              <span>{valueColumnTitle}</span>
              <Fa
                icon={getSortIcon('value', sortBy, sortDirection)}
                class="ml-2 text-xs text-gray-500"
              />
            </button>
          {/if}
        </div>
      </div>

      <!-- Table Body -->
      <div>
        {#each paginatedItems as item (item.id)}
          <div
            class="mx-4 box-border flex items-center rounded-md {selectedItemId === item.id
              ? 'border-2 border-stone-500'
              : 'hover:bg-stone-100'}"
          >
            <!-- Checkbox Column (only if multiselect is enabled) -->
            {#if allowMultiselect}
              <div class="flex w-10 items-center justify-center px-2 py-3">
                <input
                  type="checkbox"
                  checked={(selectedItemIds ?? []).includes(item.id)}
                  on:click|stopPropagation={() => {}}
                  on:change={() => handleMultiselect(item)}
                  class="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
                />
              </div>
            {/if}

            <!-- Name and Description Column -->
            <div
              class="min-w-0 flex-grow px-4 py-3 {allowMultiselect ? '' : 'cursor-pointer'}"
              class:cursor-pointer={!allowMultiselect}
              on:click={allowSingleSelect
                ? () => handleItemSelect(item)
                : allowMultiselect
                  ? () => handleMultiselect(item)
                  : undefined}
              role="button"
              tabindex={0}
              on:keydown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  if (allowSingleSelect) handleItemSelect(item);
                  else if (allowMultiselect) handleMultiselect(item);
                }
              }}
            >
              <div class="truncate font-medium text-gray-900">
                {item.name}
              </div>
              {#if item.description}
                <div class="truncate text-sm text-gray-500">
                  {item.description}
                </div>
              {/if}
              {#if (item.tags?.length ?? 0) > 0}
                <div class="mt-1 text-xs font-semibold">
                  {#each item.tags as tag, i}
                    <span
                      class="mr-1 mb-1 inline-block rounded border-sky-200/50 bg-sky-100 px-1.5 py-0.5 whitespace-nowrap text-sky-800"
                      >{tag}</span
                    >
                  {/each}
                </div>
              {/if}
            </div>

            <!-- Value Column (only if items have values) -->
            {#if hasValues}
              <div
                class="min-w-32 px-4 py-3 text-right text-sm text-gray-700 {allowMultiselect
                  ? ''
                  : 'cursor-pointer'}"
                class:cursor-pointer={!allowMultiselect}
                on:click={allowSingleSelect
                  ? () => handleItemSelect(item)
                  : allowMultiselect
                    ? () => handleMultiselect(item)
                    : undefined}
                role="button"
                tabindex={0}
                on:keydown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    if (allowSingleSelect) handleItemSelect(item);
                    else if (allowMultiselect) handleMultiselect(item);
                  }
                }}
              >
                {item.value || ''}
              </div>
            {/if}
          </div>
        {/each}

        <!-- Empty State -->
        {#if paginatedItems.length === 0}
          <div class="flex items-center justify-center py-12 text-gray-500">
            {#if searchQuery}
              {#if searchResultQuery != searchQuery}
                Press Enter to search.
              {:else}
                No items match your search query.
              {/if}
            {:else}
              No items to display.
            {/if}
          </div>
        {/if}
      </div>
    </div>
  </div>

  <!-- Pagination -->
  {#if totalPages > 1}
    <div class="mx-4 mt-2 flex shrink-0 items-center justify-center">
      <button
        class="cursor-pointer px-2 py-1 hover:opacity-50 disabled:opacity-30"
        disabled={currentPage === 0}
        on:click={() => goToPage(0)}><Fa icon={faAnglesLeft} title="First page" /></button
      >
      <button
        class="cursor-pointer px-2 py-1 hover:opacity-50 disabled:opacity-30"
        disabled={currentPage === 0}
        on:click={() => goToPage(currentPage - 1)}
        ><Fa icon={faAngleLeft} title="Previous page" /></button
      >
      <div class="text-sm whitespace-nowrap text-gray-700">
        {currentPage * itemsPerPage + 1} to {Math.min(
          (currentPage + 1) * itemsPerPage,
          sortedItems.length
        )} of {sortedItems.length}
      </div>
      <button
        class="cursor-pointer px-2 py-1 hover:opacity-50 disabled:opacity-30"
        disabled={currentPage === totalPages - 1}
        on:click={() => goToPage(currentPage + 1)}
        title="Next page"><Fa icon={faAngleRight} /></button
      >
      <button
        class="cursor-pointer px-2 py-1 hover:opacity-50 disabled:opacity-30"
        disabled={currentPage === totalPages - 1}
        on:click={() => goToPage(totalPages - 1)}
        title="Last page"><Fa icon={faAnglesRight} /></button
      >
    </div>
  {/if}
</div>

{#if allowTags}
  <BulkImportTagsDialog
    isOpen={bulkImportTagsOpen}
    {allTags}
    on:close={() => (bulkImportTagsOpen = false)}
    on:import={(e) =>
      dispatch('tag', {
        items: e.detail.patientIds
          .map((id) => items.find((i) => i.id == id))
          .filter((item) => !!item),
        tag: e.detail.tag,
        include: true
      })}
  />
{/if}
