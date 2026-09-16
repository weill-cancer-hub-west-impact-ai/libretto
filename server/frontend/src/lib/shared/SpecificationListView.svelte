<script lang="ts">
  import type { BlockOrchestratorVariable, ExtractionSpec } from '$lib/extraction_types';
  import { createEventDispatcher, onMount } from 'svelte';
  import Fa from 'svelte-fa';
  import {
    faChevronDown,
    faChevronRight,
    faPencil,
    faPlus
  } from '@fortawesome/free-solid-svg-icons';
  import moment from 'moment';

  const dispatch = createEventDispatcher();

  export let specs: ExtractionSpec[] = [];
  export let selectedSpec: ExtractionSpec | null = null;
  export let newSpecName: string | null = null; // placeholder if creating a new spec
  export let showEditButton: boolean = false;
  export let showNewButton: boolean = false;
  export let compact: boolean = false;

  // Group specs by ancestry (parent_version_id)
  $: groupedSpecs = groupSpecsByAncestry(specs);
  $: expandedGroups = new Set<string>();

  interface SpecGroup {
    rootId: string;
    name: string;
    specs: ExtractionSpec[];
    currentSpec: ExtractionSpec;
    hasMultipleVersions: boolean;
  }

  // Recursive function to find the root spec ID for a given spec
  function findRootSpecId(specId: string, specMap: Map<string, ExtractionSpec>): string {
    const spec = specMap.get(specId);
    if (!spec || !spec.parent_version_id) {
      return specId; // This is the root
    }

    return findRootSpecId(spec.parent_version_id, specMap);
  }

  // Build ancestry maps: spec ID -> root spec ID and root spec ID -> list of descendant specs
  function buildAncestryMaps(specs: ExtractionSpec[]) {
    const specMap = new Map<string, ExtractionSpec>();
    const specToRoot = new Map<string, string>();
    const rootToSpecs = new Map<string, ExtractionSpec[]>();

    // First, create a map of all specs by ID
    for (const spec of specs) {
      specMap.set(spec.id, spec);
    }

    // Build the spec -> root mapping
    for (const spec of specs) {
      const rootId = findRootSpecId(spec.id, specMap);
      specToRoot.set(spec.id, rootId);

      if (!rootToSpecs.has(rootId)) {
        rootToSpecs.set(rootId, []);
      }
      rootToSpecs.get(rootId)!.push(spec);
    }

    return { specToRoot, rootToSpecs };
  }

  function groupSpecsByAncestry(specs: ExtractionSpec[]): SpecGroup[] {
    const { rootToSpecs } = buildAncestryMaps(specs);

    // Convert to grouped format
    return Array.from(rootToSpecs.entries())
      .map(([rootId, specsInGroup]) => {
        // Sort by version descending (newest first)
        const sortedSpecs = specsInGroup.sort((a, b) => {
          const versionA = a.spec_version ?? 1;
          const versionB = b.spec_version ?? 1;
          return versionB - versionA;
        });

        // Find current spec (is_current === true) or fall back to highest version
        const currentSpec = sortedSpecs.find((s) => s.is_current) || sortedSpecs[0];

        return {
          rootId,
          name: currentSpec.name, // Use current spec's name as the group name
          specs: sortedSpecs,
          currentSpec,
          hasMultipleVersions: sortedSpecs.length > 1
        };
      })
      .sort((a, b) => {
        // Sort groups by most recent modification date
        const dateA = moment(a.currentSpec.date_modified ?? a.currentSpec.date_added);
        const dateB = moment(b.currentSpec.date_modified ?? b.currentSpec.date_added);
        return dateB.valueOf() - dateA.valueOf();
      });
  }

  // Auto-expand groups when a non-current spec is selected
  onMount(() => {
    if (selectedSpec && groupedSpecs) {
      const selectedGroup = groupedSpecs.find((group) =>
        group.specs.some((spec) => spec.id === selectedSpec?.id)
      );

      if (selectedGroup && selectedGroup.hasMultipleVersions) {
        // Check if the selected spec is not the current spec
        const isNonCurrent = selectedSpec.id !== selectedGroup.currentSpec.id;
        if (isNonCurrent) {
          expandedGroups.add(selectedGroup.rootId);
          expandedGroups = new Set(expandedGroups); // Trigger reactivity
        }
      }
    }
  });

  function toggleGroup(groupRootId: string) {
    if (expandedGroups.has(groupRootId)) {
      expandedGroups.delete(groupRootId);
    } else {
      expandedGroups.add(groupRootId);
    }
    expandedGroups = new Set(expandedGroups); // Trigger reactivity
  }

  function selectSpec(spec: ExtractionSpec) {
    dispatch('select', { spec });
  }

  function editSpec(spec: ExtractionSpec) {
    dispatch('editSpec', { spec });
  }

  function createNewSpec() {
    dispatch('new');
  }

  function getDisplayName(spec: ExtractionSpec): string {
    if (spec.is_current) return spec.name;
    const version = spec.spec_version ?? 1;
    return `${spec.name} (Version ${version})`;
  }

  // Add selected spec to specs list if it's not already there (for cases where selectedSpec comes from elsewhere)
  $: specsToShow = [
    ...specs,
    ...(!!selectedSpec && !specs.find((s) => s.id == selectedSpec!.id) ? [selectedSpec] : [])
  ];
