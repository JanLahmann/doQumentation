# Evaluation: "Use a previous Qiskit level" option

Date: 2026-06-09
Status: **Evaluation / design — not implemented**
Prompted by: the qiskit 2.3.0 → 2.4.1 dep bump (#270); some users may want to
pin to the prior level when a minor bump changes notebook behavior.

## TL;DR

**Feasible and cheap — but only for the Binder (`github-pages`) tier**, which is
the default tier on doqumentation.org. QuBins already publishes a full ladder of
version-tagged, pre-built Binder images (`2.0-xl` … `2.4-xl`, `latest-xl`), so a
version selector is just "point `binderUrl` at a different existing tag." There
is **no new image to build or maintain on our side** for this tier. The CE and
local tiers can't easily switch (single baked-in image / user-controlled) and are
out of scope.

**Recommendation: implement a small Settings control for the Binder tier**, using
the existing `backendOverride` pattern as the template. ~half a day. The other
tiers are explicitly out of scope and should be labelled as such in the UI.

## Where the Qiskit version is actually determined (verified)

Three execution tiers in `src/config/jupyter.ts` (`buildConfigFor`):

| Tier (`environment`) | Qiskit version source | Can switch? |
|---|---|---|
| **`github-pages`** (Binder, the public default) | `binderUrl` hardcodes `mybinder.org/v2/gh/QuBins/qiskit-images/**2.3-xl**` (jupyter.ts:245) | **YES — trivially.** QuBins has tags `1.4/2.0/2.1/2.2/2.3/2.4-xl` + `latest-xl`, all pre-built. Swap the tag. |
| **`code-engine`** | our self-built `ghcr.io/janlahmann/doqumentation-codeengine:latest`, one Qiskit baked in from `binder/jupyter-requirements.txt` | Not without a 2nd tagged CE image (real build/maintenance cost). Out of scope. |
| **`rasqberry` / `custom` / local** | the user's own kernel/server | User controls it; not ours. Out of scope. |

So the version pin lives in exactly one editable place for the tier that matters:
the `binderUrl` tag.

## Available QuBins tags (verified via `git ls-remote`)

`1.4-{small,xl}`, `2.0-{small,xl}`, `2.1-{small,xl}`, `2.2-{small,xl}`,
`2.3-{small,xl}`, `2.4`, `2.4-{small,xl,xxl}`, `latest-{small,xl,xxl}`, `main`.

We currently use `2.3-xl`. After #270 (qiskit 2.4.1) our `binder/jupyter-
requirements.txt` is **ahead** of the Binder default — note jupyter.ts:244 says
"Matches binder/jupyter-requirements.txt (qiskit[all]~=2.3.0). Bump in lockstep."
**That comment is now stale** — we bumped the pin to 2.4.1 but the Binder image is
still `2.3-xl`. Independent of the version-selector feature, the default Binder
tag should move to `2.4-xl` to stay in lockstep (small standalone fix).

## Design (if we build it)

Mirror the existing **`backendOverride`** mechanism exactly (it already does
"persist a per-user override in localStorage and apply it in `buildConfigFor`"):

1. **Storage** (`jupyter.ts`): add `STORAGE_KEY_QISKIT_VERSION =
   'doqumentation_qiskit_version'` + `getQiskitVersion()/setQiskitVersion()`,
   alongside the existing `backendOverride` helpers (jupyter.ts:57/98/105).
2. **Apply** (`jupyter.ts:245`): in the `github-pages` case, build the tag from
   the override: ``binderUrl: `https://mybinder.org/v2/gh/QuBins/qiskit-images/${getQiskitVersion() ?? '2.4-xl'}` `` (default = current/lockstep tag). Validate against an allow-list of known QuBins tags so a bad value can't break the URL.
3. **UI** (`jupyter-settings.tsx`): a `<select>` near the existing backend
   controls (~line 560 backend-selection section), only shown/enabled when the
   active environment is `github-pages`. Options = the supported `-xl` tags
   (e.g. "Qiskit 2.4 (current)", "2.3", "2.2", …). Label clearly that it applies
   to the Binder backend only. Reset on "clear settings" (jupyter.ts:285 already
   clears `backendOverride` — add the new key there too).
4. **i18n**: one new label string (the page is fully i18n-wrapped).

Effort: **~half a day**, low risk (additive, one tier, allow-list-guarded,
reuses a proven pattern). No CI/image/deploy implications.

## Open questions for product decision (before building)

1. **Is the demand real?** This adds a knob most learners won't touch. Cheaper
   alternative: document the current version + how to `!pip install qiskit==X` in
   a notebook cell, and skip the UI entirely.
2. **How many old versions to expose?** Suggest current + 2 prior (`2.4/2.3/2.2`)
   rather than the full ladder down to 1.4 (old Qiskit pre-2.0 APIs differ enough
   that tutorials won't run). An allow-list makes this a one-line policy choice.
3. **`small` vs `xl`?** Keep `-xl` (matches today); don't expose the size axis.
4. **CE-tier parity?** If workshop/CE users ever need version choice, that's a
   separate, costlier effort (second tagged CE image). Recommend NOT bundling it.

## QuBins vs our pins — exact-version caveat (verified 2026-06-09)

The Binder image and our CE image are **independently pinned** and match at
**minor** granularity only, NOT patch/ecosystem-exact:

| | qiskit | ibm-runtime | serverless | ibm-catalog |
|---|---|---|---|---|
| **CE/Docker** (`binder/jupyter-requirements.txt`) | `~=2.4.1` | `~=0.47.0` | `~=0.32.0` | `~=0.16.0` |
| **QuBins `2.4-xl`** (`versions/2.4-xl/requirements.txt`) | `~=2.4.0` | `~=0.45.1` | `~=0.30.0` | `~=0.14.0` |

- `~=2.4.0` and `~=2.4.1` both float to the **same latest 2.4.x** (currently
  2.4.1), so qiskit itself effectively matches. The pin *text* differs; the
  installed version doesn't.
- Our CE image is **ahead** on runtime/serverless/catalog. A notebook using a
  runtime≥0.47-only API works on CE but may differ on Binder (0.45.1). This is
  inherent to having two independently-pinned backends — it predates and is not
  caused by the version-selector; the prior 2.3-xl gap was larger.
- **Lockstep is enforced at MINOR granularity by design** — QuBins only ships
  minor-tagged images (`2.4-xl`, not `2.4.1-xl`), so the CI guard can't (and
  shouldn't) require patch-exact parity. Minor-level is the achievable contract.

## Recommended next step

Two separable pieces:
- **(a) Lockstep fix (do regardless):** bump the default Binder tag `2.3-xl →
  2.4-xl` to match the #270 dep bump, and refresh the stale jupyter.ts:244 comment.
- **(b) The selector (needs product go-ahead):** implement the Settings control
  above if there's real demand; otherwise document the pip-pin workaround.
