<script lang="ts">
  import Fa from 'svelte-fa';
  import type {
    Annotation,
    AnnotationSelection,
    ExtractionAnnotation,
    ExtractionResult,
    Feedback,
    Note,
    NoteExtraction,
    Patient,
    ExtractionSpec
  } from '../extraction_types';
  import ExtractionSourceSelector from './ExtractionSourceSelector.svelte';
  import StructuredTextView from './StructuredTextView.svelte';
  import ModelCardHeader from './ModelCardHeader.svelte';
  import ExtractionItem from './ExtractionItem.svelte';
  import { areObjectsEqual } from '../utils/utils';
  import {
    faChevronLeft,
    faChevronRight,
    faMessage,
    faPlus,
    faRetweet,
    faRotateLeft,
    faXmark,
    faFilter,
    faDownload,
    faPlay,
    faFileLines
  } from '@fortawesome/free-solid-svg-icons';
  import ResizablePanel from '$lib/utils/ResizablePanel.svelte';
  import { createEventDispatcher, onMount } from 'svelte';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import PatientView from '../patient_view/PatientView.svelte';
  import ActionMenuButton from '$lib/utils/ActionMenuButton.svelte';
  import FilterSortMenu from './FilterSortMenu.svelte';
  import ExtractionDownloadMenu from './ExtractionDownloadMenu.svelte';
  import NoteAnnotation from './NoteAnnotation.svelte';
  import PatientSelector from '$lib/patient_view/PatientSelector.svelte';
  import { selectedSpec } from '$lib/stores/data';

  const dispatch = createEventDispatcher();

  export let selectedPatient: Patient | null = null;
  let patientToShow: Patient | null = null; // the fully loaded patient (from PatientView)
  export let noteID: string | null = null;
  let note: Note | null = null;
  let currentPatientSearchQuery: string | null = null;
  export let needsPatientRefresh: boolean = false;

  export let extractionSpecs: ExtractionSpec[] = [];

  export let comparisonSpecs: ExtractionSpec[] = [];

  export let fetchModelOutput: (
    sources: ExtractionSpec[],
    patientID: string
  ) => Promise<ExtractionResult[]> = async () => [];
  export let fetchAvailableSpecs:
    | ((noteID: string | undefined) => Promise<ExtractionSpec[]>)
    | undefined = undefined;
  export let fetchTaskStatus: ((specID?: string, patientID?: string) => Promise<any>) | undefined =
    undefined;

  export let onFeedbackChange: (feedback: Feedback) => void = () => {};
  export let downloadResponses: ((patientId: string | null, csv?: boolean) => void) | null = null;

  export let hoveredAnnotation: AnnotationSelection | null = null;
  export let selectedAnnotation: AnnotationSelection | null = null;

  export let selectedResponse: NoteExtraction | null = null;
  export let refreshTrigger: boolean = false;

  // Combined view - no separate tabs needed

  const ModelAnnotationClasses = [
    'bg-blue-200 hover:bg-blue-300',
    'bg-orange-200 hover:bg-orange-300',
    'bg-green-200 hover:bg-green-300',
    'bg-rose-200 hover:bg-rose-300'
  ];

  const ModelIconClasses = ['bg-blue-700', 'bg-orange-700', 'bg-green-700', 'bg-rose-700'];

  const MultipleModelAnnotationClass = 'bg-gray-200 hover:bg-gray-300';

  // array of extraction results for each of the extraction sources
  let extractionResults: ExtractionResult[] = [];
  let currentExtractions: NoteExtraction[][] = [];
  let loadingModelOutputs: boolean = false;

  let noteAnnotations: ExtractionAnnotation[] = [];
  $: if (!!selectedPatient && comparisonSpecs.length > 0) {
    _loadModelOutputs(comparisonSpecs);
  }

  // Trigger refresh when refreshTrigger changes to true
  $: if (refreshTrigger && !!selectedPatient && comparisonSpecs.length > 0) {
    setTimeout(() => _loadModelOutputs(comparisonSpecs));
  }

  async function _loadModelOutputs(sources: ExtractionSpec[]) {
    loadingModelOutputs = true;
    noteAnnotations = [];
    try {
      console.log('fetching model output');
      extractionResults = await fetchModelOutput(sources, selectedPatient!.id);
      console.log('results:', extractionResults);
      loadingModelOutputs = false;
    } catch (err) {
      console.error('error loading model outputs:', err);
      loadingModelOutputs = false;
    }
  }

  let editingSourceIndex: number | null = null;
  let showingSourceSelector: boolean = false;
  let showingFilterMenu: boolean = false;

  $: if (extractionResults.length > 0) {
    if (!!note) {
      // Filter extractions for the current note from each source
      currentExtractions = extractionResults.map(
        (result) =>
          result.extractions?.filter((ext) => ext.citations.some((c) => c.note_id === note!.id)) ??
          []
      );
    } else {
      // Show all extractions (both patient-level and note-level)
      currentExtractions = extractionResults.map((result) => result.extractions ?? []);
    }
  }

  $: if (currentExtractions.length > 0) {
    noteAnnotations = comparisonSpecs
      .map((source, i) => {
        return filterModelOutputs(currentExtractions[i] ?? [], selectedFilter)
          .map((ext) =>
            ext.citations.map((citation) => ({
              note_id: citation.note_id ?? undefined,
              char_interval: citation.char_interval,
              source: source.id,
              sourceName: source.name,
              description: ext.extraction_class,
              extraction: ext
            }))
          )
          .flat();
      })
      .flat();
    console.log('note annotations in ExtractioNView:', noteAnnotations);
  } else {
    noteAnnotations = [];
  }

  $: if (!note) {
    selectedAnnotation = null;
    selectedResponse = null;
  }

  // Filter and sort controls
  type FilterSpec = { type?: string; feedback?: string };
  let selectedFilter: FilterSpec = {};
  let selectedSort: string = 'Text Order'; // 'Text Order', 'Note Order', or 'Type'

  function filterModelOutputs(outputs: NoteExtraction[], filters: FilterSpec): NoteExtraction[] {
    return outputs.filter((ext) => {
      // Type filter
      if (filters.type && ext.extraction_class !== filters.type) {
        return false;
      }

      // Feedback filter
      if (filters.feedback) {
        if (filters.feedback === 'Reviewed' && !ext.feedback) {
          return false;
        }
        if (filters.feedback === 'Unreviewed' && !!ext.feedback) {
          return false;
        }
      }

      return true;
    });
  }

  // Reset sort when switching between note and patient view
  $: if (!!note && selectedSort === 'Note Order') {
    selectedSort = 'Text Order';
  } else if (!note && selectedSort === 'Text Order') {
    selectedSort = 'Note Order';
  }

  // Get unique extraction classes for filter options
  let availableClasses: string[] = [];
  $: if (currentExtractions.length > 0) {
    const classes = new Set<string>();

    currentExtractions.forEach((extractions) => {
      extractions.forEach((extraction) => {
        if (extraction.extraction_class) {
          classes.add(extraction.extraction_class);
        }
      });
    });

    availableClasses = Array.from(classes).sort();
  } else {
    availableClasses = [];
  }

  // Reset filter if current selection is no longer available
  $: if (selectedFilter.type && !availableClasses.includes(selectedFilter.type)) {
    selectedFilter = { ...selectedFilter, type: undefined };
  }

  $: if (!note) selectedSort = 'Type';

  $: if (showingSourceSelector) {
    refreshSpecs();
  }

  function clearFilter() {
    selectedFilter = { type: undefined, feedback: undefined };
    noteID = null;
  }

  async function refreshSpecs() {
    if (!!fetchAvailableSpecs) extractionSpecs = await fetchAvailableSpecs(undefined);
  }

  // fuzzy matches annotations from patient level to current note annotations
  function getFuzzyMatchedAnnotations(
    patientAnnotations: ExtractionAnnotation[],
    allNoteAnnotations: ExtractionAnnotation[]
  ): ExtractionAnnotation[] {
    return allNoteAnnotations.filter((ann) => {
      return patientAnnotations.some(
        (patientAnn) =>
          patientAnn.note_id == ann.note_id &&
          patientAnn.source == ann.source &&
          patientAnn.extraction.extraction_class == ann.extraction.extraction_class &&
          areObjectsEqual(patientAnn.char_interval, ann.char_interval)
      );
    });
  }

  function sortExtractions(a: NoteExtraction, b: NoteExtraction): number {
    if (selectedSort === 'Type') {
      // Sort by extraction_class first, then by fallback order
      const classCompare = (a.extraction_class || '').localeCompare(b.extraction_class || '');
      if (classCompare !== 0) return classCompare;
    }

    if (selectedSort === 'Note Order' && !!patientToShow && !!patientToShow.notes) {
      // Sort by note order first, then by character position within the note
      let firstCitA = a.citations.length > 0 ? a.citations[0] : null;
      let firstCitB = b.citations.length > 0 ? b.citations[0] : null;
      if (firstCitA != null && firstCitB != null) {
        const noteIdxA = patientToShow.notes.findIndex((n) => n.id === firstCitA.note_id);
        const noteIdxB = patientToShow.notes.findIndex((n) => n.id === firstCitB.note_id);
        if (noteIdxA !== noteIdxB) return noteIdxA - noteIdxB;
        else
          return (
            (firstCitA.char_interval?.start_pos ?? 0) - (firstCitB.char_interval?.start_pos ?? 0)
          );
      } else if (firstCitA != null) {
        return 1;
      } else if (firstCitB != null) {
        return -1;
      }
    }

    return 0;
  }

  function selectionHasExtraction(
    selectionObj: AnnotationSelection | null,
    specID: string,
    extraction: NoteExtraction
  ): boolean {
    return (
      selectionObj != null &&
      selectionObj.annotations != null &&
      selectionObj.annotations.find(
        (ann) =>
          ann.source == specID &&
          areObjectsEqual((ann as ExtractionAnnotation).extraction, extraction)
      ) != null &&
      (selectionObj.source == null || selectionObj.source == specID)
    );
  }

  $: console.log('selected annotation:', selectedAnnotation, currentExtractions);
  let patientSelectorCollapsed = true;
