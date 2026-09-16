<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import Fa from 'svelte-fa';
  import { faUsers, faFolder, faPlus } from '@fortawesome/free-solid-svg-icons';
  import { authenticatedFetch, authStore } from '$lib/stores/auth';
  import TableView from '$lib/utils/TableView.svelte';
  import UserEditDialog from '$lib/admin/UserEditDialog.svelte';
  import ProjectEditDialog from '$lib/admin/ProjectEditDialog.svelte';

  type User = {
    id: number;
    username: string;
    created_at: string;
    last_login?: string;
    is_admin: boolean;
  };

  type Project = {
    id: number;
    name: string;
    source_connection: string;
    source_read_only: boolean;
    note_metadata_query?: string;
    note_text_query?: string;
    created_at?: string;
    updated_at?: string;
  };

  let activeTab = 'users';
  let users: User[] = [];
  let projects: Project[] = [];
  let selectedUserIds: string[] = [];
  let selectedProjectIds: string[] = [];
  let showUserDialog = false;
  let showProjectDialog = false;
  let editingUser: User | null = null;
  let editingProject: Project | null = null;
  let loading = false;
  let error = '';

  // Check admin access
  onMount(async () => {
    // Check if user is admin by trying to access admin endpoint
    try {
      await authenticatedFetch('/api/auth/users');
    } catch (e) {
      goto('/');
      return;
    }

    // Get active tab from URL
    const tab = $page.url.searchParams.get('tab');
    if (tab && ['users', 'projects'].includes(tab)) {
      activeTab = tab;
    }

    await loadData();
  });

  async function loadData() {
    loading = true;
    error = '';

    try {
      if (activeTab === 'users') {
        await loadUsers();
      } else if (activeTab === 'projects') {
        await loadProjects();
      }
    } catch (e) {
      console.error('Failed to load data:', e);
      error = 'Failed to load data. Please try again.';
    } finally {
      loading = false;
    }
  }

  async function loadUsers() {
    const response = await authenticatedFetch('/api/auth/users');
    if (response.ok) {
      users = await response.json();
    } else {
      throw new Error('Failed to load users');
    }
  }

  async function loadProjects() {
    const response = await authenticatedFetch('/api/projects?all=true');
    if (response.ok) {
      projects = await response.json();
    } else {
      throw new Error('Failed to load projects');
    }
  }

  function switchTab(tab: string) {
    activeTab = tab;
    selectedUserIds = [];
    selectedProjectIds = [];
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    goto(url.toString(), { replaceState: true });
    loadData();
  }

  function handleAddUser() {
    editingUser = null;
    showUserDialog = true;
  }

  function handleEditUser(event: CustomEvent) {
    const userId = parseInt(event.detail.item.id);
    editingUser = users.find((u) => u.id === userId) || null;
    showUserDialog = true;
  }

  function handleAddProject() {
    editingProject = null;
    showProjectDialog = true;
  }

  function handleEditProject(event: CustomEvent) {
    const projectId = parseInt(event.detail.item.id);
    editingProject = projects.find((p) => p.id === projectId) || null;
    showProjectDialog = true;
  }

  async function handleUserDelete(event: CustomEvent) {
    const userId = parseInt(event.detail.item.id);
    if (userId === $authStore.user?.id) {
      alert('You cannot delete your own account');
      return;
    }

    if (confirm('Are you sure you want to delete this user?')) {
      try {
        const response = await authenticatedFetch(`/api/auth/users/${userId}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          await loadUsers();
        } else {
          const errorData = await response.json();
          alert(`Failed to delete user: ${errorData.detail || 'Unknown error'}`);
        }
      } catch (e) {
        console.error('Delete error:', e);
        alert('Failed to delete user. Please try again.');
      }
    }
  }

  async function handleProjectDelete(event: CustomEvent) {
    const projectId = parseInt(event.detail.item.id);

    if (confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
      try {
        const response = await authenticatedFetch(`/api/projects/${projectId}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          await loadProjects();
        } else {
          const errorData = await response.json();
          alert(`Failed to delete project: ${errorData.detail || 'Unknown error'}`);
        }
      } catch (e) {
        console.error('Delete error:', e);
        alert('Failed to delete project. Please try again.');
      }
    }
  }

  function handleUserDialogSuccess() {
    showUserDialog = false;
    editingUser = null;
    loadUsers();
  }

  function handleProjectDialogSuccess() {
    showProjectDialog = false;
    editingProject = null;
    loadProjects();
  }

  // Format users for TableView
  $: userItems = users.map((user) => ({
    id: user.id.toString(),
    name: user.username,
    value: user.is_admin ? 'Admin' : 'User'
  }));

  // Format projects for TableView
  $: projectItems = projects.map((project) => ({
    id: project.id.toString(),
    name: project.name,
    value: project.source_read_only ? 'Read-only' : 'Read-write'
  }));
