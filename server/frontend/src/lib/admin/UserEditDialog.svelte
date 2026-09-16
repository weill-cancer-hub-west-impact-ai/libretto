<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';
  import { faXmark, faTrash } from '@fortawesome/free-solid-svg-icons';
  import { authenticatedFetch, authStore } from '$lib/stores/auth';

  export let isOpen: boolean = false;
  export let user: {
    id: number;
    username: string;
    created_at: string;
    last_login?: string;
    is_admin: boolean;
  } | null = null;

  const dispatch = createEventDispatcher();

  export let showAdminControls: boolean = false; // set to true to allow editing as admin

  let username = '';
  let password = '';
  let isAdmin = false;
  let saving = false;
  let deleting = false;
  let errorMessage = '';

  $: if (isOpen && user) {
    // Editing existing user
    username = user.username;
    password = '';
    isAdmin = user.is_admin;
    errorMessage = '';
  } else if (isOpen && !user) {
    // Creating new user
    username = '';
    password = '';
    isAdmin = false;
    errorMessage = '';
  }

  $: isCreating = !user;
  $: canDeleteUser = user && user.id !== $authStore.user?.id;
  $: canChangeAdminStatus = !user || user.id !== $authStore.user?.id;

  async function handleSave() {
    if (!username.trim()) {
      errorMessage = 'Username is required';
      return;
    }

    if (isCreating && !password.trim()) {
      errorMessage = 'Password is required for new users';
      return;
    }

    saving = true;
    errorMessage = '';

    try {
      let response;

      if (isCreating) {
        // Create new user
        response = await authenticatedFetch('/api/auth/users', {
          method: 'POST',
          body: JSON.stringify({
            username: username.trim(),
            password: password,
            is_admin: isAdmin
          })
        });
      } else {
        // Update existing user
        const updateData: any = {};
        if (password.trim()) {
          updateData.password = password;
        }
        if (canChangeAdminStatus) {
          updateData.is_admin = isAdmin;
        }

        response = await authenticatedFetch(
          showAdminControls ? `/api/auth/users/${user!.id}` : `/api/auth/me/password`,
          {
            method: 'PUT',
            body: JSON.stringify(updateData)
          }
        );
      }

      if (response.ok) {
        dispatch('success');
        handleClose();
      } else {
        const errorData = await response.json();
        errorMessage = errorData.detail || `Failed to ${isCreating ? 'create' : 'update'} user`;
      }
    } catch (error) {
      console.error('Save error:', error);
      errorMessage = `Failed to ${isCreating ? 'create' : 'update'} user. Please try again.`;
    } finally {
      saving = false;
    }
  }

  async function handleDelete() {
    if (!user || !canDeleteUser) return;

    if (confirm(`Are you sure you want to delete user "${user.username}"?`)) {
      deleting = true;
      errorMessage = '';

      try {
        const response = await authenticatedFetch(`/api/auth/users/${user.id}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          dispatch('success');
          handleClose();
        } else {
          const errorData = await response.json();
          errorMessage = errorData.detail || 'Failed to delete user';
        }
      } catch (error) {
        console.error('Delete error:', error);
        errorMessage = 'Failed to delete user. Please try again.';
      } finally {
        deleting = false;
      }
    }
  }

  function handleClose() {
    username = '';
    password = '';
    isAdmin = false;
    errorMessage = '';
    saving = false;
    deleting = false;
    dispatch('close');
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
    } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      handleSave();
      event.stopPropagation();
      event.preventDefault();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
  <!-- Modal backdrop -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    on:click={handleBackdropClick}
    on:keydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    tabindex="-1"
  >
    <!-- Modal content -->
    <div class="mx-4 flex max-h-3/4 w-full max-w-xl flex-col rounded-lg bg-white py-4 shadow-xl">
      <!-- Header -->
      <div class="mb-4 flex shrink-0 items-center justify-between px-6">
        <h2 id="modal-title" class="text-lg font-bold text-gray-900">
          {showAdminControls
            ? 'Account Settings'
            : isCreating
              ? 'Create User'
              : `Edit User "${user?.username}"`}
        </h2>
        <button
          on:click={handleClose}
          class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close modal"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <div class="min-h-0 w-full overflow-y-auto px-6">
        <!-- Form -->
        <div class="space-y-4">
          <!-- Username -->
          <div>
            <label for="username" class="block text-sm font-medium text-gray-700"> Username </label>
            <input
              id="username"
              bind:value={username}
              type="text"
              disabled={!isCreating}
              class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500 focus:outline-none disabled:bg-gray-100 disabled:text-gray-500"
              placeholder="Enter username"
              required
            />
            {#if !isCreating}
              <p class="mt-1 text-xs text-gray-500">Username cannot be changed</p>
            {/if}
          </div>

          <!-- Password -->
          <div>
            <label for="password" class="block text-sm font-medium text-gray-700">
              {isCreating ? 'Password' : 'New Password (leave blank to keep current)'}
            </label>
            <input
              id="password"
              bind:value={password}
              type="password"
              class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500 focus:outline-none"
              placeholder={isCreating ? 'Enter password' : 'Enter new password'}
              required={isCreating}
            />
          </div>

          {#if showAdminControls}
            <!-- Admin checkbox -->
            <div class="flex items-center">
              <input
                id="is-admin"
                bind:checked={isAdmin}
                type="checkbox"
                disabled={!canChangeAdminStatus}
                class="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500 disabled:bg-gray-100 disabled:text-gray-400"
              />
              <label for="is-admin" class="ml-2 block text-sm text-gray-700">
                Administrator privileges
              </label>
            </div>

            {#if !canChangeAdminStatus}
              <p class="text-xs text-gray-500">You cannot change your own admin status</p>
            {/if}
          {/if}

          {#if user && !isCreating}
            <!-- User info -->
            <div class="space-y-2 rounded-lg bg-gray-50 p-3 text-sm">
              <div>
                <span class="font-medium text-gray-700">Created:</span>
                <span class="text-gray-600">
                  {new Date(user.created_at).toLocaleString()}
                </span>
              </div>
              {#if user.last_login}
                <div>
                  <span class="font-medium text-gray-700">Last login:</span>
                  <span class="text-gray-600">
                    {new Date(user.last_login).toLocaleString()}
                  </span>
                </div>
              {:else}
                <div>
                  <span class="font-medium text-gray-700">Last login:</span>
                  <span class="text-gray-500">Never</span>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      </div>

      <!-- Error message -->
      {#if errorMessage}
        <div class="mx-6 mt-4 mb-4 shrink-0 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {errorMessage}
        </div>
      {/if}

      <!-- Actions -->
      <div class="flex shrink-0 justify-between px-6 pt-4">
        <div>
          {#if !isCreating && canDeleteUser && showAdminControls}
            <button on:click={handleDelete} disabled={deleting || saving} class="btn btn-danger">
              <Fa icon={faTrash} class="mr-2 inline h-3 w-3" />
              {deleting ? 'Deleting...' : 'Delete'}
            </button>
          {/if}
        </div>

        <div class="flex space-x-3">
          <button on:click={handleClose} disabled={saving || deleting} class="btn btn-secondary">
            Cancel
          </button>
          <button on:click={handleSave} disabled={saving || deleting} class="btn btn-primary">
            {saving ? 'Saving...' : isCreating ? 'Create' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
