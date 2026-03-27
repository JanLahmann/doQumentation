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

## Priority order

1. **#1 (validator fix)** — highest impact, purely mechanical, no risk of regression
2. **#2 (prompt rule)** — one line addition, immediately reduces the most common failure
3. **#3 (chunk threshold)** — safe change, reduces edge-case truncation
4. **#4 (boundary overlap)** — more complex to phrase clearly, lowest frequency
