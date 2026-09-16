import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// Auth store interface
function createAuthStore() {
  const { subscribe, set, update } = writable<{
    isAuthenticated: boolean;
    user: any;
    token: string | null;
  }>({
    isAuthenticated: false,
    user: null,
    token: null
  });

  return {
    subscribe,

    // Initialize auth state from localStorage
    init() {
      if (browser) {
        const token = localStorage.getItem('auth_token');
        const user = localStorage.getItem('auth_user');

        if (token && user) {
          try {
            set({
              isAuthenticated: true,
              token,
              user: JSON.parse(user)
            });
          } catch (e) {
            // Clear invalid data
            localStorage.removeItem('auth_token');
            localStorage.removeItem('auth_user');
          }
        }
      }
    },

    // Login with token and user info
    login(token: string, username: string, is_admin: boolean) {
      const userData = { username, is_admin };

      if (browser) {
        localStorage.setItem('auth_token', token);
        localStorage.setItem('auth_user', JSON.stringify(userData));
      }

      set({
        isAuthenticated: true,
        token,
        user: userData
      });
    },

    // Logout and clear storage
    logout() {
      if (browser) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
      }

      set({
        isAuthenticated: false,
        token: null,
        user: null
      });
    },

    // Get authorization header for API calls
    getAuthHeader() {
      let token = null;
      const unsubscribe = subscribe((state) => {
        token = state.token;
      });
      unsubscribe();

      return token ? { Authorization: `Bearer ${token}` } : {};
    }
  };
}

export const authStore = createAuthStore();

// Enhanced fetch function that automatically includes auth headers
export async function authenticatedFetch(url: string, options: any = {}, useJSON: boolean = true) {
  const authHeaders = authStore.getAuthHeader();

  const mergedOptions = {
    ...options,
    headers: {
      ...(useJSON ? { 'Content-Type': 'application/json' } : {}),
      ...authHeaders,
      ...options.headers
    }
  };

  const response = await fetch(url, mergedOptions);

  // If we get 401, user's token is invalid - log them out
  if (response.status === 401) {
    console.log('401 error, redirecting to login');
    authStore.logout();
    // Redirect to login if not already there
    if (browser && !window.location.pathname.includes('/login')) {
      window.location.href = '/login';
    }
  }

  return response;
}
