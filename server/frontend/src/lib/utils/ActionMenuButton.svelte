<script lang="ts">
  import { faEllipsisVertical } from '@fortawesome/free-solid-svg-icons';
  import { untrack } from 'svelte';
  import Fa from 'svelte-fa';

  let {
    visible = $bindable(false),
    buttonClass = 'bg-transparent hover:opacity-60 text-slate-600 py-2 px-1 mr-2',
    buttonActiveClass = '',
    buttonTitle = 'Show more actions',
    buttonStyle = '',
    align = 'left' as 'left' | 'center' | 'right',
    menuWidth = 240,
    disabled = false,
    onShow = undefined,
    onHide = undefined,
    singleClick = true,
    buttonContent = null,
    options
  } = $props();

  let optionsMenuOpacity = $state(0.0);
  let optionsMenu = $state<Element>();
  let observer = $state<ResizeObserver | null>(null);
  let button = $state<HTMLElement>();
  let container = $state<HTMLElement>();
  let menuX = $state(0);
  let menuY = $state(0);
  let loaded = $state(false);

  // Effect to handle mount
  $effect(() => {
    loaded = true;
  });

  // Effect to handle visibility changes
  $effect(() => {
    if (visible && loaded) {
      window.addEventListener('keydown', escapeOptionsMenu, true);
      untrack(() => {
        if (button) {
          if (observer) observer.unobserve(button);
          observer = new ResizeObserver(() => {
            if (!container || !button) return;
            let bounds = button.getBoundingClientRect();
            let containerBounds = container.getBoundingClientRect();
            if (align == 'left') menuX = bounds.left - containerBounds.left;
            else if (align == 'right') menuX = bounds.right - containerBounds.left;
            else if (align == 'center')
              menuX = bounds.left + bounds.width / 2 - containerBounds.left;
            menuY = bounds.bottom - containerBounds.top;
          });
          observer.observe(button);
        }
      });
    } else if (loaded) {
      window.removeEventListener('keydown', escapeOptionsMenu, true);
      untrack(() => {
        if (button && observer) {
          observer.unobserve(button);
          observer = null;
        }
      });
    }
  });

  function escapeOptionsMenu(e) {
    if (e.key === 'Escape') {
      hideOptionsMenu();
      e.stopPropagation();
      e.preventDefault();
    }
  }

  function showOptionsMenu() {
    optionsMenuOpacity = 0;
    visible = true;
    setTimeout(() => (optionsMenuOpacity = 1.0), 10);
    if (!!optionsMenu) optionsMenu.focus();
    if (!!onShow) onShow();
  }

  function hideOptionsMenu() {
    optionsMenuOpacity = 0;
    setTimeout(() => (visible = false), 200);
    if (!!onHide) onHide();
  }

  function dismiss() {
    visible = false;
  }
</script>

<div class="relative">
  <button
    type="button"
    bind:this={button}
    class="{buttonClass} {visible ? buttonActiveClass : ''}"
    style={buttonStyle}
    id="menu-button"
    title={buttonTitle}
    {disabled}
    onclick={(e) => {
      e.stopPropagation();
      showOptionsMenu();
    }}
    aria-expanded={visible}
    aria-label="Options menu"
    aria-haspopup="true"
  >
    {#if buttonContent}
      {@render buttonContent()}
    {:else}
      <Fa icon={faEllipsisVertical} class="inline text-center" />
    {/if}
  </button>
  {#if visible}
    <div
      class="fixed top-0 right-0 bottom-0 left-0 h-full w-full"
      bind:this={container}
      style="z-index: 999;"
      onclick={(e) => {
        e.stopPropagation();
        hideOptionsMenu();
      }}
      onkeydown={(e) => {}}
    >
      <div
        class="absolute overflow-y-auto rounded-md bg-white shadow-lg ring-1 ring-gray-400/50 transition-opacity duration-200 focus:outline-none"
        style="top: {menuY}px; max-height: calc(100% - {menuY +
          12}px); left: {menuX}px; opacity: {optionsMenuOpacity}; width: {menuWidth}px; transform: translate({align ==
        'right'
          ? '-100%'
          : align == 'center'
            ? '-50%'
            : '0'}, 4px); z-index: 1000;"
        role="menu"
        aria-orientation="vertical"
        aria-labelledby="menu-button"
        bind:this={optionsMenu}
        onclick={(e) => {
          e.stopPropagation();
          if (singleClick) hideOptionsMenu();
        }}
        onkeydown={(e) => {}}
      >
        <div class="menu-options my-1" role="none">
          {#if options}
            {@render options(dismiss)}
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>
