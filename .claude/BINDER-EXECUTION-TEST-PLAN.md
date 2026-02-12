# doQumentation — Comprehensive Binder Test Plan

**Updated:** February 12, 2026
**Site:** https://doqumentation.org
**Purpose:** Systematic testing of all Binder-powered features on the live site

---

## Prerequisites

- Access to https://doqumentation.org with stable internet
- Modern browser (Chrome recommended) with DevTools
- ~3 hours for full coverage
- Optional: Valid IBM Quantum API credentials (Section 5)
- Fresh start: `localStorage.clear()` in DevTools Console before testing

## Result Format

For each test record: **PASS** / **FAIL** / **SKIP** + notes.
Use timing benchmarks: Excellent / Good / Acceptable / Poor.

---

## Section 1: Kernel Connection & Bootstrap (15 tests)

### 1.1 — Run Button Presence
Navigate to `/tutorials/hello-world`. Verify "Run" button visible in toolbar above first code block. Text: "Execute via Binder (may take a moment to start)". Button is clickable and styled.

### 1.2 — First Click: Binder Startup
Click "Run" on a fresh page. Button changes to "Connecting..." within 2s. Status message: "Starting Binder (this may take 1–2 minutes on first run)...". Connection completes within 90s.
**Benchmarks:** <45s Excellent · 45–75s Good · 75–90s Acceptable · >90s Poor

### 1.3 — Kernel Bootstrap Completion
After connection: "Connecting..." becomes "Back" button. Status legend appears: running (amber) | done (green) | error (red). Code cells become editable (CodeMirror). Execution mode badge appears (e.g. "AERSIMULATOR" if simulator enabled). No JS errors in console.

### 1.4 — Simulator Mode Auto-Activation
Enable Simulator Mode in Settings (AerSimulator) → navigate to tutorial → click Run.
**Expect:** Green toast "Simulator active — using AerSimulator" (auto-fades 4s). Badge "AERSIMULATOR" (blue) in toolbar.

### 1.5 — IBM Quantum Credentials Auto-Injection
Save IBM credentials in Settings → navigate to tutorial → click Run.
**Expect:** Badge "IBM QUANTUM" (teal) in toolbar. `save_account()` injected at kernel start. No credential exposure in UI.

### 1.6 — Binder Package Pre-Installation
After kernel ready, run: `import qiskit; print(qiskit.__version__)`.
**Expect:** Import succeeds, version prints. No `ModuleNotFoundError`.

### 1.7 — Warning Suppression
Run code that would trigger warnings (e.g. deprecated API).
**Expect:** No `FutureWarning` / `DeprecationWarning` in cell output.

### 1.8 — Multiple Pages: Kernel Isolation
Start kernel on Page A → navigate to Page B → verify kernel does NOT persist. Page B requires fresh "Run" click. No state leakage between pages.

### 1.9 — Console Logging
Open DevTools Console → click Run → monitor messages.
**Expect:** Connection status logged. No excessive logging. Errors have clear messages.

### 1.10 — Network Failure During Bootstrap
Click Run → disconnect internet during Binder startup.
**Expect:** Error message displayed. Retry option available. No infinite loading state.

### 1.11 — Slow Network: Connection Timeout
Simulate slow network (DevTools throttling: Slow 3G). Click Run → wait up to 3 min.
**Expect:** Connection either completes or times out gracefully with error message.

### 1.12 — Second Visit: Connection Speed
First connection → note time. Refresh page → click Run again → time second connection.
**Expect:** Second connection noticeably faster (cached Binder image). Target: <30s.

### 1.13 — Binder Hint After Connection
On GitHub Pages: after kernel ready, dismissible "Binder packages" hint appears in toolbar.
**Expect:** Hint shows pre-installed packages. Click × to dismiss. Hint stays dismissed across navigation (localStorage `dq-binder-hint-dismissed`).

### 1.14 — Mobile: Binder Connection
Access site on mobile (or DevTools mobile emulation at 375px).
**Expect:** Run button accessible. Connection succeeds. UI adapts to small screen. Toolbar doesn't overflow.

### 1.15 — Browser Compatibility
Test Run → Connection in Chrome, Firefox, Safari (if available).
**Expect:** Connection works in all modern browsers. No browser-specific errors.

---

## Section 2: Cell Execution & State Management (25 tests)

### 2.1 — Execute Single Cell: Success
Click "run" on first code cell. Border turns amber (running) → green (done). Output appears below. Execution completes <5s for simple code.

### 2.2 — Execute Multiple Cells Sequentially
Execute Cell 1 → wait → Cell 2 → wait → Cell 3. Variables from Cell 1 available in Cell 2. Each cell shows correct status colors.

### 2.3 — Variable Persistence
Cell 1: `x = 42`. Cell 2: `print(x)`. **Expect:** Prints `42`. No `NameError`.

