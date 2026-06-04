# Domain 3 — Live Verification Checklist (code execution & Binder/Jupyter)

Run against the real site (doqumentation.org / a locale subdomain / a CE workshop pod).
Static review can't confirm runtime timing/concurrency behavior — these do.
Each item: what to do → what PASS looks like → which finding it confirms.

## A. Core execution smoke test (#11) — the baseline "does it work"
1. **Binder connect + run.** Open a tutorial with a code cell → click Run → wait for kernel.
   PASS: kernel connects (30-40s cold), cell executes, green border feedback, output shows.
2. **pip-install injection.** Run a cell needing an injected package (the prerequisites cell).
   PASS: `!pip install -q ...` runs first, import succeeds.
3. **Simulator / fake-backend mode.** Switch execution mode to Aer/fake → run a circuit.
   PASS: runs without IBM credentials; FakeBackend dropdown populates (confirms L3 onIOPub fired).
4. **Circuit diagram + histogram.** Run a cell that draws a circuit and one that plots counts.
   PASS: matplotlib/plotly render inline.
5. **Run/Back toggle + dual output.** Toggle Back → static MDX output returns; Run again → live.
   PASS: static and live outputs both present, toggle is clean.
6. **Run All.** Trigger Run All on a multi-cell page incl. a comment-only/instant cell.
   PASS: completes without a ~60s stall on the trivial cell (watch for L5 safety-net delay).

## B. Race / session findings needing live confirmation
7. **H1 EventSource leak.** Click Run on page A → within the build window (<2 min) navigate to page B.
   Watch DevTools Network (EventSource tab) + console.
   FAIL (confirms H1): the page-A SSE stays open after nav; later writes `dq-binder-session`.
   PASS (if fixed): SSE closes on navigation.
8. **H2 cross-page retry.** Force a kernel-race failure on page A (or throttle), navigate to page B
   within 1s. Watch console for `retrying bootstrap after kernel race`.
   FAIL (confirms H2): retry fires against page B's DOM / wrong options.
9. **H3 false-ready.** During the 1s race-retry window on a page with multiple cells, click Run on a
   second cell. FAIL (confirms H3): second cell flips to "ready" and lets you execute with no live kernel.
10. **M1/M2 session host mismatch.** Configure CE instance A, connect, then switch to instance B (or bump
    workshop pool version) and Run. Inspect `sessionStorage['dq-binder-session'].url` host vs active config.
    FAIL: session for A reused while config points at B.
11. **M4 pool-down failover.** Point a 3-instance workshop pool at all-down URLs → Run. Watch
    `dq-workshop-assigned` + repeated `connecting` phases. FAIL (confirms M4): walks the ring repeatedly
    instead of stopping after one failover.
12. **M5 stalled-SSE.** Force a Binder cache miss (push a commit to invalidate, then Run). PASS: slow-startup
    warning banner appears; Cancel actually aborts the SSE. Watch for the 20-min worst-case on a silent stall.
13. **L4 injection-failure.** Kill the kernel right after connect. FAIL (confirms L4): cells still flip to
    "ready" with no credential/simulator patch and no warning.

## C. Workshop backend (CE pod) — needs a pod + load
14. **connections_dict memory creep (known-open).** Run a multi-session workshop day on one pod; poll
    `/stats`. CONFIRM-OPEN: `kernels`/`memory_mb` climb monotonically with no auto-recovery. Workaround:
    restart pod between sessions.
15. **F1 connect-storm / rate limit.** 80 users (or the stress harness) behind ONE IP click Run within ~2s.
    Count 503s on `/build/`. FAIL (confirms F1): ~30 get 503; single-pod → hard reject. This is the headline
    workshop risk — pairs with the missing stagger.
16. **F3 wedged-pod.** With kernels exhausted but `/api/status` returning 200, start new clients.
    FAIL (confirms F3): SSE clients hang ~30s; confirm whether pool failover rescues them.
17. **F5 CORS origin.** From the actual locale subdomain that hits the CE pod, make a `/build/` request.
    FAIL (confirms F5): CORS rejection if `CORS_ORIGIN` doesn't match the deployed subdomain.

## Priority for a single live session
If time-boxed: do **A1-A5** (does execution work at all), then **15 (F1 connect-storm)** and
**14 (memory creep)** — those two are the load-bearing workshop risks. The race findings (7-9) are real
but only bite under fast-navigation + concurrency; verify after the fixes land.
