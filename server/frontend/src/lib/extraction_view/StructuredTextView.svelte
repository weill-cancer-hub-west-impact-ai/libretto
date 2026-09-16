<script lang="ts">
  import { Fa } from 'svelte-fa';
  import { faChevronUp, faChevronDown } from '@fortawesome/free-solid-svg-icons';
  import Markdown, { type Plugin } from 'svelte-exmarkdown';
  import type { Annotation, AnnotationSelection } from '../extraction_types';
  import rehypeRaw from 'rehype-raw';
  import rehypeNoteComponents from './rehype_svelte';
  import NoteAnnotation from './NoteAnnotation.svelte';
  import { setContext } from 'svelte';
  import { writable, type Writable } from 'svelte/store';
  import { areObjectsEqual } from '../utils/utils';
  import remarkBreaks from 'remark-breaks';
  import DeidentificationToken from './DeidentificationToken.svelte';

  export let text: string = '';
  export let title: string | undefined = undefined;
  export let collapsible: boolean = false;
  export let collapsed: boolean = false;

  export let annotations: Annotation[] = [];
  // map from source attribute of annotation to class name(s)
  export let annotationClasses: { [key: string]: string } = {};
  export let annotationIconClasses: { [key: string]: string } = {};
  export let multipleAnnotationClasses: string = '';

  export let hoveredAnnotation: AnnotationSelection | null = null;
  export let selectedAnnotation: AnnotationSelection | null = null;

  const transformHTML = (options = {}): Plugin => ({
    rehypePlugin: [rehypeRaw, options]
  });

  const addBreaks = (options = {}): Plugin => ({
    remarkPlugin: [remarkBreaks, options]
  });

  const processAnnotations = (): Plugin => ({
    rehypePlugin: [
      rehypeNoteComponents,
      {
        annotations,
        annotationClasses,
        annotationIconClasses,
        multipleAnnotationClasses
      }
    ]
  });

  const renderAnnotations: Plugin = {
    renderer: {
      noteannotation: NoteAnnotation,
      deidentification: DeidentificationToken
    }
  };

  const hoveredAnnotationStore: Writable<AnnotationSelection | null> = writable(null);
  setContext('hoveredAnnotation', hoveredAnnotationStore);
  const selectedAnnotationStore: Writable<AnnotationSelection | null> = writable(null);
  setContext('selectedAnnotation', selectedAnnotationStore);

  let oldHoveredAnnotation: AnnotationSelection | null = null;
  $: {
    if (!areObjectsEqual(oldHoveredAnnotation, $hoveredAnnotationStore)) {
      hoveredAnnotation = $hoveredAnnotationStore;
      oldHoveredAnnotation = $hoveredAnnotationStore;
    }
    if (!areObjectsEqual(oldHoveredAnnotation, hoveredAnnotation)) {
      $hoveredAnnotationStore = hoveredAnnotation;
      oldHoveredAnnotation = hoveredAnnotation;
    }
  }
  let oldSelectedAnnotation: AnnotationSelection | null = null;
  $: {
    if (!areObjectsEqual(oldSelectedAnnotation, $selectedAnnotationStore)) {
      selectedAnnotation = $selectedAnnotationStore;
      oldSelectedAnnotation = $selectedAnnotationStore;
    }
    if (!areObjectsEqual(oldSelectedAnnotation, selectedAnnotation)) {
      $selectedAnnotationStore = selectedAnnotation;
      oldSelectedAnnotation = selectedAnnotation;
    }
  }

  let transformedText: string = '';

  function addAnnotationsToText(rawText: string): string {
    console.log('annotations:', annotations);
    console.log('text:', rawText);
    // go backwards through annotations and add them to transformed text, independently by paragraph
    let textByParagraph = rawText.split('\n\n');
    let paragraphIndices = textByParagraph.reduce(
      (prev, curr) => [...prev, prev[prev.length - 1] + curr.length + 2],
      [0]
    );

    // first split all annotations by paragraph and merge overlapping annotations together
    let allBoundaries: {
      pos: number;
      type: 'start' | 'end' | 'paragraph';
      annotation?: Annotation;
    }[] = [];
    paragraphIndices.forEach((pi) => allBoundaries.push({ pos: pi, type: 'paragraph' }));
    annotations.forEach((ann) => {
      if (!ann.char_interval) return;
      allBoundaries.push({ pos: ann.char_interval.start_pos, type: 'start', annotation: ann });
      allBoundaries.push({ pos: ann.char_interval.end_pos, type: 'end', annotation: ann });
    });
    allBoundaries.sort((a, b) => a.pos - b.pos);

    let combinedAnnotations: { start_pos: number; end_pos: number; annotations: Annotation[] }[] =
      [];
    allBoundaries.forEach((b) => {
      if (b.type == 'start' || b.type == 'paragraph') {
        let existing: Annotation[] = [];
        if (combinedAnnotations.length > 0) {
          let last = combinedAnnotations[combinedAnnotations.length - 1];
          if (last.end_pos >= rawText.length) {
            combinedAnnotations[combinedAnnotations.length - 1] = {
              start_pos: last.start_pos,
              end_pos: b.pos,
              annotations: last.annotations
            };
            existing = last.annotations;
          }
        }
        if (b.type == 'start') existing = [...existing, b.annotation!];
        if (existing.length > 0)
          combinedAnnotations.push({
            start_pos: b.pos,
            end_pos: rawText.length,
            annotations: existing
          });
      } else if (b.type == 'end') {
        let last = combinedAnnotations[combinedAnnotations.length - 1];
        combinedAnnotations[combinedAnnotations.length - 1] = {
          start_pos: last.start_pos,
          end_pos: b.pos,
          annotations: last.annotations
        };
      }
    });
    combinedAnnotations = combinedAnnotations.filter(
      (segment) => segment.start_pos < segment.end_pos
    );

    let result = rawText;
    combinedAnnotations.toReversed().forEach((segment) => {
      result =
        result.substring(0, segment.start_pos) +
        `<NoteAnnotation pos=${segment.start_pos}>` +
        result.substring(segment.start_pos, segment.end_pos) +
        `</NoteAnnotation>` +
        result.substring(segment.end_pos);
    });
    return result;
  }

  $: if (text.length > 0) {
    transformedText = text;
    if (annotations.length > 0) transformedText = addAnnotationsToText(transformedText);
    transformedText = transformedText.replaceAll(
      /(\*{3,}\W+)*\*{3,}/g,
      '<deidentification></deidentification>'
    );
  } else {
    transformedText = '';
  }

  function clearSelection() {
    selectedAnnotation = null;
  }
</script>

<div class="flex flex-col {collapsible && !collapsed ? 'min-h-1/4 flex-auto' : 'h-full'}">
  {#if title}
    <button
      class="block flex w-full shrink-0 cursor-pointer items-center gap-2 p-2 text-left hover:opacity-50"
      on:click={() => (collapsed = !collapsed)}
    >
      {#if collapsible}
        <Fa icon={collapsed ? faChevronUp : faChevronDown} />
      {/if}
      <div class="text-sm font-semibold uppercase">{title}</div>
    </button>
  {/if}
  {#if !collapsible || !collapsed}
    <div
      class="markdown-container min-h-0 w-full flex-auto overflow-auto p-4 text-sm transition-colors duration-500 {!!selectedAnnotation ||
      !!hoveredAnnotation
        ? 'text-black/50'
        : 'text-black'}"
      on:click={clearSelection}
    >
      <div class="rounded-lg border-2 border-stone-300/50 bg-white p-4 shadow-lg">
        {#key annotations}
          <Markdown
            md={transformedText}
            plugins={[addBreaks(), transformHTML(), processAnnotations(), renderAnnotations]}
          />
        {/key}
      </div>
    </div>
  {/if}
</div>