### 2.4 — Function Definition Across Cells
Cell 1: `def greet(name): return f"Hello, {name}!"`. Cell 2: `print(greet("World"))`.
**Expect:** Prints `Hello, World!`.

### 2.5 — Import Persistence
Cell 1: `from qiskit import QuantumCircuit`. Cell 2: `qc = QuantumCircuit(2); print(qc.num_qubits)`.
**Expect:** Prints `2`. Import persists.

### 2.6 — Long-Running Cell (15s)
```python
import time
print("Starting...")
time.sleep(15)
print("Done!")
```
**Expect:** Amber border for full 15s. "Starting..." appears immediately. "Done!" after 15s. Green border on completion.

### 2.7 — Green Border Accuracy (Fast Cell)
Execute `print(1+1)`. **Expect:** Amber briefly → green only after completion. Output: `2`. No premature green.

### 2.8 — Output: Text
`print("Hello, World!")` → Output shows `Hello, World!`. Readable, properly formatted.

### 2.9 — Output: Numbers
`42 * 2` → Output: `84`. Correct formatting.

### 2.10 — Output: Matplotlib Plots
```python
import matplotlib.pyplot as plt
plt.plot([1, 2, 3], [1, 4, 9])
plt.show()
```
**Expect:** Plot image renders below cell. Clear, no broken images. Green border (not premature — matplotlib triggers multiple busy/idle transitions).

### 2.11 — Output: Qiskit Circuit Diagrams
```python
from qiskit import QuantumCircuit
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.draw('mpl')
```
**Expect:** Circuit diagram displays. Image clear, gates labeled correctly.

### 2.12 — Output: Quantum Simulation (Bell State)
```python
from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()

sampler = StatevectorSampler()
result = sampler.run([qc], shots=1000).result()
counts = result[0].data.meas.get_counts()
print(counts)
```
**Expect:** Results show roughly ~50/50 split between `00` and `11`. Scientifically accurate.

### 2.13 — Output: Histogram
```python
from qiskit.visualization import plot_histogram
plot_histogram(counts)
```
**Expect:** Histogram image renders. Shows `00` and `11` bars.

### 2.14 — Multiple Outputs Per Cell
```python
print("First")
print("Second")
print("Third")
```
**Expect:** All three lines in order.

### 2.15 — No-Output Cell
Execute `x = 42`. **Expect:** Green border. No output. Variable available in next cell.

### 2.16 — Cell Re-execution
Execute cell 3 times. **Expect:** Executes each time. No errors from re-execution.

### 2.17 — Out-of-Order Execution
Execute Cell 3 before Cell 1. **Expect:** Cell 3 may error if it depends on Cell 1 — that's correct behavior. No system-level errors.

### 2.18 — Code Editing During Execution
Start 15s sleep cell → edit code in another cell while first runs.
**Expect:** Editing allowed during execution. Can queue next cell.

### 2.19 — Large Output
```python
for i in range(500):
    print(f"Line {i}")
```
**Expect:** Output displays without crashing. Performance acceptable.

### 2.20 — Unicode Output
`print("Hello 世界")` → Output: `Hello 世界`. No encoding errors.

### 2.21 — Static + Live Output: Dual Display
Run code on a page with pre-computed outputs (e.g. circuit diagrams).
**Expect:** Both pre-computed (static MDX) and live outputs visible side-by-side. Static outputs from IBM's original runs remain visible.

### 2.22 — Hide Pre-computed Outputs Toggle
Settings → Display → enable "Hide pre-computed outputs during live execution".
Run code on page with static outputs.
**Expect:** Pre-computed outputs hidden. Only live outputs visible. Click Back → static outputs return.

### 2.23 — Code Font Size in Live Mode
Settings → Display → set code font size to 18px. Run kernel.
**Expect:** CodeMirror cells use 18px font (CSS variable `--dq-code-font-size`). Matches static code blocks.

### 2.24 — Cell Execution Order Indicator
Execute cells: amber border tracks which cell is currently running. Only one cell runs at a time (kernel is single-threaded).

### 2.25 — Concurrent Cell Clicks
Click run on 3 cells rapidly. **Expect:** Cells execute in order (queued). No errors from rapid clicking.

---

## Section 3: Error Handling & Recovery (18 tests)

### 3.1 — SyntaxError
```python
print("Missing quote)
```
**Expect:** Red border. `SyntaxError` message. Clear traceback.

### 3.2 — IndentationError
```python
def foo():
print("Bad indent")
```
**Expect:** Red border. `IndentationError` message.

### 3.3 — NameError
`print(undefined_variable)` → Red border. `NameError: name 'undefined_variable' is not defined`.

### 3.4 — TypeError
```python
x = "5"
y = x + 10
```
**Expect:** Red border. `TypeError`.

