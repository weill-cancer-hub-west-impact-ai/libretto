<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher, getContext } from 'svelte';
  import Fa from 'svelte-fa';
  import { faPlus, faXmark } from '@fortawesome/free-solid-svg-icons';
  import TaskDropdownItem from './TaskDropdownItem.svelte';
  import LoadingView from '$lib/utils/LoadingView.svelte';
  import type { Task } from '$lib/extraction_types';
  import { authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';

  const dispatch = createEventDispatcher();

  let tasks: Task[] = $state([]);
  let loading: boolean = $state(false);
  let hideStopped: boolean = $state(false);
  let filteredTasks: Task[] = $state([]);
  let pollInterval: number | null = null;

  // Filter tasks based on showCompleted toggle
  $effect(() => {
    if (!hideStopped) {
      filteredTasks = tasks;
    } else {
      filteredTasks = tasks.filter(
        (task) =>
          task.status?.toLowerCase() !== 'failed' && task.status?.toLowerCase() !== 'canceled'
      );
    }
  });

  async function fetchTasks() {
    loading = true;
    try {
      const response = await authenticatedFetch(`/api/projects/${$projectID}/tasks`);
      if (response.ok) {
        tasks = await response.json();
      } else {
        console.error('Failed to fetch tasks');
        tasks = [];
      }
    } catch (error) {
      console.error('Error fetching tasks:', error);
      tasks = [];
    } finally {
      loading = false;
    }
  }

  function startPolling() {
    // Fetch tasks immediately
    fetchTasks();

    // Set up polling every 5 seconds
    pollInterval = setInterval(fetchTasks, 5000);
  }

  function stopPolling() {
    if (pollInterval !== null) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  onMount(() => {
    startPolling();
  });

  onDestroy(() => {
    stopPolling();
  });

  function handleCreateTask() {
    dispatch('createTask');
  }

  async function handleCancelTask(event: CustomEvent) {
    const taskId = event.detail;

    try {
      const response = await authenticatedFetch(`/api/projects/${$projectID}/tasks/${taskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'cancel' })
      });

      if (!response.ok) {
        throw new Error('Failed to cancel task');
      }

      // Update local tasks list immediately
      const updatedTask = await response.json();
      tasks = tasks.map((t) => (t.id === taskId ? updatedTask : t));
    } catch (error) {
      console.error('Error canceling task:', error);
      alert('Failed to cancel task. Please try again.');
    }
  }

  async function handleRetryTask(event: CustomEvent) {
    const task = event.detail;

    try {
      const response = await authenticatedFetch(`/api/projects/${$projectID}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          specID: task.spec_id,
          patientIDs: task.patient_ids || null,
          overwrite: true // Use overwrite=true to reprocess notes
        })
      });

      if (!response.ok) {
        throw new Error('Failed to retry task');
      }

      // Refresh the task list to show the new task
      await fetchTasks();
    } catch (error) {
      console.error('Error retrying task:', error);
      alert('Failed to retry task. Please try again.');
    }
  }
</script>

<div class="bg-white">
  <!-- Controls -->
  <div class="flex items-center justify-between border-b border-gray-100 px-4 py-3">
    <label class="flex cursor-pointer items-center space-x-2">
      <input
        type="checkbox"
        bind:checked={hideStopped}
        class="rounded border-gray-300 text-sky-600 focus:ring-sky-500"
      />
      <span class="text-sm text-gray-700">Hide stopped</span>
    </label>

    <button
      onclick={handleCreateTask}
      class="inline-flex items-center space-x-1 rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-700 focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:outline-none"
    >
      <Fa icon={faPlus} class="h-3 w-3" />
      <span>Start</span>
    </button>
  </div>

  <!-- Tasks List -->
  <div class="max-h-96 overflow-y-auto">
    {#if loading && filteredTasks.length == 0}
      <div class="p-4">
        <LoadingView text="Loading jobs..." />
      </div>
    {:else if filteredTasks.length === 0}
      <div class="p-4 text-center text-gray-500">
        <p class="text-sm">No jobs found</p>
      </div>
    {:else}
      {#each filteredTasks.slice(0, 10) as task (task.id)}
        <TaskDropdownItem
          {task}
          on:cancel={handleCancelTask}
          on:retry={handleRetryTask}
          on:selectPatient
        />
      {/each}
    {/if}
  </div>
</div>