</script>

<div class="space-y-2">
  {#if newSpecName != null}
    <button
      class="block w-full rounded-md border-2 border-stone-500 px-3 py-2 text-left transition-colors"
    >
      <div class="flex items-center">
        <div class="flex-1">
          <!-- Spec Name -->
          <div class="font-medium text-stone-900">
            {newSpecName || 'Untitled'}
          </div>
        </div>
      </div>
    </button>
  {/if}
  {#each groupedSpecs as group (group.rootId)}
    <div>
      <!-- Main spec button (current version) -->
      <button
        class="block w-full rounded-md px-3 py-2 text-left transition-colors {selectedSpec?.id ===
        group.currentSpec.id
          ? 'border-2 border-stone-500'
          : 'hover:bg-stone-100'}"
        on:click={() => selectSpec(group.currentSpec)}
      >
        <div class="flex items-center">
          <!-- Disclosure arrow for multiple versions -->
          {#if group.hasMultipleVersions}
            <button
              on:click|stopPropagation={() => toggleGroup(group.rootId)}
              class="mr-2 p-1 text-stone-400 hover:text-stone-600"
              aria-label="Toggle versions"
            >
              <Fa
                icon={expandedGroups.has(group.rootId) ? faChevronDown : faChevronRight}
                class="text-xs"
              />
            </button>
          {/if}

          <div class="flex-1">
            <!-- Spec Name -->
            <div class="font-medium text-stone-900">
              {getDisplayName(group.currentSpec)}
            </div>
            {#if !compact}
              <div class="text-xs text-stone-600">
                {moment(group.currentSpec.date_modified ?? group.currentSpec.date_added)
                  .local()
                  .fromNow()}
              </div>

              <!-- Spec Preview -->
              <div class="mt-2 line-clamp-2 text-sm text-stone-600">
                {#if group.currentSpec.executor == 'noteextract'}
                  <span class="mr-1 rounded-sm bg-stone-200 px-1 py-0.5 text-xs">NoteExtract</span>
                  {group.currentSpec.content?.prompt ?? JSON.stringify(group.currentSpec.content)}
                {:else if group.currentSpec.executor == 'prompt_only'}
                  <span class="mr-1 rounded-sm bg-stone-200 px-1 py-0.5 text-xs">Prompt Only</span>
                  {group.currentSpec.content?.prompt ?? JSON.stringify(group.currentSpec.content)}
                {/if}
              </div>
            {/if}
          </div>

          <!-- Edit button -->
          {#if showEditButton}
            <button
              on:click|stopPropagation={() => editSpec(group.currentSpec)}
              class="ml-2 rounded p-1 text-gray-500 hover:text-gray-700"
              aria-label="Edit spec"
              title="Edit spec"
            >
              <Fa icon={faPencil} />
            </button>
          {/if}
        </div>
      </button>

      <!-- Version list (when expanded) -->
      {#if group.hasMultipleVersions && expandedGroups.has(group.rootId)}
        <div class="mt-1 ml-8 space-y-1">
          {#each group.specs as spec (spec.id)}
            {#if spec.id !== group.currentSpec.id}
              <button
                class="block w-full rounded-md px-3 py-2 text-left text-sm transition-colors {selectedSpec?.id ===
                spec.id
                  ? 'border-2 border-stone-500'
                  : 'hover:bg-stone-100'}"
                on:click={() => selectSpec(spec)}
              >
                <div class="flex items-center">
                  <div class="flex-1">
                    <div class="font-medium text-stone-700">
                      {getDisplayName(spec)}
                    </div>
                    {#if !compact}
                      <div class="text-xs text-stone-500">
                        {moment(spec.date_modified ?? spec.date_added)
                          .local()
                          .fromNow()}
                      </div>
                    {/if}
                  </div>

                  <!-- Edit button for version -->
                  {#if showEditButton}
                    <button
                      on:click|stopPropagation={() => editSpec(spec)}
                      class="ml-2 rounded p-1 text-gray-500 hover:text-gray-700"
                      aria-label="Edit spec version"
                      title="Edit spec version"
                    >
                      <Fa icon={faPencil} />
                    </button>
                  {/if}
                </div>
              </button>
            {/if}
          {/each}
        </div>
      {/if}
    </div>
  {/each}

  {#if showNewButton}
    <div class="sticky bottom-0 w-full bg-white py-4">
      <button on:click={createNewSpec} class="btn btn-secondary w-full cursor-pointer">
        <Fa icon={faPlus} class="mr-2 inline" />
        New Specification
      </button>
    </div>
  {/if}
</div>
