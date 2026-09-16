<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import Fa from 'svelte-fa';
  import { faXmark, faTrash, faPlus } from '@fortawesome/free-solid-svg-icons';
  import { authenticatedFetch } from '$lib/stores/auth';
  import TableView from '$lib/utils/TableView.svelte';
  import ActionMenuButton from '$lib/utils/ActionMenuButton.svelte';
  import { areObjectsEqual } from '$lib/utils/utils';

  export let isOpen: boolean = false;
  export let project: {
    id: number;
    name: string;
    source_connection: string;
    source_read_only: boolean;
    note_metadata_query?: string;
    note_text_query?: string;
    created_at?: string;
    updated_at?: string;
  } | null = null;

  const dispatch = createEventDispatcher();

  let name = '';
  let sourceConnection = '';
  let sourceReadOnly = false;
  let noteMetadataQuery = '';
  let noteTextQuery = '';
  let environmentVars = '';
  let saving = false;
  let deleting = false;
  let errorMessage = '';

  // Project users management
  let projectUserIDs: string[] = [];
  let editedProjectUserIDs: string[] = [];
  let allUsers: any[] = [];
  let loadingUsers = false;

  $: if (isOpen && project) {
    // Editing existing project
    name = project.name;
    sourceConnection = project.source_connection;
    sourceReadOnly = project.source_read_only;
    noteMetadataQuery = project.note_metadata_query || '';
    noteTextQuery = project.note_text_query || '';
    environmentVars = '';
    errorMessage = '';
    loadProjectUsers();
    loadAllUsers();
  } else if (isOpen && !project) {
    // Creating new project
    name = '';
    sourceConnection = '';
    sourceReadOnly = false;
    noteMetadataQuery = '';
    noteTextQuery = '';
    environmentVars = '';
    errorMessage = '';
    projectUserIDs = [];
    editedProjectUserIDs = [];
    allUsers = [];
  }

  $: isCreating = !project;

  async function loadProjectUsers() {
    if (!project) return;

    loadingUsers = true;
    try {
      const response = await authenticatedFetch(`/api/projects/${project.id}/users`);
      if (response.ok) {
        projectUserIDs = (await response.json()).map((u: any) => u.id.toString());
        editedProjectUserIDs = [...projectUserIDs];
        console.log('project user IDs:', projectUserIDs);
      }
    } catch (error) {
      console.error('Failed to load project users:', error);
    } finally {
      loadingUsers = false;
    }
  }

  async function loadAllUsers() {
    try {
      const response = await authenticatedFetch('/api/auth/users');
      if (response.ok) {
        allUsers = await response.json();
      }
    } catch (error) {
      console.error('Failed to load all users:', error);
    }
  }

  async function handleSave() {
    if (!name.trim()) {
      errorMessage = 'Project name is required';
      return;
    }

    if (!sourceConnection.trim()) {
      errorMessage = 'Source connection is required';
      return;
    }

    saving = true;
    errorMessage = '';

    try {
      let envVars = null;
      if (environmentVars.trim()) {
        try {
          envVars = JSON.parse(environmentVars);
        } catch (e) {
          errorMessage = 'Environment variables must be valid JSON';
          saving = false;
          return;
        }
      }

      let response;
      const projectData = {
        name: name.trim(),
        source_connection: sourceConnection.trim(),
        source_read_only: sourceReadOnly,
        note_metadata_query: noteMetadataQuery.trim() || null,
        note_text_query: noteTextQuery.trim() || null,
        environment_vars: envVars
      };

      if (isCreating) {
        // Create new project
        response = await authenticatedFetch('/api/projects', {
          method: 'POST',
          body: JSON.stringify(projectData)
        });
      } else {
        // Update existing project
        response = await authenticatedFetch(`/api/projects/${project!.id}`, {
          method: 'PUT',
          body: JSON.stringify(projectData)
        });
      }

      // Update project access
      if (!areObjectsEqual(editedProjectUserIDs, projectUserIDs)) {
        let unionUsers = new Set([...editedProjectUserIDs, ...projectUserIDs]);
        unionUsers.forEach((userID) => {
          if (editedProjectUserIDs.includes(userID) && !projectUserIDs.includes(userID))
            handleAddUser(parseInt(userID));
          else if (!editedProjectUserIDs.includes(userID) && projectUserIDs.includes(userID))
            handleRemoveUser(parseInt(userID));
        });
      }

      if (response.ok) {
        dispatch('success');
        handleClose();
      } else {
        const errorData = await response.json();
        errorMessage = errorData.detail || `Failed to ${isCreating ? 'create' : 'update'} project`;
      }
    } catch (error) {
      console.error('Save error:', error);
      errorMessage = `Failed to ${isCreating ? 'create' : 'update'} project. Please try again.`;
    } finally {
      saving = false;
    }
  }

  async function handleDelete() {
    if (!project) return;

    if (
      confirm(
        `Are you sure you want to delete project "${project.name}"? This action cannot be undone and will remove all associated data.`
      )
    ) {
      deleting = true;
      errorMessage = '';

      try {
        const response = await authenticatedFetch(`/api/projects/${project.id}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          dispatch('success');
          handleClose();
        } else {
          const errorData = await response.json();
          errorMessage = errorData.detail || 'Failed to delete project';
        }
      } catch (error) {
        console.error('Delete error:', error);
        errorMessage = 'Failed to delete project. Please try again.';
      } finally {
        deleting = false;
      }
    }
  }

  async function handleAddUser(userId: number) {
    if (!project) return;

    await authenticatedFetch(`/api/projects/${project.id}/users`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId })
    });
  }

  async function handleRemoveUser(userId: number) {
    if (!project) return;

    await authenticatedFetch(`/api/projects/${project.id}/users/${userId}`, {
      method: 'DELETE'
    });
  }

  function handleClose() {
    name = '';
    sourceConnection = '';
    sourceReadOnly = false;
    noteMetadataQuery = '';
    noteTextQuery = '';
    environmentVars = '';
    errorMessage = '';
    saving = false;
    deleting = false;
    projectUserIDs = [];
    editedProjectUserIDs = [];
    allUsers = [];
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
    }
  }

  // Format users for TableView
  $: projectUserItems = allUsers.map((user) => ({
    id: user.id.toString(),
    name: user.username,
    value: user.is_admin ? 'Admin' : 'User'
  }));
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
    <div class="mx-4 flex h-5/6 w-3/4 flex-col rounded-lg bg-white py-4 shadow-xl">
      <!-- Header -->
      <div class="mb-4 flex shrink-0 items-center justify-between px-6">
        <h2 id="modal-title" class="text-lg font-bold text-gray-900">
          {isCreating ? 'Create Project' : `Edit Project "${project?.name}"`}
        </h2>
        <button
          on:click={handleClose}
          class="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close modal"
        >
          <Fa icon={faXmark} />
        </button>
      </div>

      <div class="min-h-0 w-full flex-auto px-6">
        <div class="grid h-full w-full grid-cols-1 gap-2 lg:grid-cols-2">
          <!-- Project Settings -->
          <div class="space-y-4 overflow-y-auto pr-2">
            <h3 class="text-base font-semibold text-gray-900">Project Settings</h3>

            <!-- Name -->
            <div>
              <label for="name" class="block text-sm font-medium text-gray-700">
                Project Name
              </label>
              <input
                id="name"
                bind:value={name}
                type="text"
                class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500 focus:outline-none"
                placeholder="Enter project name"
                required
              />
            </div>

            <!-- Source Connection -->
            <div>
              <label for="source-connection" class="block text-sm font-medium text-gray-700">
                SQL Connection String
              </label>
              <input
                id="source-connection"
                bind:value={sourceConnection}
                type="text"
                class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500 focus:outline-none"
                placeholder="postgresql://user:password@host:port/database"
                required
              />
            </div>

            <!-- Read-only checkbox -->
            <div class="flex items-center">
              <input
                id="read-only"
                bind:checked={sourceReadOnly}
                type="checkbox"
                class="h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500"
              />
              <label for="read-only" class="ml-2 block text-sm text-gray-700">
                Read-only access
              </label>
            </div>

            <!-- Note Metadata Query -->
            <div>
              <label for="note-metadata-query" class="block text-sm font-medium text-gray-700">
                Note Metadata Query (optional)
              </label>
              <textarea
                id="note-metadata-query"
                bind:value={noteMetadataQuery}
                rows="3"
                class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500 focus:outline-none"
                placeholder="SELECT statement for note metadata"
              ></textarea>
            </div>

            <!-- Note Text Query -->
            <div>
              <label for="note-text-query" class="block text-sm font-medium text-gray-700">
                Note Text Query (optional)
              </label>
              <textarea
                id="note-text-query"
                bind:value={noteTextQuery}
                rows="3"
                class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500 focus:outline-none"
                placeholder="SELECT statement for note text"
              ></textarea>
            </div>

            <!-- Environment Variables -->
            <div>
              <label for="environment-vars" class="block text-sm font-medium text-gray-700">
                Environment Variables (JSON)
              </label>
              <textarea
                id="environment-vars"
                bind:value={environmentVars}
                rows="4"
                class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-sky-500 focus:ring-2 focus:ring-sky-500 focus:outline-none"
                placeholder={'{"API_KEY": "value", "ENV": "production"}'}
              ></textarea>
              <p class="mt-1 text-xs text-gray-500">Optional. Must be valid JSON if provided.</p>
            </div>
          </div>

          <!-- Project Users -->
          <div class="flex flex-col gap-4 overflow-y-auto pl-2">
            <div>
              <h3 class="text-base font-semibold text-gray-900">Project Users</h3>
              <p class="mt-1 text-xs text-gray-500">
                Select users that should have access to the project data.
              </p>
            </div>

            {#if loadingUsers}
              <div class="flex items-center justify-center py-8">
                <div class="animate-pulse text-gray-500">Loading users...</div>
              </div>
            {:else}
              <div class="min-h-32 flex-auto">
                <TableView
                  items={projectUserItems}
                  bind:selectedItemIds={editedProjectUserIDs}
                  nameColumnTitle="Username"
                  valueColumnTitle="Role"
                  allowSearch={false}
                  allowTags={false}
                  allowDelete={false}
                  allowMultiselect
                  allowSingleSelect={false}
                />
              </div>
            {/if}
          </div>
        </div>
      </div>

      <!-- Error message -->
      {#if errorMessage}
        <div class="mt-4 mb-4 shrink-0 rounded-lg bg-red-50 p-3 px-6 text-sm text-red-700">
          {errorMessage}
        </div>
      {/if}

      <!-- Actions -->
      <div class="flex shrink-0 justify-between px-6 pt-4">
        <div>
          {#if !isCreating && project}
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
