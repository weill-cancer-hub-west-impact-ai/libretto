<script lang="ts">
  import Fa from 'svelte-fa';
  import { faChevronDown, faChevronRight } from '@fortawesome/free-solid-svg-icons';

  export let data: any;
  export let name: string = '';
  export let indentLevel: number = 0;

  let isExpanded: boolean = false;

  function isObject(value: any): boolean {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function isArray(value: any): boolean {
    return Array.isArray(value);
  }

  function isPrimitive(value: any): boolean {
    return (
      value === null ||
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean'
    );
  }

  function isLongString(value: any): boolean {
    return typeof value === 'string' && value.length > 1000;
  }

  function isSingleLevelObject(value: any): boolean {
    return isObject(value) && Object.values(value).every((v) => !isObject(v) && !isArray(v));
  }

  function formatValue(value: any): string {
    if (value === null) return 'null';
    if (typeof value === 'string') {
      return `"${value}"`;
    }
    if (isSingleLevelObject(value)) {
      return Object.entries(value)
        .map(([k, v]) => `${k} = ${formatValue(v)}`)
        .join(', ');
    }
    return String(value);
  }

  function getKeys(obj: any): string[] {
    if (isArray(obj)) {
      return obj.map((_, index) => index.toString());
    }
    return Object.keys(obj);
  }

  $: hasChildren = isObject(data) || isArray(data);
  $: shouldShowInline = (isPrimitive(data) || isSingleLevelObject(data)) && !isLongString(data);
</script>

<!-- Current row -->
{#if indentLevel > 0}
  <div
    class="flex items-center py-1 text-sm hover:bg-gray-50"
    style="padding-left: {(indentLevel - 1) * 16}px"
  >
    <!-- Disclosure triangle or spacer -->
    {#if hasChildren}
      <div class="flex justify-center">
        <button
          class="h-4 w-4 text-xs text-gray-500 hover:opacity-50"
          on:click={() => (isExpanded = !isExpanded)}
        >
          <Fa icon={isExpanded ? faChevronDown : faChevronRight} />
        </button>
      </div>
    {/if}

    <div class="flex-auto">
      <!-- Key name -->
      {#if name}
        <span class="mr-2 font-semibold text-gray-500">{name}</span>
      {/if}

      <!-- Value (if primitive) -->
      {#if shouldShowInline && !(hasChildren && (isExpanded || indentLevel == 0))}
        <span class="font-mono text-sm text-gray-900">{formatValue(data)}</span>
      {:else if isPrimitive(data) && isLongString(data)}
        <span class="mr-2 flex-1 font-mono text-sm text-gray-900">
          {isExpanded ? formatValue(data) : `"${data.slice(0, 50)}..."`}
        </span>
        <button
          class="ml-auto text-xs text-blue-500 hover:text-blue-700"
          on:click={() => (isExpanded = !isExpanded)}
        >
          {isExpanded ? 'collapse' : 'expand'}
        </button>
      {:else if hasChildren}
        {@const numChildren = isArray(data) ? data.length : Object.keys(data).length}
        <span class="text-xs text-gray-500">
          {numChildren} value{numChildren != 1 ? 's' : ''}
        </span>
      {/if}
    </div>
  </div>
{/if}

<!-- Children (rendered outside parent div to maintain flat hierarchy) -->
{#if hasChildren && (isExpanded || indentLevel == 0)}
  {#each getKeys(data) as key}
    <svelte:self
      data={data[key]}
      name={isArray(data) ? `[${key}]` : key}
      indentLevel={indentLevel + 1}
    />
  {/each}
{/if}
