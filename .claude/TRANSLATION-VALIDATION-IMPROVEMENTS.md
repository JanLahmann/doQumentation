# Translation Validation Improvements

Identified during Malay (ms) translation session (2026-03-27).
Ask: implement these before the next major translation run.

---

## 1. Fix false positive in `check_indented_headings` (validator bug)

**File:** `translation/scripts/validate-translation.py`, function `check_indented_headings` (~line 542)

**Problem:** The check skips indented headings that also appear indented in the EN source — but the comparison is text-based (`stripped in en_indented`). Since the TR heading is translated, the text never matches EN, so the skip never fires. Result: every notebook-style file with an indented `# Title` heading fails with a false positive, requiring `--force` to promote.

**Example:**
- EN source line 12: `  # Quantum noise and error mitigation` → adds `"# Quantum noise and error mitigation"` to `en_indented`
- TR line 13: `  # Hingar kuantum dan pengurangan ralat` → stripped text not in `en_indented` → false FAIL

**Fix:** Track indented heading positions (ordinal index among all headings) in EN, then compare by position in TR, not by text.

```python
def check_indented_headings(tr_content: str, en_content: str = "") -> CheckResult:
    """Detect headings with leading whitespace — MDX won't parse {#anchor} on these."""

    def get_heading_info(content):
        """Returns list of (is_indented, stripped_text) for each heading, skipping code blocks."""
        result = []
        in_code = False
        for line in content.split('\n'):
            if line.strip().startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                continue
            if re.match(r'^\s*#{1,6}\s+', line):
                indented = bool(re.match(r'^(\s+)#{1,6}\s+', line))
                result.append(indented)
        return result

    en_heading_indented = get_heading_info(en_content) if en_content else []

    in_code = False
    details = []
    tr_heading_idx = 0

    for i, line in enumerate(tr_content.split('\n')):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r'^(\s+)(#{1,6})\s+(.+)$', line)
        if re.match(r'^\s*#{1,6}\s+', line):
            is_indented = bool(m)
            if is_indented:
                # Check if EN heading at same position is also indented
                if tr_heading_idx < len(en_heading_indented) and en_heading_indented[tr_heading_idx]:
                    tr_heading_idx += 1
                    continue  # EN also has this indented — not a translation error
                details.append(
                    f"Line {i + 1}: '{line.strip()[:60]}' has {len(m.group(1))} leading space(s)")
            tr_heading_idx += 1

    if details:
        return CheckResult("Indented headings", False,
                           f"{len(details)} heading(s) with leading whitespace (breaks MDX)",
                           details)
    return CheckResult("Indented headings", True, "No indented headings")
```

**Impact:** Eliminates false positives for ~10+ notebook-style files per locale. No `--force` needed for these.

---

## 2. Add "no leading spaces in code blocks" rule to agent prompt

**File:** `translation/translation-prompt.md`, Step 3 agent prompt block (~line 74)

