<script lang="ts">
  import type { ExtractionSpec } from '$lib/extraction_types';
  import { createEventDispatcher, getContext, onMount } from 'svelte';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';
  import GenerationTextView from '$lib/utils/GenerationTextView.svelte';

  export let selectedSpec: ExtractionSpec | null = null;
  export let generationPaneVisible: boolean = false;
  export let generationPrompt: string = '';
  export let generationExplanation: string = '';
  export let generationError: string = '';
  export let generating: boolean = false;
  export let historyType: string = 'spec_generation_noteextract';

  let dispatch = createEventDispatcher();

  let promptHistory: Array<{
    id: number;
    date_added: string;
    type: string;
    spec_id: string | null;
    prompt: string;
    response: string;
  }> = [];

  async function loadPromptHistory() {
    try {
      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/prompt_history?type=${historyType}&limit=5`
      );
      if (response.ok) {
        promptHistory = await response.json();
      }
    } catch (error) {
      console.error('Error loading prompt history:', error);
    }
  }

  async function handleGenerateSubmit(e: CustomEvent<{ prompt: string }>) {
    if (!selectedSpec) return;
    dispatch('generate', e.detail);
  }
</script>

<div class="space-y-4">
  <!-- Generation Error Display -->
  {#if generationError}
    <div class="rounded-md bg-red-50 p-3 text-sm text-red-700">
      {generationError}
    </div>
  {/if}

  {#if generationPaneVisible}
    <div class="h-48 max-h-1/2 w-full">
      <GenerationTextView
        multiline
        showHistory
        {promptHistory}
        placeholder="Describe how you want to create or modify the specification..."
        on:history={() => loadPromptHistory()}
        bind:generationPrompt
        disabled={generating}
        on:generate={handleGenerateSubmit}
      />
    </div>
  {/if}

  <!-- Generation Explanation Display -->
  {#if generationExplanation}
    <div class="mb-4 rounded-md bg-gray-100 p-3 text-sm text-gray-800">
      <span class="font-semibold">AI Response:</span>
      {generationExplanation}
    </div>
  {/if}
</div>
