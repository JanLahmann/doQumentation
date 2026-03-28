# Italian Translation Linguistic Review

**Date**: 2026-03-28
**Scope**: Full review of all 392 Italian translation files (`i18n/it/`)
**Reviewer**: Automated linguistic analysis

---

## Executive Summary

The Italian translations are generally of **good quality** -- the prose reads naturally in most cases, technical content is accurately conveyed, and mathematical notation is preserved correctly. However, several **systematic issues** affect consistency and polish across the entire translation corpus.

### Top Issues by Impact

| Priority | Issue | Scope | Est. Occurrences |
|----------|-------|-------|-----------------|
| **P0** | Register inconsistency (tu/Lei/voi mixing) | All file types | 100+ |
| **P0** | "Circuit" left as capitalized English noun | Guides, tutorials, learning | 150+ |
| **P1** | Untranslated section headings ("Background", "Setup") | Tutorials | ~20 files |
| **P1** | Untranslated text in LaTeX math (`\text{and}`, `\text{outcome is}`) | Learning courses | 30+ |
| **P1** | "Gate"/"Qubit" inconsistently capitalized | All MDX files | 50+ |
| **P2** | Untranslated UI labels ("Settings", card titles) | JSON, index.mdx | ~15 |
| **P2** | Terminology inconsistency ("Passi successivi" vs "Prossimi passi") | Guides | ~10 |
| **P3** | Untranslated image alt text and video titles | Learning courses | 20+ |

---

## 1. CRITICAL: Register Inconsistency (tu / Lei / voi)

The translations inconsistently mix three registers:
- **Informal singular (tu)**: "clicca", "hai", "tuo", "assicurati"
- **Formal singular (Lei)**: "Inserisca", "Salvi", "il suo", "Scelga"
- **Formal plural (voi)**: "Costruite", "avete", "assicuratevi", "vostro"

### Where it occurs

- **code.json**: Mixes tu and Lei throughout (~30 strings affected)
- **index.mdx (homepage)**: Same sentence switches register (line 155: "Usa Docker invece? Sostituisca semplicemente")
- **Tutorials**: Different files use different registers; some switch mid-file (e.g., `chsh-inequality.mdx` starts with tu, switches to voi at line 88; `repetition-codes.mdx` starts tu, switches to voi at line 54)
- **Learning courses**: Mostly use tu (appropriate), with occasional Lei/voi

### Recommendation
Standardize on **informal tu** for UI and tutorials (industry standard for Italian software). Use **impersonal si** constructions for formal documentation sections.

---

## 2. CRITICAL: "Circuit" Left as English Word

The English word "Circuit" (capitalized) appears in Italian prose where "circuito" (singular) or "circuiti" (plural) should be used. This is the most pervasive translation omission.

### Examples

| File | Line | Current | Should be |
|------|------|---------|-----------|
| `guides/build-noise-models.mdx` | 34 | `simulare Circuit quantistici` | `simulare circuiti quantistici` |
| `guides/choose-execution-mode.mdx` | 67 | `Costruire un Circuit` | `Costruire un circuito` |
| `learning/.../qiskit-implementation.mdx` | 297 | `Un'anteprima dei Circuit quantistici` | `Un'anteprima dei circuiti quantistici` |
| `learning/.../circuits.mdx` | 2-3 | `title: "Circuit"` | `title: "Circuiti"` |
| `learning/.../utility-i.mdx` | 27+ | `un Circuit su scala utility` | `un circuito su scala utility` |
| `guides/create-transpiler-plugin.mdx` | 38-39 | `la descrizione di un Circuit quantistico` | `la descrizione di un circuito quantistico` |

Affects 15+ files with 150+ total occurrences.

---

## 3. HIGH: "Gate" and "Qubit" Capitalization

"Gate" and "Qubit" are used as capitalized English nouns inconsistently. Italian convention keeps them as lowercase loanwords.

| Term | Current (inconsistent) | Correct |
|------|----------------------|---------|
| Gate | `errori di Gate CPTP`, `un Gate a singolo Qubit` | `errori di gate CPTP`, `un gate a singolo qubit` |
| Qubit | `sono Qubit`, `due Qubit`, `a 127 Qubit` | `sono qubit`, `due qubit`, `a 127 qubit` |