### 3.5 — ZeroDivisionError
`1 / 0` → Red border. `ZeroDivisionError`.

### 3.6 — IndexError
```python
lst = [1, 2, 3]
print(lst[10])
```
**Expect:** Red border. `IndexError`.

### 3.7 — ModuleNotFoundError + Error Hint
`import nonexistent_package_xyz` → Red border. `ModuleNotFoundError`. Contextual error hint appears suggesting install.

### 3.8 — Pip Install Button on ModuleNotFoundError
Run `import some_missing_pkg`. **Expect:** "Install some_missing_pkg" button appears below error. Click button → runs `%pip install -q some_missing_pkg`. If package exists on PyPI, installs and auto-re-runs cell. If not, shows pip error.

### 3.9 — ImportError (Bad Import)
`from qiskit import NonExistentClass` → Red border. `ImportError`.

### 3.10 — Cell Recovery After Error
Execute cell with error → fix code → run again. **Expect:** Error clears. Cell executes successfully. Green border.

### 3.11 — Subsequent Cell After Error
Cell 1 errors (red). Execute Cell 2 (valid code). **Expect:** Cell 2 executes normally. Error doesn't block subsequent cells.

### 3.12 — Kernel State After Multiple Errors
Execute several cells with errors → then valid code. **Expect:** Kernel still responsive. Valid code works. Kernel robust.

### 3.13 — Network Loss During Execution
Start cell execution → disconnect internet. **Expect:** Error message. Retry guidance. No infinite amber border.

### 3.14 — Kernel Death Detection
If kernel dies (e.g. memory exhaustion): **Expect:** Error notification "Kernel died" or similar. All cells marked red. Clear instructions.

### 3.15 — RecursionError
```python
def recurse(): return recurse()
recurse()
```
**Expect:** Red border. `RecursionError`. Kernel survives.

### 3.16 — MemoryError
```python
import numpy as np
arr = np.zeros((100000, 100000))
```
**Expect:** Either executes (enough RAM) or `MemoryError`. Kernel handles gracefully.

### 3.17 — Error Message Readability
Generate SyntaxError, NameError, ModuleNotFoundError. Review all error outputs.
**Expect:** Messages readable. Tracebacks included. Contextual hints where applicable.

### 3.18 — Error Logging to Console
Open DevTools → generate errors. **Expect:** Errors logged to console. No sensitive info exposed.

---

## Section 4: Simulator Mode (14 tests)

### 4.1 — Enable AerSimulator
Settings → Simulator Mode → toggle ON → AerSimulator selected.
Navigate to tutorial → click Run.
**Expect:** Green toast "Simulator active — using AerSimulator" (fades 4s). Badge "AERSIMULATOR" (blue).

### 4.2 — FakeBackend Selection
Settings → Simulator → FakeBackend → device picker appears.
**Expect:** Devices grouped by qubit count. Select a device (e.g. FakeSherbrooke). Save persists.

### 4.3 — FakeBackend Execution
Select FakeBackend (e.g. FakeSherbrooke) → run quantum circuit.
**Expect:** Badge shows device name. Results show noise (not perfect). More realistic than AerSimulator.

### 4.4 — Simulator Code Injection
Enable AerSimulator → Run → execute code using `QiskitRuntimeService`.
**Expect:** `QiskitRuntimeService` monkey-patched. No IBM account needed. `service.backend()` returns AerSimulator.

### 4.5 — Simulator save_account() Feedback
With simulator ON, execute:
```python
from qiskit_ibm_runtime import QiskitRuntimeService
QiskitRuntimeService.save_account(token="test", instance="test")
```
**Expect:** Cell output prints: `[doQumentation] Simulator mode active — save_account() skipped (no credentials needed)`. Green border. User knows credentials weren't actually saved.

### 4.6 — Badge Visibility Throughout Session
Enable simulator → Run → execute multiple cells.
**Expect:** Badge stays visible in toolbar during entire session. Disappears only after clicking Back.

### 4.7 — Toast Auto-Dismiss + Manual Dismiss
Enable simulator → Run. Toast appears.
**Expect:** Auto-fades after 4s. OR click × to dismiss immediately.

### 4.8 — Disable Simulator Mid-Session
Enable simulator → run code → Settings → disable simulator → return → Run again.
**Expect:** New kernel session without simulator. No badge. `QiskitRuntimeService` is the real one (may error without credentials).

### 4.9 — Simulator Without IBM Account
Clear all IBM credentials. Enable simulator. Run quantum code.
**Expect:** Code executes successfully. No authentication errors.

### 4.10 — AerSimulator Performance
Run standard 2-qubit Bell state circuit with 1000 shots.
**Expect:** Execution completes <3s. Results accurate.

