/**
 * Kernel Ready Helper
 *
 * Ensures the thebelab kernel is bootstrapped and idle before the adapter
 * sends a simulation. If no kernel is connected, triggers bootstrap and
 * waits for the 'ready' status broadcast by ExecutableCode.
 */

import { ensureKernel, getActiveKernel } from '../ExecutableCode';

const STATUS_EVENT = 'executablecode:status';
const DEFAULT_TIMEOUT_MS = 120000; // 2 minutes — enough for Binder cold start

/**
 * Wait for the kernel to reach 'ready' status, starting bootstrap if needed.
 * Resolves once the kernel is available; rejects on timeout or error.
 */
export function waitForKernelReady(timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  // Already ready — no waiting needed
  if (getActiveKernel()) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      window.removeEventListener(STATUS_EVENT, onStatus as EventListener);
      reject(new Error('Kernel bootstrap timed out'));
    }, timeoutMs);

    const onStatus = (e: CustomEvent<string>) => {
      if (e.detail === 'ready' && getActiveKernel()) {
        clearTimeout(timer);
        window.removeEventListener(STATUS_EVENT, onStatus as EventListener);
        resolve();
      } else if (e.detail === 'error') {
        clearTimeout(timer);
        window.removeEventListener(STATUS_EVENT, onStatus as EventListener);
        reject(new Error('Kernel bootstrap failed'));
      }
    };

    window.addEventListener(STATUS_EVENT, onStatus as EventListener);
    ensureKernel();
  });
}
