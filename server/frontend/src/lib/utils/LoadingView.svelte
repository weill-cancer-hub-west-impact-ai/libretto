<script lang="ts">
  export let text: string = 'Loading...';
</script>

<div class="flex h-full w-full flex-col items-center justify-center">
  <div class="flex flex-col items-center gap-4 text-gray-500">
    <div class="h-6 w-6 animate-spin rounded-full border-4 border-gray-300 border-t-blue-500"></div>
    <div class="text-sm">{text}</div>
  </div>
</div>