### 4.11 — Fake Backend Discovery Cache
Enable FakeBackend → kernel connects → device picker populates.
**Expect:** First run: introspects `fake_provider` (may take a few seconds). Subsequent runs: loads from localStorage cache instantly. Check DevTools → Application → localStorage → `doqumentation_fake_backends`.

### 4.12 — Conflict Resolution: Both Simulator + Credentials
Enable simulator AND save IBM credentials.
**Expect:** Settings page shows "Active Mode" radio buttons (Simulator / IBM Quantum). User must choose one.

### 4.13 — No Mode Selected Warning
Both configured, no active mode selected → Run code.
**Expect:** Warning banner. Defaults to simulator mode.

### 4.14 — Simulator Hint Dismissal Persistence
See Binder packages hint → dismiss → navigate away → return.
**Expect:** Hint stays dismissed (localStorage `dq-binder-hint-dismissed`).

---

## Section 5: IBM Quantum Credentials & Settings UX (16 tests)

### 5.1 — Security Disclaimer Visible
Navigate to Settings → IBM Quantum Account section.
**Expect:** Yellow warning box: "Security note: Credentials are stored in your browser's localStorage in plain text..." visible before the credential form.

### 5.2 — Save Credentials
Enter API token + CRN → click "Save Credentials".
**Expect:** Success message: "Credentials saved! They will be auto-injected when the kernel starts." Expiry notice appears.

### 5.3 — Expiry Notice
After saving credentials.
**Expect:** Blue info bar: "Credentials expire in **7 days**." (default TTL).

### 5.4 — Adjustable TTL Dropdown
In the expiry info bar, find "Auto-delete after:" dropdown.
**Expect:** Options: 1 day / 3 days / 7 days. Default: 7 days.

### 5.5 — Change TTL to 1 Day
Select "1 day" from dropdown.
**Expect:** Expiry notice updates to "Credentials expire in **1 day**." Persists after page refresh (check localStorage `doqumentation_ibm_ttl_days` = "1").

### 5.6 — Change TTL to 3 Days
Select "3 days". **Expect:** Notice updates. Value persists.

### 5.7 — TTL Persists After Delete/Re-save
Set TTL to 1 day → delete credentials → re-save credentials.
**Expect:** TTL still at 1 day (dropdown remembers). Expiry notice shows 1 day.

### 5.8 — Copyable save_account() Snippet
Below credential buttons, find collapsed `<details>`: "Alternative: Run save_account() manually in a notebook cell".
**Expect:** Click to expand. Shows Python snippet with `QiskitRuntimeService.save_account(...)`. Code is copyable.

### 5.9 — Delete Credentials
Click "Delete Credentials". **Expect:** Fields cleared. Expiry notice disappears. localStorage keys removed.

### 5.10 — Credential Auto-Injection on Run
Save credentials → navigate to tutorial → Run.
**Expect:** `save_account()` injected. Badge "IBM QUANTUM" (teal). Toast: "IBM Quantum credentials applied".

### 5.11 — IBM Quantum Badge
With credentials active: badge "IBM QUANTUM" in teal.
**Expect:** Badge visible during execution session. Distinct from simulator blue badge.

### 5.12 — Expired Credentials
Set TTL to 1 day → save credentials → manually set `doqumentation_ibm_saved_at` to 2 days ago in localStorage.
Refresh Settings page.
**Expect:** Yellow warning: "Your IBM Quantum credentials have expired and were deleted." Fields empty.

### 5.13 — Invalid Credentials Handling
Enter invalid API token → save → Run code that uses IBM services.
**Expect:** Credentials save (no client-side validation). Error on execution (authentication failure). Clear error message.

### 5.14 — Credentials Not Exposed
Save credentials → inspect DOM, network requests, console.
**Expect:** Token not visible in plain text in DOM. Not logged to console. Token field is `type="password"`.

### 5.15 — Active Mode Radio Buttons
Enable simulator + save credentials → Settings page.
**Expect:** "Active Mode" section with radio: "Use Simulator" / "Use IBM Quantum credentials". Selecting one changes `doqumentation_active_mode` in localStorage.

### 5.16 — Pre-computed Outputs Label & Description
Settings → Display section.
**Expect:** Heading "Pre-computed Outputs" (not "Static Outputs"). Description explains: outputs from IBM's original runs, shown alongside live results, toggle hides originals during live execution.

---

## Section 6: Package Management (10 tests)

### 6.1 — Pre-Installed: Qiskit
`import qiskit; print(qiskit.__version__)` → Version prints. No install needed.

### 6.2 — Pre-Installed: qiskit-aer
`from qiskit_aer import AerSimulator; print("OK")` → Prints `OK`.

### 6.3 — Pre-Installed: qiskit-ibm-runtime
`from qiskit_ibm_runtime import QiskitRuntimeService; print("OK")` → Prints `OK`.

