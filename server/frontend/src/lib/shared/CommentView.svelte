<svelte:options accessors />

<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { authStore, authenticatedFetch } from '$lib/stores/auth';
  import { projectID } from '$lib/stores/data';
  import Comment from './Comment.svelte';
  import Fa from 'svelte-fa';
  import { faPlus, faSpinner } from '@fortawesome/free-solid-svg-icons';

  const dispatch = createEventDispatcher();

  // Props
  export let entityType: 'patient' | 'spec';
  export let entityId: string;

  // State
  let creatingNewComment: boolean = false;
  let comments: any[] = [];
  let loading = false;
  let error: string | null = null;
  let newComment = '';
  let submittingComment = false;

  $: if (!!entityId) loadComments();
  else comments = [];

  export function createNewComment() {
    creatingNewComment = true;
  }

  async function loadComments() {
    loading = true;
    error = null;

    try {
      const endpoint =
        entityType === 'patient'
          ? `/api/projects/${$projectID}/patients/${entityId}/comments`
          : `/api/projects/${$projectID}/specs/${entityId}/comments`;

      const response = await authenticatedFetch(endpoint);

      if (!response.ok) {
        if (response.status != 404) throw new Error('Failed to load comments');
        else {
          loading = false;
          comments = [];
          return;
        }
      }

      comments = await response.json();
    } catch (err) {
      console.error('Error loading comments:', err);
      error = 'Failed to load comments';
      comments = [];
    } finally {
      loading = false;
    }
  }

  async function handleAddComment() {
    if (!newComment.trim()) return;

    submittingComment = true;
    error = null;

    try {
      const endpoint =
        entityType === 'patient'
          ? `/api/projects/${$projectID}/patients/${entityId}/comments`
          : `/api/projects/${$projectID}/specs/${entityId}/comments`;

      const response = await authenticatedFetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          comment: newComment.trim()
        })
      });

      if (!response.ok) {
        throw new Error('Failed to add comment');
      }

      const newCommentData = await response.json();
      comments = [newCommentData, ...comments];
      newComment = '';

      // Dispatch event for parent components to react to new comment
      dispatch('commentAdded', { comment: newCommentData });
    } catch (err) {
      console.error('Error adding comment:', err);
      error = 'Failed to add comment';
    } finally {
      submittingComment = false;
      creatingNewComment = false;
    }
  }

  async function handleEditComment(event: CustomEvent) {
    const { commentId, newComment: updatedComment } = event.detail;

    try {
      const endpoint =
        entityType === 'patient'
          ? `/api/projects/${$projectID}/patients/${entityId}/comments/${commentId}`
          : `/api/projects/${$projectID}/specs/${entityId}/comments/${commentId}`;

      const response = await authenticatedFetch(endpoint, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          comment: updatedComment
        })
      });

      if (!response.ok) {
        throw new Error('Failed to update comment');
      }

      const updatedCommentData = await response.json();

      // Update the comment in the list
      comments = comments.map((comment) =>
        comment.id === commentId ? updatedCommentData : comment
      );

      dispatch('commentEdited', { comment: updatedCommentData });
    } catch (err) {
      console.error('Error updating comment:', err);
      error = 'Failed to update comment';
    }
  }

  async function handleDeleteComment(event: CustomEvent) {
    const { commentId } = event.detail;

    try {
      const endpoint =
        entityType === 'patient'
          ? `/api/projects/${$projectID}/patients/${entityId}/comments/${commentId}`
          : `/api/projects/${$projectID}/specs/${entityId}/comments/${commentId}`;

      const response = await authenticatedFetch(endpoint, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error('Failed to delete comment');
      }

      // Remove the comment from the list
      comments = comments.filter((comment) => comment.id !== commentId);

      dispatch('commentDeleted', { commentId });
    } catch (err) {
      console.error('Error deleting comment:', err);
      error = 'Failed to delete comment';
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleAddComment();
    }
  }
</script>

<div class="space-y-4" class:mb-4={comments.length > 0 || creatingNewComment}>
  {#if comments.length > 0}
    <div class="text-sm font-bold uppercase">Comments</div>
  {/if}
  <!-- Error message -->
  {#if error}
    <div class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
      {error}
    </div>
  {/if}

  {#if creatingNewComment}
    <div class="space-y-2 pt-1">
      <textarea
        bind:value={newComment}
        placeholder="Add a comment..."
        class="min-h-[80px] w-full resize-y rounded-md border border-gray-300 p-3 focus:border-blue-500 focus:bg-white focus:ring-1 focus:ring-blue-500 focus:outline-none"
        on:keydown={handleKeydown}
        disabled={submittingComment}
      ></textarea>

      <div class="flex items-center justify-end gap-2">
        <button class="btn-small btn-secondary" on:click={() => (creatingNewComment = false)}>
          Cancel
        </button>
        <button
          class="btn-small btn-primary"
          on:click={handleAddComment}
          disabled={!newComment.trim() || submittingComment}
        >
          {#if submittingComment}
            <Fa icon={faSpinner} class="h-4 w-4 animate-spin" />
            Submitting...
          {:else}
            Save
          {/if}
        </button>
      </div>
    </div>
  {/if}

  <!-- Comments list -->
  {#if comments.length > 0}
    <div class="space-y-3">
      {#if loading}
        <div class="flex items-center justify-center py-8">
          <Fa icon={faSpinner} class="mr-2 h-6 w-6 animate-spin text-gray-400" />
          <span class="text-gray-500">Loading comments...</span>
        </div>
      {:else}
        {#each comments as comment (comment.id)}
          <Comment {comment} on:edit={handleEditComment} on:delete={handleDeleteComment} />
        {/each}
      {/if}
    </div>
  {/if}
</div>
