<script lang="ts">
  import Fa from 'svelte-fa';
  import type {
    Annotation,
    AnnotationSelection,
    ExtractionAnnotation,
    ExtractionSpec,
    Note,
    Patient
  } from '../extraction_types';
  import StructuredTextView from '../extraction_view/StructuredTextView.svelte';
  import {
    faChevronLeft,
    faChevronRight,
    faChevronDown,
    faChevronUp,
    faPlay,
    faXmark,
    faBars
  } from '@fortawesome/free-solid-svg-icons';
  import PatientSelector from './PatientSelector.svelte';
  import PatientSelectorViewOptions from './PatientSelectorViewOptions.svelte';
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import JSONTreeView from '$lib/utils/JSONTreeView.svelte';
  import ResizablePanel from '$lib/utils/ResizablePanel.svelte';
  import TableView from '$lib/utils/TableView.svelte';
  import ActionMenuButton from '$lib/utils/ActionMenuButton.svelte';
  import TagEditMenu from '$lib/utils/TagEditMenu.svelte';
  import CommentView from '$lib/shared/CommentView.svelte';
  import {
    faFilter,
    faTag,
    faXmark as faXmarkSolid,
    faComment
  } from '@fortawesome/free-solid-svg-icons';
  import { getPatientDetails, patients } from '$lib/stores/data';
  import { loadNoteViewState, saveNoteViewState } from '$lib/stores/viewOptions';
  import { authenticatedFetch } from '$lib/stores/auth';

  const dispatch = createEventDispatcher();

  export let selectedPatient: Patient | null = null;
  export let noteID: string | null = null;
  export let patientSearchQuery: string | null = null;
  export let showEditControls: boolean = true;
  export let secondaryBackground: boolean = false;

  export let note: Note | null = null; // managed by this component

  export let extractionSpecs: ExtractionSpec[] = [];
  export let selectedSpec: ExtractionSpec | null = null;

  export let fetchTaskStatus: ((specID?: string, patientID?: string) => Promise<any>) | undefined =
    undefined;

  export let hoveredAnnotation: AnnotationSelection | null = null;
  export let selectedAnnotation: AnnotationSelection | null = null;

  export let loadingAnnotations: boolean = false;

  export let modelAnnotationClasses: string[] = [];
  export let modelIconClasses: string[] = [];
  export let multipleModelAnnotationClass: string = '';

  export let noteAnnotations: ExtractionAnnotation[] = [];

  export let showPatientSelector: boolean = false;

  // after details are loaded
  let loadedPatient: Patient | null = null;
  let loadingPatientDetails: boolean = false;
  $: if (!!selectedPatient && loadedPatient?.id != selectedPatient?.id) {
    loadingPatientDetails = true;
    getPatientDetails(selectedPatient.id, selectedSpec?.id ?? undefined).then((p) => {
      loadedPatient = p;
      loadingPatientDetails = false;
    });
  }
  export let patientToShow: Patient | null = null;
  $: patientToShow =
    !!selectedPatient && !!loadedPatient && loadedPatient.id == selectedPatient.id
      ? loadedPatient
      : selectedPatient;
  $: if (
    !!loadedPatient &&
    !!selectedPatient &&
    loadedPatient.id == selectedPatient?.id &&
    !!noteID
  ) {
    // load the note if it exists, otherwise reset
    let theNote = loadedPatient.notes?.find((n) => n.id == noteID) ?? null;
    if (!theNote) noteID = null;
  }

  let extracting: boolean = false;
  let pollingInterval: NodeJS.Timeout | null = null;
  let noteIdx: number | null = null;

  // Notes view options
  let noteSelectedViewType: string = 'note_date';
  let noteMetadataFieldName: string = '';
  let noteSortDirection: 'asc' | 'desc' = 'desc';
  let noteSortField: 'name' | 'value' | null = null;
  let noteViewStateLoaded: boolean = false;

  // Define view types for note selector
  const noteViewTypes = [
    { name: 'Note Date', value: 'note_date' },
    { name: 'Metadata Field', value: 'metadata_field' }
  ];

  // Helper function to extract metadata field names with string or number values from notes
  function getNoteMetadataFieldNames(notes: Note[]): string[] {
    const fieldNames = new Set<string>();

    // Get the first note with metadata to check field types
    for (const note of notes) {
      if (note.metadata && typeof note.metadata === 'object') {
        Object.entries(note.metadata).forEach(([key, value]) => {
          if (typeof value === 'string' || typeof value === 'number') {
            fieldNames.add(key);
          }
        });
      }
      // Only check the first note to avoid processing all notes
      if (fieldNames.size > 0) break;
    }

    return Array.from(fieldNames).sort();
  }

  $: if (!!patientToShow && !!patientToShow.notes && !!noteID && sortedNoteIds.length > 0) {
    // Find the index in the sorted list
    noteIdx = sortedNoteIds.findIndex((id) => id == noteID);
    if (noteIdx >= 0) {
      note = patientToShow.notes.find((n) => n.id == noteID) ?? null;
    } else {
      noteIdx = null;
      note = null;
    }
  } else {
    noteIdx = null;
    note = null;
  }

  // Get available metadata field names from notes
  $: noteMetadataFieldNames = patientToShow?.notes
    ? getNoteMetadataFieldNames(patientToShow.notes)
    : [];

  // Load note view state from localStorage when component mounts
  $: if (!noteViewStateLoaded) {
    const noteViewState = loadNoteViewState();
    noteSelectedViewType = noteViewState.viewType;
    noteMetadataFieldName = noteViewState.metadataFieldName;
    noteSortDirection = noteViewState.sort as 'asc' | 'desc';
    noteSortField = noteViewState.sortField as 'name' | 'value' | null;
    noteViewStateLoaded = true;
  }

  // Save sort direction and sort field when they change
  $: if (noteViewStateLoaded) {
    saveNoteViewState({ sort: noteSortDirection, sortField: noteSortField });
  }

  // Create sorted note IDs list based on current view state and sort settings
  $: if (notesToShow && notesToShow.length > 0) {
    // Create a sortable array with notes and their sort values
    const sortableNotes = notesToShow.map((n) => {
      let sortValue: string | number;
      if (
        noteSelectedViewType === 'metadata_field' &&
        noteMetadataFieldName &&
        n.metadata &&
        n.metadata[noteMetadataFieldName] !== undefined
      ) {
        sortValue = n.metadata[noteMetadataFieldName];
      } else {
        sortValue = n.date || (n.note_text ?? '').length;
      }
      return { note: n, sortValue };
    });

    // Sort the array based on current settings
    if (noteSortField === 'value') {
      sortableNotes.sort((a, b) => {
        let aVal = a.sortValue;
        let bVal = b.sortValue;

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

        if (aVal < bVal) return noteSortDirection === 'asc' ? -1 : 1;
        if (aVal > bVal) return noteSortDirection === 'asc' ? 1 : -1;
        return 0;
      });
    } else if (noteSortField === 'name') {
      sortableNotes.sort((a, b) => {
        const aVal = a.note.id.toLowerCase();
        const bVal = b.note.id.toLowerCase();
        if (aVal < bVal) return noteSortDirection === 'asc' ? -1 : 1;
        if (aVal > bVal) return noteSortDirection === 'asc' ? 1 : -1;
        return 0;
      });
    }

    // Extract the sorted note IDs
    sortedNoteIds = sortableNotes.map((item) => item.note.id);
  } else {
    sortedNoteIds = [];
  }

  // Reactive polling for task status
  $: if (selectedPatient && fetchTaskStatus) {
    checkTaskStatus();
  }

  // Cleanup polling on component destroy
  onDestroy(() => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }
  });

  export let showingPatientSelector: boolean = false;
  let commentView: CommentView;

  // Define search targets for notes search
  const noteSearchTargets = [
    { name: 'All Fields', value: 'all' },
    { name: 'Note ID', value: 'id' },
    { name: 'Note Text', value: 'text' },
    { name: 'Metadata', value: 'metadata' }
  ];

  // Helper function to generate a snippet with the search query highlighted
  function generateSearchSnippet(text: string, query: string, contextLength: number = 50): string {
    if (!query || !text) return text;

    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();
    const index = lowerText.indexOf(lowerQuery);

    if (index === -1) return text;

    const start = Math.max(0, index - contextLength);
    const end = Math.min(text.length, index + query.length + contextLength);

    let snippet = text.substring(start, end);
    if (start > 0) snippet = '...' + snippet;
    if (end < text.length) snippet = snippet + '...';

    return snippet;
  }

  // Search function for notes (client-side filtering)
  async function searchNotes(searchQuery: string, searchTarget?: string): Promise<string[]> {
    // Use patientSearchQuery if provided, otherwise use the provided searchQuery
    const actualQuery = patientSearchQuery || searchQuery;
    if (!patientToShow || !patientToShow.notes || !actualQuery.trim()) {
      return [];
    }

    const query = actualQuery.toLowerCase().trim();
    const filteredNotes = patientToShow.notes.filter((note) => {
      switch (searchTarget) {
        case 'id':
          return note.id.toLowerCase().includes(query);
        case 'text':
          return (note.note_text || '').toLowerCase().includes(query);
        case 'metadata':
          return note.metadata
            ? JSON.stringify(note.metadata).toLowerCase().includes(query)
            : false;
        case 'all':
        default:
          // Search in all fields
          const idMatch = note.id.toLowerCase().includes(query);
          const textMatch = (note.note_text || '').toLowerCase().includes(query);
          const metadataMatch = note.metadata
            ? JSON.stringify(note.metadata).toLowerCase().includes(query)
            : false;
          const dateMatch = note.date ? note.date.toLowerCase().includes(query) : false;
          return idMatch || textMatch || metadataMatch || dateMatch;
      }
    });

    return filteredNotes.map((note) => note.id);
  }

  function handleNoteSelect(event: CustomEvent<{ item: any }>) {
    if (patientToShow && !!patientToShow.notes) {
      noteID = event.detail.item?.id ?? null;
    }
  }

  async function checkTaskStatus() {
    if (!selectedPatient || !fetchTaskStatus) return;

    // Clear any existing polling interval
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }

    try {
      const task = await fetchTaskStatus(undefined, selectedPatient.id);

      if (task && task.status && (task.status === 'running' || task.status === 'pending')) {
        extracting = true;
        // Start polling every second
        pollingInterval = setInterval(async () => {
          try {
            const updatedTask = await fetchTaskStatus!(undefined, selectedPatient!.id);
            if (
              !updatedTask ||
              !updatedTask.status ||
              (updatedTask.status !== 'running' && updatedTask.status !== 'pending')
            ) {
              extracting = false;
              if (pollingInterval) {
                clearInterval(pollingInterval);
                pollingInterval = null;
              }
            }
          } catch (error) {
            // Task not found or error - assume completed
            extracting = false;
            if (pollingInterval) {
              clearInterval(pollingInterval);
              pollingInterval = null;
            }
          }
        }, 1000);
      } else {
        extracting = false;
      }
    } catch (error) {
      // Task not found or error - not running
      extracting = false;
    }
  }

  function handleExtract() {
    if (!selectedPatient) return;

    dispatch('extract', { patientIDs: [selectedPatient.id] });
    setTimeout(checkTaskStatus, 1000);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (showingPatientSelector && e.key === 'Escape') {
      showingPatientSelector = false;
      e.stopPropagation();
      e.preventDefault();
    }
  }

  let noteSearchQuery: string = '';
  let notesToShow: Note[] = [];
  let sortedNoteIds: string[] = []; // Note IDs in sorted order

  // Available tags - should be provided by parent component
  $: allPatientTags = Array.from(new Set(($patients ?? []).map((p) => p.tags ?? []).flat()));

  // Tag handling functions
  function handleTagToggle(tag: string, include: boolean, items: any[]) {
    if (!selectedPatient || items.length === 0) return;

    // For patient view, we only work with one patient
    const patient = items[0];
    const currentTags = patient.tags || [];
    let newTags: string[];

    if (!include) {
      // Remove tag
      newTags = currentTags.filter((t: string) => t !== tag);
    } else {
      // Add tag
      newTags = [...currentTags.filter((t: string) => t !== tag), tag];
    }

    // Update the patient object
    if (loadedPatient && loadedPatient.id === selectedPatient.id) {
      loadedPatient = { ...loadedPatient, tags: newTags };
    }

    // Dispatch the tag event for parent handling
    dispatch('tag', { items: [selectedPatient], tag, include });
  }

  function handleRemoveTag(tag: string) {
    if (!selectedPatient) return;
    handleTagToggle(tag, false, [selectedPatient]);
  }

  $: if (!!patientToShow?.notes && patientToShow.notes.length > 0) {
    if (!!patientSearchQuery) {
      searchNotes(patientSearchQuery, 'all').then(
        (r) => (notesToShow = patientToShow?.notes?.filter((n) => r.includes(n.id)) ?? [])
      );
    } else {
      notesToShow = patientToShow.notes;
    }
  } else {
    notesToShow = [];
  }

  $: isFilteringNotes = false;
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="flex h-full w-full flex-col gap-4 pt-4" class:bg-stone-50={secondaryBackground}>
  <div class="flex w-full shrink-0 items-center justify-between gap-2 px-4">
    {#if showPatientSelector}
      <button class="btn btn-secondary shrink-0" on:click={() => (showingPatientSelector = true)}>
        <Fa icon={faBars} class="mr-2 inline" />
        {#if !!selectedPatient}
          <strong>Patient&nbsp;</strong>
          <span class="mr-2 font-mono">{selectedPatient.id}</span>
        {:else}
          <strong>Patients</strong>
        {/if}
      </button>
    {:else if !!selectedPatient}
      <div>
        <span class="text-lg text-stone-900"
          ><strong>Patient</strong>
          <span class="font-mono">{selectedPatient?.id}</span></span
        >
        {#if loadingPatientDetails}
          <div
            class="mr-2 inline-block h-3 w-3 animate-spin rounded-full border-2 border-stone-500 border-t-transparent"
          ></div>
          <span class="text-sm text-stone-500">Fetching details...</span>
        {/if}
      </div>
    {:else}
      <div></div>
    {/if}

    {#if !!selectedPatient && showEditControls}
      <div class="flex shrink-0 items-center gap-2">
        <!-- Comment Button -->
        <button
          class="btn-icon"
          title="View and add comments for this patient"
          on:click={() => commentView?.createNewComment()}
        >
          <Fa icon={faComment} />
        </button>

        <!-- Tag Menu Button -->
        <ActionMenuButton
          buttonClass="btn-icon"
          disabled={false}
          buttonTitle="Add/Remove tags for this patient"
          menuWidth={200}
          align="right"
        >
          {#snippet buttonContent()}
            <Fa icon={faTag} />
          {/snippet}
          {#snippet options(dismiss: () => void)}
            <TagEditMenu
              items={patientToShow ? [patientToShow] : []}
              allTags={allPatientTags}
              onTagToggle={handleTagToggle}
            />
          {/snippet}
        </ActionMenuButton>

        <!-- Extract Button -->
        <button
          class="btn btn-primary"
          on:click={handleExtract}
          disabled={extracting}
          title="Run extraction on this patient using the selected specification"
        >
          {#if extracting}
            <div
              class="mr-2 inline-block h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent"
            ></div>
            Extracting...
          {:else}
            <Fa class="mr-2 inline" icon={faPlay} />Extract
          {/if}
        </button>
      </div>
    {/if}
  </div>
  {#if !!note && noteIdx !== null && !!patientToShow && !!patientToShow.notes}
    <div class="flex w-full shrink-0 items-center justify-between gap-4 px-4">
      <div class="flex flex-auto items-center gap-4">
        <button class="btn btn-secondary shrink-0" on:click={() => (noteID = null)}>
          <Fa class="mr-2 inline" icon={faChevronLeft} />Overview
        </button>
        <span class="truncate text-base font-medium break-all whitespace-nowrap text-stone-900"
          ><strong>Note</strong> <span class="font-mono">{noteID}</span></span
        >
      </div>
      <div class="flex flex-auto items-center justify-end overflow-hidden">
        <button
          class="shrink-0 grow-0 cursor-pointer px-2 py-1 hover:opacity-50 disabled:opacity-30"
          disabled={noteIdx == 0}
          on:click={() => (noteID = sortedNoteIds[noteIdx! - 1])}
          ><Fa icon={faChevronLeft} title="Previous note for this patient" /></button
        >
        <div class="shrink truncate text-sm whitespace-nowrap text-gray-700">
          Note {noteIdx + 1} of {sortedNoteIds.length}
        </div>
        <button
          class="shrink-0 grow-0 cursor-pointer px-2 py-1 hover:opacity-50 disabled:opacity-30"
          disabled={noteIdx == sortedNoteIds.length - 1}
          on:click={() => (noteID = sortedNoteIds[noteIdx! + 1])}
          title="Next note for this patient"><Fa icon={faChevronRight} /></button
        >
      </div>
    </div>
  {/if}
  {#if loadingAnnotations && !!note}
    <LoadingView text="Processing note annotations..." />
  {:else if !!note}
    <div class="flex min-h-0 w-full flex-auto flex-col">
      <!-- Metadata Panel -->
      {#if (note.metadata && Object.keys(note.metadata).length > 0) || note.date}
        <ResizablePanel
          bottomResizable={true}
          width="100%"
          height={200}
          minHeight={80}
          collapsible={true}
          maxHeight="50%"
        >
          <div class="h-full w-full overflow-auto p-4">
            <div class="mb-2">
              <h3 class="text-sm font-bold uppercase">Note Metadata</h3>
            </div>
            {#if note.date}
              <div class="mb-2 flex border-b border-stone-200 pb-2 text-sm">
                <span class="mr-2 font-semibold text-gray-500">Date</span>
                <span class="font-mono text-gray-900">{note.date}</span>
              </div>
            {/if}
            {#if note.metadata && Object.keys(note.metadata).length > 0}
              <JSONTreeView data={note.metadata} indentLevel={0} />
            {/if}
          </div>
        </ResizablePanel>
      {/if}

      <!-- Note Content -->
      <div class="min-h-0 w-full flex-auto">
        <StructuredTextView
          text={note.note_text ?? ''}
          collapsible={false}
          annotations={noteAnnotations}
          annotationClasses={Object.fromEntries(
            extractionSpecs.map((source, i) => [source.id, modelAnnotationClasses[i]])
          )}
          multipleAnnotationClasses={multipleModelAnnotationClass}
          annotationIconClasses={Object.fromEntries(
            extractionSpecs.map((source, i) => [source.id, modelIconClasses[i]])
          )}
          bind:hoveredAnnotation
          bind:selectedAnnotation
        />
      </div>
    </div>
  {/if}
  {#if !!patientToShow}
    <!-- Patient Overview - keep component alive even when note detail is showing -->
    <div
      class:hidden={!!note}
      class="flex min-h-0 w-full flex-auto flex-col gap-4 overflow-auto pb-4"
    >
      <div class="px-4">
        <CommentView entityType="patient" entityId={patientToShow.id} bind:this={commentView} />
      </div>

      <!-- Patient Tags -->
      {#if patientToShow?.tags && patientToShow.tags.length > 0}
        <div class="px-4">
          <h3 class="mb-2 text-sm font-bold uppercase">Tags</h3>
          <div class="flex flex-wrap gap-1">
            {#each patientToShow.tags as tag}
              <span
                class="inline-flex items-center gap-1 rounded border-sky-200/50 bg-sky-100 px-2 py-1 text-sm font-semibold text-sky-800"
              >
                {tag}
                <button
                  class="ml-1 cursor-pointer p-0.5 text-sky-600 hover:opacity-50"
                  on:click={() => handleRemoveTag(tag)}
                  title="Remove tag"
                >
                  <Fa icon={faXmarkSolid} class="h-2 w-2" />
                </button>
              </span>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Patient Metadata -->
      {#if patientToShow.metadata && Object.keys(patientToShow.metadata).length > 0}
        <div class="max-h-1/2 min-h-0 shrink-0 overflow-auto px-4">
          <h3 class="mb-2 text-sm font-bold uppercase">Patient Metadata</h3>
          <JSONTreeView data={patientToShow.metadata} indentLevel={0} />
        </div>
      {/if}

      <!-- Notes List -->
      <div class="mt-2 shrink-0 px-4 text-sm font-bold uppercase">Patient Notes</div>

      <!-- Patient Search Banner -->
      {#if patientSearchQuery}
        <div class="mx-4 mb-2 flex items-center justify-between rounded-md bg-sky-100 px-4 py-1.5">
          <div class="flex-auto text-sm font-medium text-sky-800">
            Searching for "{patientSearchQuery}"
          </div>
          <button
            class="btn-icon btn-icon-blue text-sm text-sky-800"
            on:click={() => (patientSearchQuery = null)}
            title="Clear patient search"
          >
            <Fa icon={faXmark} />
          </button>
        </div>
      {/if}

      <div class="min-h-48 flex-auto">
        {#if notesToShow.length > 0}
          {@const tableItems = notesToShow.map((n, index) => {
            let value: string | number;
            if (
              noteSelectedViewType === 'metadata_field' &&
              noteMetadataFieldName &&
              n.metadata &&
              n.metadata[noteMetadataFieldName] !== undefined
            ) {
              value = n.metadata[noteMetadataFieldName];
            } else {
              value = n.date || (n.note_text ?? '').length;
            }
            // Generate description - use snippet if there's a search query
            let description = n.note_text ?? '';
            const activeSearchQuery = patientSearchQuery || noteSearchQuery;
            if (activeSearchQuery && description) {
              description = generateSearchSnippet(description, activeSearchQuery);
            }

            return {
              id: n.id,
              name: n.id,
              description,
              value
            };
          })}
          <TableView
            {secondaryBackground}
            items={tableItems}
            nameColumnTitle="Note"
            valueColumnTitle={noteSelectedViewType === 'metadata_field' && noteMetadataFieldName
              ? noteMetadataFieldName
              : notesToShow.some((n) => n.date)
                ? 'Date'
                : 'Characters'}
            fixedHeight={true}
            height="100%"
            itemsPerPage={10}
            selectedItemId={noteID}
            bind:searchQuery={noteSearchQuery}
            bind:sortBy={noteSortField}
            bind:sortDirection={noteSortDirection}
            allowSearch={!patientSearchQuery}
            on:select={handleNoteSelect}
            searchFunction={searchNotes}
            searchTargets={noteSearchTargets}
          >
            <ActionMenuButton
              slot="viewOptionsMenu"
              buttonClass={isFilteringNotes ? 'btn-icon-active' : 'btn-icon'}
              buttonTitle="View options"
              menuWidth={250}
              align="left"
              singleClick={false}
            >
              {#snippet buttonContent()}
                <Fa icon={faFilter} />
              {/snippet}
              {#snippet options()}
                <PatientSelectorViewOptions
                  viewTypes={noteViewTypes}
                  bind:selectedViewType={noteSelectedViewType}
                  bind:metadataFieldName={noteMetadataFieldName}
                  metadataFieldNames={noteMetadataFieldNames}
                  filterTag={null}
                  allTags={[]}
                  on:viewTypeChange={(e) => {
                    noteSelectedViewType = e.detail.viewType;
                    saveNoteViewState({ viewType: e.detail.viewType });
                  }}
                  on:metadataFieldChange={(e) => {
                    noteMetadataFieldName = e.detail.field;
                    saveNoteViewState({ metadataFieldName: e.detail.field });
                  }}
                  on:tagFilterChange={() => {}}
                />
              {/snippet}
            </ActionMenuButton>
          </TableView>
        {:else}
          <div class="flex h-full w-full items-center justify-center text-stone-600">
            No notes available for this patient
          </div>
        {/if}
      </div>
    </div>
  {:else}
    <div class="flex h-full w-full flex-col items-center justify-center">
      <div class="text-center text-stone-600">No patient selected</div>
    </div>
  {/if}
</div>
{#if showPatientSelector && showingPatientSelector}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    on:click={(event) => {
      if (event.target === event.currentTarget) {
        showingPatientSelector = false;
      }
    }}
    on:keydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    tabindex="-1"
  >
    <div class="mx-4 h-3/4 w-full max-w-4xl rounded-lg bg-white shadow-xl">
      <PatientSelector
        {selectedSpec}
        {selectedPatient}
        on:select={(e) => {
          selectedPatient = e.detail.patient;
          noteID = null;
        }}
        on:close={() => (showingPatientSelector = false)}
        editable={false}
      />
    </div>
  </div>
{/if}
