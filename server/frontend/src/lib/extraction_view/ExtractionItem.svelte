<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type {
    NoteExtraction,
    Annotation,
    AnnotationSelection,
    ExtractionCitation
  } from '../extraction_types';
  import { areObjectsEqual } from '../utils/utils';
  import Fa from 'svelte-fa';
  import {
    faCircleQuestion,
    faExclamationCircle,
    faQuoteLeft,
    faWarning
  } from '@fortawesome/free-solid-svg-icons';
  import FeedbackEditor from './FeedbackEditor.svelte';

  type ExtractionAnnotation = Annotation & { extraction: NoteExtraction };

  export let extraction: NoteExtraction;
  export let specID: string;
  export let iconClass: string;
  export let isSelected: boolean = false;
  export let isHighlighted: boolean = false;
  export let noteAnnotations: ExtractionAnnotation[] = [];
  export let hasAnySelection: boolean = false;
  export let showNoteLink: boolean = false;
  export let onFeedbackChange: (
    extractionId: number,
    feedback: {
      approved: boolean;
      rejected: boolean;
      comment?: string;
    }
  ) => void;

  const dispatch = createEventDispatcher();
  let element: HTMLElement;

  // Find the matching annotation for this extraction
  $: matchingAnnotations = noteAnnotations.filter(
    (ann) => ann.source == specID && areObjectsEqual(ann.extraction, extraction)
  );

  function handleMouseEnter() {
    if (matchingAnnotations.length > 0) {
      dispatch('mouseenter', {
        annotations: matchingAnnotations
      });
    }
  }

  function handleMouseLeave() {
    dispatch('mouseleave');
  }

  function getMatchingAnnotations(citation: ExtractionCitation | null = null): Annotation[] {
    return noteAnnotations.filter((ann) => {
      if (!citation && ann.source == specID && areObjectsEqual(ann.extraction, extraction))
        return true;
      if (!citation)
        return extraction.citations.some((c) => {
          if (
            ann.note_id == c.note_id &&
            c.char_interval?.start_pos != null &&
            c.char_interval.end_pos != null &&
            ann.char_interval?.start_pos != null &&
            ann.char_interval.end_pos != null
          )
            return (
              ann.char_interval.start_pos < c.char_interval.end_pos &&
              ann.char_interval.end_pos > c.char_interval.start_pos
            );
        });
      else if (
        ann.source == specID &&
        areObjectsEqual(ann.extraction, extraction) &&
        ann.note_id == citation.note_id &&
        citation.char_interval?.start_pos != null &&
        citation.char_interval.end_pos != null &&
        ann.char_interval?.start_pos != null &&
        ann.char_interval.end_pos != null
      )
        return (
          ann.char_interval.start_pos < citation.char_interval.end_pos &&
          ann.char_interval.end_pos > citation.char_interval.start_pos
        );
      return false;
    });
  }

  function handleSelect() {
    dispatch('select', {
      isSelected,
      annotations: matchingAnnotations
    });
  }

  function handleFeedbackChange(feedback: {
    approved: boolean;
    rejected: boolean;
    comment?: string;
  }) {
    onFeedbackChange(extraction.id, feedback);
  }

  $: if (isSelected && !!element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions, a11y_click_events_have_key_events -->
<div
  bind:this={element}
  class="block w-full rounded-md p-4 text-left text-wrap whitespace-normal {isSelected
    ? 'border-2 border-stone-500'
    : 'hover:bg-stone-100'} {!isHighlighted && hasAnySelection ? 'opacity-30' : ''}"
  on:mouseenter={handleMouseEnter}
  on:mouseleave={handleMouseLeave}
  on:click|stopPropagation={!isSelected ? handleSelect : undefined}
>
  <div class="flex items-start gap-2">
    <div class="h-2 w-2 shrink-0 rounded-full {iconClass} mt-2"></div>
    <div class="flex-auto">
      <div class="mb-2 font-mono text-base">
        {extraction.extraction_class}
        {#if extraction.attributes?.uncertainty_flag ?? false}
          <Fa
            icon={faCircleQuestion}
            class="ml-1 inline text-stone-600"
            title="This extraction was flagged as uncertain"
          />
        {/if}
        {#if extraction.attributes?.conflict_flag ?? false}
          <Fa
            icon={faExclamationCircle}
            class="ml-1 inline text-stone-600"
            title="This extraction was flagged as based on conflicting information"
          />
        {/if}
      </div>
      <div class="mb-2">
        {#each Object.entries(extraction.attributes ?? {}) as [key, val] (key)}
          {#if isSelected || !['explanation', 'conflict_flag', 'uncertainty_flag'].includes(key)}
            {#if key == 'conflict_flag'}
              {#if val}
                <div class="text-sm">
                  <Fa icon={faExclamationCircle} class="mr-1 inline text-stone-600" />
                  Extraction may be based on conflicting information
                </div>
              {/if}
            {:else if key == 'uncertainty_flag'}
              {#if val}
                <div class="text-sm">
                  <Fa icon={faCircleQuestion} class="mr-1 inline text-stone-600" />
                  Extraction may be uncertain
                </div>
              {/if}
            {:else if key != 'explanation' || !!val}
              <div class="text-sm">
                <span class="mr-2 font-mono font-semibold">{key}</span>{val}
              </div>
            {/if}
          {/if}
        {/each}
      </div>
      {#if isSelected}
        <div class="space-y-2">
          {#each extraction.citations as citation, i (i)}
            <div class="flex w-full items-start gap-2">
              <Fa icon={faQuoteLeft} class="shrink-0 text-stone-600" />
              <div class="flex-auto">
                <div class="line-clamp-2 text-sm text-stone-700">
                  {citation.quote}
                </div>
                {#if showNoteLink && !!citation.note_id}
                  <button
                    class="mt-1 shrink cursor-pointer rounded-md bg-blue-300/50 px-2 py-0.5 text-sm font-semibold whitespace-nowrap text-gray-800 hover:bg-blue-400/50"
                    on:click|stopPropagation={() =>
                      dispatch('shownote', {
                        note_id: citation.note_id,
                        annotations: getMatchingAnnotations(citation)
                      })}
                  >
                    Show in Context</button
                  >
                {/if}
                {#if citation.char_interval?.start_pos == null}
                  <div class="mt-1 text-sm text-stone-600">
                    <Fa icon={faWarning} class="mr-2 inline" />No match to note text
                  </div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
    <div class="mt-1 shrink-0 self-start">
      <FeedbackEditor feedback={extraction.feedback} onFeedbackChange={handleFeedbackChange} />
    </div>
  </div>
</div>
