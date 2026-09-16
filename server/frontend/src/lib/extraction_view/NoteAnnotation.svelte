<script lang="ts">
  import { getContext, onMount } from 'svelte';
  import { type Annotation, type AnnotationSelection } from '../extraction_types';
  import type { Writable } from 'svelte/store';
  import { areObjectsEqual, areSetsEqual } from '../utils/utils';

  const hoveredAnnotation: Writable<AnnotationSelection | null> = getContext('hoveredAnnotation');
  const selectedAnnotation: Writable<AnnotationSelection | null> = getContext('selectedAnnotation');

  export let pos: number = 0;
  export let annotations: Annotation[] = [];
  export let annotationIconClasses: { [key: string]: string } = {};
  export let className: string = '';

  export let highlightContainer: HTMLElement;

  let showTooltip = false;

  function isSelected(
    anns: Annotation[],
    selection: {
      annotations?: Annotation[] | null;
      source?: string | null;
    } | null
  ): boolean {
    if (selection == null || (selection.source == null && selection.annotations == null))
      return false;
    if (selection.source != null && !!anns.find((ann) => ann.source == selection.source))
      return true;
    if (
      selection.annotations != null &&
      selection.annotations.some((ann) => !!anns.find((x) => areObjectsEqual(x, ann)))
    )
      return true;
    return false;
  }

  $: if (
    !!$selectedAnnotation &&
    !!highlightContainer &&
    isSelected(annotations, $selectedAnnotation)
  ) {
    highlightContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
</script>

<div class="relative inline">
  <span
    role="button"
    tabindex="0"
    bind:this={highlightContainer}
    class="{className} cursor-pointer hover:rounded {!!$selectedAnnotation &&
    isSelected(annotations, $selectedAnnotation)
      ? 'font-bold'
      : ''} {(!!$selectedAnnotation && isSelected(annotations, $selectedAnnotation)) ||
    (!!$hoveredAnnotation && isSelected(annotations, $hoveredAnnotation))
      ? 'text-black'
      : !!$selectedAnnotation || !!$hoveredAnnotation
        ? 'text-black/50'
        : 'text-black'}"
    on:mouseenter={() => {
      $hoveredAnnotation = { annotations };
      showTooltip = true;
    }}
    on:mouseleave={() => {
      $hoveredAnnotation = null;
      showTooltip = false;
    }}
    on:click|stopPropagation={() => ($selectedAnnotation = { annotations })}
    on:keydown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        $selectedAnnotation = { annotations };
      }
    }}><slot /></span
  >{#if showTooltip && annotations.length > 0}
    <div
      class="absolute bottom-full left-0 z-10 mb-1 transform rounded-md border border-gray-300/50 bg-gray-100 p-2 text-sm whitespace-nowrap text-gray-800 shadow-lg"
    >
      <div class="space-y-1">
        {#each annotations as annotation}
          <div class="flex items-center gap-2">
            {#if !!annotationIconClasses[annotation.source]}
              <span class="h-3 w-3 rounded-full {annotationIconClasses[annotation.source]}"></span>
            {/if}
            <span class="font-semibold">{annotation.sourceName ?? annotation.source}</span>
            {#if annotation.description}
              <span class="font-mono text-gray-600">{annotation.description}</span>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>
