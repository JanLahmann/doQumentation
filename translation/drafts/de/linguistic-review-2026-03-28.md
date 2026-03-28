# Full Linguistic Review of German (de) Translations

**Date:** 2026-03-28
**Scope:** All 391 German translation files (4 JSON + 172 guides + 170 learning/courses + 45 tutorials/index)
**Reviewer:** Automated linguistic review (Claude)

---

## Executive Summary

The overall translation quality is **high** -- most files read naturally, use correct German grammar, and handle technical quantum computing terminology well. However, systematic issues were found across all categories. The most impactful problems are:

1. **Critical terminology error:** "Fehlerkorrektur" used instead of "Fehlerminderung" for "error mitigation" (confuses two fundamentally different QC concepts)
2. **Repeated spelling errors:** "fehlerotolerant" (8x), "Fehlerkennung" (missing "er"), "Messfehlermindung" (missing "er")
3. **du/Sie register inconsistency:** Several files use formal "Sie" while the project standard is informal "du"
4. **~80+ untranslated strings** in guide files (headings, admonition titles, boilerplate text)
5. **Terminology inconsistencies** across files (Circuit/Schaltkreis/Schaltung, Stabilizer/Stabilisator, etc.)

| Priority | Issue Count | Category |
|----------|-------------|----------|
| Critical | ~25 | Wrong terminology (Fehlerkorrektur vs. Fehlerminderung) |
| Critical | 19 | Spelling errors (fehlerotolerant, Fehlerkennung, etc.) |
| Critical | 11 | Untranslated `\text{and}` in LaTeX formulas |
| High | ~30 | du/Sie register inconsistency |
| High | ~80+ | Untranslated strings in guides |
| Medium | ~30 | Terminology inconsistencies |
| Medium | ~20 | Awkward/overly literal phrasing |
| Low | ~15 | Minor style inconsistencies |

---

## 1. JSON UI Translation Files (4 files)

### 1.1 Untranslated Strings

| File | Key | Current | Fix |
|------|-----|---------|-----|
| `footer.json` | `link.item.label.Settings` | "Settings" | "Einstellungen" |
| `navbar.json` | `item.label.Settings` | "Settings" | "Einstellungen" |
| `current.json` | `sidebar...link.Home` | "Home" | "Startseite" |
| `code.json` | `features.ui.mobile.title` | "Mobile Responsive" | "Mobilgeräte-optimiert" |

### 1.2 Grammar Errors

| File | Key | Current | Issue | Fix |
|------|-----|---------|-------|-----|
| `code.json` | `theme.docs.paginator.navAriaLabel` | "Dokumentation Seiten" | Compound noun not joined | "Dokumentationsseiten" |
| `code.json` | `theme.blog.post.paginator.navAriaLabel` | "Blog Post Seiten Navigation" | Broken compound | "Seitennavigation für Blogbeiträge" |
| `code.json` | `theme.docs.versions.unmaintainedVersionLabel` | "Das ist die Dokumentation..." | Colloquial + broken relative clause | "Dies ist die Dokumentation für {siteTitle} {versionLabel}, die nicht mehr gepflegt wird." |
| `code.json` | `features.execution.feedback.desc` | "...grün wenn fertig" | Missing comma | "...grün, wenn fertig" |

### 1.3 Anglicisms in German Text

| File | Key | Current | Fix |
|------|-----|---------|-----|
| `code.json` | `theme.blog.post.paginator.newerPost` | "Neuer Post" | "Neuerer Beitrag" |
| `code.json` | `theme.blog.post.paginator.olderPost` | "Älterer Post" | "Älterer Beitrag" |
| `code.json` | `theme.blog.post.plurals` | "Ein Post\|{count} Posts" | "Ein Beitrag\|{count} Beiträge" |
| `code.json` | `theme.docs.tagDocListPageTitle.nDocsTagged` | "Ein doc getaggt\|{count} docs getaggt" | "Ein Dokument markiert\|{count} Dokumente markiert" |
| `code.json` | `theme.blog.tagTitle` | "{nPosts} getaggt mit..." | "{nPosts} markiert mit..." |