### 6.4 — Pre-Installed: matplotlib
`import matplotlib; print(matplotlib.__version__)` → Version prints.

### 6.5 — Pre-Installed: numpy, scipy
`import numpy, scipy; print(numpy.__version__, scipy.__version__)` → Versions print.

### 6.6 — Pip Install in Cell
```python
!pip install -q requests
import requests
print(requests.__version__)
```
**Expect:** Installation succeeds. Import works. Version prints.

### 6.7 — Pre-Injected %pip Install Cells
Navigate to a notebook that requires extra packages (e.g. one of the 46 notebooks with injected deps).
**Expect:** First code cell is `%pip install -q <packages>`. Executes on first run. Subsequent cells can import those packages.

### 6.8 — Settings: Binder Packages List
Settings → Binder Packages section (bottom of page).
**Expect:** List of pre-installed packages: qiskit[visualization], qiskit-aer, qiskit-ibm-runtime, pylatexenc, qiskit-ibm-catalog, qiskit-addon-utils, pyscf.

### 6.9 — Package Installation Speed
Time: `!pip install -q pandas`. **Expect:** Completes <30s.

### 6.10 — Already-Installed Package
`!pip install -q qiskit` → "Requirement already satisfied" message. Fast (<2s).

---

## Section 7: UI/UX & Visual Feedback (18 tests)

### 7.1 — Run Button Styling
Verify Run button clearly visible, appropriately sized, calls attention without being intrusive.

### 7.2 — Status Legend
After kernel connects: colored dots legend visible. Colors match actual cell borders.
Legend: running (amber) | done (green) | error (red).

### 7.3 — Cell Border Colors
Run cell → amber border. Complete → green. Error → red.
Colors distinct and accessible.

### 7.4 — CodeMirror Editor Features
After kernel connects: cells become editable. Syntax highlighting works. Can modify code and re-run.

### 7.5 — Code Copy Button
Hover over static code block → copy button appears (top right). Click → copies to clipboard.

### 7.6 — Back Button Prominent
After kernel connects: "Back" button visible in toolbar. Clear it's an exit/revert action.

### 7.7 — Back Button Confirmation
Click Back → confirmation dialog: "Going back will discard..." with Cancel/OK.
Cancel → stays in execution view. OK → reverts to static view.

### 7.8 — Back: State Fully Resets
Click Back → confirm. Run button reappears. Static outputs return. Live outputs cleared.
Click Run again → fresh kernel (no stale variables).

### 7.9 — Execution Mode Badge Position
Badge (AERSIMULATOR / IBM QUANTUM) positioned in toolbar. Visible but not obstructive.

### 7.10 — Toolbar Button Overflow
On narrow screens: toolbar buttons don't overflow outside container.
**CSS fix:** `flex-wrap: wrap` or overflow handling.

### 7.11 — Responsive: Execution View
Resize: 1920px → 1024px → 768px → 375px.
**Expect:** Toolbar adapts. Cells usable. No horizontal scroll. Mobile-friendly.

### 7.12 — Dark Mode: Execution UI
Enable dark mode → Run kernel.
**Expect:** CodeMirror readable. Syntax highlighting adapted. Borders visible. Good contrast.

### 7.13 — Dark Mode: Cell Borders
Amber/green/red borders clearly visible in dark mode.

### 7.14 — Loading Indicators
All loading states have visual feedback: "Connecting...", amber borders during execution. No "frozen" UI.

### 7.15 — Onboarding Tip on First Visit
Clear localStorage → visit notebook page.
**Expect:** Tip bar: "Click Run to execute code blocks..." on first visit. Auto-dismisses after 3 page visits. Manual dismiss via ×.

### 7.16 — Binder Packages Hint
After kernel connects on GitHub Pages: packages hint appears.
**Expect:** Shows installed packages. Dismissible. Dismissal persists.

### 7.17 — thebelab Button Overflow
After kernel connects: thebelab's built-in buttons hidden (we use our own toolbar).
If any thebelab buttons leak through, they don't overflow the container.

### 7.18 — Cell Injection Feedback Toast
On kernel start with simulator/credentials: green toast notification appears.
"Simulator active — using AerSimulator" or "IBM Quantum credentials applied".
Auto-fades after 4s. Non-blocking.

---

## Section 8: Performance & Reliability (12 tests)

### 8.1 — Connection Time: First Run
Fresh page → Run → time until kernel ready.
**Benchmarks:** <45s Excellent · 45–75s Good · 75–90s Acceptable · >90s Poor

### 8.2 — Connection Time: Subsequent Run
Second connection (cached Binder image).
**Target:** <30s. Noticeably faster than first.

### 8.3 — Cell Speed: Simple Code
`print("Hello")` → time from click to output.
**Target:** <1s.

### 8.4 — Cell Speed: Quantum Simulation
Bell state circuit (2 qubits, 1000 shots) → time.
**Target:** <5s.

