# Full Linguistic Review of French Translations

**Date:** 2026-03-28
**Scope:** All 391 French translation files (4 JSON + 387 MDX)
**Reviewer:** Automated linguistic analysis

---

## Executive Summary

The overall quality of the French translations is **good to very good**. The prose is generally fluent, technically accurate, and reads naturally. However, the review uncovered several **critical issues** (files in the wrong language, missing accents, factual errors) alongside systematic inconsistencies that should be addressed.

**Key statistics:**
- Files reviewed: 391
- Critical issues: 13
- High-severity issues: ~25
- Medium-severity issues: ~40
- Low-severity/style issues: ~50+

---

## 1. CRITICAL Issues

These must be fixed immediately as they render content unusable or factually incorrect.

### 1.1 Files in Spanish Instead of French

| File | Description |
|------|-------------|
| `guides/primitive-input-output.mdx` | **Entire file** is in Spanish (e.g., "Entradas y salidas de las primitivas"). Every line of translatable text is Spanish. |
| `learning/courses/variational-algorithm-design/cost-functions.mdx` | **Entire file** is in Spanish (e.g., `title: "Funciones de costo"`, "En esta leccion aprenderemos..."). |

**Action:** Both files must be completely retranslated into French.

### 1.2 Files Missing ALL French Accents

| File | Description |
|------|-------------|
| `tutorials/error-mitigation-with-qiskit-functions.mdx` | Systematically missing every accent (e, e, a, u, etc.). Text is nearly unreadable in French. |
| `tutorials/depth-reduction-with-circuit-cutting.mdx` | Same issue -- all accents stripped. |
| `tutorials/spin-chain-vqe.mdx` | Same issue in frontmatter and early content. |

**Action:** Re-add all French accents throughout these files.

### 1.3 Large Untranslated English Sections

| File | Lines | Description |
|------|-------|-------------|
| `guides/qiskit-code-assistant-local.mdx` | 201-310 | ~110 lines of `<details>` sections completely in English |
| `guides/qiskit-1.0-features.mdx` | 115-126 | Full paragraph left in English |
| `learning/courses/quantum-chem-with-vqe/classical-optimizers.mdx` | 44-59 | ~15 lines explaining `minimize` function left in English |
| `learning/courses/quantum-machine-learning/introduction.mdx` | 281-295 | Full paragraph + Q&A section in English |

**Action:** Translate all untranslated sections.

### 1.4 Truncated/Incomplete File

| File | Description |
|------|-------------|
| `guides/qiskit-addons-sqd-get-started.mdx` | File ends at line 156 mid-content. Missing the SQD workflow, results, and next steps sections. |

**Action:** Complete the translation with the remaining content.

### 1.5 Factual/Mathematical Errors

| File | Line(s) | Error |
|------|---------|-------|
| `tutorials/chsh-inequality.mdx` | 231 | **Classical/quantum bounds inverted.** Text says outer lines = quantum bounds (+-2) and inner lines = classical bounds (+-2sqrt2). It's the opposite: classical = +-2, quantum (Tsirelson) = +-2sqrt2. |
| `learning/modules/quantum-mechanics/bells-inequality-with-qiskit.mdx` | 367-373 | **Hadamard gate coefficient wrong.** Shows 1/2 instead of 1/sqrt(2) for all three Hadamard expressions. |
| `learning/modules/quantum-mechanics/stern-gerlach-measurements-with-qiskit.mdx` | 918 | **S_z matrix wrong in summary table.** Shows identity matrix instead of Pauli-Z (missing the -1). |

**Action:** Fix all mathematical errors.

### 1.6 Wrong Metadata

| File | Line(s) | Error |
|------|---------|-------|
| `learning/courses/quantum-chem-with-vqe/classical-optimizers.mdx` | 1-3 | Title says "Geometrie moleculaire" but content is about "Optimiseurs classiques". Copy-paste error. |
| `learning/courses/quantum-machine-learning/introduction.mdx` | 25 | Video title describes quantum diagonalization but this is the QML introduction page. Wrong video description. |

**Action:** Fix metadata to match actual content.

---

## 2. HIGH-Severity Issues

### 2.1 Untranslated Text in Specific Locations