### 1.4 Ambiguous/Unnatural Phrasing

| File | Key | Current | Fix |
|------|-----|---------|-----|
| `code.json` | `theme.docs.versions.latestVersionLinkLabel` | "letzte Version" | "neueste Version" (unambiguous) |
| `code.json` | `theme.docs.versions.latestVersionSuggestionLabel` | "...bitte auf {link} gehen" | "Die aktuellste Dokumentation finden Sie unter {link}." |
| `code.json` | `features.ui.video.desc` | "Fällt auf IBM Video zurück" | "Greift auf IBM Video zurück" |
| `code.json` | `features.ui.video.desc` | "YouTube-Zuordnung" | "YouTube-Verknüpfung" |
| `code.json` | `theme.docs.breadcrumbs.navAriaLabel` | "Breadcrumbs" | "Navigationspfad" |

### 1.5 Sidebar Terminology (current.json)

| Key | Current | Issue | Fix |
|-----|---------|-------|-----|
| `sidebar...Purifications and fidelity` | "Reinigungen und Fidelity" | "Reinigungen" wrong QC term | "Purifikationen und Fidelity" |
| `sidebar...Variational algorithm design` | "Design variationaler Algorithmen" | "Design" anglicism | "Entwurf variationaler Algorithmen" |

---

## 2. Guide Translations (172 files)

### 2.1 CRITICAL: Wrong Terminology -- "Fehlerkorrektur" vs. "Fehlerminderung"

In quantum computing, **error correction** (QEC) and **error mitigation** are fundamentally different concepts. Two files systematically use "Fehlerkorrektur" (error correction) when they mean "Fehlerminderung" (error mitigation):

- **`error-mitigation-and-suppression-techniques.mdx`**: ~15 instances (lines 2-4, 16, 35, 78, 125, 179, 208-209)
- **`directed-execution-model.mdx`**: ~10 instances (lines 14, 16, 20, 37, 64)

**Fix:** Replace all instances of "Fehlerkorrektur" with "Fehlerminderung" in these files.

### 2.2 Untranslated "Package versions" Headers (22 files)

The following files have `<summary><b>Package versions</b></summary>` instead of `<summary><b>Paketversionen</b></summary>`:

`DAG-representation.mdx`, `bit-ordering.mdx`, `construct-circuits.mdx`, `create-transpiler-plugin.mdx`, `custom-backend.mdx`, `fractional-gates.mdx`, `get-qpu-information.mdx`, `get-started-with-primitives.mdx`, `hello-world.mdx`, `interoperate-qiskit-qasm2.mdx`, `interoperate-qiskit-qasm3.mdx`, `qiskit-addons-obp-get-started.mdx`, `represent-quantum-computers.mdx`, `run-jobs-batch.mdx`, `run-jobs-session.mdx`, `save-jobs.mdx`, `set-optimization.mdx`, `simulate-with-qiskit-sdk-primitives.mdx`, `specify-runtime-options.mdx`, `synthesize-unitary-operators.mdx`, `transpiler-plugins.mdx`, `visualize-circuits.mdx`

14 of these also have untranslated boilerplate: "The code on this page was developed using the following requirements..."
**Fix:** "Der Code auf dieser Seite wurde mit den folgenden Anforderungen entwickelt. Wir empfehlen die Verwendung dieser oder neuerer Versionen."

### 2.3 Untranslated Admonition Titles (8+ files)

| Title | Files | Fix |
|-------|-------|-----|
| `title="Recommendations"` | DAG-representation, bit-ordering, construct-circuits, get-qpu-information, get-started-with-primitives, hello-world, initialize-account, visualize-circuits | `title="Empfehlungen"` |
| `title="Recommendation"` | create-transpiler-plugin | `title="Empfehlung"` |
| `title="Important"` | hello-world | `title="Wichtig"` |
| `title="Note"` / `title="Notes"` | create-transpiler-plugin, get-qpu-information, initialize-account | `title="Hinweis"` / `title="Hinweise"` |

