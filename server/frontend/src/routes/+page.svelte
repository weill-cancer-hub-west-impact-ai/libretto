<script lang="ts">
  import type { ExtractionSpec } from '$lib/extraction_types';
  import PatientFileUploadDialog from '$lib/patient_view/PatientFileUploadDialog.svelte';
  import PatientImportDialog from '$lib/patient_view/PatientImportDialog.svelte';
  import { page } from '$app/state';
  import { goto, pushState, replaceState } from '$app/navigation';
  import { browser } from '$app/environment';
  import { getContext, onMount } from 'svelte';
  import type { Writable } from 'svelte/store';
  import { v4 as uuid } from 'uuid';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import ResizablePanel from '$lib/utils/ResizablePanel.svelte';
  import PatientView from '$lib/patient_view/PatientView.svelte';
  import PatientSelector from '$lib/patient_view/PatientSelector.svelte';
  import { patients, selectedPatient, syncPatients, selectedSpec } from '$lib/stores/data';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';

  let loadingPatients: boolean = false;
  let patientIDsForExtraction: Writable<ExtractionSpec | null> =
    getContext('patientIDsForExtraction');

  onMount(() => {
    if (!$patients) loadPatientData();
  });

  $: if (browser && $projectID !== null) {
    authenticatedFetch('/api/logs/pageview', {
      method: 'POST',
      body: JSON.stringify({
        page: 'patients',
        projectID: $projectID,
        patientID: $selectedPatient?.id,
        noteID: selectedNoteID,
        specID: $selectedSpec?.id
      })
    });
  }

  async function loadPatientData() {
    loadingPatients = true;
    await syncPatients();
    loadingPatients = false;
  }

  // State management for selected patient and note
  let selectedNoteID: string | null = null;
  let currentPatientSearchQuery: string | null = null;

  // Dialog state
  let showFileUploadDialog = false;
  let showManualImportDialog = false;

  // Function to update URL with note ID
  function updateUrl({ patientID, noteID }: { patientID?: string | null; noteID?: string | null }) {
    if (!browser) return;

    const url = new URL(window.location.href);
    if (noteID !== undefined) {
      if (noteID !== null) {
        url.searchParams.set('noteID', noteID);
      } else {
        url.searchParams.delete('noteID');
      }
    }
    if (patientID !== undefined) {
      if (patientID !== null) {
        url.searchParams.set('patientID', patientID);
      } else {
        url.searchParams.delete('patientID');
      }
    }

    // Use replace to avoid adding history entries for every note change
    console.log('going to', url);
    if (window.location.href !== url.toString()) goto(url.toString(), { replaceState: true });
  }

  $: if (browser && !!$patients && $patients.length > 0 && !$selectedPatient) {
    const patientIDFromUrl = page.url.searchParams.get('patientID');
    const noteIdFromUrl = page.url.searchParams.get('noteID');
    console.log(patientIDFromUrl, noteIdFromUrl);
    if (!!patientIDFromUrl) {
      $selectedPatient = $patients.find((p) => p.id == patientIDFromUrl) ?? null;
      if ($selectedPatient && !!noteIdFromUrl) {
        selectedNoteID = noteIdFromUrl;
      } else selectedNoteID = null;
    } else if (!patientIDFromUrl && !$selectedPatient) {
      // Set default to first patient and first note if no URL param
      $selectedPatient = $patients[0];
      updateUrl({ patientID: $selectedPatient.id });
    }
    console.log('set to', $selectedPatient);
  }

  // Watch for changes to note and update URL
  $: if (browser && $selectedPatient) {
    console.log('updating from variable');
    updateUrl({ patientID: $selectedPatient.id ?? undefined, noteID: selectedNoteID });
  }

  async function handleTagPatients(
    event: CustomEvent<{ items: any[]; tag: string; include: boolean }>
  ) {
    const { items, tag, include } = event.detail;

    if (!items || items.length === 0) {
      console.warn('No items selected for tagging');
      return;
    }

    const patient_ids = items.map((item) => item.id);
    const action = include ? 'add' : 'remove';

    try {
      const response = await authenticatedFetch(`/api/projects/${$projectID}/tags`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          patient_ids,
          tag,
          action
        })
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Tag operation successful:', result);

        // Refresh the patient data to show updated tags
        loadPatientData();
      } else {
        const errorText = await response.text();
        console.error('Failed to update tags:', response.status, response.statusText, errorText);
      }
    } catch (error) {
      console.error('Error updating tags:', error);
    }
  }

  function handleImportManual() {
    showManualImportDialog = true;
  }

  function handleImportFile() {
    showFileUploadDialog = true;
  }

  async function handlePatientSuccess(event: CustomEvent<{ patientIds: string[] }>) {
    const { patientIds } = event.detail;

    // Set the current patient to the first imported patient if available
    if (patientIds.length > 0) {
      // Wait a bit for the patient list to refresh
      await syncPatients();
      setTimeout(() => {
        if (!$patients) return;
        const importedPatient = $patients.find((p) => patientIds.includes(p.id));
        if (importedPatient) {
          $selectedPatient = importedPatient;
          selectedNoteID = null;
          updateUrl({ patientID: importedPatient.id, noteID: null });
        }
      }, 500);
    }
  }
</script>

{#if loadingPatients}
  <LoadingView text="Loading patients..." />
{:else}
  <div class="relative flex h-full w-full">
    <ResizablePanel
      rightResizable
      minWidth={240}
      maxWidth="80%"
      collapsible={false}
      width={600}
      height="100%"
      ><PatientSelector
        selectedPatient={$selectedPatient}
        allowClose={false}
        on:select={(e) => {
          $selectedPatient = e.detail.patient ?? null;
          selectedNoteID = null;
          // If there's a search query when selecting a patient, pass it to PatientView
          if ($selectedPatient) {
            if (e.detail.searchQuery.trim() && ['all', 'text'].includes(e.detail.searchTarget)) {
              currentPatientSearchQuery = e.detail.searchQuery;
            } else {
              currentPatientSearchQuery = null;
            }
          }
        }}
        on:tag={handleTagPatients}
        on:importManual={handleImportManual}
        on:importFile={handleImportFile}
      /></ResizablePanel
    >
    <div class="h-full min-w-0 flex-auto">
      <PatientView
        bind:selectedPatient={$selectedPatient}
        bind:noteID={selectedNoteID}
        bind:patientSearchQuery={currentPatientSearchQuery}
        showPatientSelector={false}
        noteAnnotations={[]}
        on:extract={(e) => ($patientIDsForExtraction = e.detail.patientIDs)}
        on:tag={handleTagPatients}
        on:importManual={handleImportManual}
        on:importFile={handleImportFile}
      />
    </div>
  </div>
{/if}

<!-- Patient Import Dialogs -->
<PatientFileUploadDialog
  isOpen={showFileUploadDialog}
  on:success={handlePatientSuccess}
  on:close={() => (showFileUploadDialog = false)}
/>

<PatientImportDialog
  isOpen={showManualImportDialog}
  on:success={handlePatientSuccess}
  on:close={() => (showManualImportDialog = false)}
/>