### 8.5 — Cell Speed: Matplotlib Plot
Simple line plot → time.
**Target:** <3s. Green border accurate (not premature from multi-phase busy/idle).

### 8.6 — Memory: Client Side
Open DevTools Performance Monitor → run 10+ cells → monitor memory.
**Expect:** <500MB. No memory leaks. Stable over time.

### 8.7 — Multiple Tabs: Kernel Isolation
Open 3 tutorials in separate tabs → Run in each.
**Expect:** Each tab gets independent kernel. No cross-contamination. Acceptable performance.

### 8.8 — Long Session: 30+ Minutes
Keep kernel running 30+ min. Execute cells periodically.
**Expect:** Kernel remains stable. No degradation. No automatic disconnects.

### 8.9 — Page Refresh: Kernel Reset
Start kernel → define `x = 42` → refresh page → Run again → `print(x)`.
**Expect:** `NameError` — kernel does not persist across refresh. Fresh state. This is correct behavior.

### 8.10 — Rapid Button Clicking
Click run button 10 times rapidly on same cell.
**Expect:** Executions queued or duplicates ignored. No system errors.

### 8.11 — Slow Network Execution
Throttle to 3G (DevTools) → execute cells.
**Expect:** Slower but functional. No timeouts on normal operations.

### 8.12 — DevTools Open
Run kernel with DevTools open. Execute cells.
**Expect:** Works normally. Helpful debug info in console. WebSocket traffic visible in Network tab.

---

## Section 9: Back Button & State Reset (8 tests)

### 9.1 — Back Confirmation Dialog
Run kernel → execute cells → click Back.
**Expect:** Confirmation: "Going back will discard all live outputs and disconnect the kernel. Continue?"

### 9.2 — Cancel Back
Click Back → Cancel.
**Expect:** Dialog closes. Execution view remains. Kernel active. Previous outputs preserved.

### 9.3 — Confirm Back
Click Back → OK.
**Expect:** Returns to static view. Code blocks read-only. Live outputs cleared. Static outputs restored.

### 9.4 — State Reset After Back
Back → confirm → Run again → try `print(x)` (variable from previous session).
**Expect:** `NameError`. Fresh kernel. No stale state.

### 9.5 — Run Button Returns
After Back: "Run" button reappears. Toolbar reverts to pre-execution state.

### 9.6 — Static Outputs Return
With "Hide pre-computed outputs" enabled: Run → outputs hidden → Back.
**Expect:** Pre-computed outputs visible again.

### 9.7 — Back → Run → Back Cycle
Repeat Run → Back 3 times.
**Expect:** Each cycle works correctly. No degradation. State resets each time.

### 9.8 — Browser Back Button
Run kernel → press browser back button.
**Expect:** Navigates to previous page (normal browser behavior). Kernel disconnected.

---

## Section 10: Edge Cases & Stress Tests (12 tests)

### 10.1 — Empty Cell
Delete all code from cell → click run.
**Expect:** Executes without error. Green border. No output.

### 10.2 — Comment-Only Cell
```python
# This is just a comment
```
**Expect:** Executes. Green border. No output.

### 10.3 — Very Long Output
```python
for i in range(1000):
    print(f"Line {i}")
```
**Expect:** Output displays without crashing. May need scrolling.

### 10.4 — Infinite Loop
```python
while True: pass
```
**Expect:** Cell stays amber. No stop button (by design). User must click Back to reset.

### 10.5 — Deep Recursion
```python
def recurse(): return recurse()
recurse()
```
**Expect:** `RecursionError`. Red border. Kernel survives.

### 10.6 — Large Memory Allocation
```python
import numpy as np
arr = np.zeros((10000, 10000))
print(f"Allocated {arr.nbytes / 1e6:.0f} MB")
```
**Expect:** Either succeeds (~800MB) or `MemoryError`. Kernel handles gracefully.

### 10.7 — Special Characters / Unicode
```python
name = "世界"
print(f"Hello {name}")
```
**Expect:** Correct output: `Hello 世界`.

### 10.8 — Complex Cell Dependencies
Create 5 cells where each depends on previous. Execute out of order.
**Expect:** Clear `NameError`s when dependencies missing. User can fix by running in order.

### 10.9 — Rapid Cell Clicks (Different Cells)
Click run on 5 different cells as fast as possible.
**Expect:** Cells queue and execute in click order. All complete eventually. Correct borders.

### 10.10 — Multiple Page Runs in Sequence
Page A: Run → execute cells → Back. Navigate to Page B: Run → execute cells → Back.
**Expect:** Each page independent. No leftover state from Page A affecting Page B.

### 10.11 — thebelab Restart Buttons Hidden
After kernel connects: inspect for thebelab's default restart/run-all buttons.
**Expect:** Hidden (our custom toolbar replaces them).

