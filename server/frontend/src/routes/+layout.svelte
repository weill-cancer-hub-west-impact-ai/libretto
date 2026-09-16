<script lang="ts">
  import './layout.css';
  import favicon from '$lib/assets/favicon.ico';
  import TaskDropdownList from '$lib/tasks_view/TaskDropdownList.svelte';
  import NewTaskDialog from '$lib/tasks_view/NewTaskDialog.svelte';
  import type { ExtractionSpec, Project, Task } from '$lib/extraction_types';
  import ActionMenuButton from '$lib/utils/ActionMenuButton.svelte';
  import { writable, type Writable } from 'svelte/store';
  import { setContext, onMount, onDestroy } from 'svelte';
  import { areObjectsEqual } from '$lib/utils/utils';
  import { v4 as uuid } from 'uuid';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import { selectedPatient, selectedSpec, specs, projectID, patients } from '$lib/stores/data';
  import { authStore, authenticatedFetch } from '$lib/stores/auth.js';
  import Logo from '$lib/assets/logo-dark.png';
  import { faFolder, faUserCircle } from '@fortawesome/free-solid-svg-icons';
  import Fa from 'svelte-fa';
  import UserEditDialog from '$lib/admin/UserEditDialog.svelte';

  // Initialize auth state from localStorage
  authStore.init();

  let { children } = $props();

  const Tabs = [
    { name: 'Patients', url: '/', route: '/' },
    { name: 'Specifications', url: '/specs.html', route: '/specs' },
    { name: 'Extractions', url: '/extractions.html', route: '/extractions' }
  ];

  let specForExtraction: Writable<ExtractionSpec | null> = writable(null);
  setContext('specForExtraction', specForExtraction);
  let patientIDsForExtraction: Writable<string[] | null> = writable(null);
  setContext('patientIDsForExtraction', patientIDsForExtraction);

  let needsResultsRefresh: Writable<boolean> = writable(false);
  setContext('needsResultsRefresh', needsResultsRefresh);

  let showingAccountSettings: boolean = $state(false);
  let currentUser: any = $state(null);
  let showingNewTaskModal: boolean = $state(false);
  let preSelectedSpecForTask: ExtractionSpec | null = $state(null);
  let preSelectedPatientsForTask: string[] | null = $state(null);
  let tasks: Task[] = $state.raw([]);
  let mostRecentTask: Task | null = $state(null);
  let pollInterval: number | null = null;
  let lastCheckedTask: Task | null = $state(null);
  let projects: Project[] = $state([]);
  let selectedProject: Project | null = $derived.by(() =>
    $projectID !== null ? (projects.find((p) => p.id == $projectID) ?? null) : null
  );

  function handleTaskCreated(event: CustomEvent) {
    let patientID =
      event.detail.task.patient_ids.length > 0
        ? event.detail.task.patient_ids[0]
        : ($selectedPatient?.id ?? null);
    if (patientID != $selectedPatient?.id || event.detail.task.spec_id != $selectedSpec?.id)
      window.location.href = new URL(
        '/extractions?' +
          makeQueryParameters({ spec: event.detail.task.spec_id, patient: patientID }).toString(),
        window.location.origin
      ).toString();
    fetchTasks();
  }

  // Sync projectID with URL parameters
  $effect(() => {
    if (browser) {
      let projectIDFromUrl: number | null = parseInt(page.url.searchParams.get('projectID') ?? '');
      if (Number.isNaN(projectIDFromUrl)) projectIDFromUrl = null;
      if (projectIDFromUrl !== null && projectIDFromUrl !== $projectID) {
        $projectID = projectIDFromUrl;
        console.log('set project ID from URL', $projectID);
      }
    }
  });

  // Update URL when projectID changes
  $effect(() => {
    if (browser && $projectID !== null) {
      const url = new URL(window.location.href);
      if ($projectID !== null) {
        url.searchParams.set('projectID', $projectID.toString());
      } else {
        url.searchParams.delete('projectID');
      }
      if (window.location.href !== url.toString()) {
        console.log('going to URL from project ID', $projectID, url);
        goto(url.toString(), { replaceState: true });
      }
    }
  });

  async function fetchProjects() {
    try {
      const response = await authenticatedFetch('/api/projects');
      if (response.ok) {
        projects = await response.json();

        // Set default project if none selected and projects available
        if (!$projectID && projects.length > 0) {
          selectedProject = projects[0];
          $projectID = selectedProject.id;
        } else if ($projectID && projects.length > 0) {
          selectedProject = projects.find((p) => p.id === $projectID) || projects[0];
        }
        console.log('set project', $projectID, selectedProject, projects);
      } else {
        console.error('Failed to fetch projects');
      }
    } catch (error) {
      console.error('Error fetching projects:', error);
    }
  }

  async function fetchTasks() {
    try {
      if (!$projectID) {
        console.error('No project selected for fetching tasks');
        return;
      }
      const response = await authenticatedFetch(`/api/projects/${$projectID}/tasks`);
      if (response.ok) {
        const fetchedTasks = await response.json();
        const previousTasks = tasks;
        tasks = fetchedTasks;

        // Find the most recent task by created_at date
        if (tasks.length > 0) {
          mostRecentTask = tasks.reduce((latest, current) =>
            new Date(current.created_at) > new Date(latest.created_at) ? current : latest
          );
        } else {
          mostRecentTask = null;
        }

        // Check for task completion and trigger results refresh
        if (previousTasks.length > 0) {
          for (const currentTask of tasks) {
            const previousTask = previousTasks.find((t) => t.id === currentTask.id);
            if (
              previousTask &&
              previousTask.status !== 'completed' &&
              previousTask.status !== 'success' &&
              (currentTask.status === 'completed' || currentTask.status === 'success')
            ) {
              console.log('Task completed, triggering results refresh:', currentTask.id);
              $needsResultsRefresh = true;
              break;
            }
          }
        }

        if (lastCheckedTask == null) lastCheckedTask = mostRecentTask;
      } else {
        console.error('Failed to fetch tasks');
      }
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  }

  function startPolling() {
    // Fetch tasks immediately
    console.log('starting polling', $projectID, selectedProject);
    fetchTasks();

    // Set up polling every 5 seconds
    if (pollInterval !== null) clearInterval(pollInterval);
    pollInterval = setInterval(fetchTasks, 5000);
  }

  function stopPolling() {
    if (pollInterval !== null) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  onMount(() => {
    // Check if user is authenticated, redirect to login if not
    if (browser && !page.route?.id?.includes('login')) {
      authenticatedFetch('/api/auth/me').then((resp) => {
        if (resp.ok) {
          resp.json().then((u) => (currentUser = u));
          fetchProjects().then(() => startPolling());
        }
      });
      return;
    }

    // Only start polling if authenticated
    if ($authStore.isAuthenticated) {
      fetchProjects().then(() => startPolling());
    }
  });

  onDestroy(() => {
    stopPolling();
  });

  function handleLogout() {
    authStore.logout();
    goto('/login');
  }

  function makeProjectURL(projectID: number) {
    let destination = new URL(window.location.href);
    makeQueryParameters().forEach((value, key) => destination.searchParams.set(key, value));
    destination.searchParams.set('projectID', projectID.toString());
    return destination.toString();
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
      if (!$projectID) {
        console.error('No project selected');
        return;
      }

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
      } else {
        const errorText = await response.text();
        console.error('Failed to update tags:', response.status, response.statusText, errorText);
      }
    } catch (error) {
      console.error('Error updating tags:', error);
    }
  }

  $effect(() => {
    if (!!$specForExtraction && !$patientIDsForExtraction) {
      preSelectedSpecForTask = $specForExtraction;
      showingNewTaskModal = true;
      $specForExtraction = null;
    }
  });

  async function handleExtract(patientIDs: string[], spec: ExtractionSpec) {
    if (!spec) {
      console.error('No extraction spec selected');
      return;
    }

    try {
      if (!$projectID) {
        console.error('No project selected');
        return;
      }

      let taskDesc = {
        specID: spec.id,
        patientIDs: patientIDs,
        overwrite: true
      };
      const response = await authenticatedFetch(`/api/projects/${$projectID}/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(taskDesc)
      });

      if (response.ok) {
        const task = await response.json();
        handleTaskCreated(new CustomEvent('created', { detail: { task } }));
      } else {
        console.error('Failed to create extraction task:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('Error creating extraction task:', error);
    }
  }

  $effect(() => {
    if (!!$patientIDsForExtraction) {
      if ($specForExtraction) {
        handleExtract($patientIDsForExtraction, $specForExtraction);
      } else {
        showingNewTaskModal = true;
        preSelectedPatientsForTask = [...$patientIDsForExtraction];
      }
      $patientIDsForExtraction = null;
      $specForExtraction = null;
    }
  });

  function makeQueryParameters(
    newValues:
      | {
          patient?: string;
          spec?: string;
          project?: number;
        }
      | undefined = undefined
  ): URLSearchParams {
    let params = new URLSearchParams();
    let newPatientID = newValues?.patient ?? $selectedPatient?.id;
    if (newPatientID) params.set('patientID', newPatientID);
    let newSpecID = newValues?.spec ?? $selectedSpec?.id;
    if (newSpecID) params.set('specID', newSpecID);
    let newProjectID = newValues?.project ?? $projectID;
    if (newProjectID) params.set('projectID', newProjectID.toString());
    return params;
  }
</script>

<svelte:head
  ><link rel="icon" href={favicon} /><title>Libretto</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@100..900&display=swap"
    rel="stylesheet"
  />
</svelte:head>
<div class="flex h-screen w-screen flex-col">
  <div class="relative flex w-full shrink-0 items-center gap-4 bg-stone-800 px-4 py-2 text-white">
    <div class="flex-1">
      <img src={Logo} alt="Libretto" class="mr-auto h-8 w-auto" />
    </div>
    <div class="flex flex-1 items-center justify-center gap-2">
      {#each Tabs as tab (tab.name)}
        <button
          class="{page.route.id == tab.route
            ? 'border-b border-white font-bold'
            : 'cursor-pointer rounded-md hover:bg-stone-600/50'} px-3 py-1"
          disabled={page.route.id == tab.route}
          onclick={() => goto(tab.route + '?' + makeQueryParameters().toString())}
          >{tab.name}</button
        >
      {/each}
    </div>

    <div class="flex flex-1 items-center justify-end gap-2">
      <!-- User menu -->
      {#if $authStore.isAuthenticated && $authStore.user}
        <ActionMenuButton
          buttonClass="btn-icon-dark"
          buttonTitle="User menu"
          singleClick
          menuWidth={280}
          align="right"
        >
          {#snippet buttonContent()}
            <Fa icon={faUserCircle} />
          {/snippet}
          {#snippet options(dismiss: () => void)}
            {#if $authStore.user.is_admin}
              <button
                class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                role="menuitem"
                onclick={() => goto('/admin')}
              >
                Admin
              </button>
            {/if}
            <button
              class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
              role="menuitem"
              onclick={() => (showingAccountSettings = true)}
            >
              Account Settings
            </button>
            <button
              class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
              role="menuitem"
              onclick={handleLogout}
            >
              Log Out
            </button>
          {/snippet}
        </ActionMenuButton>
      {/if}
      <ActionMenuButton
        buttonClass="btn btn-secondary-dark"
        buttonTitle="Manage running extraction jobs"
        singleClick={false}
        menuWidth={300}
        align="right"
        onShow={() => (lastCheckedTask = Object.assign({}, mostRecentTask))}
      >
        {#snippet buttonContent()}
          <div class="flex items-center gap-2">
            {#if mostRecentTask && !areObjectsEqual(lastCheckedTask, mostRecentTask)}
              <div class="flex items-center gap-1">
                <div
                  class="h-2 w-2 rounded-full {mostRecentTask.status?.toLowerCase() ===
                    'completed' || mostRecentTask.status?.toLowerCase() === 'success'
                    ? 'bg-green-400'
                    : mostRecentTask.status?.toLowerCase() === 'failed' ||
                        mostRecentTask.status?.toLowerCase() === 'error'
                      ? 'bg-red-400'
                      : mostRecentTask.status?.toLowerCase() === 'canceled'
                        ? 'bg-gray-400'
                        : 'animate-pulse bg-yellow-400'}"
                  title={`Latest task: ${mostRecentTask.status}`}
                ></div>
              </div>
            {/if}
            <span>Jobs</span>
          </div>
        {/snippet}
        {#snippet options(dismiss: () => void)}
          <TaskDropdownList
            on:createTask={() => {
              showingNewTaskModal = true;
              dismiss();
            }}
            on:selectPatient={(e) => {
              if (!!$patients) {
                let patientToSelect = $patients.find((p) => p.id == e.detail.patientID);
                if (!!patientToSelect) {
                  goto('/extractions?' + makeQueryParameters({ patient: patientToSelect.id }), {
                    replaceState: true
                  });
                  $selectedPatient = patientToSelect;
                  dismiss();
                }
              }
            }}
          />
        {/snippet}
      </ActionMenuButton>
      <ActionMenuButton
        buttonClass="btn btn-secondary-dark max-w-36 truncate"
        buttonTitle="Select project"
        singleClick={false}
        menuWidth={280}
        align="right"
      >
        {#snippet buttonContent()}
          <Fa icon={faFolder} class="mr-2 inline" />
          {selectedProject?.name ?? 'Projects'}
        {/snippet}
        {#snippet options(dismiss: () => void)}
          {#if projects.length > 0}
            {#each projects as project (project.id)}
              <a
                class:pointer-events-none={selectedProject?.id === project.id}
                class="block w-full px-4 py-2 text-left text-sm {selectedProject?.id === project.id
                  ? 'font-semibold text-sky-600'
                  : 'text-gray-700 hover:bg-gray-100'}"
                href={makeProjectURL(project.id)}
              >
                {project.name}
              </a>
            {/each}
          {:else}
            <div class="px-4 py-2 text-sm text-stone-500">No projects available</div>
          {/if}
        {/snippet}
      </ActionMenuButton>
    </div>
  </div>
  {#if $projectID !== null || page.route.id == '/login' || page.route.id == '/admin'}
    <div class="min-h-0 w-full flex-auto">
      {@render children()}
    </div>
  {:else}
    <div class="flex min-h-0 w-full flex-auto flex-col items-center justify-center gap-4">
      <div class="max-w-1/2 text-lg text-stone-500">No Projects</div>
      <div class="max-w-1/2 text-sm text-stone-500">
        Ask the administrator to create or add you to a project to use Libretto.
      </div>
    </div>
  {/if}
</div>
<NewTaskDialog
  isOpen={showingNewTaskModal}
  selectedSpec={preSelectedSpecForTask}
  selectedPatientIDs={preSelectedPatientsForTask ? preSelectedPatientsForTask : []}
  on:close={() => {
    showingNewTaskModal = false;
    preSelectedSpecForTask = null;
    preSelectedPatientsForTask = null;
  }}
  on:created={handleTaskCreated}
  on:createSpec={(e) => {
    showingNewTaskModal = false;
    goto(`/specs?specID=${uuid()}`);
  }}
  on:editSpec={(e) => {
    showingNewTaskModal = false;
    $selectedSpec = $specs?.find((s) => s.id == e.detail.spec.id) ?? null;
    console.log('selected spec from edit:', $specs, $selectedSpec?.id);
    goto(`/specs?specID=${e.detail.spec.id}`);
  }}
  on:editPatients={() => {
    showingNewTaskModal = false;
    goto($selectedPatient ? `/?patientID=${$selectedPatient?.id}` : '/');
  }}
  on:tag={handleTagPatients}
/>
<UserEditDialog
  bind:isOpen={showingAccountSettings}
  user={currentUser}
  on:success={() => (showingAccountSettings = false)}
  on:close={() => (showingAccountSettings = false)}
/>