Some files already use lowercase correctly, creating inconsistency within the corpus.

---

## 4. HIGH: Untranslated Section Headings

~20 tutorial files leave "Background" and "Setup" headings in English, while other files correctly translate them.

| English | Used in some files | Should be (per established convention) |
|---------|-------------------|---------------------------------------|
| Background | Left as `## Background` | `## Contesto` |
| Setup | Left as `## Setup` | `## Configurazione` |
| Next steps | `## Prossimi passi` or `## Passi successivi` | Standardize to one |

---

## 5. HIGH: Untranslated Text in LaTeX Math

English text within `\text{}` blocks in math formulas is not translated:

| Pattern | Count | Fix |
|---------|-------|-----|
| `\text{and}` | ~20 occurrences in 8 files | `\text{e}` |
| `\text{outcome is 0}` | ~10 occurrences in 3 files | `\text{il risultato \`e 0}` |
| `\text{probability of being in the state 00}` | 4 occurrences in 1 file | `\text{probabilit\`a di trovarsi nello stato 00}` |

---

## 6. MEDIUM: Untranslated UI Strings

| File | Key/Line | Current | Fix |
|------|----------|---------|-----|
| `navbar.json` | line 35 | `"Settings"` | `"Impostazioni"` |
| `footer.json` | line 47 | `"Settings"` | `"Impostazioni"` |
| `current.json` | line 99 | `"Circuit Functions"` | `"Funzioni di circuito"` |
| `current.json` | line 103 | `"Application Functions"` | `"Funzioni applicative"` |
| `current.json` | line 143 | `"Primitives"` | `"Primitive"` |
| `current.json` | line 191 | `"Circuit Cutting (CC)"` | `"Taglio dei circuiti (CC)"` |
| `current.json` | line 403 | `"Home"` | `"Pagina iniziale"` |
| `guides/index.mdx` | 24-88 | Card titles in English | Translate all card titles |

---

## 7. MEDIUM: Grammar and Spelling Errors

### Grammar

| File | Line | Error | Fix |
|------|------|-------|-----|
| `learning/.../introduction.mdx` | 79 | `Nella studio dell'informazione` | `Nello studio` (masculine article) |
| `quantum-safe-cryptography/index.mdx` | 16 | `i sviluppatori` | `gli sviluppatori` (s+consonant rule) |
| `tutorials/shors-algorithm.mdx` | 405 | `traspiamo il circuito` | `traspiliamo il circuito` |
| `code.json` | 263 | `hai lasciato` (tu) in Lei context | `ha lasciato` or standardize register |
| `code.json` | 744 | `l'ha collegata` (feminine default) | `l'ha collegato` (masculine default) |
| `current.json` | 319 | `il calcolo quantistico e ad alte prestazioni` | `il calcolo quantistico e il calcolo ad alte prestazioni` |

### Spelling/Typos

| File | Line | Error | Fix |
|------|------|-------|-----|
| `guides/create-a-provider.mdx` | 28 | `from qsikit.providers` | `from qiskit.providers` |
| `guides/create-a-provider.mdx` | 55 | `BackendSampleV2` | `BackendSamplerV2` |
| `guides/cloud-setup-rest-api.mdx` | 53 | `urlendcoded` | `urlencoded` |
| `learning/.../utility-i.mdx` | 258 | `traspiiliamo` (double i) | `traspiliamo` |

---