</script>

<div class="relative flex h-full w-full">
  <ResizablePanel
    bind:collapsed={patientSelectorCollapsed}
    rightResizable
    minWidth={240}
    maxWidth="40%"
    collapsible={true}
    width="30%"
    height="100%"
    ><PatientSelector
      bind:needsPatientRefresh
      selectedSpec={comparisonSpecs.length == 1 ? comparisonSpecs[0] : null}
      title="Patient to Review"
      secondaryBackground
      {selectedPatient}
      allowClose={false}
      editable={false}
      allowMultiSelect={false}
      on:select={(e) => {
        selectedPatient = e.detail.patient ?? null;
        noteID = null;
        // If there's a search query when selecting a patient, pass it to PatientView
        if (selectedPatient) {
          if (e.detail.searchQuery.trim() && ['all', 'text'].includes(e.detail.searchTarget)) {
            currentPatientSearchQuery = e.detail.searchQuery;
          } else {
            currentPatientSearchQuery = null;
          }
        }
      }}
    /></ResizablePanel
  >

  <div class="h-full w-0 flex-auto">
    <PatientView
      secondaryBackground
      bind:selectedPatient
      bind:patientToShow
      bind:noteID
      bind:note
      extractionSpecs={comparisonSpecs}
      selectedSpec={comparisonSpecs.length == 1 ? comparisonSpecs[0] : null}
      patientSearchQuery={currentPatientSearchQuery}
      {fetchTaskStatus}
      bind:hoveredAnnotation
      bind:selectedAnnotation
      loadingAnnotations={loadingModelOutputs}
      modelAnnotationClasses={ModelAnnotationClasses}
      modelIconClasses={ModelIconClasses}
      multipleModelAnnotationClass={MultipleModelAnnotationClass}
      noteAnnotations={noteAnnotations.filter(
        (ext) => !!ext.char_interval && (!note || (!!ext.note_id && note.id == ext.note_id))
      )}
      on:extract
      on:tag={(e) => dispatch('tagPatients', e.detail)}
    />
  </div>
  <ResizablePanel
    leftResizable
    minWidth={240}
    maxWidth={patientSelectorCollapsed ? '80%' : '49%'}
    collapsible={false}
    width="40%"
    height="100%"
  >
    <div class="relative flex h-full w-full flex-col pt-4">
      <div class="flex w-full shrink-0 flex-wrap items-center justify-end gap-2 px-2">
        <div class="mr-2 w-0 flex-auto">
          {#if comparisonSpecs.length <= 1}
            <button
              class="btn btn-secondary flex max-w-full items-center"
              on:click={() => {
                editingSourceIndex = 0;
                showingSourceSelector = true;
              }}
            >
              <Fa icon={faFileLines} class="mr-2" />
              {#if comparisonSpecs.length > 0}
                <span class="block truncate">{comparisonSpecs[0].name}</span>
              {:else}
                <span class="block truncate">Select Spec</span>
              {/if}
            </button>
          {/if}
        </div>

        <button
          class="btn btn-tertiary shrink cursor-pointer text-clip"
          disabled={comparisonSpecs.length >= 3}
          on:click={() => {
            editingSourceIndex = null;
            showingSourceSelector = true;
          }}
          ><Fa icon={faPlus} class="mr-1 inline" />
          Comparison</button
        >

        <!-- Filter and Sort Menu -->
        <ActionMenuButton
          bind:visible={showingFilterMenu}
          buttonClass="btn-icon"
          buttonTitle="View options"
          align="right"
          menuWidth={280}
          singleClick={false}
        >
          {#snippet buttonContent()}
            <Fa icon={faFilter} />
          {/snippet}
          {#snippet options(dismiss: () => void)}
            <FilterSortMenu
              bind:selectedFilter
              bind:selectedSort
              {availableClasses}
              isNoteView={!!note}
            />
          {/snippet}
        </ActionMenuButton>

        <!-- Download Button -->
        {#if downloadResponses}
          <ActionMenuButton
            buttonClass="shrink-0 btn-icon"
            buttonTitle="Download Results"
            align="right"
            menuWidth={280}
            singleClick={false}
            disabled={!selectedPatient}
          >
            {#snippet buttonContent()}
              <Fa icon={faDownload} />
            {/snippet}
            {#snippet options(dismiss: () => void)}
              <ExtractionDownloadMenu
                disabled={!selectedPatient}
                on:download={(e) => {
                  const { patientId, csv } = e.detail;
                  const actualPatientId =
                    patientId === 'current' ? selectedPatient?.id || null : null;
                  downloadResponses(actualPatientId, csv);
                  dismiss();
                }}
              />
            {/snippet}
          </ActionMenuButton>
        {/if}

        <button
          class="btn-icon shrink-0"
          disabled={comparisonSpecs.length == 0 || !selectedPatient}
          on:click={() => {
            _loadModelOutputs(comparisonSpecs);
          }}><Fa icon={faRotateLeft} /></button
        >
      </div>
      {#if selectedFilter?.type || selectedFilter?.feedback || noteID != null}
        {@const hasFilter = selectedFilter?.type || selectedFilter?.feedback}
        <div
          class="mx-2 mt-2 flex items-center justify-between rounded-md bg-stone-100 px-4 py-1.5"
        >
          <div class="flex-auto text-sm font-medium text-stone-800">
            {#if noteID != null}In note <span class="font-mono">{noteID}</span>{#if hasFilter}
                &nbsp;&middot;&nbsp;{/if}{/if}
            {[
              ['Extraction Type', selectedFilter?.type],
              ['Feedback', selectedFilter?.feedback]
            ]
              .filter((el) => !!el[1])
              .map((el) => `${el[0]} = ${el[1]}`)
              .join(', ')}
          </div>
          <button class="btn-icon text-sm" on:click={clearFilter} title="Clear filter">
            <Fa icon={faXmark} />
          </button>
        </div>
      {/if}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
      <div
        class="min-h-0 w-full flex-auto overflow-x-auto"
        on:click={() => (selectedAnnotation = null)}
      >
        {#if loadingModelOutputs}
          <!-- Loading state for main content area -->
          <LoadingView text="Loading model outputs..." />
        {:else if comparisonSpecs.length == 0}
          <!-- Placeholder when no specs selected -->
          <div class="flex h-full w-full items-center justify-center">
            <div class="text-center text-gray-500">
              <div class="mb-2 text-lg">No extraction specs selected</div>
              <div class="text-sm">
                Click &ldquo;+ Comparison&rdquo; above to select at least one spec to compare.
              </div>
            </div>
          </div>
        {:else if currentExtractions.length == comparisonSpecs.length}
          <div class="flex h-full gap-2">
            {#each comparisonSpecs as source, i}
              {@const specID = source.id}
              {@const filteredExtractions = filterModelOutputs(
                currentExtractions[i] ?? [],
                selectedFilter
              )}
              <div
                class="h-full px-2 {comparisonSpecs.length == 1
                  ? 'w-full flex-auto pt-2'
                  : 'max-w-96 min-w-64 flex-1'} overflow-y-auto"
              >
                {#if comparisonSpecs.length > 1}
                  <ModelCardHeader
                    spec={source}
                    iconClass={ModelIconClasses[i]}
                    allowReplace
                    allowRemove={comparisonSpecs.length > 1}
                    on:replace={() => {
                      editingSourceIndex = i;
                      showingSourceSelector = true;
                    }}
                    on:remove={() => {
                      let idx = comparisonSpecs.indexOf(source);
                      comparisonSpecs = [
                        ...comparisonSpecs.slice(0, idx),
                        ...comparisonSpecs.slice(idx + 1)
                      ];
                    }}
                    on:edit={(e) => {
                      dispatch('editSpec', { spec: e.detail });
                    }}
                  />
                {/if}

                {#if filteredExtractions.length == 0}
                  <div class="p-4 text-center text-stone-500">
                    <div class="text-sm">
                      {#if extractionResults[i].extraction_run}No extractions found{:else}Extraction
                        not run{/if}
                    </div>
                    <div class="mt-1 text-xs text-stone-400">
                      {#if !extractionResults[i].extraction_run}
                        Click <span class="font-semibold"
                          ><Fa icon={faPlay} class="ml-1 inline" /> Extract</span
                        > to run extraction
                      {:else if (currentExtractions[i] ?? []).length > 0}
                        Adjust your filters to see the available extractions
                      {:else}
                        This model did not generate any extractions for this {!!note
                          ? 'note'
                          : 'patient'}
                      {/if}
                    </div>
                  </div>
                {/if}

                {#each filteredExtractions.sort(sortExtractions) as extraction, j}
                  {@const isHighlighted =
                    selectionHasExtraction(hoveredAnnotation, specID, extraction) ||
                    selectionHasExtraction(selectedAnnotation, specID, extraction)}
                  {@const isSelected = selectionHasExtraction(
                    selectedAnnotation,
                    specID,
                    extraction
                  )}
                  <ExtractionItem
                    {extraction}
                    {specID}
                    iconClass={ModelIconClasses[i]}
                    {isSelected}
                    {isHighlighted}
                    {noteAnnotations}
                    hasAnySelection={!!hoveredAnnotation || !!selectedAnnotation}
                    showNoteLink
                    onFeedbackChange={(extractionId, feedback) => {
                      onFeedbackChange({
                        extraction_id: extractionId,
                        approved: feedback.approved,
                        rejected: feedback.rejected,
                        comment: feedback.comment
                      });
                      // save locally as well
                      extractionResults = [
                        ...extractionResults.slice(0, i),
                        {
                          ...extractionResults[i],
                          extractions:
                            extractionResults[i].extractions?.map((e) =>
                              e.id == extractionId ? { ...e, feedback } : e
                            ) ?? null
                        },
                        ...extractionResults.slice(i + 1)
                      ];
                    }}
                    on:mouseenter={(e) => (hoveredAnnotation = e.detail)}
                    on:mouseleave={() => (hoveredAnnotation = null)}
                    on:select={(e) => {
                      console.log('selecting:', e.detail.annotations);
                      if (e.detail.isSelected) selectedAnnotation = null;
                      else selectedAnnotation = { annotations: e.detail.annotations };
                    }}
                    on:shownote={(e) => {
                      noteID = e.detail.note_id;
                      if (!!noteID && !!e.detail.annotations) {
                        setTimeout(() => {
                          selectedAnnotation = {
                            annotations: getFuzzyMatchedAnnotations(
                              e.detail.annotations,
                              noteAnnotations
                            )
                          };
                        });
                      }
                    }}
                  />
                {/each}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </ResizablePanel>
  <ExtractionSourceSelector
    {extractionSpecs}
    isOpen={showingSourceSelector}
    selectedSpec={editingSourceIndex !== null ? comparisonSpecs[editingSourceIndex] : null}
    fetchFilteredSpecs={fetchAvailableSpecs && note
      ? () => fetchAvailableSpecs!(note!.id)
      : undefined}
    on:close={() => (showingSourceSelector = false)}
    on:select={(e) => {
      let newSource = e.detail.spec;
      if (editingSourceIndex !== null) {
        let comparisonEditIdx = comparisonSpecs.indexOf(comparisonSpecs[editingSourceIndex]);
        comparisonSpecs = [
          ...comparisonSpecs.slice(0, comparisonEditIdx),
          newSource,
          ...comparisonSpecs.slice(comparisonEditIdx + 1)
        ];
      } else comparisonSpecs = [...comparisonSpecs, newSource];
      showingSourceSelector = false;
      editingSourceIndex = null;
    }}
    on:createSpec={(e) => {
      showingSourceSelector = false;
      dispatch('createSpec', e.detail);
    }}
    on:editSpec={(e) => {
      showingSourceSelector = false;
      dispatch('editSpec', e.detail);
    }}
  />
</div>