### 10.12 — Kernel Death + Recovery
If testable: run code that kills kernel (e.g. extreme memory).
**Expect:** `kernelDead` flag set. Error broadcast to all cells. Red borders. "Kernel died" message. Must click Back and restart.

---

## Section 11: Learning Progress During Execution (8 tests)

### 11.1 — Page Visit Tracked on Navigation
Navigate to `/tutorials/hello-world` without clicking Run.
**Expect:** Sidebar shows ✓ next to "Hello World". Page recorded in `dq-visited-pages`.

### 11.2 — Execution Tracked on Run
Click Run on a tutorial page.
**Expect:** Sidebar shows ▶ (executed) instead of ✓ (visited). `dq-executed-pages` updated.

### 11.3 — Category Badge Updates
Visit 3 tutorials. Check Tutorials category header.
**Expect:** Badge "3/42" (or similar count). Updates in real-time.

### 11.4 — Resume Card After Execution
Run code on a tutorial → navigate to homepage.
**Expect:** "Continue where you left off" card shows that tutorial. Correct title.

### 11.5 — Recently Viewed Updates
Visit 3 tutorials → homepage.
**Expect:** "Recently viewed" widget shows all 3. Most recent first.

### 11.6 — Progress Indicator Clickable
Click ✓ on a sidebar item.
**Expect:** Visited status cleared for that page. ✓ disappears. Category badge decrements.

### 11.7 — Click Category Badge to Clear Section
Click the "3/42" badge on Tutorials category.
**Expect:** All tutorial progress cleared. Badge disappears. ✓/▶ indicators gone.

### 11.8 — Settings: Clear All Progress
Settings → Learning Progress → "Clear All Progress".
**Expect:** All ✓/▶ indicators removed. All badges reset. Recent pages cleared. Resume card disappears.

---

## Section 12: Bookmarks During Execution (5 tests)

### 12.1 — Bookmark Toggle on Doc Pages
Scroll to bottom of a tutorial page (below content, near "Edit this page").
**Expect:** ☆ "Bookmark" button inline with "Edit this page" link.

### 12.2 — Toggle Bookmark
Click ☆ → changes to ★ "Bookmarked". Click again → reverts to ☆.

### 12.3 — Bookmark Persists After Run
Bookmark a page → click Run → execute cells → click Back.
**Expect:** Bookmark still set (★). Not affected by execution.

### 12.4 — BookmarksList on Homepage
Bookmark 3 pages → navigate to homepage.
**Expect:** "Bookmarks" widget shows all 3 with remove buttons.

### 12.5 — Settings: Clear All Bookmarks
Settings → Bookmarks → "Clear all bookmarks".
**Expect:** All bookmarks removed. Widget disappears from homepage.

---

## Section 13: Settings Page (Full Feature Check) (12 tests)

### 13.1 — Page Title
Navigate to `/jupyter-settings`. **Expect:** Title "doQumentation Settings". H1 matches.

### 13.2 — Environment Status Bar
Blue info bar at top showing current environment (GitHub Pages / Custom / RasQberry / Unknown).

### 13.3 — All Sections Present
Scroll through page. Verify sections:
IBM Quantum Account → Simulator Mode → Active Mode (conditional) → Learning Progress → Display → Bookmarks (conditional) → Onboarding → Other → Binder Packages → Advanced (Custom Server)

### 13.4 — IBM 5-Step Setup Guide
Numbered list with links to IBM Quantum registration, API token page.

### 13.5 — Custom Server Fields
URL + token inputs. Buttons: Test Connection / Save / Default (RasQberry) / Clear.

### 13.6 — Test Connection
Enter valid Jupyter URL → click "Test Connection" → success message with version.
Enter invalid URL → click "Test Connection" → error message.

### 13.7 — Default Button (RasQberry)
Click Default → URL pre-filled with `http://localhost:8888`, token `rasqberry`.

### 13.8 — Clear Custom Server
Save custom URL → click Clear → fields empty. Environment falls back to auto-detect.

### 13.9 — Docker Help Section
Settings page shows Docker deployment help (if environment = rasqberry/docker): how to find token in logs.

### 13.10 — Display: Code Font Size
+/– buttons change font size (10–22px). Live preview updates. Persists after refresh.

### 13.11 — Onboarding: Reset Tips
"Reset Onboarding Tips" button. Click → visit a doc page → tip bar reappears.

### 13.12 — Settings: Clear All Preferences
"Clear All Preferences" button at bottom.
**Expect:** All localStorage cleared. Page reloads to default state.

---

## Section 14: Homepage & Navigation (10 tests)

### 14.1 — Homepage Hero
Load `/`. **Expect:** "doQumentation" title, one-liner subtitle, clickable stats bar (42 / 171 / 154 / 14).