### 2.4 Largely Untranslated Files

- **`guides/index.mdx`**: Title, sidebar_label, main heading, all Card titles and linkText values are English
- **`DAG-representation.mdx`** (lines 126-260): Multiple entire sections with untranslated English headings and paragraphs

### 2.5 du/Sie Inconsistency (4 files)

| File | Lines | Issue |
|------|-------|-------|
| `context-based-restrictions.mdx` | 3, 11, 15, 17 | Entire file uses formal "Sie" |
| `c-extension-for-python.mdx` | 101, 114 | "Geben Sie dann einfach..." in otherwise du-file |
| `circuit-library.mdx` | 63 | "Versuchen Sie" in tagLine |
| `calibration-jobs.mdx` | 62 | "Führen Sie Benchmarking..." |

### 2.6 Spelling Error

- **`algorithmiq-tem.mdx`** (line 80): "Messfehlermindung" → "Messfehlerminderung"

### 2.7 Formatting Issues

- **`access-instances-platform-apis.mdx`** (line 31): Stray period `.` on its own line
- **`qiskit-1.0-installation.mdx`** (line 290): Stray period `.` on its own line

---

## 3. Tutorial Translations (45 files)

### 3.1 Spelling Errors

| File | Line | Current | Fix |
|------|------|---------|-----|
| `ghz-spacetime-codes.mdx` | 2-3 | "Fehlerkennung" | "Fehler**er**kennung" (Fehler + Erkennung) |
| `krylov-quantum-diagonalization.mdx` | 31 | "Quanten-Eigenwertloeser" | "Quanten-Eigenwert**lö**ser" (missing umlaut) |
| `krylov-quantum-diagonalization.mdx` | 31 | "Aus diesen Gruenden" | "Aus diesen Gr**ü**nden" (missing umlaut) |
| `global-data-quantum-optimizer.mdx` | 86 | "handelfreie Tage" | "handel**s**freie Tage" (Fugen-s) |

### 3.2 Grammar Errors

| File | Line | Current | Issue | Fix |
|------|------|---------|-------|-----|
| `dc-hex-ising.mdx` | 18 | "folgendes unitäres Operator" | Wrong gender (Operator = masculine) | "folgenden unitären Operator" |
| `periodic-boundary-conditions...mdx` | 4 | "ein periodisches Kettenprobleme" | Singular/plural mismatch | "ein periodisches Kettenproblem" |
| `colibritd-pde.mdx` | 29 | "wie du die Funktion verwenden, um..." | Missing modal verb | "wie du die Funktion verwenden **kannst**, um..." |

### 3.3 du/Sie Inconsistency

- **`index.mdx`** (root): Uses formal "Sie" throughout (lines 48, 55, 69, 72, etc.) while all 44 tutorial files use informal "du"
- **Fix:** Convert root index.mdx to "du" form

### 3.4 Terminology Inconsistencies

| Term | Variants Found | Suggested Standard |
|------|---------------|-------------------|
| Circuit | "Circuit", "Schaltkreis", "Schaltung" | Pick one consistently |
| Error mitigation | "Fehlermitigation", "Fehlerminderung", "Fehlermilderung" | "Fehlerminderung" |
| Hamiltonian | "Hamiltonoperator", "Hamiltonian", "Hamilton-" | Standardize |
| Setup (heading) | "Setup", "Einrichtung" | Standardize |
| visualization (link) | "visualization", "Visualisierung" | "Visualisierung" |

### 3.5 Inconsistent "Grid" Translation

- `tutorials/index.mdx` line 125: "Grid-Stabilitäts-Workflow"
- `sml-classification.mdx` line 2: "Netzstabilitäts-Workflow"
- **Fix:** Standardize to "Netzstabilitäts-Workflow" ("Netz" is the correct German for power grid)

---

## 4. Learning/Course Translations (170 files)

### 4.1 CRITICAL: Repeated Spelling Error "fehlerotolerant"

