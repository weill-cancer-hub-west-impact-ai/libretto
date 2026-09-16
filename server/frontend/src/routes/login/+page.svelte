<script>
  import { browser } from '$app/environment';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { authStore } from '$lib/stores/auth.js';

  let username = '';
  let password = '';
  let isLoading = false;
  let error = '';

  // Redirect if already logged in
  onMount(() => {
    if (browser && $authStore.isAuthenticated) {
      goto('/');
    }
  });

  async function handleLogin() {
    if (!username || !password) {
      error = 'Please enter both username and password';
      return;
    }

    isLoading = true;
    error = '';

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
      });

      const data = await response.json();

      if (response.ok) {
        // Store the token and user info
        authStore.login(data.access_token, data.username, data.is_admin);
        window.location.href = '/';
      } else {
        error = data.detail || 'Login failed';
      }
    } catch (err) {
      error = 'Network error. Please try again.';
    } finally {
      isLoading = false;
    }
  }

  function handleKeydown(event) {
    if (event.key === 'Enter') {
      handleLogin();
    }
  }
</script>

<div class="flex min-h-full items-center justify-center bg-gray-50">
  <div class="w-full max-w-md space-y-8 p-8">
    <div>
      <h2 class="text-center text-3xl font-extrabold text-gray-900">Welcome to Libretto</h2>
    </div>

    <form class="mt-8 space-y-6" on:submit|preventDefault={handleLogin}>
      <div class="space-y-4">
        <div>
          <label for="username" class="sr-only">Username</label>
          <input
            id="username"
            name="username"
            type="text"
            autocomplete="username"
            required
            class="relative block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-500 focus:z-10 focus:border-indigo-500 focus:ring-indigo-500 focus:outline-none sm:text-sm"
            placeholder="Username"
            bind:value={username}
            on:keydown={handleKeydown}
            disabled={isLoading}
          />
        </div>

        <div>
          <label for="password" class="sr-only">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autocomplete="current-password"
            required
            class="relative block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-500 focus:z-10 focus:border-indigo-500 focus:ring-indigo-500 focus:outline-none sm:text-sm"
            placeholder="Password"
            bind:value={password}
            on:keydown={handleKeydown}
            disabled={isLoading}
          />
        </div>
      </div>

      {#if error}
        <div class="rounded bg-red-100 p-3 text-center text-sm text-red-600">
          {error}
        </div>
      {/if}

      <div>
        <button
          type="submit"
          disabled={isLoading}
          class="group btn-big btn-primary relative flex w-full justify-center"
        >
          {#if isLoading}
            <svg
              class="mr-3 -ml-1 h-5 w-5 animate-spin text-white"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            Logging in...
          {:else}
            Login
          {/if}
        </button>
      </div>
    </form>
  </div>
</div>