</script>

<svelte:head>
  <title>Admin Console</title>
</svelte:head>

<div class="flex h-full w-full">
  <!-- Sidebar -->
  <div class="flex w-64 flex-col bg-white">
    <div class="p-4">
      <h2 class="text-lg font-bold text-stone-900">Admin</h2>
    </div>

    <nav class="flex-1 p-4">
      <ul class="space-y-2">
        <li>
          <button
            on:click={() => switchTab('users')}
            class="flex w-full items-center rounded-lg px-4 py-2 font-medium transition-colors {activeTab ===
            'users'
              ? 'bg-sky-100 text-sky-800'
              : 'cursor-pointer text-stone-700 hover:bg-stone-100'}"
          >
            <Fa icon={faUsers} class="mr-3 h-4 w-4" />
            Users
          </button>
        </li>
        <li>
          <button
            on:click={() => switchTab('projects')}
            class="flex w-full items-center rounded-lg px-4 py-2 font-medium transition-colors {activeTab ===
            'projects'
              ? 'bg-sky-100 text-sky-800'
              : 'cursor-pointer text-stone-700 hover:bg-stone-100'}"
          >
            <Fa icon={faFolder} class="mr-3 h-4 w-4" />
            Projects
          </button>
        </li>
      </ul>
    </nav>
  </div>

  <!-- Main content -->
  <div class="flex flex-1 flex-col">
    <!-- Header -->
    <div class="bg-white px-4 pt-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-stone-900">
          {activeTab === 'users' ? 'Users' : 'Projects'}
        </h2>

        {#if activeTab === 'users'}
          <button on:click={handleAddUser} class="btn btn-primary" disabled={loading}>
            <Fa icon={faPlus} class="mr-2 inline" /> User
          </button>
        {:else if activeTab === 'projects'}
          <button on:click={handleAddProject} class="btn btn-primary" disabled={loading}>
            <Fa icon={faPlus} class="mr-2 inline" /> Project
          </button>
        {/if}
      </div>
    </div>

    <!-- Content area -->
    <div class="flex-1 py-4">
      {#if error}
        <div class="mx-4 mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      {/if}

      {#if loading}
        <div class="flex items-center justify-center py-12">
          <div class="animate-pulse text-stone-500">Loading...</div>
        </div>
      {:else if activeTab === 'users'}
        <TableView
          items={userItems}
          selectedItemId={showUserDialog ? (editingUser?.id.toString() ?? null) : null}
          selectedItemIds={selectedUserIds}
          nameColumnTitle="Username"
          valueColumnTitle="Role"
          allowSearch
          allowTags={false}
          allowDelete
          on:select={handleEditUser}
          on:delete={handleUserDelete}
        />
      {:else if activeTab === 'projects'}
        <TableView
          items={projectItems}
          selectedItemId={showProjectDialog ? (editingProject?.id.toString() ?? null) : null}
          selectedItemIds={selectedProjectIds}
          nameColumnTitle="Project Name"
          valueColumnTitle="Source Database"
          allowSearch
          allowTags={false}
          allowDelete
          on:select={handleEditProject}
          on:delete={handleProjectDelete}
        />
      {/if}
    </div>
  </div>
</div>

<!-- Dialogs -->
<UserEditDialog
  bind:isOpen={showUserDialog}
  user={editingUser}
  showAdminControls
  on:success={handleUserDialogSuccess}
  on:close={() => {
    showUserDialog = false;
    editingUser = null;
  }}
/>

<ProjectEditDialog
  bind:isOpen={showProjectDialog}
  project={editingProject}
  on:success={handleProjectDialogSuccess}
  on:close={() => {
    showProjectDialog = false;
    editingProject = null;
  }}
/>
