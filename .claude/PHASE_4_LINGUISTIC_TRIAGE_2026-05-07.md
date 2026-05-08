# Phase 4 Linguistic Review Triage — 2026-05-07

Source: 222 Phase 1 reviews + 27 Phase 1.5 spot-checks (all Sonnet). Total: 249 files reviewed today, 16 FAILs and 53 MINOR_ISSUES recorded across 9 mostly-done locales (de, es, fr, it, ja, uk, pt, tl, ar).

## High-priority FAILs (need fix before next translation pass)

### 1. JA systematic ご〜ください register violation (18 files affected, 3 FAILs)

The translator has a strong default toward honorific request forms (`ご覧ください`, `ご参照ください`, `お読みください`, `ご利用ください`) where the EN source uses neutral "see [link]" / "refer to". Per [translation/review-prompt.md](../translation/review-prompt.md) JA register section, these are explicit register violations.

**Fix**: Global find-replace across ALL JA files, not just the 18 flagged:
- `ご覧ください` → `参照してください`
- `ご参照ください` → `参照してください`
- `お読みください` → `読んでください`
- `ご利用ください` → `使ってください`
- `ご利用いただけます` → `使用できます`

The Haiku reviews missed this entirely (the spot-check found 3/3 prior PASS files had violations). Low effort, high impact — 1-line `sed` per pattern across `i18n/ja/`.

### 2. AR "diagonalization → التقطير (distillation)" systematic error (2 FAILs, more likely)

Catalogued in [memory/project_ar_review_issues.md](../memory/project_ar_review_issues.md). Confirmed today in:
- `learning/courses/quantum-diagonalization-algorithms/introduction.mdx` (10+ occurrences)
- `learning/courses/use-a-qc-today/your-first-quantum-experiment.mdx` line 342

Plus "variational" → "التفاضلي" (differential) — should be "التغايري".

**Fix**: This is a re-translation, not a find-replace, because the same Arabic word is used in different contexts. Need a translator pass over the entire `learning/courses/quantum-diagonalization-algorithms/` subtree.

### 3. AR "observable" cross-file inconsistency (3 MINOR)

Same EN word "observable" rendered three different ways across the AR locale:
- `العنصر القابل للرصد` (in cutting/, mpf/, pna/01)
- `المتغير الملاحظ` (in slc/01)
- `الرصدية` (in qiskit-addons/obp/)

**Fix**: Pick one canonical translation, search-and-replace. Safer to standardize on `العنصر القابل للرصد` (most-used, most literal).

### 4. PT broken env-var fragment (1 FAIL)

`guides/qiskit-1.0-installation.mdx` lines 587/589 have orphan `_1_0_IMPORT_ERROR=1\``.` fragments after the env-var name `QISKIT_SUPPRESS_1_0_IMPORT_ERROR=1` was split during translation. Easy manual edit.

### 5. TL `workshop/03_Qiskit 101 Hands-on.mdx` ~75% untranslated (1 FAIL each in `_solution.mdx` + main)

Sections 2-5 (IBM Cloud setup, Quantum Circuits, Multi-Qubit Gates, Running on QPU) are entirely English in the TL translation. Same applies to `_solution.mdx`. Both files need re-translation.

### 6. TL "inyong/ninyo" formal-register boilerplate (6 files)

The phrase `Ang inyong runtime ay maaaring mag-iba` ("Your runtime may vary") appears as boilerplate at the top of multiple TL tutorials with formal register. Single find-replace: `Ang inyong runtime` → `Ang iyong runtime`.

### 7. DE qiskit-addons/slc/01 multiple terminology + typo issues (1 FAIL)

- "Probabilistische Fehlerkorrektur" → should be "Probabilistische Fehlerauslöschung" (PEC = error *cancellation*, not correction)
- Typo "migtierten" line 14 → "mitigierten"
- Typo "getwirbeldte" line 1008 → "getwirbelten"
- "nicht minimierten" line 1091 → "nicht mitigierten"
- Broken syntax line 14: "Während PEC, um die Dämpfung … zu kompensieren, wird …"

Single file, surgical edits.

### 8. TL `quantum-computing-context.mdx` + `quantum-mechanics-basics.mdx` "panganib" accuracy (1 FAIL + 1 MINOR)

Line 194 in BOTH files: `parehong panganib na matematika` (panganib = danger/risk) translates `same underlying mathematics`. Should be `parehong pinagbabatayan na matematika`. Likely shared boilerplate copied between files.

## Medium-priority MINOR_ISSUES patterns

### FR `veuillez consulter` (3 files)
Same boilerplate `veuillez consulter [l'article]` slipping into tu-register text. Find-replace: `veuillez consulter` → `consulte`.

### Capitalized English nouns mid-sentence (4 files across ES/PT/UK)
Translator left "Circuit", "Gate", "Qubit", "Backend" capitalized in target-language prose. Localized fix per file.

### Untranslated English passages in workshop/03 family (7 files across DE/ES/IT/TL)
The `workshop/03_Qiskit 101 Hands-on.mdx` and `04_Hands-on Introduction to Qiskit.mdx` files have isolated English paragraphs in several locales. TL is worst (full FAIL); others are isolated MINOR.

### UK formal-plural imperatives (~5 files)
`зверніться`, `перегляньте`, `беріть` slipping into ти-register. Find-replace patterns:
- `зверніться` → `звернись`
- `перегляньте` → `переглянь`
- `беріть` → `бери`

### JA translator preference: capitalize "Qubit/Circuit/Gate/Backend"
Cosmetic only; not a register violation.

## Recommended action sequence

1. **Cheap wins** (single-day): JA find-replace, FR `veuillez` find-replace, UK formal-plural find-replace, TL `inyong runtime` find-replace, DE slc/01 surgical edits, PT qiskit-1.0-installation fragment fix.
2. **Re-translation pass**: TL `workshop/03_Qiskit 101 Hands-on*.mdx` (both variants) — these are major content gaps.
3. **AR diagonalization re-translation**: scope is the entire `quantum-diagonalization-algorithms` course subtree + isolated occurrences.
4. **AR observable canonicalization**: low-priority terminology consistency pass.

## Validator improvements suggested by these findings

- Add a check: `ご覧ください` / `ご参照ください` / `ご利用ください` should fail the JA register check. Add to `lint-translation.py` or `validate-translation.py`.
- Add a check: AR files containing "diagonalization" in EN should not contain "تقطير" in AR.
- Add a check: FR files should not contain `veuillez` (or only in narrow contexts).
- Add a "untranslated paragraph" detector: count consecutive paragraphs whose word-overlap with EN exceeds 80%.
