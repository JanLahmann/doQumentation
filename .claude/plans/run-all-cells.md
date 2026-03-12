# Plan: "Run All Cells" Button

## Goal

Add a page-level "Run All Cells" button that executes all thebelab cells on the
page sequentially, in DOM order — mimicking Jupyter's "Run All" (Kernel → Run All
Cells).

## Where It Lives

The button goes in the global status/toolbar row (rendered by the first
`ExecutableCode` instance on the page — the one that shows "Restart Kernel" /
"Clear Session"). Visible only when `thebeStatus === 'ready'`.

## Implementation

### 1. New custom event

```typescript
const RUNALL_EVENT = 'executablecode:runall';
```

### 2. "Run All" button in the toolbar

In the JSX toolbar section (alongside Restart Kernel / Clear Session):

```tsx
{thebeStatus === 'ready' && isFirstCell && (
  <button
    className="executable-code__toolbar-btn"
    onClick={handleRunAll}
    disabled={runningAll}
    title={translate({ id: 'executable.runAll.tooltip',
                       message: 'Run all cells on this page in order' })}
  >
    {runningAll
      ? translate({ id: 'executable.runAll.progress',
                    message: 'Running {current}/{total}…',
                    values: { current: runAllProgress.current,
                              total: runAllProgress.total } })
      : translate({ id: 'executable.runAll.label', message: 'Run All' })}
  </button>
)}
```

State additions (module-level, shared):
```typescript
let runningAll = false;
```

Per-component state:
```typescript
const [runAllProgress, setRunAllProgress] = useState({ current: 0, total: 0 });
```

### 3. `handleRunAll` function

```typescript
const handleRunAll = async () => {
  if (runningAll) return;
  runningAll = true;

  // 1. Activate all cells (switch to run mode) if not already
  window.dispatchEvent(new CustomEvent(ACTIVATE_EVENT));

  // 2. Wait for thebelab to render all <pre data-executable> → thebelab cells
  await new Promise(r => setTimeout(r, 300));

  // 3. Collect all run buttons in DOM order
  const runBtns = Array.from(
    document.querySelectorAll<HTMLButtonElement>('.thebelab-run-button')
  );
  setRunAllProgress({ current: 0, total: runBtns.length });

  for (let i = 0; i < runBtns.length; i++) {
    setRunAllProgress({ current: i + 1, total: runBtns.length });
    runBtns[i].click();

    // Wait for kernel to go busy then idle (reuse existing idle-detection pattern)
    await waitForKernelIdle();
  }

  runningAll = false;
  setRunAllProgress({ current: 0, total: 0 });
};
```

### 4. `waitForKernelIdle()` helper

Reuses the `activeKernel` reference already captured in `bootstrapOnce`:

```typescript
function waitForKernelIdle(): Promise<void> {
  return new Promise(resolve => {
    if (!activeKernel) { resolve(); return; }
    const kernel = activeKernel as { statusChanged?: { connect: Function } };
    if (!kernel.statusChanged) { resolve(); return; }

    let sawBusy = false;
    const conn = kernel.statusChanged.connect((_: unknown, status: string) => {
      if (status === 'busy') sawBusy = true;
      if (sawBusy && status === 'idle') {
        conn.disconnect();
        setTimeout(resolve, 200); // small buffer after idle
      }
    });

    // Fallback: if kernel never goes busy (e.g. empty cell), resolve after 1s
    setTimeout(() => { conn.disconnect?.(); resolve(); }, 1000);
  });
}
```

### 5. i18n strings to add (all 19 locales in `i18n/*/code.json`)

| Key | EN default |
|-----|-----------|
| `executable.runAll.label` | `Run All` |
| `executable.runAll.tooltip` | `Run all cells on this page in order` |
| `executable.runAll.progress` | `Running {current}/{total}…` |

## Edge Cases

- **Already in run mode**: `ACTIVATE_EVENT` is idempotent — safe to dispatch again.
- **Cell erroring**: Continue to next cell regardless (mirrors Jupyter default behaviour). Error border already shows on the failed cell.
- **Kernel dead**: `activeKernel` is null → `waitForKernelIdle()` resolves immediately. The click on the run button will show the error state.
- **User clicks "Restart" during Run All**: `RESET_EVENT` is dispatched; `runningAll` should be reset. Add listener for `RESTART_EVENT` that sets `runningAll = false`.
- **`isFirstCell` detection**: The existing pattern (first `ExecutableCode` on page renders the global toolbar) already handles this via a module-level flag.

## Files to Change

| File | Change |
|------|--------|
| `src/components/ExecutableCode/index.tsx` | Add `RUNALL_EVENT`, `handleRunAll`, `waitForKernelIdle`, toolbar button, state |
| `i18n/*/code.json` (19 files) | Add 3 new keys per locale |

## Testing

1. Open a tutorial page with multiple code cells (e.g. Hello World)
2. Click "Run" on any cell to start the kernel
3. Once kernel is ready, "Run All" button appears
4. Click "Run All" — verify cells execute top to bottom, progress counter updates
5. Verify a failing cell shows red border but execution continues to next cell
6. Restart kernel, click "Run All" immediately — should trigger kernel connect + run all
