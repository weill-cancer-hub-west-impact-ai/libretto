<script lang="ts">
  import { faCheck, faXmark, faComment } from '@fortawesome/free-solid-svg-icons';
  import Fa from 'svelte-fa';
  import ActionMenuButton from '$lib/utils/ActionMenuButton.svelte';
  import type { Feedback } from '$lib/extraction_types';

  interface Props {
    feedback?: Feedback;
    onFeedbackChange: (feedback: {
      approved: boolean;
      rejected: boolean;
      comment?: string;
    }) => void;
  }

  let { feedback, onFeedbackChange }: Props = $props();

  // Local state for feedback
  let approved = $derived(feedback?.approved ?? false);
  let rejected = $derived(feedback?.rejected ?? false);
  let comment = $derived(feedback?.comment ?? '');
  let showApproveEditor = $state(false);
  let showRejectEditor = $state(false);
  let showCommentEditor = $state(false);
  let commentText = $derived(feedback?.comment ?? '');

  $effect(() => console.log('feedback:', feedback));

  function handleApprove() {
    approved = !approved;
    if (approved) {
      rejected = false;
    }
    onFeedbackChange({ approved, rejected, comment });
  }

  function handleReject() {
    rejected = !rejected;
    if (rejected) {
      approved = false;
    }
    onFeedbackChange({ approved, rejected, comment });
  }

  function handleCommentSave() {
    comment = commentText;
    onFeedbackChange({ approved, rejected, comment });
    showCommentEditor = false;
    showApproveEditor = false;
    showRejectEditor = false;
  }

  function handleCommentCancel() {
    commentText = comment; // Reset to previous value
    showCommentEditor = false;
    showApproveEditor = false;
    showRejectEditor = false;
  }
</script>

{#snippet commentMenu()}
  <div class="space-y-3 p-4">
    <div>
      <label for="comment-textarea" class="mb-2 block text-sm font-medium text-gray-700">
        Comment
      </label>
      <textarea
        id="comment-textarea"
        bind:value={commentText}
        class="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500 focus:outline-none"
        rows="4"
        placeholder="Enter your comment..."
      ></textarea>
    </div>
    <div class="flex justify-end gap-2">
      <button
        class="px-3 py-1 text-sm text-gray-600 transition-colors hover:opacity-50"
        onclick={handleCommentCancel}
      >
        Cancel
      </button>
      <button
        class="rounded bg-blue-500 px-3 py-1 text-sm text-white transition-colors hover:bg-blue-600"
        onclick={handleCommentSave}
      >
        Save
      </button>
    </div>
  </div>
{/snippet}
<div class="ml-2 flex items-center gap-1">
  <!-- Approve Button -->
  <ActionMenuButton
    bind:visible={showApproveEditor}
    buttonClass="flex h-6 w-6 items-center justify-center rounded-full transition-colors
           {approved ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-600 hover:bg-green-100'}"
    buttonTitle="Accept"
    align="right"
    menuWidth={320}
    singleClick={false}
    onShow={() => {
      if (approved) showApproveEditor = false;
      handleApprove();
    }}
  >
    {#snippet buttonContent()}
      <Fa icon={faCheck} size="xs" />
    {/snippet}

    {#snippet options()}
      {@render commentMenu()}
    {/snippet}
  </ActionMenuButton>

  <!-- Reject Button -->
  <ActionMenuButton
    bind:visible={showRejectEditor}
    buttonClass="flex h-6 w-6 items-center justify-center rounded-full transition-colors
           {rejected ? 'bg-red-500 text-white' : 'bg-gray-200 text-gray-600 hover:bg-red-100'}"
    buttonTitle="Reject"
    align="right"
    menuWidth={320}
    singleClick={false}
    onShow={() => {
      if (rejected) showRejectEditor = false;
      handleReject();
    }}
  >
    {#snippet buttonContent()}
      <Fa icon={faXmark} size="xs" />
    {/snippet}

    {#snippet options()}
      {@render commentMenu()}
    {/snippet}
  </ActionMenuButton>

  <!-- Comment Button -->
  <ActionMenuButton
    bind:visible={showCommentEditor}
    buttonClass="w-6 h-6 rounded-full flex items-center justify-center transition-colors
                {comment
      ? 'bg-blue-500 text-white'
      : 'bg-gray-200 hover:bg-blue-100 text-gray-600'}"
    buttonTitle="Add Comment"
    align="right"
    menuWidth={320}
    singleClick={false}
  >
    {#snippet buttonContent()}
      <Fa icon={faComment} size="xs" />
    {/snippet}

    {#snippet options()}
      {@render commentMenu()}
    {/snippet}
  </ActionMenuButton>
</div>
