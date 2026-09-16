<svelte:options accessors />

<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import Fa from 'svelte-fa';
  import {
    faCommentDots,
    faCubes,
    faHighlighter,
    faXmark
  } from '@fortawesome/free-solid-svg-icons';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import SpecSidebar from './SpecSidebar.svelte';
  import NoteExtractSpecEditor from './NoteExtractSpecEditor.svelte';
  import PromptOnlySpecEditor from './PromptOnlySpecEditor.svelte';
  import { DefaultSpecContent, type ExtractionSpec } from '$lib/extraction_types';
  import { v4 as uuid } from 'uuid';
  import { beforeNavigate, goto } from '$app/navigation';
  import { selectedPatient, specs } from '$lib/stores/data';
  import ResizablePanel from '$lib/utils/ResizablePanel.svelte';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';

  export let fetchSpecs: (() => Promise<ExtractionSpec[]>) | undefined = undefined;

  const dispatch = createEventDispatcher();

  export let selectedSpec: ExtractionSpec | null = null;
  $: if (!!$specs && $specs.length > 0 && selectedSpec === null) {
    selectedSpec = $specs[0];
  }

  let mounted: boolean = false;
  onMount(() => (mounted = true));

  export let showHeader: boolean = true;
  let loadingSpecs: boolean = false;
  let saving: boolean = false;
  let uploading: boolean = false;

  let newSelectedID: string | null = null;
  let extractAfterRefresh: boolean = false;

  // Track whether the currently-displayed editor has unsaved changes.
  // The child editor reports this via bind:hasChanges.
  let editorHasChanges: boolean = false;
  let editorNewSpecName: string = '';

  let showingNewSpecDialog: boolean = false;
  $: (selectedSpec, (showingNewSpecDialog = false));

  $: isNewSpec = $specs != null && !!selectedSpec && !$specs.find((s) => s.id == selectedSpec?.id);

  let needsSpecRefresh: boolean = false;
  $: if ((mounted || needsSpecRefresh) && fetchSpecs) {
    loadingSpecs = true;
    refreshSpecs();
  }

  function confirmChangeSelectedSpec(spec: ExtractionSpec) {
    if (!editorHasChanges) {
      selectedSpec = spec;
    } else if (
      confirm('The specification has unsaved changes. Are you sure you want to discard them?')
    )
      selectedSpec = spec;
  }

  beforeNavigate(({ cancel }) => {
    if (
      editorHasChanges &&
      !confirm('The specification has unsaved changes. Are you sure you want to discard them?')
    )
      cancel();
  });

  async function refreshSpecs() {
    if (!fetchSpecs) {
      loadingSpecs = false;
      needsSpecRefresh = false;
      return;
    }
    try {
      $specs = await fetchSpecs();
      loadingSpecs = false;
      needsSpecRefresh = false;
      if (selectedSpec) selectedSpec = $specs.find((s) => s.id == selectedSpec!.id) ?? null;
    } catch (err) {
      console.error('Error loading specs:', err);
      loadingSpecs = false;
      needsSpecRefresh = false;
    } finally {
      if (!!newSelectedID) {
        selectedSpec = $specs?.find((s) => s.id == newSelectedID) ?? null;
      }
      newSelectedID = null;
      if (extractAfterRefresh) {
        dispatch('extract', { spec: selectedSpec });
        extractAfterRefresh = false;
      }
    }
  }

  function handleClose() {
    if (
      !editorHasChanges ||
      confirm('The specification has unsaved changes. Are you sure you want to discard them?')
    ) {
      if (!!selectedSpec && !$specs?.find((s) => s.id == selectedSpec?.id)) {
        selectedSpec = !!$specs && $specs.length > 0 ? $specs[0] : null;
      }
      dispatch('close');
    }
  }

  async function handleDelete() {
    if (!selectedSpec) return;

    if (!confirm(`Are you sure you want to delete the specification "${selectedSpec.name}"?`)) {
      return;
    }

    if (isNewSpec) {
      selectedSpec = ($specs ?? [null])[0];
      return;
    }

    try {
      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/specs/${selectedSpec.id}`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        console.error('Failed to delete spec');
        alert('Failed to delete specification. Please try again.');
      }
    } catch (error) {
      console.error('Error deleting spec:', error);
      alert('Error deleting specification. Please try again.');
    } finally {
      needsSpecRefresh = true;
      selectedSpec = null;
    }
  }

  function makeNewName(baseName: string): string {
    let newName = baseName;
    if (!!$specs && $specs.find((s) => s.name == newName)) {
      let idx = 2;
      while ($specs.find((s) => s.name == newName + ` ${idx}`)) idx++;
      newName += ` ${idx}`;
    }
    return newName;
  }

  async function handleDuplicate() {
    if (!selectedSpec) return;

    const newId = uuid();
    confirmChangeSelectedSpec({
      id: newId,
      name: makeNewName(`${selectedSpec.name}`),
      executor: selectedSpec.executor,
      content: { ...selectedSpec.content },
      is_current: true
    });
  }

  export async function selectSpec(id: string) {
    await refreshSpecs();
    selectedSpec = $specs?.find((s) => s.id == id) ?? null;
    if (!selectedSpec) newSpec(id);
  }

  export async function newSpec(
    id: string | null = null,
    executor: 'noteextract' | 'prompt_only' = 'noteextract'
  ) {
    showingNewSpecDialog = false;
    const newId = id ?? uuid();
    let newName = `New Specification`;
    if ($specs?.find((s) => s.name == newName)) {
      let idx = 2;
      while ($specs.find((s) => s.name == newName + ` ${idx}`)) idx++;
      newName = `New Specification ${idx}`;
    }

    setTimeout(() =>
      confirmChangeSelectedSpec({
        id: newId,
        name: newName,
        executor: executor,
        content: DefaultSpecContent[executor],
        is_current: true
      })
    );
  }

  async function handleDownload() {
    if (!selectedSpec) return;

    try {
      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/specs/${selectedSpec.id}/download`
      );

      if (!response.ok) {
        console.error('Failed to download spec');
        alert('Failed to download specification. Please try again.');
        return;
      }

      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `spec_${selectedSpec.name}.json`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
        if (filenameMatch) filename = filenameMatch[1];
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading spec:', error);
      alert('Error downloading specification. Please try again.');
    }
  }

  async function handleFileUpload(file: File) {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.json')) {
      alert('Please select a JSON file.');
      return;
    }

    if (
      editorHasChanges &&
      !confirm('The specification has unsaved changes. Are you sure you want to discard them?')
    )
      return;
    uploading = true;

    try {
      const fileContent = await file.text();
      let specData;
      try {
        specData = JSON.parse(fileContent);
      } catch (error) {
        alert('Invalid JSON file format.');
        return;
      }

      if (!specData || typeof specData !== 'object') {
        alert('JSON file must contain a specification object.');
        return;
      }

      const requiredFields = ['name', 'prompt', 'schema', 'examples'];
      const missingFields = requiredFields.filter((field) => !specData[field]);
      if (missingFields.length > 0) {
        alert(`Specification is missing required fields: ${missingFields.join(', ')}`);
        return;
      }

      let newID = uuid();
      saving = true;
      const response = await authenticatedFetch(`/api/projects/${$projectID}/specs/${newID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...specData })
      });

      if (!response.ok) {
        saving = false;
        console.error('Failed to save spec');
        alert('Failed to upload specification. Please try again.');
      } else {
        needsSpecRefresh = true;
        newSelectedID = (await response.json()).spec_id;
        saving = false;
      }
    } catch (error) {
      console.error('Error uploading spec:', error);
      alert(
        error instanceof Error ? error.message : 'Error uploading specification. Please try again.'
      );
    } finally {
      uploading = false;
    }
  }

  function handleSaved(e: CustomEvent<{ newSelectedID: string }>) {
    newSelectedID = e.detail.newSelectedID;
    needsSpecRefresh = true;
  }

  function handleExtractAfterRefresh() {
    extractAfterRefresh = true;
  }
</script>

<!-- Modal content -->
<div class="flex h-full w-full flex-col">
  {#if showHeader}
    <div class="flex shrink-0 items-center justify-between px-6 pt-4">
      <h2 id="modal-title" class="text-lg font-bold text-gray-900">Specification Editor</h2>
      <button
        on:click={handleClose}
        class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
        aria-label="Close modal"
      >
        <Fa icon={faXmark} />
      </button>
    </div>
  {/if}

  <!-- Content -->
  <div class="relative flex min-h-0 w-full flex-auto">
    <!-- Sidebar -->
    <ResizablePanel
      height="100%"
      rightResizable
      width={400}
      maxWidth="50%"
      minWidth={300}
      collapsible
    >
      <SpecSidebar
        bind:specs={$specs}
        {selectedSpec}
        newSpecName={isNewSpec ? editorNewSpecName : null}
        on:new={() => (showingNewSpecDialog = true)}
        on:select={(e) => confirmChangeSelectedSpec(e.detail.spec)}
        on:delete={handleDelete}
        on:duplicate={handleDuplicate}
        on:upload={(e) => handleFileUpload(e.detail.file)}
        on:download={handleDownload}
      />
    </ResizablePanel>

    <!-- Main Editor Area -->
    {#if showingNewSpecDialog}
      <div class="mt-8 flex h-full w-full flex-col items-center justify-center gap-4">
        <h1 class="text-xl font-semibold">New Specification</h1>
        <div class="mb-8 max-w-3/4 text-center text-base text-stone-700">
          Choose a format for the new specification:
        </div>
        <div class="flex max-w-3/4 justify-center gap-4">
          <button
            class="block flex flex-1 cursor-pointer flex-col items-center justify-start gap-4 rounded-lg border-2 border-stone-300/50 p-4 transition-all hover:shadow-lg"
            on:click={() => newSpec(null, 'prompt_only')}
          >
            <Fa icon={faCommentDots} class="text-4xl text-stone-300" />
            <div class="text-lg font-bold">Prompt Only</div>
            <div class="text-sm text-stone-700">Run a free-text prompt across all notes</div>
          </button>
          <button
            class="block flex flex-1 cursor-pointer flex-col items-center justify-start gap-4 rounded-lg border-2 border-stone-300/50 p-4 transition-all hover:shadow-lg"
            on:click={() => newSpec(null, 'noteextract')}
          >
            <Fa icon={faHighlighter} class="text-4xl text-stone-300" />
            <div class="text-lg font-bold">NoteExtract</div>
            <div class="text-sm text-stone-700">
              Suitable for extracting information explicitly mentioned in text without reasoning
              across multiple notes
            </div>
          </button>
        </div>
      </div>
    {:else if selectedSpec}
      {#if selectedSpec.executor === 'noteextract'}
        <NoteExtractSpecEditor
          {selectedSpec}
          {saving}
          bind:hasChanges={editorHasChanges}
          bind:newSpecName={editorNewSpecName}
          on:saved={handleSaved}
          on:extract={(e) => dispatch('extract', e.detail)}
          on:extractAfterRefresh={handleExtractAfterRefresh}
        />
      {:else if selectedSpec.executor === 'prompt_only'}
        <PromptOnlySpecEditor
          {selectedSpec}
          {saving}
          bind:hasChanges={editorHasChanges}
          bind:newSpecName={editorNewSpecName}
          on:saved={handleSaved}
          on:extract={(e) => dispatch('extract', e.detail)}
          on:extractAfterRefresh={handleExtractAfterRefresh}
        />
      {:else}
        <div class="flex h-full flex-auto items-center justify-center text-stone-500">
          <p>No editor available for executor "{selectedSpec.executor}"</p>
        </div>
      {/if}
    {:else}
      <div class="flex h-full flex-auto items-center justify-center text-stone-500">
        <p>No specification selected</p>
      </div>
    {/if}

    {#if loadingSpecs}
      <div class="absolute top-0 left-0 h-full w-full bg-white">
        <LoadingView text="Loading specifications..." />
      </div>
    {/if}
  </div>
</div>
