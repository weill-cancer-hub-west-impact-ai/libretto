<svelte:options accessors />

<script lang="ts">
  import { createEventDispatcher, getContext, onMount } from 'svelte';
  import type { Patient, Note, ExtractionSpec } from '../extraction_types';
  import Fa from 'svelte-fa';
  import { faXmark, faUpload, faDownload, faFilter } from '@fortawesome/free-solid-svg-icons';
  import TableView from '$lib/utils/TableView.svelte';
  import ActionMenuButton from '$lib/utils/ActionMenuButton.svelte';
  import PatientSelectorViewOptions from './PatientSelectorViewOptions.svelte';
  import {
    loadPatientViewState,
    savePatientViewState,
    saveActiveTag
  } from '$lib/stores/viewOptions';
  import { goto } from '$app/navigation';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { browser } from '$app/environment';
  import { areObjectsEqual } from '$lib/utils/utils';
  import { loadPatients, patients as globalPatients, projectID } from '$lib/stores/data';
  import LoadingView from '$lib/utils/LoadingView.svelte';

  export let showHeader: boolean = true;
  export let title: string = 'Patients';
  export let allowMultiSelect: boolean = true;
  export let multiSelectOnly: boolean = false; // disable single select
  export let defaultSelectAll: boolean = false;
  export let secondaryBackground: boolean = false;

  let patients: Patient[] = $globalPatients ?? [];
  export let selectedSpec: ExtractionSpec | null = null;
  export let needsPatientRefresh: boolean = false;
  let loadingPatients: boolean = false;

  let oldSpec: ExtractionSpec | null = null;
  let fetchedPatients: boolean = false;
  $: if (!selectedSpec) patients = $globalPatients ?? [];
  $: if (
    (browser && !!selectedSpec && !areObjectsEqual(oldSpec, selectedSpec)) ||
    (patients.length == 0 && !fetchedPatients) ||
    needsPatientRefresh
  ) {
    loadingPatients = true;
    oldSpec = selectedSpec;
    syncSpecPatients();
    needsPatientRefresh = false;
  }

  export function syncSpecPatients() {
    if (!selectedSpec) return;
    loadPatients(selectedSpec?.id ?? null).then((p) => {
      patients = p ?? [];
      loadingPatients = false;
      fetchedPatients = true;
    });
  }

  $: if (patients.length > 0) setDefaultPatientIDs();

  function setDefaultPatientIDs() {
    if (defaultSelectAll && selectedPatientIds.length == 0)
      selectedPatientIds = patients.map((p) => p.id);
  }

  let mounted: boolean = false;

  onMount(() => (mounted = true));

  const dispatch = createEventDispatcher();

  export let selectedPatient: Patient | null = null;
  export let canEditPatients: boolean = false;
  export let allowClose: boolean = true;
  export let editable: boolean = true;
  export let selectedPatientIds: string[] = [];

  let filterTag: string | null = null;
  let extractionStatusFilter: string = 'all';
  let selectedViewType: string = 'note_count';
  let metadataFieldName: string = '';
  let sortDirection: 'asc' | 'desc' = 'desc';
  let sortField: 'name' | 'value' | null = null;
  let loadedPatientViewState: boolean = false;

  let searchQuery: string = '';
  let searchTarget: string = '';

  // Advanced filters for patient list
  let filterExtractionSpecs: any = {};
  let metadataFilters: any[] = [];
  let extractionFilters: any[] = [];

  // Define view types for patient selector
  $: patientViewTypes = [
    { name: 'Number of Notes', value: 'note_count' },
    ...(!!selectedSpec ? [{ name: 'Number of Extractions', value: 'extraction_count' }] : []),
    { name: 'Earliest Note Date', value: 'earliest_date' },
    { name: 'Latest Note Date', value: 'latest_date' },
    { name: 'Patient Metadata Field', value: 'metadata_field' }
  ];

  $: if (!selectedSpec) extractionStatusFilter = 'all';

  // Define search targets for patient search
  const searchTargets = [
    { name: 'All Fields', value: 'all' },
    { name: 'Patient ID', value: 'id' },
    { name: 'Note Text', value: 'text' },
    { name: 'Metadata', value: 'metadata' }
  ];

  // Helper function to extract metadata field names with string or number values
  function getMetadataFields(patients: Patient[]): { name: string; type: string }[] {
    let fieldNames: { name: string; type: string }[] = [];

    // Get the first patient with metadata to check field types
    for (const patient of patients) {
      if (patient.metadata && typeof patient.metadata === 'object') {
        Object.entries(patient.metadata).forEach(([key, value]) => {
          if (
            typeof value === 'string' ||
            typeof value === 'number' ||
            typeof value === 'boolean'
          ) {
            fieldNames.push({ name: key, type: typeof value });
          }
        });
      }
      // Only check the first patient to avoid processing all patients
      if (fieldNames.length > 0) break;
    }

    return Array.from(fieldNames).sort((a, b) => a.name.localeCompare(b.name));
  }

  // Search function for patient search
  async function searchPatients(searchQuery: string, searchTarget?: string): Promise<string[]> {
    try {
      const params = new URLSearchParams({
        full: '1',
        search: searchQuery,
        metadata_filters: JSON.stringify(metadataFilters),
        extraction_filters: JSON.stringify(extractionFilters)
      });

      // Add search target parameter if provided
      if (searchTarget) {
        params.set('searchTarget', searchTarget);
      }

      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/patients?${params.toString()}`
      );
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const searchResults: Patient[] = await response.json();
      return searchResults.map((patient) => patient.id);
    } catch (error) {
      console.error('Error searching patients:', error);
      return [];
    }
  }

  let filteredPatientIDs: Set<string> | null = null;

  async function applyPatientFilters() {
    if (!advancedFiltersActive) {
      filteredPatientIDs = null;
      return;
    }

    try {
      const params = new URLSearchParams({
        metadata_filters: JSON.stringify(metadataFilters),
        extraction_filters: JSON.stringify(extractionFilters)
      });

      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/patients?${params.toString()}`
      );
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const searchResults: Patient[] = await response.json();
      filteredPatientIDs = new Set(searchResults.map((patient) => patient.id));
    } catch (error) {
      console.error('Error filtering patients:', error);
      filteredPatientIDs = null;
    }
  }

  // Load patient view state from local storage when component mounts
  $: if (mounted && filterTag === null) {
    const patientViewState = loadPatientViewState();
    filterTag = patientViewState.activeTag;
    selectedViewType = patientViewState.viewType;
    searchTarget = patientViewState.searchTarget;
    metadataFieldName = patientViewState.metadataFieldName;
    sortDirection = patientViewState.sort as 'asc' | 'desc';
    sortField = patientViewState.sortField as 'name' | 'value';

    // Load filters from JSON strings
    try {
      metadataFilters = JSON.parse(patientViewState.metadataFilters);
    } catch (error) {
      console.warn('Failed to parse metadata filters from local storage:', error);
      metadataFilters = [];
    }

    try {
      extractionFilters = JSON.parse(patientViewState.extractionFilters);
    } catch (error) {
      console.warn('Failed to parse extraction filters from local storage:', error);
      extractionFilters = [];
    }

    loadedPatientViewState = true;
  }

  // Save search target when it changes
  $: if (mounted && searchTarget) {
    savePatientViewState({ searchTarget });
  }

  // Save metadata field name when it changes
  $: if (mounted && metadataFieldName !== undefined) {
    savePatientViewState({ metadataFieldName });
  }

  // Save sort direction and sort field when they change
  $: if (loadedPatientViewState) {
    savePatientViewState({ sort: sortDirection, sortField });
  }

  // Save filters when they change
  $: if (loadedPatientViewState && metadataFilters) {
    savePatientViewState({ metadataFilters: JSON.stringify(metadataFilters) });
  }

  $: if (loadedPatientViewState && extractionFilters) {
    savePatientViewState({ extractionFilters: JSON.stringify(extractionFilters) });
  }

  $: console.log('selected patients:', selectedPatientIds);

  // Filter patients by extraction status
  $: filteredPatients = patients.filter((patient) => {
    if (extractionStatusFilter === 'run' && !(patient.extraction_run ?? false)) {
      return false;
    }
    if (extractionStatusFilter === 'not_run' && (patient.extraction_run ?? false)) {
      return false;
    }
    if (filteredPatientIDs !== null && !filteredPatientIDs.has(patient.id)) return false;
    return true;
  });

  // Convert patients to TableView format
  $: tableItems = filteredPatients.map((patient) => {
    let description = `${patient.note_count} note${patient.note_count !== 1 ? 's' : ''}`;
    if (patient.extraction_count !== undefined && patient.extraction_count > 0) {
      description += `, ${patient.extraction_count} extraction${patient.extraction_count !== 1 ? 's' : ''}`;
    }

    let value: string | number | undefined = undefined;

    // Set description and value based on selected view type
    switch (selectedViewType) {
      case 'note_count':
        value = patient.note_count;
        break;
      case 'extraction_count':
        value = patient.extraction_count ?? 0;
        break;
      case 'earliest_date':
        // Assume patient has earliest_note_date field
        if (patient.earliest_note_date) {
          value = patient.earliest_note_date;
        } else {
          value = '';
        }
        break;
      case 'latest_date':
        // Assume patient has latest_note_date field
        if (patient.latest_note_date) {
          const date = new Date(patient.latest_note_date);
          value = patient.latest_note_date;
        } else {
          description = 'No notes';
          value = '';
        }
        break;
      case 'metadata_field':
        if (
          metadataFieldName &&
          patient.metadata &&
          patient.metadata[metadataFieldName] !== undefined
        ) {
          value = patient.metadata[metadataFieldName];
        } else {
          value = '';
        }
        break;
      default:
        value = patient.note_count;
    }

    return {
      id: patient.id,
      name: patient.id,
      description,
      value,
      tags: patient.tags || []
    };
  });

  $: selectedItemId = selectedPatient?.id || null;

  // Collect all unique tags from patients
  $: allTags = [...new Set(patients.flatMap((patient) => patient.tags || []))].sort();

  // Get available metadata field names from patients
  $: metadataFields = getMetadataFields(patients);

  // Handle view option changes
  function handleViewTypeChange(event: CustomEvent<{ viewType: string }>) {
    selectedViewType = event.detail.viewType;
    savePatientViewState({ viewType: selectedViewType });
  }

  function handleMetadataFieldChange(event: CustomEvent<{ field: string }>) {
    metadataFieldName = event.detail.field;
  }

  function handleTagFilterChange(event: CustomEvent<{ tag: string | null }>) {
    filterTag = event.detail.tag;
    saveActiveTag(filterTag);
  }

  function handleExtractionStatusFilterChange(event: CustomEvent<{ status: string }>) {
    extractionStatusFilter = event.detail.status;
  }

  // Load extraction specs for filtering
  async function loadExtractionSpecs() {
    try {
      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/results/extraction_classes`
      );
      if (response.ok) {
        const data = await response.json();
        filterExtractionSpecs = data.extraction_specs || {};
      }
    } catch (error) {
      console.error('Failed to load extraction specs:', error);
    }
  }

  $: (metadataFilters, extractionFilters, advancedFiltersActive, applyPatientFilters());

  onMount(async () => {
    try {
      let editResponse = await authenticatedFetch(`/api/projects/${$projectID}/patients/test`);
      if (editResponse.status == 403) canEditPatients = false;
      else {
        let response = await editResponse.json();
        if (response.success) canEditPatients = true;
      }
    } catch (e) {
      canEditPatients = false;
    }

    loadExtractionSpecs();
  });

  function handlePatientSelect(
    event: CustomEvent<{ item: { id: string; name: string; description?: string } | null }>
  ) {
    if (!event.detail.item) {
      dispatch('select', { patient: null, searchQuery, searchTarget });
      return;
    }
    const patient = patients.find((p) => p.id === event.detail.item!.id);
    if (patient) {
      selectedPatient = patient;
      dispatch('select', { patient: selectedPatient!, searchQuery, searchTarget });
      handleClose();
    }
  }

  function handleClose() {
    dispatch('close');
  }

  async function handleDelete(event: CustomEvent<{ ids: string[] }>) {
    const { ids } = event.detail;

    if (ids.length === 0) return;

    const confirmMessage =
      ids.length === 1
        ? `Are you sure you want to delete patient "${ids[0]}"?`
        : `Are you sure you want to delete ${ids.length} patients?`;

    if (!confirm(confirmMessage)) return;

    try {
      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/patients?patientIDs=${ids.join(',')}`,
        {
          method: 'DELETE'
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to delete patients: ${response.statusText}`);
      }

      const result = await response.json();

      // Update the patients list by removing deleted patients
      patients = patients.filter((patient) => !ids.includes(patient.id));

      // Clear selection if selected patient was deleted
      if (selectedPatient && ids.includes(selectedPatient.id)) {
        selectedPatient = null;
      }

      console.log(`Successfully deleted ${result.patient_ids?.length || ids.length} patients`);
    } catch (error) {
      console.error('Error deleting patients:', error);
      alert(
        `Failed to delete patients: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  async function handleExport(format: 'csv' | 'json') {
    // Determine which patients to export
    const exportPatientIds = selectedPatientIds.length > 0 ? selectedPatientIds : undefined;

    // Build query parameters
    const params = new URLSearchParams({ format });
    if (exportPatientIds) {
      params.set('patientIDs', exportPatientIds.join(','));
    }

    const downloadURL = new URL(
      `/api/projects/${$projectID}/patients/download?${params.toString()}`,
      window.location.origin
    );
    try {
      let response = await authenticatedFetch(downloadURL.toString());
      let blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      const disposition = response.headers.get('Content-Disposition');
      let filename = 'extractions.' + format; // Default fallback

      if (disposition && disposition.includes('filename=')) {
        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        const matches = filenameRegex.exec(disposition);
        if (matches != null && matches[1]) {
          filename = matches[1].replace(/['"]/g, '');
        }
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click(); // Programmatically trigger the click
      a.remove();
    } catch (e) {
      alert('Unable to download patients: ' + e);
    }
  }

  $: advancedFiltersActive = !(
    (metadataFilters.length == 0 && extractionFilters.length == 0) ||
    metadataFilters.some((f) => !f.field || !f.operator) ||
    extractionFilters.some((f) => !f.spec_id || !f.extraction_class || !f.operator)
  );
  $: isFiltering = filterTag != null || extractionStatusFilter != 'all' || advancedFiltersActive;
</script>

<div
  class="flex h-full w-full flex-col gap-4"
  class:py-4={showHeader}
  class:bg-stone-50={secondaryBackground}
>
  {#if loadingPatients}
    <LoadingView text="Loading patients..." />
  {:else}
    {#if showHeader}
      <!-- Header -->
      <div class="flex shrink-0 items-center justify-between px-4">
        <h2 id="modal-title" class="text-lg font-bold text-stone-900">{title}</h2>
        <div class="flex items-center gap-2">
          {#if editable}
            <ActionMenuButton
              buttonClass="btn-icon"
              disabled={!canEditPatients}
              buttonTitle={canEditPatients
                ? 'Import patients and notes...'
                : 'Cannot modify this patient set'}
              align="right"
              menuWidth={200}
              singleClick={true}
            >
              {#snippet buttonContent()}
                <Fa icon={faUpload} />
              {/snippet}
              {#snippet options(dismiss: () => void)}
                <div class="py-1" role="none">
                  <button
                    class="group flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                    role="menuitem"
                    on:click={() => {
                      dispatch('importManual');
                      dismiss();
                    }}
                  >
                    Manual Entry
                  </button>
                  <button
                    class="group flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                    role="menuitem"
                    on:click={() => {
                      dispatch('importFile');
                      dismiss();
                    }}
                  >
                    Upload File
                  </button>
                </div>
              {/snippet}
            </ActionMenuButton>
            <ActionMenuButton
              buttonClass="btn-icon"
              buttonTitle={'Export' +
                (selectedPatientIds.length > 0
                  ? ` ${selectedPatientIds.length} patient${
                      selectedPatientIds.length != 1 ? 's' : ''
                    }...`
                  : '...')}
              align="right"
              menuWidth={200}
              singleClick={true}
            >
              {#snippet buttonContent()}
                <Fa icon={faDownload} />
              {/snippet}
              {#snippet options(dismiss: () => void)}
                <div class="py-1" role="none">
                  <button
                    class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                    role="menuitem"
                    on:click={() => {
                      handleExport('csv');
                      dismiss();
                    }}
                  >
                    CSV Format
                  </button>
                  <button
                    class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                    role="menuitem"
                    on:click={() => {
                      handleExport('json');
                      dismiss();
                    }}
                  >
                    JSON Format
                  </button>
                </div>
              {/snippet}
            </ActionMenuButton>
          {:else}
            <button
              on:click={() => goto('/')}
              class="btn-small btn-secondary"
              title="Add or delete patients"
            >
              Edit...
            </button>
          {/if}
          {#if allowClose}
            <button
              on:click={handleClose}
              class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              aria-label="Close modal"
            >
              <Fa icon={faXmark} />
            </button>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Content -->
    <div class="flex min-h-0 flex-auto gap-4">
      <TableView
        {secondaryBackground}
        items={tableItems}
        nameColumnTitle="Patient"
        valueColumnTitle={selectedViewType === 'note_count'
          ? 'Notes'
          : selectedViewType === 'extraction_count'
            ? 'Extractions'
            : selectedViewType === 'earliest_date'
              ? 'Earliest'
              : selectedViewType === 'latest_date'
                ? 'Latest'
                : metadataFieldName || 'Value'}
        fixedHeight={true}
        height="100%"
        itemsPerPage={20}
        {selectedItemId}
        bind:selectedItemIds={selectedPatientIds}
        bind:filterTag
        bind:searchQuery
        bind:sortBy={sortField}
        bind:sortDirection
        on:select={handlePatientSelect}
        on:tag={(e) => dispatch('tag', e.detail)}
        on:delete={handleDelete}
        on:filterTag={(e) => saveActiveTag(e.detail.filterTag)}
        allowMultiselect={editable || multiSelectOnly || allowMultiSelect}
        allowSingleSelect={!multiSelectOnly}
        allowTags={editable}
        allowDelete={editable && canEditPatients}
        searchFunction={searchPatients}
        {searchTargets}
        bind:selectedSearchTarget={searchTarget}
      >
        <ActionMenuButton
          slot="viewOptionsMenu"
          buttonClass={isFiltering ? 'btn-icon-active' : 'btn-icon'}
          buttonTitle="View options"
          menuWidth={320}
          align="left"
          singleClick={false}
        >
          {#snippet buttonContent()}
            <Fa icon={faFilter} />
          {/snippet}
          {#snippet options()}
            <PatientSelectorViewOptions
              viewTypes={patientViewTypes}
              bind:selectedViewType
              bind:metadataFieldName
              {metadataFields}
              bind:filterTag
              {allTags}
              specForExtractionStatus={selectedSpec?.name ?? undefined}
              showExtractionFilter={!!selectedSpec}
              bind:extractionStatusFilter
              on:viewTypeChange={handleViewTypeChange}
              on:metadataFieldChange={handleMetadataFieldChange}
              on:tagFilterChange={handleTagFilterChange}
              on:extractionStatusFilterChange={handleExtractionStatusFilterChange}
              showAdvancedFilters
              bind:extractionSpecs={filterExtractionSpecs}
              bind:metadataFilters
              bind:extractionFilters
            />
          {/snippet}
        </ActionMenuButton>
      </TableView>
    </div>
  {/if}
</div>
