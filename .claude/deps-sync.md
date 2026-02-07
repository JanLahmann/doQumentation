# Keeping Requirements in Sync with Upstream

## Problem
Our `binder/jupyter-requirements.txt` and `binder/jupyter-requirements-amd64.txt` mirror
the canonical dependency list at `JanLahmann/Qiskit-documentation/scripts/nb-tester/requirements.txt`.
When upstream bumps versions, we need to follow.

## Current exceptions (intentional divergences)
| Package | Upstream | Ours | Reason |
|---------|----------|------|--------|
| `pylatexenc` | absent | added (cross-platform) | Needed for LaTeX in Qiskit visualizations |
| `gem-suite` | no platform marker | amd64-only | No prebuilt arm64 wheel |
| `qiskit-addon-aqc-tensor[quimb-jax]` | `; sys.platform != 'darwin'` | amd64-only | kahypar has no arm64 wheel |
| `qiskit-ibm-transpiler[ai-local-mode]` | all platforms | amd64-only | Closed-source binary, no arm64 build |
| `sys.platform` markers | `!win32`, `!darwin` | dropped | Linux-only containers |

## Options for automated sync

### 1. GH Actions scheduled diff (lightweight)
Weekly workflow that fetches upstream file, diffs against ours, opens an issue if changed.
- Pro: Simple, no PRs to review unless something changed
- Con: Manual update still needed

### 2. GH Actions auto-PR (medium)
Scheduled workflow that fetches upstream, applies our exception rules, opens a PR if different.
- Pro: Ready-to-merge PR with the exact changes
- Con: Needs logic to preserve our exceptions (arch splits, pylatexenc addition)

### 3. Dependabot / Renovate (heavy)
Let a bot bump individual package versions.
- Pro: Industry standard
- Con: Doesn't understand our "sync with upstream" requirement — would propose independent bumps

### 4. Manual periodic review
Run a Claude Code session: "compare our requirements with upstream and propose updates."
- Pro: Zero infrastructure
- Con: Easy to forget

## Recommendation
Option 2 (auto-PR) is the best balance. The workflow would:
1. Fetch `scripts/nb-tester/requirements.txt` from `JanLahmann/Qiskit-documentation`
2. Parse packages + versions
3. Apply exception rules (arch splits, additions, marker removals)
4. Write updated `jupyter-requirements.txt` and `jupyter-requirements-amd64.txt`
5. If changed, open a PR

This could live in `.github/workflows/sync-deps.yml`.