8 occurrences across 2 files:
- **`threshold-theorem.mdx`** (lines 49, 57, 88): "fehlerotolerant"
- **`controlling-error-propagation.mdx`** (lines 140, 209, 219, 227, 239, 261): "fehlerotolerant"
- **Fix:** "fehler**t**olerant"

### 4.2 Untranslated `\text{and}` in LaTeX (11 occurrences)

- **`single-systems/classical-information.mdx`**: 6 occurrences (lines 57, 96, 130, 280, 446, 462)
- **`quantum-circuits/limitations-on-quantum-information.mdx`**: 4 occurrences (lines 73, 83, 132, 218)
- **`multiple-systems/qiskit-implementation.mdx`**: 1 occurrence (line 58)
- **Fix:** `\text{and}` → `\text{und}`

### 4.3 Untranslated Coin Ket Labels

- **`single-systems/classical-information.mdx`** (lines 123-136): `\vert\text{heads}\rangle`, `\vert\text{tails}\rangle`
- **Fix:** `\vert\text{Kopf}\rangle`, `\vert\text{Zahl}\rangle`

### 4.4 Untranslated Course Titles in learning/index.mdx

All 13 course titles on `learning/index.mdx` (lines 10-22) are in English. Should be translated to match the actual course overview pages.

### 4.5 Terminology Inconsistencies

| Term | Variants | Files | Fix |
|------|----------|-------|-----|
| Stabilizer/Stabilisator | "Stabilizer-Codes" vs. "Stabilisator-Code" | stabilizer-codes.mdx vs. repetition-code-revisited.mdx | Standardize |
| Quantum (prefix) | "Quantumdiagonalisierung" vs. "Quantendiagonalisierung" | sqd-overview.mdx, sqd-skqd.mdx | "Quanten-" (German prefix) |
| Overview | "Überblick" vs. "Übersicht" | Various index pages | Pick one |
| Lesson video | "Lektionsvideo" vs. "Lernvideo" | Most files vs. density-matrices/introduction.mdx | "Lektionsvideo" |

### 4.6 Untranslated Titles

| File | Line | Current | Fix |
|------|------|---------|-----|
| `sqd-overview.mdx` | 2-3, 15 | "Sample-based Quantum Diagonalization" | "Stichprobenbasierte Quantendiagonalisierung (SQD)" |
| `quantum-key-distribution.mdx` | 1-2, 14 | "Quantum Key Distribution" | "Quantenschlüsselverteilung" |

### 4.7 du/Sie Register Issue

- **`modules/computer-science/grovers.mdx`**: Entire file uses "Sie" (formal) -- ~15 instances across lines 3, 23, 25, 39, 46, 84-94, 125-131, 368-369, 426, 439, 461-462, 499-506, 540
- **`multiple-systems/quantum-information.mdx`** (line 180): Isolated "Beachten Sie" in otherwise du-file

---

## 5. Module Translations (15 files)

### 5.1 Potential Mathematical Errors (verify against English source)

- **`bells-inequality-with-qiskit.mdx`** (lines 366-370): Hadamard normalization uses `$\frac{1}{2}$` instead of `$\frac{1}{\sqrt{2}}$`
- **`bells-inequality-with-qiskit.mdx`** (line 273): Missing `/2` in `$\sin^2(\theta)$` -- should be `$\sin^2(\theta/2)$`

### 5.2 Spelling

- **`vqe.mdx`** (line 79): "Mehrelelektronenwellenfunktion" → "Mehrelektronenwellenfunktion" (extra "e")

### 5.3 Untranslated Link Text

| File | Line | Current | Fix |
|------|------|---------|-----|
| `quantum-key-distribution.mdx` | 24 | `[Install Qiskit]` | `[Qiskit installieren]` |
| `quantum-key-distribution.mdx` | 25 | `[Set up your IBM Cloud account]` | `[IBM Cloud-Konto einrichten]` |
| `superposition-with-qiskit.mdx` | 24-25 | Same as above | Same |

### 5.4 Awkward Phrasing

