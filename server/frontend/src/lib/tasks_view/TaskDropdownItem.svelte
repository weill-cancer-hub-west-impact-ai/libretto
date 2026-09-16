<script lang="ts">
  import Fa from 'svelte-fa';
  import {
    faCircleNotch,
    faCheckCircle,
    faTimesCircle,
    faChevronDown,
    faChevronUp,
    faClock,
    faXmark,
    faRotateLeft
  } from '@fortawesome/free-solid-svg-icons';
  import { createEventDispatcher } from 'svelte';
  import moment from 'moment';

  import type { Task } from '$lib/extraction_types';

  let { task }: { task: Task } = $props();

  const dispatch = createEventDispatcher();

  let patientIDs: string[] = $derived(task.patient_ids ?? []);
  let patientListExpanded: boolean = $state(false);
  let showFullError: boolean = $state(false);

  function handleCancel(event: Event) {
    event.stopPropagation();
    if (confirm(`Cancel this ${task.status} task?`)) {
      dispatch('cancel', task.id);
    }
  }

  function handleRetry(event: Event) {
    event.stopPropagation();
    dispatch('retry', task);
  }

  function getStatusIcon(status: string) {
    switch (status?.toLowerCase()) {
      case 'running':
        return faCircleNotch;
      case 'pending':
        return faClock;
      case 'completed':
      case 'success':
        return faCheckCircle;
      case 'failed':
      case 'error':
        return faTimesCircle;
      case 'canceled':
        return faXmark;
      default:
        return faCircleNotch;
    }
  }

  function getStatusColor(status: string) {
    switch (status?.toLowerCase()) {
      case 'running':
        return 'text-blue-500';
      case 'pending':
        return 'text-gray-500';
      case 'completed':
      case 'success':
        return 'text-green-500';
      case 'failed':
      case 'error':
        return 'text-red-500';
      case 'canceled':
        return 'text-gray-400';
      default:
        return 'text-gray-500';
    }
  }

  function hasError(task: any) {
    return task.error_message && task.error_message.trim().length > 0;
  }
</script>

<div class="border-b border-gray-100 px-4 py-3 hover:bg-gray-50">
  <div class="flex items-start space-x-3">
    <!-- Status Icon -->
    <div class="flex-shrink-0 pt-1">
      <Fa
        icon={getStatusIcon(task.status)}
        class={`h-4 w-4 ${getStatusColor(task.status)} ${task.status == 'running' ? 'animate-spin' : ''}`}
      />
    </div>

    <!-- Task Content -->
    <div class="min-w-0 flex-1">
      <!-- Task Header -->
      <div class="flex items-start justify-between">
        <div class="flex-1">
          <div class="text-sm font-medium text-gray-900">
            {#if task.spec_name}
              {task.spec_name}
            {/if}
          </div>
          <div class="mt-1 text-xs text-gray-500">
            {task.status_message ?? task.status}{(task.progress_current ?? 0) > 0
              ? ` (${task.progress_current}/${task.progress_total})`
              : ''} · {moment(task.created_at).local().fromNow()}
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex space-x-1">
          <!-- Retry Button (for failed tasks) -->
          {#if task.status == 'failed' || task.status == 'error'}
            <button
              class="rounded p-1 text-blue-500 transition-opacity hover:opacity-50"
              onclick={handleRetry}
              title="Retry task"
            >
              <Fa icon={faRotateLeft} size="sm" />
            </button>
          {/if}

          <!-- Cancel Button (for pending/running tasks) -->
          {#if task.status === 'pending' || task.status === 'running'}
            <button
              class="rounded p-1 text-red-500 transition-opacity hover:opacity-50"
              onclick={handleCancel}
              title="Cancel task"
            >
              <Fa icon={faXmark} size="sm" />
            </button>
          {/if}
        </div>
      </div>

      {#if patientIDs.length > 0}
        <div class="mt-1 text-xs text-gray-800">
          {patientIDs.length} patient{patientIDs.length != 1 ? 's' : ''} ·
          {#if patientListExpanded}
            {#each patientIDs as id, i (i)}
              <a
                class="font-semibold text-sky-600 hover:opacity-50"
                href="#"
                onclick={() => dispatch('selectPatient', { patientID: id })}>{id}</a
              >{i < patientIDs.length - 1 ? ', ' : ''}
            {/each}
            <button class="btn-icon-small" onclick={() => (patientListExpanded = false)}
              ><Fa icon={faChevronUp} /></button
            >
          {:else}
            <a
              class="font-semibold text-sky-600 hover:opacity-50"
              href="#"
              onclick={() => dispatch('selectPatient', { patientID: patientIDs[0] })}
              >{patientIDs[0]}</a
            >
            {#if patientIDs.length > 1}
              and {patientIDs.length - 1} other{patientIDs.length - 1 != 1 ? 's' : ''}
              <button class="btn-icon-small" onclick={() => (patientListExpanded = true)}
                ><Fa icon={faChevronDown} /></button
              >
            {/if}
          {/if}
        </div>
      {/if}

      <!-- Error Message Preview -->
      {#if hasError(task)}
        <div
          class="mt-2 flex w-full cursor-pointer items-center justify-between rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-600"
          onclick={() => (showFullError = !showFullError)}
        >
          <div class="flex-auto break-all" class:line-clamp-2={!showFullError}>
            {task.error_message}
          </div>
          <Fa icon={showFullError ? faChevronUp : faChevronDown} class="ml-2 h-3 w-3 shrink-0" />
        </div>
      {/if}
    </div>
  </div>
</div>
