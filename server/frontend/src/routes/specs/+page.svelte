<script lang="ts">
  import type { ExtractionResult, Patient, ExtractionSpec, Note } from '$lib/extraction_types';
  import { page } from '$app/state';
  import { replaceState } from '$app/navigation';
  import { browser } from '$app/environment';
  import { getContext, onMount } from 'svelte';
  import { writable, type Writable } from 'svelte/store';
  import SpecEditor from '$lib/spec_view/SpecEditor.svelte';
  import { selectedSpec, projectID, patients, syncPatients } from '$lib/stores/data';
  import { authenticatedFetch } from '$lib/stores/auth';

  let specForExtraction: Writable<ExtractionSpec | null> = getContext('specForExtraction');

  $: if (browser && $projectID !== null && !!$selectedSpec) {
    authenticatedFetch('/api/logs/pageview', {
      method: 'POST',
      body: JSON.stringify({
        page: 'specs',
        projectID: $projectID,
        specID: $selectedSpec?.id
      })
    });
  }

  onMount(() => {
    if (!$patients) syncPatients();
  });

  function handleExtract(spec: ExtractionSpec | null = null) {
    $specForExtraction = spec;
  }

  async function fetchSpecs(): Promise<ExtractionSpec[]> {
    let response = await authenticatedFetch(`/api/projects/${$projectID}/specs`);
    return await response.json();
  }

  function updateUrl(specID: string | null) {
    if (!browser) return;

    const url = new URL(window.location.href);
    if (specID) {
      url.searchParams.set('specID', specID);
    } else {
      url.searchParams.delete('specID');
    }

    // Use replace to avoid adding history entries for every note change
    if (window.location.href != url.toString()) replaceState(url.toString(), page.state);
  }

  // Initialize state from URL on page load or set defaults
  $: if (browser && !$selectedSpec) {
    const specIDFromUrl = page.url.searchParams.get('specID');
    if (!!specIDFromUrl) {
      console.log('updating spec ID from url');
      fetchSpecs().then((specs) => {
        $selectedSpec = specs.find((s) => s.id == specIDFromUrl) ?? null;
        if (!$selectedSpec && specs.length > 0) $selectedSpec = specs[0];
        if (!!$selectedSpec) updateUrl($selectedSpec.id);
      });
    }
  }

  // Watch for changes to note and update URL
  $: if (browser && $selectedSpec) {
    updateUrl($selectedSpec?.id ?? null);
  }
</script>

<SpecEditor
  {fetchSpecs}
  bind:selectedSpec={$selectedSpec}
  on:extract={(e) => handleExtract(e.detail.spec)}
  showHeader={false}
/>
