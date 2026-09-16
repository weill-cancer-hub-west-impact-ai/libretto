<script lang="ts">
  import { faPlus } from '@fortawesome/free-solid-svg-icons';
  import Fa from 'svelte-fa';

  // Generic item interface - using any to be compatible with different item types
  type TaggableItem = {
    id: string;
    tags?: string[];
    [key: string]: any; // Allow additional properties
  };

  // Props
  export let items: TaggableItem[] = [];
  export let allTags: string[] = [];
  export let onTagToggle: (tag: string, include: boolean, items: TaggableItem[]) => void;

  function handleTagToggle(tag: string, include: boolean) {
    onTagToggle(tag, include, items);
  }

  function handleNewTag() {
    const newTag = prompt('Enter new tag name:');
    if (newTag && newTag.trim()) {
      handleTagToggle(newTag.trim(), true);
    }
  }

  function getTagState(tag: string): 'checked' | 'unchecked' | 'indeterminate' {
    if (items.length === 0) return 'unchecked';

    const withTag = items.filter((item) => item.tags?.includes(tag));

    if (withTag.length === 0) return 'unchecked';
    if (withTag.length === items.length) return 'checked';
    return 'indeterminate';
  }
</script>

{#if allTags.length > 0}
  {#each allTags as tag}
    {@const hasTag = getTagState(tag) === 'checked'}
    <button
      class="flex w-full items-center px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
      on:click={() => handleTagToggle(tag, !hasTag)}
    >
      <input
        type="checkbox"
        checked={hasTag}
        indeterminate={getTagState(tag) === 'indeterminate'}
        on:click|stopPropagation={() => handleTagToggle(tag, !hasTag)}
        class="mr-3 h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
      />
      {tag}
    </button>
  {/each}
  <div class="my-1 border-t border-gray-200"></div>
{/if}
<button
  class="flex w-full items-center px-3 py-2 text-left text-sm font-medium text-sky-600 hover:bg-sky-50"
  on:click={handleNewTag}
>
  <Fa icon={faPlus} class="mr-3 h-4 w-4" />
  New Tag
</button>
