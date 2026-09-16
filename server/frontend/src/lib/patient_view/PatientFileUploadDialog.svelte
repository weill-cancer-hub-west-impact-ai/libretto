<script lang="ts">
  import { createEventDispatcher, getContext } from 'svelte';
  import Fa from 'svelte-fa';
  import {
    faXmark,
    faUpload,
    faChevronDown,
    faChevronRight
  } from '@fortawesome/free-solid-svg-icons';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';

  export let isOpen: boolean = false;

  const dispatch = createEventDispatcher();

  const exampleJSON = `[
  {
    "patient_id": "patient_001",
    "notes": [
      {
        "note_id": "note_001",
        "note_text": "Patient presents with...",
        "date": "2023-01-15",
        "metadata": {}
      }
    ],
    "metadata": {}
  }
]`;

  let fileInput: HTMLInputElement;
  let selectedFile: File | null = null;
  let isDragOver = false;
  let showInstructions = false;
  let uploading = false;
  let errorMessage = '';

  function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files[0]) {
      const file = target.files[0];
      if (validateFile(file)) {
        selectedFile = file;
        errorMessage = '';
      }
    }
  }

  function validateFile(file: File): boolean {
    const allowedExtensions = ['.csv', '.json'];
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!allowedExtensions.includes(fileExtension)) {
      errorMessage = 'Only CSV and JSON files are allowed.';
      selectedFile = null;
      return false;
    }
    return true;
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault();
    isDragOver = true;
  }

  function handleDragLeave(event: DragEvent) {
    event.preventDefault();
    isDragOver = false;
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    isDragOver = false;

    if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
      const file = event.dataTransfer.files[0];
      if (validateFile(file)) {
        selectedFile = file;
        errorMessage = '';
      }
    }
  }

  function handleBrowseClick() {
    fileInput.click();
  }

  async function handleUpload() {
    if (!selectedFile) return;

    uploading = true;
    errorMessage = '';

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await authenticatedFetch(
        `/api/projects/${$projectID}/patients/upload`,
        {
          method: 'POST',
          body: formData
        },
        false
      );

      if (response.ok) {
        const result = await response.json();
        dispatch('success', { patientIds: result.patient_ids || [] });
        handleClose();
      } else {
        const errorData = await response.json();
        errorMessage = errorData.detail || 'Upload failed. Please try again.';
      }
    } catch (error) {
      console.error('Upload error:', error);
      errorMessage = 'Upload failed. Please check your connection and try again.';
    } finally {
      uploading = false;
    }
  }

  function handleClose() {
    selectedFile = null;
    errorMessage = '';
    uploading = false;
    showInstructions = false;
    dispatch('close');
  }

  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      handleClose();
      event.stopPropagation();
      event.preventDefault();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
  <!-- Modal backdrop -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    on:click={handleBackdropClick}
    on:keydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    tabindex="-1"
  >
    <!-- Modal content -->
    <div
      class="mx-4 flex max-h-3/4 w-full max-w-2xl flex-col rounded-lg bg-white px-6 py-4 shadow-xl"
    >
      <!-- Header -->
      <div class="mb-4 flex shrink-0 items-center justify-between">
        <h2 id="modal-title" class="text-lg font-bold text-gray-900">Upload Patient File</h2>
        <button
          on:click={handleClose}
          class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close modal"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <div class="min-h-0 w-full overflow-auto">
        <!-- File upload area -->
        <div
          class="mb-4 rounded-lg border-2 border-dashed p-8 text-center transition-colors {isDragOver
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 bg-gray-50'} {selectedFile ? 'border-green-500 bg-green-50' : ''}"
          on:dragover={handleDragOver}
          on:dragleave={handleDragLeave}
          on:drop={handleDrop}
          role="button"
          tabindex="0"
          on:click={handleBrowseClick}
          on:keydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              handleBrowseClick();
            }
          }}
        >
          <input
            bind:this={fileInput}
            type="file"
            accept=".csv,.json"
            on:change={handleFileSelect}
            class="hidden"
          />

          <Fa icon={faUpload} class="mx-auto mb-4 h-8 w-8 text-gray-400" />

          {#if selectedFile}
            <div class="mb-2 text-lg font-medium text-green-700">{selectedFile.name}</div>
            <div class="text-sm text-green-600">
              {Math.round(selectedFile.size / 1024)} KB - Ready to upload
            </div>
          {:else}
            <div class="mb-2 text-lg font-medium text-gray-700">
              Drag and drop a file here, or click to browse
            </div>
            <div class="text-sm text-gray-500">Supports CSV and JSON files</div>
          {/if}
        </div>

        <!-- Instructions section -->
        <div class="mb-4">
          <button
            on:click={() => (showInstructions = !showInstructions)}
            class="flex w-full items-center rounded-lg bg-gray-100 px-4 py-2 text-left text-sm font-medium text-gray-700 hover:bg-gray-200"
          >
            <Fa icon={showInstructions ? faChevronDown : faChevronRight} class="mr-2" />
            <span>File Format Requirements</span>
          </button>

          {#if showInstructions}
            <div class="mt-2 space-y-4 rounded-lg border border-gray-200 bg-white p-4 text-sm">
              <div>
                <h4 class="font-medium text-gray-900">CSV Format:</h4>
                <p class="mt-1 text-gray-600">
                  Must include columns: <code class="bg-gray-100 px-1">patient_id</code>,
                  <code class="bg-gray-100 px-1">note_id</code>,
                  <code class="bg-gray-100 px-1">note_text</code>
                </p>
                <p class="mt-1 text-gray-600">
                  Optional: <code class="bg-gray-100 px-1">note_date</code> (date/time string),
                  <code class="bg-gray-100 px-1">note_metadata</code>
                  (JSON string),
                  <code class="bg-gray-100 px-1">patient_metadata</code> (JSON string)
                </p>
              </div>

              <div>
                <h4 class="font-medium text-gray-900">JSON Format:</h4>
                <pre class="mt-1 overflow-x-auto rounded bg-gray-100 p-2 text-xs"><code
                    >{exampleJSON}</code
                  ></pre>
              </div>
            </div>
          {/if}
        </div>
      </div>

      <!-- Error message -->
      {#if errorMessage}
        <div class="mb-4 shrink-0 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {errorMessage}
        </div>
      {/if}

      <!-- Actions -->

      <div class="flex shrink-0 justify-end space-x-3">
        <button
          on:click={handleUpload}
          disabled={!selectedFile || uploading}
          class="btn-primary btn-big"
        >
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
      </div>
    </div>
  </div>
{/if}