| File | Location | Issue |
|------|----------|-------|
| `guides/retired-qpus.mdx` | Lines 109-111 | Entire Admonition block in English |
| `guides/configure-error-suppression.mdx` | Line 77 | CodeAssistantAdmonition tagLine in English |
| `learning/courses/quantum-safe-cryptography/cryptographic-hash-functions.mdx` | Line 51 | `<en>Mathematical description</en>` tag with English content |
| `learning/courses/basics-of-quantum-information/index.mdx` | Lines 14-16 | Course name links in English instead of French |
| `learning/modules/` (8 files) | Various | "Qiskit in Classrooms" left in English |
| `learning/modules/computer-science/shors-algorithm.mdx` | Various | `GCD` should be `PGCD` (French abbreviation) |
| `learning/modules/computer-science/deutsch-jozsa.mdx` | 287-308 | `\text{if}` in LaTeX should be `\text{si}` |
| `guides/cloud-setup.mdx` | Line 54 | Admonition title "Recommendations" in English (should be "Recommandations") |
| `guides/serverless-run-first-workload.mdx` | Line 205 | Same: "Recommendations" instead of "Recommandations" |

### 2.2 Semantic/Translation Errors

| File | Line | Issue |
|------|------|-------|
| `guides/get-started-with-primitives.mdx` | 181 | Sampler section says "calculer la valeur d'esperance" (copied from Estimator). Sampler samples, it doesn't compute expectation values. |
| `guides/serverless-port-code.mdx` | 165 | Garbled phrase: "le calcul quantique centre sur les quantum" -- meaningless text |
| `guides/qunova-chemistry.mdx` | 135 | "interrupteur" is a mistranslation (should be "consecutif" or similar) |
| `guides/colibritd-pde.mdx` | 51 | Possible swap of u (displacement) and sigma (stress) definitions |
| `guides/multiverse-computing-singularity.mdx` | 667 | English word "Importantly" left untranslated mid-sentence |
| `guides/plans-overview.mdx` | 59 | "algorithmes et applications quantiques classiques" -- contradictory |
| `guides/qasm-feature-table.mdx` | 138 | "evaluera eagerly" -- English word "eagerly" not translated |
| `learning/courses/quantum-diagonalization-algorithms/sqd-implementation.mdx` | 37 | Spanish verb "transpilar" instead of French "transpiler" |

### 2.3 Typos and Code Errors

| File | Line | Issue |
|------|------|-------|
| `guides/instances.mdx` | 39 | `QiskitRuntimeServicee` -- double "e" typo |
| `guides/transpiler-stages.mdx` | 62 | `optimzation_level=1` -- missing "i" in "optimization" |
| `guides/transpiler-stages.mdx` | 62 | `[0,1,1,3]` -- should be `[0,1,2,3]` |
| `guides/qiskit-addons-aqc.mdx` | 39 | `git clone git clone` -- duplicated command |
| `guides/qiskit-addons-aqc.mdx` | 62 | `generated_ansatz_from_circuit()` -- should be `generate_ansatz_from_circuit()` |
| `tutorials/nishimori-phase-transition.mdx` | 53 | `<YOUR_API_KEYN>` -- typo, should be `<YOUR_API_KEY>` |
| `learning/courses/quantum-diagonalization-algorithms/sqd-implementation.mdx` | 365 | "Nomons-les" -- should be "Nommons-les" |
| `learning/courses/general-formulation-of-quantum-information/quantum-channels/representations-of-channels.mdx` | 28 | "Gran partie" -- should be "Grande partie" |

### 2.4 Broken/Incorrect Links

| File | Line | Issue |
|------|------|-------|
| `guides/interoperate-qiskit-qasm2.mdx` | 250 | Link points to `qasm3#loads` instead of `qasm2#loads` |
| `guides/custom-backend.mdx` | 64 | Text says "CXGates" but link points to `ECRGate` |
| `guides/simulate-stabilizer-circuits.mdx` | 166 | Links to SDK primitives instead of Qiskit Aer page |
| `guides/simulate-with-qiskit-sdk-primitives.mdx` | 32 | Links to stabilizer circuits instead of Qiskit Aer page |
| `guides/dynamical-decoupling-pass-manager.mdx` | 158 | URL uses wrong domain `quantum-computing.ibm.com` |
| `guides/transpile.mdx` | 65 | Same wrong domain in URL |
| `guides/transpiler-stages.mdx` | 278 | Same wrong domain in URL |

