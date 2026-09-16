<script lang="ts">
  import type {
    ExtractionResult,
    Patient,
    ExtractionSpec,
    Note,
    Feedback
  } from '$lib/extraction_types';
  import ExtractionView from '$lib/extraction_view/ExtractionView.svelte';
  import PatientFileUploadDialog from '$lib/patient_view/PatientFileUploadDialog.svelte';
  import PatientImportDialog from '$lib/patient_view/PatientImportDialog.svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import { getContext, onMount } from 'svelte';
  import type { Writable } from 'svelte/store';
  import { v4 as uuid } from 'uuid';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import {
    patients,
    specs,
    selectedPatient,
    selectedSpec,
    syncSpecs,
    syncPatients,
    projectID
  } from '$lib/stores/data';
  import { authenticatedFetch } from '$lib/stores/auth';

  let patientIDsForExtraction: Writable<string[] | null> = getContext('patientIDsForExtraction');
  let specForExtraction: Writable<ExtractionSpec | null> = getContext('specForExtraction');
  let needsResultsRefresh: Writable<boolean> = getContext('needsResultsRefresh');
  let needsPatientRefresh: boolean = false;

  let loadingSpecs: boolean = false;

  let comparisonSpecs: ExtractionSpec[] = [];

  onMount(() => {
    loadingSpecs = true;
    syncSpecs().then(() => (loadingSpecs = false));
    if ($selectedSpec) comparisonSpecs = [$selectedSpec];
  });

  $: if (browser && $projectID !== null && (!!$selectedPatient || !!$selectedSpec)) {
    authenticatedFetch('/api/logs/pageview', {
      method: 'POST',
      body: JSON.stringify({
        page: 'extractions',
        projectID: $projectID,
        patientID: $selectedPatient?.id,
        noteID: selectedNoteID,
        specID: $selectedSpec?.id,
        comparisonSpecs: comparisonSpecs.map((s) => s.id)
      })
    });
  }

  $: if (comparisonSpecs.length > 0) $selectedSpec = comparisonSpecs[0];

  onMount(() => {
    if (!$patients) syncPatients();
  });

  async function loadModelOutputs(
    sources: ExtractionSpec[],
    patientID: string
  ): Promise<ExtractionResult[]> {
    let response = await authenticatedFetch(`/api/projects/${$projectID}/results`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        specs: sources,
        patientID
      })
    });
    if (response.status != 200) {
      console.warn('Response for loading model outputs:', response);
      return [];
    }
    return await response.json();
  }

  async function fetchAvailableSpecs(): Promise<ExtractionSpec[]> {
    let response = await authenticatedFetch(`/api/projects/${$projectID}/specs`);
    if (response.status != 200) {
      console.warn('Response for loading filtered specs:', response);
      return [];
    }
    return await response.json();
  }

  async function fetchTaskStatus(specID?: string, patientID?: string): Promise<any> {
    const params = new URLSearchParams();
    if (specID) params.set('specID', specID);
    if (patientID) params.set('patientID', patientID);

    const query = params.toString() ? `?${params.toString()}` : '';
    let response = await authenticatedFetch(`/api/projects/${$projectID}/tasks${query}`);

    if (response.status === 404) {
      // Task not found - could mean it's completed or never existed
      return null;
    }

    if (response.status !== 200) {
      console.warn('Response for loading task status:', response);
      throw new Error(`Failed to fetch task status: ${response.status}`);
    }

    return await response.json();
  }

  async function saveFeedback(data: Feedback): Promise<boolean> {
    try {
      let response = await authenticatedFetch(`/api/projects/${$projectID}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });

      if (response.status !== 200) {
        console.error('Failed to save feedback:', await response.text());
        return false;
      }

      return true;
    } catch (error) {
      console.error('Error saving feedback:', error);
      return false;
    }
  }

  async function downloadResponses(patientId: string | null, csv: boolean = false) {
    const downloadURL = new URL(
      `/api/projects/${$projectID}/results/download`,
      window.location.origin
    );
    if (patientId) {
      downloadURL.searchParams.set('patient_id', patientId);
    }
    downloadURL.searchParams.set('spec_ids', comparisonSpecs.map((s) => s.id).join(','));
    if (csv) {
      downloadURL.searchParams.set('format', 'csv');
    }
    try {
      let response = await authenticatedFetch(downloadURL.toString());
      let blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      const disposition = response.headers.get('Content-Disposition');
      let filename = 'extractions.' + (csv ? 'csv' : 'json'); // Default fallback

      if (disposition && disposition.includes('filename=')) {
        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        const matches = filenameRegex.exec(disposition);
        if (matches != null && matches[1]) {
          filename = matches[1].replace(/['"]/g, '');
        }
      }

      a.download = filename;
      document.body.appendChild(a);
      a.click(); // Programmatically trigger the click
      a.remove();
    } catch (e) {
      alert('Unable to download extractions: ' + e);
    }
  }

  // State management for selected patient and note
  let selectedNoteID: string | null = null;

  // Dialog state
  let showFileUploadDialog = false;
  let showManualImportDialog = false;

  // Function to update URL with note ID
  function updateUrl({
    patientID,
    noteID,
    specID
  }: {
    patientID?: string | null;
    noteID?: string | null;
    specID?: string | null;
  }) {
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
    if (specID !== undefined) {
      if (specID !== null) {
        url.searchParams.set('specID', specID);
      } else {
        url.searchParams.delete('specID');
      }
    }

    // Use replace to avoid adding history entries for every note change
    console.log('going to', url);
    if (window.location.href !== url.toString()) goto(url.toString(), { replaceState: true });
  }

  // Initialize state from URL on page load or set defaults
  $: if (browser && !!$specs && $specs.length > 0 && !$selectedSpec) {
    console.log('updating spec ID from url');
    const specIDFromUrl = page.url.searchParams.get('specID');
    if (!!specIDFromUrl) {
      $selectedSpec = $specs.find((s) => s.id == specIDFromUrl) ?? null;
    }
    if (!$selectedSpec) $selectedSpec = $specs[0];
    if (!!$selectedSpec) {
      updateUrl({ specID: $selectedSpec.id });
      comparisonSpecs = [$selectedSpec];
    }
  }

  $: if (browser && !!$patients && $patients.length > 0 && !$selectedPatient) {
    console.log('loadding from url');
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
  $: if (browser && ($selectedPatient || $selectedSpec)) {
    console.log('updating because of', $selectedPatient?.id, $selectedSpec?.id);
    updateUrl({
      patientID: $selectedPatient?.id ?? undefined,
      noteID: selectedNoteID,
      specID: $selectedSpec?.id ?? undefined
    });
  }

  // Reset needsResultsRefresh after it's been used
  $: if ($needsResultsRefresh) {
    // Reset the flag after a short delay to allow the refresh to trigger
    setTimeout(() => {
      $needsResultsRefresh = false;
    }, 100);
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
        needsPatientRefresh = true;
        setTimeout(syncPatients);
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
      setTimeout(() => {
        if ($patients) {
          const importedPatient = $patients.find((p) => patientIds.includes(p.id));
          if (importedPatient) {
            $selectedPatient = importedPatient;
            selectedNoteID = null;
            updateUrl({ patientID: importedPatient.id });
          }
        }
      }, 500);
    }
  }
</script>

{#if loadingSpecs}
  <LoadingView text="Loading specifications..." />
{:else}
  <ExtractionView
    extractionSpecs={$specs ?? []}
    bind:comparisonSpecs
    bind:selectedPatient={$selectedPatient}
    bind:noteID={selectedNoteID}
    bind:needsPatientRefresh
    fetchModelOutput={loadModelOutputs}
    {fetchAvailableSpecs}
    {fetchTaskStatus}
    {downloadResponses}
    refreshTrigger={$needsResultsRefresh}
    onFeedbackChange={async (feedback) => {
      await saveFeedback(feedback);
    }}
    on:createSpec={(e) => {
      goto(`/specs?specID=${uuid()}`);
    }}
    on:editSpec={(e) => {
      goto(`/specs?specID=${e.detail.spec.id}`);
    }}
    on:extract={(e) => {
      $patientIDsForExtraction = e.detail.patientIDs;
      if (comparisonSpecs.length == 1) $specForExtraction = comparisonSpecs[0];
    }}
    on:tagPatients={handleTagPatients}
    on:importManual={handleImportManual}
    on:importFile={handleImportFile}
  />
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