| File | Line | Current | Fix |
|------|------|---------|-----|
| `grovers.mdx` | 25 | "Dies ist eine gutgläubige Schätzung" | "Dies ist eine Schätzung nach bestem Wissen" |
| `grovers.mdx` | 48 | "auf hoher Ebene" | "grob zusammengefasst" or "im Überblick" |
| `grovers.mdx` | 62 | "Tor zum Verständnis" | "Einstieg in" |
| `index.mdx` (CS) | 13 | "zur Verfügung steht...zur Verfügung steht" | Remove repetition |

### 5.5 Formatting

- **`quantum-teleportation.mdx`** (line 42): IBMVideo `title=` attribute left in English

---

## 6. Cross-Cutting Issues

### 6.1 Project-Wide Terminology Standardization Needed

| English Term | Variants Found | Recommended German |
|-------------|---------------|-------------------|
| Error mitigation | Fehlerminderung, Fehlermitigation, Fehlermilderung, **Fehlerkorrektur** (WRONG) | **Fehlerminderung** |
| Error suppression | Fehlerunterdrückung, Fehlerdämpfung | **Fehlerunterdrückung** |
| Circuit | Circuit, Schaltkreis, Schaltung, Quantenschaltkreis | **Schaltkreis** (or keep "Circuit") |
| Hamiltonian | Hamiltonoperator, Hamiltonian, Hamilton- | Standardize to one |
| Stabilizer | Stabilizer, Stabilisator | Standardize to one |
| Setup (heading) | Setup, Einrichtung | Standardize to one |
| Overview | Überblick, Übersicht | Standardize to one |
| Error detection | Fehlererkennung, ~~Fehlerkennung~~ | **Fehlererkennung** |

### 6.2 du/Sie Summary

All files should use informal "du". Files still using "Sie":

| File | Scope |
|------|-------|
| `i18n/de/.../current/index.mdx` (root) | Entire file |
| `guides/context-based-restrictions.mdx` | Entire file |
| `modules/computer-science/grovers.mdx` | Entire file |
| `guides/c-extension-for-python.mdx` | 2 instances |
| `guides/circuit-library.mdx` | 1 instance |
| `guides/calibration-jobs.mdx` | 1 instance |
| `learning/.../quantum-information.mdx` | 1 instance |

### 6.3 Missing Umlauts (ASCII Digraphs)

| File | Current | Fix |
|------|---------|-----|
| `krylov-quantum-diagonalization.mdx` | "Eigenwertloeser" | "Eigenwertlöser" |
| `krylov-quantum-diagonalization.mdx` | "Gruenden" | "Gründen" |

---

## 7. Previously Known Issues (from _feedback.md)

Two files flagged as FAIL due to missing URLs:
1. `tutorials/multi-product-formula.mdx` -- missing `https://arxiv.org/abs/2407.17405`
2. `tutorials/probabilistic-error-amplification.mdx` -- missing `https://your.feedback.ibm.com/jfe/form/SV_9z7nltLeb5cX9Cm`

---

## Recommended Fix Priority

1. **P0 -- Critical terminology:** Fix "Fehlerkorrektur" → "Fehlerminderung" in 2 guide files (~25 instances)
2. **P0 -- Critical spelling:** Fix "fehlerotolerant" → "fehlertolerant" (8 instances), "Fehlerkennung" → "Fehlererkennung" (2 instances)
3. **P1 -- Register:** Convert 3 files from "Sie" to "du" (grovers.mdx, context-based-restrictions.mdx, root index.mdx)
4. **P1 -- Untranslated strings:** Translate ~80+ English strings in guide files (Package versions, Recommendations, etc.)
5. **P1 -- LaTeX:** Fix 11x `\text{and}` → `\text{und}` and coin ket labels
6. **P2 -- Grammar:** Fix ~7 grammar errors (gender, singular/plural, missing verbs)
7. **P2 -- Missing umlauts:** Fix 2 ASCII digraph substitutions
8. **P2 -- Terminology:** Establish and apply consistent terminology across all files
9. **P3 -- Style:** Fix awkward phrasing, anglicisms in JSON UI strings, minor inconsistencies
