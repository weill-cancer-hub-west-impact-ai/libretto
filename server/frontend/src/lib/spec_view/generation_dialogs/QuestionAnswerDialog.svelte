<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';
  import { faXmark, faChevronRight } from '@fortawesome/free-solid-svg-icons';
  import type { BuildWorkflowQuestion } from './types';

  export let isOpen: boolean = false;
  export let questions: BuildWorkflowQuestion[] = [];

  const dispatch = createEventDispatcher<{
    submit: { answers: string[] };
    cancel: void;
  }>();

  let currentIndex = 0;
  let answers: string[] = [];

  let otherResponse: string = '';
  $: if (currentIndex) {
    otherResponse = '';
  }

  $: if (isOpen && questions.length > 0) {
    currentIndex = 0;
    answers = new Array(questions.length).fill('');
  }

  $: currentQuestion = questions[currentIndex] ?? null;
  $: isLastQuestion = currentIndex === questions.length - 1;

  function selectAnswer(choice: string) {
    answers[currentIndex] = choice;
  }

  function handleNext() {
    if (!answers[currentIndex]) return;
    if (isLastQuestion) {
      dispatch('submit', { answers: [...answers] });
    } else {
      currentIndex += 1;
    }
  }

  function handleClose() {
    dispatch('cancel');
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
    } else if (event.key === 'Enter' && answers[currentIndex]) {
      handleNext();
      event.stopPropagation();
      event.preventDefault();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen && currentQuestion}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    on:click={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    aria-labelledby="qa-modal-title"
    tabindex="-1"
  >
    <!-- Modal content -->
    <div class="mx-4 flex w-full max-w-lg flex-col rounded-lg bg-white py-4 shadow-xl">
      <!-- Header -->
      <div class="mb-4 flex shrink-0 items-center justify-between px-6">
        <div>
          <h2 id="qa-modal-title" class="text-lg font-bold text-gray-900">Follow-up Question</h2>
          {#if questions.length > 1}
            <p class="text-sm text-gray-500">{currentIndex + 1} of {questions.length}</p>
          {/if}
        </div>
        <button
          on:click={handleClose}
          class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <!-- Question -->
      <div class="px-6 pb-2">
        <p class="text-base font-medium text-gray-800">{currentQuestion.question}</p>
      </div>

      <!-- Answer choices -->
      <div class="min-h-0 overflow-y-auto px-6 py-2">
        <div class="space-y-2">
          {#each currentQuestion.answer_choices as choice}
            <button
              on:click={() => selectAnswer(choice)}
              class="w-full rounded-md border px-4 py-3 text-left text-sm transition-colors
                {answers[currentIndex] === choice
                ? 'border-sky-500 bg-sky-50 font-medium text-sky-700'
                : 'border-stone-200 bg-white text-stone-700 hover:border-stone-300 hover:bg-stone-50'}"
            >
              {choice}
            </button>
          {/each}
          <input
            type="text"
            value={otherResponse}
            on:input={(e) => {
              otherResponse = (e.target as HTMLInputElement).value;
              answers[currentIndex] = otherResponse;
            }}
            placeholder="Enter a different response..."
            class="w-full rounded-md border border-stone-300 px-2 py-1 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>
      </div>

      <!-- Progress dots -->
      {#if questions.length > 1}
        <div class="flex justify-center gap-1.5 px-6 pt-4">
          {#each questions as _, i}
            <div
              class="h-1.5 w-1.5 rounded-full transition-colors
                {i === currentIndex
                ? 'bg-sky-500'
                : i < currentIndex
                  ? 'bg-sky-200'
                  : 'bg-stone-200'}"
            ></div>
          {/each}
        </div>
      {/if}

      <!-- Actions -->
      <div class="flex shrink-0 justify-end gap-3 px-6 pt-4">
        <button on:click={handleClose} class="btn btn-secondary"> Cancel </button>
        <button
          on:click={handleNext}
          disabled={!answers[currentIndex]}
          class="btn btn-primary inline-flex items-center gap-2"
        >
          {isLastQuestion ? 'Submit' : 'Next'}
          {#if !isLastQuestion}
            <Fa icon={faChevronRight} class="h-3 w-3" />
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
