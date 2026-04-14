# Simplify Settings Page

## Context

The Settings page has two problems:
1. **Execution mode** is spread across three confusing sections: simulator toggle + backend choice + conflict resolution radios. Users set Active Mode to "credentials" and forget, then wonder why simulator isn't active.
2. **Compute backend** (where code runs) is buried under "Advanced Settings" in collapsed `<details>`. Code Engine credentials are hidden, making the CE experience feel second-class.

## New Settings layout

### Section 1: Execution Mode (replaces Simulator Mode + Active Mode)

Single radio group — "What runs when you click Run":

| Option | Description | Extra UI |
|--------|-------------|----------|
| **AerSimulator** | Ideal simulation, no noise | (none) |
| **FakeBackend** | Real IBM device noise simulation | Device dropdown |
| **IBM Quantum** | Real hardware via credentials | (none) |
| **No automatic injection** | User manages everything in code cells | (none) |

Default: `aer`.

### Section 2: IBM Quantum Credentials (always visible, unchanged fields)

Token, CRN, Plan dropdown, Expiry — always accessible regardless of execution mode. Users may save credentials for JupyterLab, for later, or for quick mode switching. When mode is "credentials" but no token saved, show a hint.

### Section 3: Compute Backend (promoted from Advanced)

Where code actually runs. Currently auto-detected but CE is hidden. Make it visible:

| Option | Description | Extra UI | Current auto-detect |
|--------|-------------|----------|-------------------|
| **Binder** (default on GitHub Pages) | Free, shared, slow cold start | Clear Binder Session button | `github-pages` env |
| **IBM Cloud Code Engine** | Fast, your own IBM Cloud account | CE URL + token + workshop fields | `code-engine` env |

CE credentials (URL, token, expiry) shown inline when CE is selected. Auto-detection still works — if CE is configured, it's pre-selected.

### Section 4: Other Settings — unchanged
Display prefs (font size, hide static outputs), clear progress, clear recent, reset sidebar.

### Advanced section (collapsed `<details>`)
- **Binder Packages** — pre-installed packages info
- **Custom Jupyter Server** — URL + token (not actively used)
- **Warning Suppression** — Python warnings toggle
- **Workshop Mode** — workshop pool config (organizers only)

## localStorage changes

- **NEW**: `doqumentation_execution_mode` — values: `'aer' | 'fake' | 'credentials' | 'none'`
- **REMOVE**: `doqumentation_simulator_mode` (boolean)
- **REMOVE**: `doqumentation_active_mode` ('credentials' | 'simulator')
- **KEEP**: `doqumentation_simulator_backend`, `doqumentation_fake_device` (still used by patch code generator)

Migration: lazy, on first `getExecutionMode()` call. Reads old keys → computes equivalent → writes new key → removes old keys.

## Files to modify

### 1. `src/config/jupyter.ts`
- Add `ExecutionMode` type, `STORAGE_KEY_EXECUTION_MODE`, `getExecutionMode()`, `setExecutionMode()`
- Add `migrateExecutionMode()` — one-time lazy migration from old keys
- Make `getSimulatorMode()` derive: `return mode === 'aer' || mode === 'fake'`
- Make `getSimulatorBackend()` derive: `return mode === 'fake' ? 'fake' : 'aer'`
- Remove `setSimulatorMode()`, `setSimulatorBackend()` (no callers after refactor)
- Remove `getActiveMode()`, `setActiveMode()`, `VALID_ACTIVE_MODES`, `ActiveMode` type
- Add `STORAGE_KEY_EXECUTION_MODE` to `ALL_JUPYTER_KEYS` array

### 2. `src/components/ExecutableCode/index.tsx`
- Replace `getSimulatorMode` / `getActiveMode` imports with `getExecutionMode`
- Simplify `injectKernelSetup()` to a clean switch on `getExecutionMode()`:
  - `'aer'`/`'fake'` → inject simulator patch (exempt pages fall back to credentials/none)
  - `'credentials'` → inject save_account + open plan patch
  - `'none'` → skip injection
- Remove conflict banner: `CONFLICT_EVENT`, `broadcastConflictBanner()`, `conflictBanner` state, useEffect listener, conflict banner JSX
- Update `annotateSaveAccountCells()`: guard on `mode === 'none'` instead of old logic
- Update `annotateSessionCells()`: check `mode === 'credentials'` instead of old logic
- Update badge link anchor `#simulator-mode` → `#execution-mode`

### 3. `src/pages/jupyter-settings.tsx`
- Replace imports: `getSimulatorMode`/`setSimulatorMode`/`getActiveMode`/`setActiveMode` → `getExecutionMode`/`setExecutionMode`
- Replace state: `simEnabled`, `simBackend`, `activeMode` → single `executionMode`
- Replace handlers: `handleSimToggle`, `handleSimBackendChange`, `handleActiveModeChange` → `handleExecutionModeChange`
- Remove `hasBothConfigured` derived value

**Execution Mode section** (replaces Simulator Mode + Active Mode, lines ~661-807):
  - AerSimulator radio
  - FakeBackend radio + device dropdown (when selected)
  - IBM Quantum radio
  - No injection radio
  - Update anchor from `#simulator-mode` to `#execution-mode`

**IBM Quantum Credentials section** — keep always visible below Execution Mode (moved up from its current position further down the page). Fields unchanged.

**Compute Backend section** (replaces Advanced Settings collapsed sections):
  - Promote CE and Custom Server out of `<details>` into visible radio group
  - Binder radio (default on GH Pages) — Clear Binder Session button when selected
  - Code Engine radio — show CE URL + token fields when selected
  - Auto-select based on `detectJupyterConfig()` result
  - Note: this is read-order reorganization + CE promotion, not a new localStorage key change. The CE/Custom detection logic in `jupyter.ts` is unchanged.

**Other Settings** — unchanged (display prefs, clear progress, reset sidebar, etc.)

**Advanced section** (collapsed `<details>`, moved to bottom):
  - Binder Packages (info only)
  - Custom Jupyter Server (URL + token)
  - Warning Suppression toggle
  - Workshop Mode (pool config — only for organizers)

### 4. `src/components/QamposerEmbed/executionMode.ts`
- Replace imports with `getExecutionMode` from jupyter.ts (the new config-level one)
- Simplify the function: switch on config `getExecutionMode()` → map to Qamposer's `ExecutionMode` union type

## Migration logic

```
if new key exists → done (idempotent)
if activeMode === 'credentials' → 'credentials'
if simMode === 'false' → token exists ? 'credentials' : 'none'  
if simMode === 'true' or unset → backend === 'fake' ? 'fake' : 'aer'
```

## Verification

1. `npx tsc --noEmit` — no type errors
2. `npm run build` — builds without warnings
3. Manual test on Settings page:
   - Select each mode → verify localStorage key
   - Refresh → mode persists
   - Click Run on a tutorial → verify correct badge (AerSimulator / FakeKyiv / IBM QUANTUM / none)
4. Migration test: set old keys in localStorage manually → reload → verify correct new key computed
5. hello-world (exempt page): verify simulator modes fall back to credentials/none
