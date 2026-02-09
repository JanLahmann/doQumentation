# Plan: IBM Quantum Credential Store & Simulator Mode

## Context

Users face two friction points when running notebooks on doQumentation:

1. **Token/CRN re-entry**: 121 notebook pages use `QiskitRuntimeService()` which requires pre-saved credentials. On Binder, sessions are ephemeral — users must re-enter their 44-char API key and CRN every session. 17 notebooks teach `save_account()` but users have to do it manually each time.

2. **No-token users stuck**: 115 files call `service.least_busy()` or `service.backend("ibm_torino")` — users without IBM Quantum accounts can't run these cells at all without manually changing every cell to use `AerSimulator` or `FakeBackend`.

**Reference**: [q-docs.org](https://q-docs.org) documents FakeBackend/AerSimulator as alternatives and notes "Binder sessions are ephemeral, so you need to re-enter your credentials each time." We go further by automating both flows.

## Solution Overview

Two features, one injection mechanism:

1. **Credential store**: Enter token + CRN once in settings UI → stored in localStorage (7-day auto-expiry) → auto-injected via `save_account()` when kernel connects
2. **Simulator mode toggle**: Flip a switch, choose backend (AerSimulator or FakeBackend with device picker) → kernel gets a monkey-patch that redirects all `QiskitRuntimeService` calls to chosen simulator → zero cell modifications needed

Both use **silent kernel code injection** after thebelab bootstrap resolves.

## Files to Modify

| File | Changes |
|------|---------|
| `src/config/jupyter.ts` | Add IBM credential + simulator mode storage functions (~50 lines) |
| `src/components/ExecutableCode/index.tsx` | Add kernel injection mechanism + toolbar indicator + backend discovery (~80 lines) |
| `src/pages/jupyter-settings.tsx` | Add IBM Quantum Account section + Simulator Mode toggle + device picker (~100 lines) |
| `src/css/custom.css` | Styles for simulator badge, settings link, toggle switch (~40 lines) |

## Change 1: Storage Layer — `src/config/jupyter.ts`

Add after existing `clearJupyterConfig()` (line 135):

```typescript
// IBM Quantum credential storage
const STORAGE_KEY_IBM_TOKEN = 'doqumentation_ibm_token';
const STORAGE_KEY_IBM_CRN = 'doqumentation_ibm_crn';
const STORAGE_KEY_IBM_SAVED_AT = 'doqumentation_ibm_saved_at';
const STORAGE_KEY_SIM_MODE = 'doqumentation_simulator_mode';
const STORAGE_KEY_SIM_BACKEND = 'doqumentation_simulator_backend';
const STORAGE_KEY_FAKE_DEVICE = 'doqumentation_fake_device';
const STORAGE_KEY_FAKE_BACKENDS_CACHE = 'doqumentation_fake_backends';

const CREDENTIAL_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

/** Check if credentials have expired (>7 days old). Auto-clears if expired. */
function checkCredentialExpiry(): boolean {
  const savedAt = localStorage.getItem(STORAGE_KEY_IBM_SAVED_AT);
  if (!savedAt) return false;
  if (Date.now() - Number(savedAt) > CREDENTIAL_TTL_MS) {
    clearIBMQuantumCredentials();
    return true; // expired and cleared
  }
  return false; // still valid
}

export function getIBMQuantumToken(): string {
  if (typeof window === 'undefined') return '';
  checkCredentialExpiry();
  return localStorage.getItem(STORAGE_KEY_IBM_TOKEN) || '';
}

export function getIBMQuantumCRN(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(STORAGE_KEY_IBM_CRN) || '';
}

/** Returns days remaining until expiry, or -1 if no credentials saved. */
export function getCredentialDaysRemaining(): number {
  if (typeof window === 'undefined') return -1;
  const savedAt = localStorage.getItem(STORAGE_KEY_IBM_SAVED_AT);
  if (!savedAt) return -1;
  const remaining = CREDENTIAL_TTL_MS - (Date.now() - Number(savedAt));
  return Math.max(0, Math.ceil(remaining / (24 * 60 * 60 * 1000)));
}

export function saveIBMQuantumCredentials(token: string, crn: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY_IBM_TOKEN, token);
  localStorage.setItem(STORAGE_KEY_IBM_CRN, crn);
  localStorage.setItem(STORAGE_KEY_IBM_SAVED_AT, String(Date.now()));
}

export function clearIBMQuantumCredentials(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STORAGE_KEY_IBM_TOKEN);
  localStorage.removeItem(STORAGE_KEY_IBM_CRN);
  localStorage.removeItem(STORAGE_KEY_IBM_SAVED_AT);
}

export type SimulatorBackend = 'aer' | 'fake';

export function getSimulatorMode(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(STORAGE_KEY_SIM_MODE) === 'true';
}

export function setSimulatorMode(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  if (enabled) {
    localStorage.setItem(STORAGE_KEY_SIM_MODE, 'true');
  } else {
    localStorage.removeItem(STORAGE_KEY_SIM_MODE);
  }
}

export function getSimulatorBackend(): SimulatorBackend {
  if (typeof window === 'undefined') return 'aer';
  return (localStorage.getItem(STORAGE_KEY_SIM_BACKEND) as SimulatorBackend) || 'aer';
}

export function setSimulatorBackend(backend: SimulatorBackend): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY_SIM_BACKEND, backend);
}

export function getFakeDevice(): string {
  if (typeof window === 'undefined') return 'FakeSherbrooke';
  return localStorage.getItem(STORAGE_KEY_FAKE_DEVICE) || 'FakeSherbrooke';
}

export function setFakeDevice(name: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY_FAKE_DEVICE, name);
}

export function getCachedFakeBackends(): Array<{name: string; qubits: number}> | null {
  if (typeof window === 'undefined') return null;
  const cached = localStorage.getItem(STORAGE_KEY_FAKE_BACKENDS_CACHE);
  return cached ? JSON.parse(cached) : null;
}

export function setCachedFakeBackends(backends: Array<{name: string; qubits: number}>): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY_FAKE_BACKENDS_CACHE, JSON.stringify(backends));
}

// Active mode: user's explicit choice when both credentials + simulator are configured
export type ActiveMode = 'credentials' | 'simulator';
const STORAGE_KEY_ACTIVE_MODE = 'doqumentation_active_mode';

export function getActiveMode(): ActiveMode | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(STORAGE_KEY_ACTIVE_MODE) as ActiveMode | null;
}

export function setActiveMode(mode: ActiveMode | null): void {
  if (typeof window === 'undefined') return;
  if (mode) {
    localStorage.setItem(STORAGE_KEY_ACTIVE_MODE, mode);
  } else {
    localStorage.removeItem(STORAGE_KEY_ACTIVE_MODE);
  }
}
```

## Change 2: Kernel Injection — `src/components/ExecutableCode/index.tsx`

### 2a. Kernel code execution function

thebelab 0.4.0's `bootstrap()` resolves to a JupyterLab kernel/session object. Use runtime detection to find `requestExecute()`:

```typescript
async function executeOnKernel(kernelObj: unknown, code: string): Promise<boolean> {
  const k = kernelObj as Record<string, any>;
  // Try direct (IKernelConnection) or via session wrapper
  const kernel = k?.requestExecute ? k : k?.kernel;
  if (!kernel?.requestExecute) {
    console.warn('[ExecutableCode] kernel.requestExecute not available');
    return false;
  }
  try {
    const future = kernel.requestExecute({ code, silent: true, store_history: false });
    if (future?.done) await future.done;
    return true;
  } catch (err) {
    console.error('[ExecutableCode] kernel exec error:', err);
    return false;
  }
}
```

`silent: true` + `store_history: false` = no visible output, no `In[N]` numbering impact.

### 2b. Setup injection (called from `bootstrapOnce` kernel-ready handler)

```typescript
async function injectKernelSetup(kernelObj: unknown): Promise<void> {
  const simMode = getSimulatorMode();
  const token = getIBMQuantumToken();
  const activeMode = getActiveMode();

  // Determine which mode to use
  const hasBoth = simMode && token;
  const useSimulator = simMode && (!hasBoth || activeMode === 'simulator');
  const useCredentials = token && (!simMode || activeMode === 'credentials');

  if (hasBoth && !activeMode) {
    // No explicit choice — show reminder banner (auto-dismiss 5s)
    // Default to simulator mode when no choice is made
    broadcastConflictBanner('simulator');
  }

  if (useSimulator || (hasBoth && !activeMode)) {
    const code = getSimulatorPatchCode();
    const ok = await executeOnKernel(kernelObj, code);
    if (ok) console.log('[ExecutableCode] Simulator mode injected');
  } else if (useCredentials) {
    const crn = getIBMQuantumCRN();
    const ok = await executeOnKernel(kernelObj, getSaveAccountCode(token, crn));
    if (ok) console.log('[ExecutableCode] IBM Quantum credentials injected');
  }

  // Always run backend discovery (caches available fake backends)
  discoverFakeBackends(kernelObj);
}
```

Inserted in `bootstrapOnce()` between kernel resolve and `broadcastStatus('ready')`:

```typescript
kernelPromise.then(
  (kernel) => {
    injectKernelSetup(kernel).then(() => {
      broadcastStatus('ready');
      setupCellFeedback();
    });
  },
  ...
);
```

### 2c. Python code constants

**Credential injection (`getSaveAccountCode`):**
```python
from qiskit_ibm_runtime import QiskitRuntimeService
try:
    QiskitRuntimeService.save_account(
        token="ESCAPED_TOKEN",
        instance="ESCAPED_CRN",
        overwrite=True, set_as_default=True
    )
except Exception as e:
    print(f"[doQumentation] Credential setup: {e}")
```

**Simulator monkey-patch (`getSimulatorPatchCode`):**

For AerSimulator (`backend === 'aer'`):
```python
try:
    from qiskit_aer import AerSimulator as _DQ_Sim
except ImportError:
    from qiskit.providers.basic_provider import BasicSimulator as _DQ_Sim
_dq_backend = _DQ_Sim()
```

For FakeBackend (`backend === 'fake'`, with dynamic device name from settings):
```python
from qiskit_ibm_runtime.fake_provider import {DEVICE_NAME} as _DQ_Cls
_dq_backend = _DQ_Cls()
```
Where `{DEVICE_NAME}` is the user's selection (e.g. `FakeSherbrooke`), inserted via string interpolation.

Shared mock class (appended for both variants):
```python
class _DQ_MockService:
    def __init__(self, *a, **kw): pass
    @staticmethod
    def save_account(*a, **kw): pass
    def least_busy(self, *a, **kw): return _dq_backend
    def backend(self, *a, **kw): return _dq_backend
    def backends(self, *a, **kw): return [_dq_backend]

import qiskit_ibm_runtime as _qir
_qir.QiskitRuntimeService = _DQ_MockService
import sys
_m = sys.modules.get('qiskit_ibm_runtime')
if _m: _m.QiskitRuntimeService = _DQ_MockService
print(f"[doQumentation] Simulator mode — using {type(_dq_backend).__name__}")
```

This patches at the module level, so subsequent `from qiskit_ibm_runtime import QiskitRuntimeService` in any cell gets the mock.

### 2d. Dynamic fake backend discovery

On kernel connect (after setup injection), run a discovery script and capture the result via IOPub:

```python
import json as _j
from qiskit_ibm_runtime import fake_provider as _fp
_bs = []
for _n in sorted(dir(_fp)):
    _c = getattr(_fp, _n)
    if isinstance(_c, type) and hasattr(_c, 'num_qubits'):
        try: _bs.append({"name": _n, "qubits": _c().num_qubits})
        except: pass
print("__DQ_BACKENDS__" + _j.dumps(_bs))
```

**Capture mechanism**: `kernel.requestExecute({ code, silent: false })` with an `onIOPub` handler that listens for stdout containing the `__DQ_BACKENDS__` sentinel. Parse the JSON, cache in `localStorage` as `doqumentation_fake_backends`.

**Settings page dropdown**: reads cached list from localStorage. Falls back to a static list of ~8 common backends if no cache exists yet:
```typescript
const FALLBACK_BACKENDS = [
  { name: 'FakeManilaV2', qubits: 5 },
  { name: 'FakeSherbrooke', qubits: 127 },
  { name: 'FakeBrisbane', qubits: 127 },
  { name: 'FakeTorontoV2', qubits: 27 },
  { name: 'FakeMelbourneV2', qubits: 14 },
  { name: 'FakeBelemV2', qubits: 5 },
  { name: 'FakeKyoto', qubits: 127 },
  { name: 'FakeWashingtonV2', qubits: 127 },
];
```

Device dropdown uses native `<select>` with `<optgroup>` headers by qubit count (5q / 14q / 27q / 127q). Native scroll handles 20-30+ devices well.

### 2e. Toolbar additions

- **Simulator badge**: Shows "Simulator" label when simulator mode is active
- **Settings gear link**: `⚙` linking to `/jupyter-settings#ibm-quantum` for quick access

## Change 3: Settings UI — `src/pages/jupyter-settings.tsx`

Add two new sections after the existing "Custom Jupyter Server" section (before "Binder Packages"):

### Section A: "IBM Quantum Account" (`id="ibm-quantum"`)

- Token field (`type="password"`, placeholder "44-character API key")
- CRN/Instance field (`type="text"`, placeholder "crn:v1:bluemix:public:...")
- Save / Delete buttons (same style as existing)
- When credentials are saved: show "Credentials expire in N days" info + "Delete now" button
- Link to IBM Quantum Platform dashboard for key generation
- Note: "Credentials are stored in your browser for 7 days, then automatically deleted. They are auto-injected when the kernel starts."
- On page load, `checkCredentialExpiry()` auto-clears expired credentials. If expired, show notification: "Your IBM Quantum credentials have expired and were deleted. Please re-enter them."

### Section B: "Simulator Mode" (`id="simulator-mode"`)

- Toggle switch (checkbox styled as slider)
- Explanation: "Enable to run notebooks without an IBM Quantum account. All QiskitRuntimeService calls are redirected to a local simulator. No cell modifications needed."
- **Backend selector** (shown when toggle is ON):
  - **AerSimulator** (default) — "Ideal simulation, no noise. Fast, works for all circuits."
  - **FakeBackend** — "Simulates real IBM device noise. More realistic but slower."
    - When FakeBackend selected: show **device dropdown** — native `<select>` with `<optgroup>` headers by qubit count (5q / 27q / 127q)
    - Populated from localStorage cache (discovered dynamically at last kernel connect)
    - Falls back to static list of ~8 common backends if no cache yet
    - Default device: FakeSherbrooke (127q, most commonly used in tutorials)
- **Active Mode selector** (shown when both credentials AND simulator are configured): Radio buttons: "Use IBM credentials" / "Use simulator". Stored as `doqumentation_active_mode` (`'credentials' | 'simulator'`). User must explicitly choose — no silent precedence.

## Change 4: CSS — `src/css/custom.css`

- `.executable-code__sim-badge` — small blue badge in toolbar
- `.executable-code__settings-link` — gear icon, right-aligned
- `.jupyter-settings__toggle-*` — toggle switch styling (track + thumb)

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Wrong token entered | `save_account()` succeeds (just writes JSON). Error surfaces when cells try to authenticate. Same as IBM's own flow. |
| Credentials expired | On next page load, `getIBMQuantumToken()` calls `checkCredentialExpiry()` which auto-clears. Settings page shows "expired" notification. Kernel injection skips (no token). |
| Toggle simulator mid-session | Show note: "Changes take effect on next kernel session. Click Stop then Run." Stop resets `thebelabBootstrapped`, so next Run re-injects. |
| Both credentials + simulator set | Settings page shows radio buttons to pick active mode. At kernel connect, if no explicit choice was made, a brief banner reminds user: "Both IBM credentials and simulator mode are configured. Using [mode]. Change in Settings." Auto-dismisses after 5s. |
| `requestExecute` not available | Log warning. No injection. Cells behave as before (users must save_account manually). |
| Page navigation (SPA) | `thebelabBootstrapped` resets on full reload. Injection happens once per kernel lifetime. |
| AerSimulator not installed | Fallback import: `BasicSimulator` from `qiskit.providers.basic_provider`. Both are in Binder deps. |

## Key Design Decisions

- **7-day auto-expiry** for IBM credentials in localStorage (with timestamp). User informed on settings page ("expires in N days"). Explicit "Delete now" button available.
- **Simulator backend choice**: AerSimulator (ideal, default) or FakeBackend (noisy, with device picker). User chooses on settings page.
- **Dynamic fake backend discovery**: Python snippet introspects `qiskit_ibm_runtime.fake_provider` at kernel connect → caches in localStorage → settings dropdown uses cache. Falls back to static list of 8 common backends.
- **Kernel injection via `requestExecute`**: Runtime-detect the method on thebelab's kernel object. `silent: true` + `store_history: false` for invisible injection.
- **Settings page** (not toolbar modal): Credentials and simulator config live on the existing `/jupyter-settings` page. Toolbar shows a "Simulator" badge + gear icon link.

## Verification

1. **Build**: `npm run build` — no TypeScript errors, no build regressions
2. **Binder + no settings**: Click Run → verify no injection occurs (no console log). `QiskitRuntimeService()` fails as expected.
3. **Binder + simulator mode ON (AerSimulator)**: Enable in settings, click Run → console shows "Simulator mode injected". Run `service = QiskitRuntimeService(); backend = service.least_busy()` → returns AerSimulator. Toolbar shows "Simulator" badge.
4. **Binder + simulator mode ON (FakeBackend)**: Select FakeBackend + device, click Run → verify chosen device name in console log.
5. **Binder + IBM credentials**: Enter token/CRN, disable simulator, click Run → console shows credentials injected. `QiskitRuntimeService()` authenticates.
6. **Credential expiry**: Set credentials, manually adjust `STORAGE_KEY_IBM_SAVED_AT` to 8 days ago, reload settings page → verify "expired" notification shown, credentials cleared.
7. **Toggle mid-session**: Enable simulator, Run, verify. Toggle off. See restart message. Stop → Run → verify no patch.
8. **Backend discovery**: After first Run, check localStorage for `doqumentation_fake_backends` cache. Visit settings → verify dropdown populated.
9. **Settings page**: All fields persist across page reloads. Clear/Delete works. Gear icon in toolbar navigates correctly.
