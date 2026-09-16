<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';
  import { faRetweet, faXmark, faMessage } from '@fortawesome/free-solid-svg-icons';
  import type { ExtractionSpec } from '../extraction_types';

  export let spec: ExtractionSpec;
  export let iconClass: string;
  export let allowReplace: boolean = true;
  export let allowRemove: boolean = true;

  const dispatch = createEventDispatcher();

  function handleReplace() {
    dispatch('replace', spec);
  }

  function handleRemove() {
    dispatch('remove', spec);
  }
</script>

<div class="sticky top-0 z-10 my-2 mb-2 border-b border-stone-800 bg-white">
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div
    class="flex w-full cursor-pointer items-baseline gap-2 rounded-t-md p-4 text-left hover:bg-stone-100"
    on:click|stopPropagation={handleReplace}
  >
    <div class="h-2 w-2 shrink-0 rounded-full {iconClass}"></div>
    <div class="flex-auto space-y-1">
      <div class="flex w-full items-center gap-2">
        <div class="flex-auto text-sm font-bold">
          {spec.name}
        </div>
        {#if allowReplace}
          <button
            on:click|stopPropagation={handleReplace}
            class="btn-icon-small"
            aria-label="Choose a different model to compare"
            title="Choose a different model to compare"
          >
            <Fa icon={faRetweet} />
          </button>
        {/if}
        {#if allowRemove}
          <button
            on:click|stopPropagation={handleRemove}
            class="btn-icon-small"
            aria-label="Remove model from comparison"
            title="Remove model from comparison"
          >
            <Fa icon={faXmark} />
          </button>
        {/if}
      </div>
    </div>
  </div>
</div>