### 2.5 Grammar Errors

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `guides/v2-primitives.mdx` | 376 | "qui a prouve donnant des resultats" | "qui s'est averee donner des resultats" |
| `guides/function-template-hamiltonian-simulation.mdx` | 147 | "retour un message d'erreur" | "retourne un message d'erreur" |
| `guides/composer.mdx` | 155 | "Passes ta souris" (imperative -er verb with erroneous -s) | "Passe ta souris" |
| `guides/composer.mdx` | 155 | "places-le" | "place-le" |
| `guides/repetition-rate-execution.mdx` | 34 | "tu soumet" | "tu soumets" |
| `guides/secure-data.mdx` | 24 | "apres que tu aies cesse" (subjunctive) | "apres que tu as cesse" (indicative) |
| `guides/qiskit-1.0-features.mdx` | 177 | "Les methodes de Circuit suivants" | "suivantes" (feminine agreement) |
| `guides/qiskit-1.0-features.mdx` | 287-290 | "primitifs" | "primitives" (feminine) |
| `guides/tools-intro.mdx` | 133 | "methode iterative preconditionne" | "preconditionnee" (feminine agreement) |

---

## 3. MEDIUM-Severity Issues — Systematic Inconsistencies

### 3.1 Terminology Inconsistencies Across Files

| English Term | Variants Found | Recommended |
|-------------|---------------|-------------|
| gate (quantum) | "gate", "Gate", "Gates", "porte", "portes" | **"porte(s)"** (standard French) |
| error mitigation | "mitigation", "attenuation" | **"attenuation"** (proper French) |
| expectation value | "valeur d'expectation", "valeur d'esperance", "valeur attendue", "valeur d'attente" | **"valeur d'esperance"** |
| fault-tolerant | "tolerant aux fautes", "tolerant aux pannes" | **"tolerant aux fautes"** (standardize) |
| packages (software) | "paquets", "packages" | **"packages"** (majority usage) |
| transpiler | "transpiler", "transpileur", "transpilateur" | **"transpileur"** (standardize) |
| jobs | "jobs", "travaux", "taches", "emplois" | **"jobs"** (widely accepted in French IT) |
| overlap (quantum) | "chevauchement", "recouvrement" | **"recouvrement"** (physics standard) |
| instructors | "instructeurs", "enseignants" | **"enseignants"** (proper French) |
| notebook | "notebook", "carnet", "cahier de travail" | **"notebook"** (standard in computing) |
| from scratch | "de zero", "a partir de zero" | **"a partir de zero"** |

### 3.2 Capitalization Issues

Many files incorrectly capitalize common nouns mid-sentence, following English convention:

| Term | Files affected | Fix |
|------|---------------|-----|
| "Circuit" -> "circuit" | quick-start, ai-transpiler-passes, qunova-chemistry, visualize-results, intro-to-patterns, configure-qiskit-local, running-quantum-circuits, utility-scale-qaoa, vqe, etc. | Lowercase |
| "Qubit(s)" -> "qubit(s)" | quick-start, intro-to-patterns, qiskit-transpiler-service, visualize-results, etc. | Lowercase |
| "Gate(s)" -> "porte(s)" | intro-to-patterns, quick-start, bit-ordering, build-noise-models, qft, etc. | Translate + lowercase |
| "Batch" -> "batch" | intro-to-patterns | Lowercase |
| "Session" -> "session" | intro-to-patterns | Lowercase |

### 3.3 Register Inconsistency (tu vs. vous)

The project predominantly uses informal "tu" (tutoiement), but several files mix registers:

| File | Issue |
|------|-------|
| `guides/composer.mdx` | "Notez" (vous) mixed with "tu" form |
| `guides/function-template-chemistry-workflow.mdx` | "Notez" (vous) at lines 46, 65, 110 mixed with "tu" |
| `tutorials/hello-world.mdx` | Mixed tu/vous within same file |
| `tutorials/repetition-codes.mdx` | "tu dois" then "Executez la version" |
| `learning/courses/quantum-computing-in-practice/running-quantum-circuits.mdx` | Sudden switch to "vous" at line 51 |
| `learning/courses/quantum-chem-with-vqe/ansatz.mdx` | "Notez" at line 83 |

**Recommendation:** Standardize to "tu" throughout (the dominant style), or switch to "vous" for professional tone.

### 3.4 Untranslated `\text{}` in LaTeX Formulas

~30+ occurrences across the learning courses where English words inside `\text{}` LaTeX commands were not translated:

| Pattern | Count | Fix |
|---------|-------|-----|
| `\text{and}` | ~20+ | `\text{et}` |
| `\text{outcome is $k$}` | ~5 | `\text{le resultat est $k$}` |
| `\text{probability of being in state ...}` | 4 | `\text{probabilite d'etre dans l'etat ...}` |
| `\text{win}` / `\text{lose}` | 2 | `\text{victoire}` / `\text{defaite}` |
| `\text{if}` | 2 | `\text{si}` |
| `\text{function}` / `\text{string}` | 2 | `\text{fonction}` / `\text{chaine}` |