### 14.2 — Stats Bar Links
Click each stat. **Expect:** Navigates to Tutorials / Guides / Courses / Modules.

### 14.3 — Simulator Callout
"No IBM Quantum account?" card with link to Settings → Simulator Mode.

### 14.4 — Getting Started Cards
Cards with category tags (Course / Tutorial / Guide):
- "Basics of QI" (Course)
- "Hello World: Your First Quantum Circuit" (Tutorial — custom)
- Hello World guide
- CHSH Inequality
- Advanced QAOA

### 14.5 — Custom Hello World Banner
Navigate to `/tutorials/hello-world`.
**Expect:** `OpenInLabBanner` shows "This tutorial was created for doQumentation." (not generic notebook message).

### 14.6 — Features Page Link
Homepage "See all features" → navigates to `/features`.
**Expect:** 22 feature cards in 5 sections. Responsive grid.

### 14.7 — Navbar: Always Dark
Toggle light/dark mode. **Expect:** Navbar stays `#161616`. GitHub icon + dark mode toggle forced to light colors.

### 14.8 — Navbar: No-Wrap
At ~900px width: navbar links stay on one line.

### 14.9 — Mobile Navigation
At 375px: hamburger icon visible. Click → sidebar opens. All sections accessible.

### 14.10 — Search
Press Ctrl+K (Cmd+K). Type "quantum circuit". **Expect:** Results from tutorials/guides/courses. Click result → navigates to page.

---

## Appendix A: Quick Smoke Test (15 minutes)

1. **Kernel Connection** (2 min) — Load tutorial → Run → wait → verify Back button + legend
2. **Basic Execution** (3 min) — `print("Hello")` → green border → output
3. **Error Handling** (2 min) — Invalid code → red border → error message
4. **Simulator Mode** (3 min) — Enable in Settings → Run → badge + toast
5. **State Reset** (2 min) — Execute code → Back → confirm → verify reset
6. **Multiple Cells** (3 min) — Execute 3 cells → variables persist → all green

**Pass: 6/6 checks**

---

## Appendix B: Performance Benchmarks

| Metric | Excellent | Good | Acceptable | Poor |
|--------|-----------|------|------------|------|
| First kernel connection | <45s | 45–75s | 75–90s | >90s |
| Subsequent connection | <15s | 15–30s | 30–45s | >45s |
| Simple cell execution | <1s | 1–2s | 2–5s | >5s |
| Quantum simulation (2q) | <3s | 3–8s | 8–15s | >15s |
| Matplotlib plot | <2s | 2–5s | 5–10s | >10s |

---

## Appendix C: Test Coverage Summary

| Section | Tests | Focus |
|---------|-------|-------|
| 1. Kernel Connection | 15 | Bootstrap, auto-activation, network errors |
| 2. Cell Execution | 25 | Outputs, state, dual display, font size |
| 3. Error Handling | 18 | All error types, recovery, pip install button |
| 4. Simulator Mode | 14 | AerSim, FakeBackend, save_account() feedback |
| 5. IBM Credentials & Settings UX | 16 | TTL, disclaimer, snippet, pre-computed outputs |
| 6. Package Management | 10 | Pre-installed, pip install, injected cells |
| 7. UI/UX & Visual Feedback | 18 | Borders, dark mode, responsive, onboarding |
| 8. Performance & Reliability | 12 | Timing, memory, stability, multi-tab |
| 9. Back Button & Reset | 8 | Confirmation, state reset, cycle test |
| 10. Edge Cases | 12 | Empty cells, infinite loop, unicode, stress |
| 11. Learning Progress | 8 | Visit tracking, badges, resume card |
| 12. Bookmarks | 5 | Toggle, persist through execution, clear |
| 13. Settings Page | 12 | All sections, font size, custom server |
| 14. Homepage & Navigation | 10 | Hero, cards, navbar, search, mobile |
| **TOTAL** | **183** | |

---

## Appendix D: Priority Classification

### P0 — Critical (must pass)
- 1.1–1.4 (kernel connects, simulator activates)
- 2.1–2.5 (basic cell execution + state)
- 3.1, 3.7 (errors detected + hints shown)
- 4.1, 4.5 (simulator works, save_account feedback)
- 9.3 (Back resets state)

### P1 — Important (should pass)
- All remaining Section 2, 3, 7, 9 tests
- 5.1–5.5 (credential UX improvements)
- 11.1–11.4 (progress tracking)

### P2 — Nice to have
- Sections 4, 5, 6, 8, 12, 13, 14 (full coverage)

### P3 — Edge cases
- Section 10 (stress tests)

---

**Test Plan Version:** 2.0
**Created:** February 11, 2026
**Updated:** February 12, 2026 — Added sections 11–14, updated for Settings UX, 133 → 183 tests

*End of Test Plan*