**Problem:** Agents consistently add a single leading space to the first line of output-type code blocks (e.g. ` ```text` blocks with numerical output). This causes code block content diffs and validation failures. It happened in 5+ files in the Malay session alone.

**Fix:** Add one line to the Rules section of the agent prompt:

```
- Never add leading spaces inside code fences. Every line within a code block must
  be byte-identical to the source — including the very first line after the opening fence.
```

**Impact:** Reduces the most common post-translation fix (bulk code-block replacement script).

---

## 3. Lower chunk threshold from 400 to 350 lines

**File:** `translation/translation-prompt.md`, Step 3 (~line 70) and Chunking section (~line 124)

**Problem:** A 379-line chunk (deutsch-jozsa part1) still got truncated mid-code-block, with the agent cutting off a long code block before finishing. 400 lines is too close to the agent's comfortable output limit when the file is code-heavy.

**Fix:** Change all references from `400` to `350`:
- "If ≤400 lines, launch agent. If >400 lines, see Chunking below." → `350`
- "Group into chunks of at most 400 lines." → `350`
- The `translation-prompt-web.md` prompt template → update `400` reference

**Impact:** Reduces truncation-related code block failures, especially in notebook files with large code cells.

---

## 4. Avoid skipping headings at chunk boundaries

**File:** `translation/translation-prompt.md`, Chunking section (~line 132)

**Problem:** When a chunk boundary falls just after a section comment heading (e.g. `# Activity 2: ...`), the part2 agent starts at the next `##` heading and skips the comment heading that immediately preceded its start. This causes heading count mismatches.

**Fix:** Add to the chunking instructions:

```
- When describing a middle or last chunk to its agent, also include the 3 lines
  immediately before the start heading, so the agent can see if there is a
  section-level heading (e.g. `# Activity 2:`) that belongs to its chunk.
  Instruct the agent: "If the line immediately before `## Start Heading` is a
  `#`-level heading, include it in your translation."
```

**Impact:** Prevents missing headings at part boundaries (heading count mismatch failures).

---

---

## 5. Validator: heading count should exclude indented headings consistently

**File:** `translation/scripts/validate-translation.py`, function `check_heading_count`

**Problem:** The heading count check counts all non-code-block headings. But `check_indented_headings` permits indented headings that are also indented in EN (by position). If the heading count check doesn't also exclude those same indented headings from its count, the two checks contradict each other. Example: `kipu-optimization.mdx` has ` #### Accepted problem formats` (1 leading space in EN). EN heading count = 26 (skips it). If TR renders it non-indented, TR count = 27 → mismatch. But `check_indented_headings` would flag it too. The workaround — adding a leading space to the TR — is fragile and surprising.

**Fix:** In the heading count check, use the same `get_heading_info()` helper from the `check_indented_headings` fix (#1 above) to exclude headings that are indented in EN from both the EN and TR counts.

**Impact:** Eliminates the kipu-style count mismatch. The two checks become consistent: a heading that is indented in EN is excluded from the count check AND permitted (not flagged) by the indented headings check.

---

## 6. Validator: lint code fence count check should compare TR to EN, not just check even/odd

**File:** `translation/scripts/lint-translation.py`, fence count check

**Problem:** The lint check flags any file where the total number of ` ``` ` fence markers is odd. But some EN source files legitimately have an odd fence count (e.g. `qiskit-code-assistant-local.mdx` has 29 fences — JSX template literals). The TR correctly mirrors the EN, but fails the lint check.

**Fix:** Compare TR fence count to EN fence count. Only flag if `TR_count != EN_count`. An odd count is fine as long as both sides match.

**Impact:** Eliminates false positive lint failures for files with JSX template fences. Currently requires `--force` to promote these files.

---

## 7. Fix upstream stray leading space in `kipu-optimization.mdx`

**File:** `upstream-docs` submodule (or `docs/guides/kipu-optimization.mdx` after sync)

**Problem:** Line 84 of `docs/guides/kipu-optimization.mdx` has a stray leading space:
```
 #### Accepted problem formats
```
This is almost certainly a typo in the IBM upstream source. It is not intentional MDX structure — unlike the `  # Title` headings in notebook-style course files (which are structural). The stray space causes every translation of this file to require manual intervention (add leading space to TR, or force-promote).

**Fix:**
1. Remove the leading space from `docs/guides/kipu-optimization.mdx` line 84 (or raise a PR upstream).
2. Re-stamp the source hash in all 12 promoted locale files for `guides/kipu-optimization.mdx` (DE, ES, FR, IT, UK, JA, AR, PT, TL, TH, MS, ID) using `check-translation-freshness.py --stamp`.

**Contrast with notebook-style files:** `error-mitigation.mdx` and `quantum-circuit-optimization.mdx` have `  # Title` at line 12. These are intentional (notebook cell title style) and should be left as-is — handled only by the validator fix (#1 + #5).

**Impact:** Future translations of `kipu-optimization.mdx` pass validation without any manual intervention.

---

## Priority order

1. **#1 (validator fix)** — highest impact, purely mechanical, no risk of regression
2. **#2 (prompt rule)** — one line addition, immediately reduces the most common failure
3. **#5 (heading count consistency)** — pairs with #1, eliminates kipu-style contradictions
4. **#6 (lint fence count)** — one-line fix, eliminates false positive lint failures
5. **#7 (upstream kipu fix)** — fixes the root cause for kipu specifically; requires hash re-stamp across 12 locales
6. **#3 (chunk threshold)** — safe change, reduces edge-case truncation
7. **#4 (boundary overlap)** — more complex to phrase clearly, lowest frequency
