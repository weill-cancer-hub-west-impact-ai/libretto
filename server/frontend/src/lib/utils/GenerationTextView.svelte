<script lang="ts">
  import Fa from 'svelte-fa';
  import { faPlay, faHistory, faPaperPlane } from '@fortawesome/free-solid-svg-icons';
  import ActionMenuButton from '$lib/utils/ActionMenuButton.svelte';
  import type { ExtractionSpec } from '$lib/extraction_types';
  import { createEventDispatcher, getContext } from 'svelte';
  import moment from 'moment';

  export let generationPrompt: string = '';
  export let showHistory: boolean = false;
  export let multiline: boolean = false;
  export let placeholder: string = '';
  export let disabled: boolean = false;

  let dispatch = createEventDispatcher();

  let historyMenuVisible: boolean = false;
  export let promptHistory: Array<{
    date_added: string;
    prompt: string;
    response: string;
  }> = [];

  function selectHistoryItem(prompt: string) {
    generationPrompt = prompt;
    historyMenuVisible = false;
  }

  async function handleGenerateSubmit() {
    console.log('generate submit');
    if (!generationPrompt.trim()) return;
    dispatch('generate', { prompt: generationPrompt.trim() });
  }
</script>

<div
  class="{multiline
    ? 'h-full'
    : ''} w-full rounded-[8px] bg-gradient-to-br from-blue-600 via-purple-500 to-rose-500 p-0.5"
>
  <form
    on:submit|preventDefault={handleGenerateSubmit}
    class="relative flex {multiline ? 'h-full' : ''} w-full flex-col rounded-md bg-white"
  >
    <!-- Text Area -->
    {#if multiline}
      <textarea
        bind:value={generationPrompt}
        {placeholder}
        class="h-full resize-none rounded-md border-0 p-3 text-sm focus:ring-0 focus:outline-none"
        {disabled}
      ></textarea>
    {:else}
      <input
        type="text"
        bind:value={generationPrompt}
        {placeholder}
        {disabled}
        class="rounded-md border-0 p-3 text-sm focus:ring-0 focus:outline-none"
      />
    {/if}

    <!-- Action Buttons -->
    <div class="absolute {multiline ? 'bottom-2' : 'top-1.5'} right-2 flex items-center gap-2">
      {#if showHistory}
        <ActionMenuButton
          onShow={() => dispatch('history')}
          bind:visible={historyMenuVisible}
          buttonClass="flex h-8 w-8 items-center justify-center rounded-md bg-gray-500 text-white hover:bg-gray-600 focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:outline-none"
          buttonTitle="Recent prompts"
          align="right"
          menuWidth={300}
        >
          {#snippet buttonContent()}
            <Fa icon={faHistory} class="h-3 w-3" />
          {/snippet}
          {#snippet options(dismiss: () => void)}
            <div class="py-1" role="none">
              {#if promptHistory.length == 0}
                <div class="px-4 py-2 text-sm text-gray-500">No recent prompts</div>
              {:else}
                {#each promptHistory as item}
                  <button
                    on:click={() => selectHistoryItem(item.prompt)}
                    class="group flex w-full items-start px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
                    role="menuitem"
                  >
                    <div class="min-w-0 flex-1">
                      <div class="truncate text-sm font-medium text-gray-900">
                        {item.prompt.length > 60
                          ? item.prompt.substring(0, 60) + '...'
                          : item.prompt}
                      </div>
                      <div class="text-xs text-gray-500">
                        {moment.utc(item.date_added).local().fromNow()}
                      </div>
                    </div>
                  </button>
                {/each}
              {/if}
            </div>
          {/snippet}
        </ActionMenuButton>
      {/if}

      <!-- Send Button -->
      <button
        type="submit"
        on:click={handleGenerateSubmit}
        disabled={!generationPrompt.trim() || disabled}
        class="flex h-8 w-8 items-center justify-center rounded-md bg-purple-600 text-white hover:bg-purple-700 focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Send generation prompt"
      >
        <Fa icon={faPaperPlane} class="h-3 w-3" />
      </button>
    </div>
  </form>
</div>
