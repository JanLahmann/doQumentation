/**
 * What a kernel status change means for the connection to the code server.
 *
 * thebelab 0.4.0 bundles an early @jupyterlab/services whose kernel folds the
 * WebSocket state into its status: a dropped socket emits 'reconnecting', a
 * reopened one 'connected', and 'dead' once the 7 reconnect attempts (about two
 * minutes) are used up. A kernel the server restarts on its own (a crash, or
 * out of memory) arrives as an iopub status 'restarting'; newer services call
 * it 'autorestarting'. Restart Kernel goes through the same statuses, so the
 * caller says whether the user asked for it.
 */
export type KernelStatusEffect =
  | 'reconnecting' // socket dropped, the kernel is retrying; may still recover
  | 'recovered'    // socket open again
  | 'dead'         // kernel or server gone for good
  | 'restarted'    // kernel restarted without the user asking: all state lost
  | 'busy'
  | 'idle'
  | 'other';

export function kernelStatusEffect(status: string, userRestartInProgress: boolean): KernelStatusEffect {
  switch (status) {
    case 'reconnecting':
      return userRestartInProgress ? 'other' : 'reconnecting';
    case 'connected':
      return 'recovered';
    case 'dead':
    case 'failed':
      return 'dead';
    case 'restarting':
    case 'autorestarting':
      return userRestartInProgress ? 'other' : 'restarted';
    case 'busy':
      return 'busy';
    case 'idle':
      return 'idle';
    default:
      return 'other';
  }
}

/** What happened to the connection, as the toolbar reports it. */
export type ConnectionIssue = 'lost' | 'restarted' | null;

/** Which message the toolbar shows when the code server can't be used. */
export function connectionErrorMessage(
  issue: ConnectionIssue,
  online: boolean,
  remoteServer: boolean,
): 'offline' | 'lost' | 'failed' {
  // A remote server (Binder, Code Engine) needs the internet; a local one doesn't.
  if (remoteServer && !online) return 'offline';
  return issue === 'lost' ? 'lost' : 'failed';
}
