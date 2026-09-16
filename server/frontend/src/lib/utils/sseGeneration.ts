/**
 * Consume a fetch Response that may be text/event-stream (SSE) or plain JSON.
 *
 * For SSE responses:
 *   - Calls onStatus(message) for each 'status' event
 *   - Resolves with the result data payload on a 'result' event
 *   - Rejects with an Error on an 'error' event
 *
 * For non-SSE responses:
 *   - Resolves immediately with the parsed JSON body
 */
export async function consumeGenerationResponse(
  response: Response,
  onStatus: (message: string) => void
): Promise<any> {
  const contentType = response.headers.get('content-type') ?? '';

  if (contentType.includes('text/event-stream')) {
    return new Promise((resolve, reject) => {
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      async function pump() {
        while (true) {
          const { done, value } = await reader.read();
          if (done) return;
          buffer += decoder.decode(value, { stream: true });

          // Split on double-newline to extract complete SSE event blocks
          const eventBlocks = buffer.split('\n\n');
          buffer = eventBlocks.pop() ?? '';

          for (const block of eventBlocks) {
            const lines = block.trim().split('\n');
            let eventType = 'message';
            let dataStr = '';
            for (const line of lines) {
              if (line.startsWith('event: ')) eventType = line.slice(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.slice(6);
            }
            if (!dataStr) continue;
            const data = JSON.parse(dataStr);

            if (eventType === 'status') {
              onStatus(data.message);
            } else if (eventType === 'result') {
              resolve(data);
            } else if (eventType === 'error') {
              reject(new Error(data.detail || 'Generation failed'));
            }
          }
        }
      }

      pump().catch(reject);
    });
  } else {
    return response.json();
  }
}