### 3.5 Untranslated Video Titles (IBMVideo `title` attributes)

Several learning course files have IBMVideo component `title` attributes left in English:

- `learning/courses/quantum-computing-in-practice/applications-of-qc.mdx`
- `learning/courses/quantum-computing-in-practice/running-quantum-circuits.mdx`
- `learning/courses/quantum-business-foundations/quantum-computing-fundamentals.mdx`
- `learning/courses/quantum-business-foundations/quantum-technology.mdx` (2 videos)
- `learning/courses/integrating-quantum-and-high-performance-computing/introduction.mdx`

### 3.6 Untranslated Image Alt Text

Several files in `learning/courses/quantum-business-foundations/` have English alt text on images (e.g., "IBM Quantum data center in Poughkeepsie", "IBM Quantum Osprey processor").

---

## 4. LOW-Severity / Style Issues

### 4.1 Anglicisms (acceptable but noted)

| Term | Better French | Context |
|------|--------------|---------|
| "mappons" | "associons" | considerations-set-up-runtime.mdx |
| "mappe" | "associe a" | specify-observables-pauli.mdx |
| "scalabilite" | "extensibilite" | sqd-overview.mdx |
| "reporting" | "etablissement de rapports" | multiple index.mdx files |
| "benchmarker" | "evaluer" | edc-cut-bell-pair-benchmarking.mdx |
| "labeliserons" | "etiquetterons" | exploring-uncertainty-with-qiskit.mdx |
| "pre-packages" | "pre-configures" | tutorials/index.mdx |
| "Grand Modele de Langage" | "grand modele de langage" (no caps) | qiskit-code-assistant.mdx |

### 4.2 Minor Formatting Issues

| File | Issue |
|------|-------|
| `guides/access-instances-platform-apis.mdx` line 31 | Stray period on its own line |
| `guides/qiskit-addons-obp.mdx` line 32 | Stray underscore after code block |
| `guides/specify-runtime-options.mdx` lines 209, 221 | Incorrect list numbering (duplicate numbers) |
| `learning/courses/quantum-safe-cryptography/quantum-safe-cryptography.mdx` line 30 | Stray backtick |
| `guides/represent-quantum-computers.mdx` lines 33-56 | Duplicated paragraph |
| `guides/global-data-quantum-optimizer.mdx` line 437 | "4 pas, 4 pas" duplicated text |

### 4.3 Inclusive Writing Inconsistency

Only 3 module files use inclusive writing ("etudiant-e-s"), while all others use masculine plural. Should be standardized.

### 4.4 "enquete" vs "sondage" for Survey

Exam/index files alternate between "enquete de fin de cours" and "sondage post-cours". Should pick one.

---

## 5. JSON Configuration Files Review

### 5.1 `code.json` (1053 lines)
- Overall excellent quality
- No significant issues found
- All UI strings properly translated

### 5.2 `current.json` (406 lines)
- Line 403: `"Home"` left untranslated (while line 399 correctly uses `"Accueil"`)
- "Algorithmes tolerants aux pannes" -- uses "pannes" while other files use "fautes"

### 5.3 `navbar.json` (42 lines)
- Line 35: `"Settings"` left untranslated (should be "Parametres")
- No other issues

### 5.4 `footer.json` (58 lines)
- Line 47: `"Settings"` left untranslated
- Line 52: `"GitHub"` left as-is (acceptable -- brand name)
- No other issues

---

## 6. Recommendations

### Immediate Priorities
1. **Retranslate** the 2 Spanish files into French
2. **Re-add accents** to the 3 accent-stripped tutorial files
3. **Fix** the 3 mathematical/factual errors
4. **Complete** the truncated `qiskit-addons-sqd-get-started.mdx`
5. **Translate** all untranslated English sections

### Short-term Improvements
6. **Standardize terminology** using the recommended terms in section 3.1
7. **Fix capitalization** of common nouns (circuit, qubit, porte)
8. **Harmonize register** (tu vs. vous) across all files
9. **Fix** all broken/incorrect links
10. **Translate** LaTeX `\text{}` content and video titles

### Style Guide Recommendations
11. Create a French translation glossary to ensure terminology consistency
12. Decide on tu vs. vous and document the choice
13. Decide on inclusive writing policy
14. Document which English terms are acceptable as loanwords (e.g., "backend", "job", "notebook")
