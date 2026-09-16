<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { authStore } from '$lib/stores/auth';
  import Fa from 'svelte-fa';
  import {
    faTrash,
    faCheck,
    faXmark,
    faChevronDown,
    faChevronUp,
    faPencil
  } from '@fortawesome/free-solid-svg-icons';
  import moment from 'moment';

  const dispatch = createEventDispatcher();

  export let comment: {
    id: number;
    annotator_id: number;
    username?: string;
    comment: string;
    created_at: string;
    updated_at: string;
  };

  // State for edit mode
  let isEditing = false;
  let editedComment = comment.comment;
  let isExpanded = false;

  // Get current user from auth store
  $: currentUser = $authStore.user;
  $: canEdit =
    comment.username == null || (!!currentUser && currentUser.username === comment.username);

  function getRelativeTime(dateString: string): string {
    return moment(dateString).fromNow();
  }

  function handleEdit() {
    isEditing = true;
    editedComment = comment.comment;
  }

  function handleSave() {
    if (editedComment.trim() === comment.comment.trim()) {
      isEditing = false;
      return;
    }

    dispatch('edit', {
      commentId: comment.id,
      newComment: editedComment.trim()
    });
    isEditing = false;
  }

  function handleCancel() {
    isEditing = false;
    editedComment = comment.comment;
  }

  function handleDelete() {
    if (confirm('Are you sure you want to delete this comment?')) {
      dispatch('delete', {
        commentId: comment.id
      });
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      handleSave();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      handleCancel();
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
  class="space-y-3 rounded-lg border border-2 border-sky-300 bg-white p-4 shadow-sm {!isEditing
    ? 'hover:bg-sky-100'
    : ''}"
  on:click={() => (isExpanded = !isExpanded)}
  tabindex="-1"
  role="button"
>
  <!-- Comment content -->
  <div class="space-y-2">
    {#if isEditing}
      <div class="space-y-2 pt-1">
        <textarea
          bind:value={editedComment}
          class="min-h-[80px] w-full resize-y rounded-md border border-stone-300 bg-white p-2 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          placeholder="Enter your comment..."
          on:keydown={handleKeydown}
        ></textarea>
        <div class="flex items-center justify-end gap-2">
          <button class="btn-small btn-secondary" on:click={handleCancel}> Cancel </button>
          <button
            class="btn-small btn-primary"
            on:click={handleSave}
            disabled={!editedComment.trim()}
          >
            Save
          </button>
        </div>
      </div>
    {:else}
      <div class="break-words whitespace-pre-wrap text-stone-900" class:line-clamp-2={!isExpanded}>
        {comment.comment}
      </div>
    {/if}
  </div>
  {#if !isEditing}
    <div class="flex items-end justify-between">
      <div class="flex items-center gap-2 text-sm text-stone-600">
        <span class="font-semibold text-stone-900">{comment.username || 'Unknown User'}</span>
        <span class="text-stone-400">•</span>
        <span class="text-stone-500" title={comment.created_at}
          >{getRelativeTime(comment.created_at)}</span
        >
        {#if comment.updated_at !== comment.created_at}
          <span class="text-stone-400">• edited</span>
        {/if}
      </div>

      {#if canEdit}
        <div class="flex items-center gap-2">
          <button class="btn-icon-small btn-fade" on:click={handleEdit} title="Edit comment">
            <Fa icon={faPencil} />
          </button>
          <button class="btn-icon-small btn-fade" on:click={handleDelete} title="Delete comment">
            <Fa icon={faTrash} />
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