## 8. MEDIUM: Mistranslations and Wrong Content

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `tutorials/chsh-inequality.mdx` | 231 | Quantum/classical limits swapped: text says quantum=$\pm 2$ and classical=$\pm 2\sqrt{2}$ | Swap: quantum=$\pm 2\sqrt{2}$, classical=$\pm 2$ |
| `tutorials/probabilistic-error-amplification.mdx` | 1 | "scala industriale" for "utility-scale" | "scala di utilita" |
| `learning/.../exam.mdx` | 2-19 | Course name "Fondamenti" vs "Basi" | Standardize to "Basi dell'informazione quantistica" |
| `learning/.../classical-optimizers.mdx` | 2-3 | Title metadata says "Geometria molecolare" for a file about classical optimizers | `title: "Ottimizzatori classici"` |
| `learning/.../qiskit-implementation.mdx` | 260 | `array_from_latex` (doesn't exist) | `array_to_latex` |

---

## 9. MEDIUM: Untranslated Content Blocks

| File | Lines | Issue |
|------|-------|-------|
| `learning/.../classical-optimizers.mdx` | 44-51 | Entire paragraph with 5 bullet points left in English |
| `guides/create-transpiler-plugin.mdx` | 27-33 | "Package versions" block in English |
| `guides/custom-backend.mdx` | 33-41 | "Package versions" block in English |
| `guides/build-noise-models.mdx` | 23 | "Package versions" header in English |

---

## 10. LOW: Style and Naturalness Issues

| File | Line | Current | Suggested |
|------|------|---------|-----------|
| `code.json` | 179 | "Suggerimenti azionabili" | "Suggerimenti pratici" (calque from "actionable") |
| `code.json` | 724 | "andata in crash" | "ha smesso di funzionare" |
| `code.json` | 314 | "Fallback su IBM Video" | "Alternativa con IBM Video" |
| `index.mdx` | 84 | "Introduzione propria di doQumentation" | "L'introduzione di doQumentation" |
| `index.mdx` | 78, 83, 98 | English-style title case in Italian | Use sentence case per Italian convention |
| `tutorials/shors-algorithm.mdx` | 352 | "ha risultato in" | "ha prodotto" (calque from "resulted in") |
| `tutorials/shors-algorithm.mdx` | 534 | "Ci rivolgiamo a" | "Utilizziamo" (calque from "we turn to") |
| `learning/.../introduction.mdx` | 20 | "pietre fondanti" | "pietre miliari" or "pilastri fondamentali" |

---

## 11. LOW: Inconsistent Terminology

| Term | Variant A | Variant B | Recommendation |
|------|-----------|-----------|----------------|
| Next steps | "Passi successivi" | "Prossimi passi" | Standardize to "Passi successivi" |
| Recommendations | "Raccomandazioni" | "Suggerimenti" / "Consigli" | Standardize to "Raccomandazioni" |
| gates (Italian) | "gate" (loanword) | "porte/porta" | Standardize to "gate" |
| transpiler | "transpiler" | "transpilatore" | Standardize to "transpiler" |
| primitive | "il primitivo" | "la primitiva" | Standardize to "la primitiva" (feminine) |

---

## 12. LOW: Punctuation and Formatting

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `code.json` | 391 | "es.," (comma after period) | "es." or "ad es." |
| `guides/access-instances-platform-apis.mdx` | 31 | Stray period on its own line | Move to end of previous line |
| `guides/configure-error-mitigation.mdx` | 64 | Table row missing closing `\|` | Add `\|` at end |
| `learning/.../utility-iii.mdx` | 19 | `[Scarica il pdf]` | `[Scarica il PDF]` |
| `learning/.../bits-gates-and-circuits.mdx` | 4 | Description starts lowercase | Capitalize first letter |

---

## Files With No Issues Found

The majority of MDX files across all sections had no significant issues beyond the systematic ones (Circuit/Gate/Qubit capitalization, register). The prose quality is consistently good, demonstrating competent human translation work.

---

## Recommended Fix Order

1. **Automated find-replace**: Fix "Circuit"/"Gate"/"Qubit" capitalization across all files
2. **Register standardization**: Convert all Lei/voi forms to tu in tutorials and UI strings
3. **Untranslated headings**: Translate "Background" -> "Contesto", "Setup" -> "Configurazione"
4. **Critical errors**: Fix grammar errors, typos, mistranslations, and wrong metadata
5. **LaTeX text**: Translate English text within `\text{}` blocks
6. **UI strings**: Translate remaining English in JSON config files
7. **Style polish**: Address calques, awkward phrasing, and terminology consistency
