# Register Fix Prompt — doQumentation

Converts formal register to informal in existing translations using Claude Code CLI with parallel Sonnet agents.

The underlying translations are good quality (Sonnet-generated) — only the register (formal pronouns, verb conjugations, possessives) needs changing. Code blocks, LaTeX, JSX, URLs, images, and heading anchors stay untouched.

**Model**: Sonnet (always — via `model: "sonnet"` in Agent calls)
**Batch size**: 1 file per agent
**Parallelism**: 3 agents per round

---

## Prompt Templates

Paste one of these into Claude Code:

```
Read translation/register-fix-prompt.md. Fix the register for all German (de) FAIL files.
```

```
Read translation/register-fix-prompt.md. Fix the register for all French (fr) FAIL files.
```

```
Read translation/register-fix-prompt.md. Fix the register for these files: de/guides/install-qiskit.mdx, de/guides/configure-error-handling.mdx
```

---

## How to Launch Register Fix Agents

Launch **one agent per file**, up to **3 agents in parallel** per round. Use `model: "sonnet"` and `subagent_type: "general-purpose"` for each agent.

**Large files (>400 lines)**: The orchestrator handles chunking — see "Large File Chunking" section below.

Each agent gets this prompt (with variables filled in):

```
You are a {LANGUAGE} register correction specialist for doQumentation (Docusaurus site for Qiskit quantum computing tutorials).

Fix the register in this translated MDX file from {FROM_REGISTER} to {TO_REGISTER}:

File: i18n/{LOCALE}/docusaurus-plugin-content-docs/current/{file}

1. Read the file using the Read tool
2. Convert ALL formal register to informal following the rules below
3. Write the corrected file back to the SAME path using the Write tool (in-place fix)

Register conversion rules for {LANGUAGE}:
{REGISTER_RULES}

Preservation rules (CRITICAL — do NOT modify any of these):
- ALL code blocks (```python, ```bash, ```text, etc.) — leave completely unchanged
- ALL math/LaTeX ($...$, $$...$$) — leave completely unchanged
- ALL JSX/HTML tags, imports, and attributes — leave completely unchanged
- ALL URLs, links, and image paths — leave completely unchanged
- ALL inline code backticks (e.g., `Statevector`, `QuantumCircuit`) — leave completely unchanged
- ALL heading anchors ({#english-anchor}) — leave completely unchanged
- Frontmatter keys — leave unchanged. DO fix register in frontmatter VALUES (title, description, sidebar_label)
- Source hash comment ({/* doqumentation-source-hash: XXXX */}) — leave completely unchanged

What to change:
- Prose paragraphs: pronouns, verb conjugations, possessives
- List items: same as paragraphs
- Admonition text content (inside <Admonition> tags)
- Display text in HTML attributes: title="...", text inside <summary>/<details>/<b>
- Frontmatter values: title, description, sidebar_label

Important:
- Do NOT rephrase, reword, or re-translate anything beyond the register change
- Do NOT add or remove content
- Do NOT change the sentence structure unless the register change requires it (e.g., German "Verwenden Sie" → "Verwende" drops the pronoun naturally)
- Maintain the same line count — do not add or remove blank lines
```

---

## Large File Chunking (>400 lines) — Orchestrator Responsibility

Same approach as `translation-prompt.md`:

1. Read the source file and count lines
2. If ≤400 lines → assign to a single agent
3. If >400 lines → split into chunks:
   a. Identify section boundaries (`## Heading`)
   b. Split into ~400-line chunks at section boundaries (500 upper limit)
   c. Launch one agent per chunk, each with modified prompt:
      - "Fix the register in this **chunk** of `{file}` (lines {start}–{end})"
      - Agent reads the full file but modifies only its assigned line range
      - First chunk includes frontmatter; subsequent chunks start at section heading
      - Each agent writes its chunk to `/tmp/{filename}-part{N}.mdx`
   d. Orchestrator concatenates temp files with blank line between chunks
   e. Write final result back to `i18n/{LOCALE}/.../current/{file}`

4. **Verify integrity**: heading count unchanged, code block count unchanged, LaTeX count unchanged, total line count similar (±2 lines)

---

## Language-Specific Register Rules

### German (de) — 64 files

```
Convert formal "Sie" register to informal "du" throughout:

Pronouns:
- Sie → du (subject)
- Ihnen → dir (dative)
- Ihr/Ihre/Ihren/Ihrem/Ihrer → dein/deine/deinen/deinem/deiner (possessive)

Verb conjugations (Sie-form → du-form):
- haben → hast, sind → bist, können → kannst, werden → wirst
- müssen → musst, sollen → sollst, wollen → willst, dürfen → darfst
- Verwenden Sie → Verwende, Führen Sie aus → Führe aus
- Beachten Sie → Beachte, Stellen Sie sicher → Stelle sicher
- Installieren Sie → Installiere, Erstellen Sie → Erstelle
- Überprüfen Sie → Überprüfe, Konfigurieren Sie → Konfiguriere

Common patterns:
- "Bitte beachten Sie" → "Beachte bitte"
- "wenn Sie ... möchten" → "wenn du ... möchtest"
- "damit Sie ... können" → "damit du ... kannst"
- "Benutzer" (formal context) → OK to keep (it's gender-neutral, not register-specific)

IMPORTANT: German "Sie" (formal you) vs "sie" (she/they) — only change capitalized "Sie" in direct address context. Do NOT change lowercase "sie" (she/they).
```

### French (fr) — 36 files

```
Convert formal "vous" register to informal "tu" throughout:

Pronouns:
- vous → tu (subject), te/t' (object)
- votre/vos → ton/ta/tes (possessive)
- vous-même → toi-même

Verb conjugations (vous-form → tu-form):
- avez → as, êtes → es, pouvez → peux, devez → dois
- allez → vas, voulez → veux, savez → sais, faites → fais
- Consultez → Consulte, Utilisez → Utilise
- Exécutez → Exécute, Configurez → Configure
- Vérifiez → Vérifie, Assurez-vous → Assure-toi

Common patterns:
- "veuillez" → drop entirely (overly formal, just use imperative)
- "si vous souhaitez" → "si tu souhaites"
- "pour que vous puissiez" → "pour que tu puisses"
- "n'hésitez pas" → "n'hésite pas"

IMPORTANT: "vous" as plural (addressing multiple people) should stay as "vous". Context: these are tutorials addressing one learner, so virtually all "vous" is formal-singular → "tu".
```

### Spanish (es) — 35 files

```
Convert formal "usted" register to informal "tú" throughout:

Pronouns:
- usted → tú (often dropped in Spanish)
- su/sus (formal possessive) → tu/tus
- le (formal object) → te

Verb conjugations (usted-form → tú-form):
- tiene → tienes, puede → puedes, debe → debes
- ha → has, es → eres (when addressing reader), va → vas
- Consulte → Consulta, Ejecute → Ejecuta
- Configure → Configura, Verifique → Verifica
- Utilice → Utiliza/Usa, Ingrese → Ingresa
- Seleccione → Selecciona, Asegúrese → Asegúrate

Common patterns:
- "puede usted" → "puedes"
- "si desea" → "si deseas"
- "para que pueda" → "para que puedas"
- "asegúrese de que" → "asegúrate de que"

Note: Some ES guides (Gemini-translated) may already use tú — check before changing. Only fix formal instances.
```

### Ukrainian (uk) — 18 files

```
Convert formal "Ви" register to informal "ти" throughout:

Pronouns:
- Ви → ти (subject)
- Вас → тебе (accusative/genitive)
- Вам → тобі (dative)
- Вами → тобою (instrumental)
- Ваш/Ваша/Ваше/Ваші → твій/твоя/твоє/твої (possessive)

Verb conjugations (Ви-form → ти-form):
- маєте → маєш, можете → можеш, повинні (Ви) → повинен/повинна (ти)
- хочете → хочеш, знаєте → знаєш, бачите → бачиш
- Використовуйте → Використовуй, Запустіть → Запусти
- Переконайтеся → Переконайся, Встановіть → Встанови

IMPORTANT: Capital "Ви/Ваш" is always formal. Lowercase "ви/ваш" could be plural — only change capitalized forms.
```

### Italian (it) — 17 files

```
Convert formal "Lei/voi" register to informal "tu" throughout:

Pronouns:
- Lei → tu (subject), voi → tu (if addressing reader)
- Suo/Sua → tuo/tua (possessive)
- Le (formal object) → ti

Verb conjugations:
- For Lei-form: consulti → consulta, utilizzi → utilizza, verifichi → verifica
- For voi-form: avete → hai, potete → puoi, dovete → devi
- Assicuratevi → Assicurati, Consultate → Consulta
- Verificate → Verifica, Utilizzate → Utilizza, Eseguite → Esegui

Common patterns:
- "se desidera" → "se desideri"
- "è possibile" → OK to keep (impersonal, not register-specific)
```

### Swabian (swg) — 10 files

```
Convert formal Swabian "Se" register to informal:

- "Se" (Swabian formal) → drop pronoun, use du-form verb
- "Nemmet Se" → "Nimm" (Swabian informal imperative)
- "Fange Se" → "Fang"
- "Verwende Se" → "Verwend"
- "Ihre/Ihrem" → "dei/deim" (Swabian possessive)

Maintain Swabian dialect features (schwäbisch vocabulary, pronunciation spellings) — only change register.
```

### Badisch (bad) — 7 files

```
Convert formal Badisch "Sie/Se" register to informal:

- "Sie" / "Se" → drop pronoun, use du-form
- "Nutze Sie" → "Nutz"
- "Fange Sie" → "Fang"
- "luege Se" → "lueg"
- "Stelle Se sicher" → "Stell sicher"
- "Ihri" → "dini" (Badisch possessive)

Maintain Badisch dialect features — only change register.
```

### Saxon (sax) — 3 files

```
Convert formal Saxon "Se" register to informal "de":

- "Se" → "de" (Saxon informal you) or drop pronoun
- Verbs: Se-conjugation → de-conjugation
- "Ihre/Ihrem" → "dei/deim" (Saxon possessive)

Maintain Saxon dialect features (sächsisch vocabulary) — only change register.
```

### Austrian (aut) — 1 file

```
Convert formal Austrian "S'/Sie" register to informal "du":

- "S'" / "Sie" → "du" or drop pronoun
- "Ihre/Ihrem" → "dein/deinem"
- Verbs: Sie-conjugation → du-conjugation (standard Austrian informal)

Only 1 file: tutorials/chsh-inequality.mdx
```

---

## Autonomous Workflow

When NO explicit file list is given, discover files to fix:

### Step 1: Discover FAIL files

```bash
python translation/scripts/get-register-fails.py [--locale XX]
```

This reads `translation/status.json` and lists all files with `review: "FAIL"` grouped by locale.

**Skip list** (not register issues):
- `nds/tutorials/pauli-correlation-experiment-on-a-quantum-computer.mdx` — soft hyphens, not register
- `tl/tutorials/grovers-algorithm.mdx` — different issue, not register

### Step 2: Launch parallel agents

Launch up to **3 agents in parallel** per round. Each agent uses `model: "sonnet"`. For files >400 lines, use the chunking workflow above.

Process in locale priority order: DE → FR → ES → UK → IT → SWG → BAD → SAX → AUT

### Step 3: Validate after each locale

After processing all files for a locale:

```bash
# Re-validate to ensure no structural breakage
python translation/scripts/validate-translation.py --locale {LOCALE} --record

# Spot-check register fix worked (example for DE)
grep -rc "\bSie\b" i18n/de/docusaurus-plugin-content-docs/current/guides/ | grep -v ":0$"
```

### Step 4: Record fixed status

After validation passes, update status.json:
```bash
# For each fixed file:
python translation/scripts/review-translations.py --record-review \
  --locale {LOCALE} --file {FILE} --verdict FIXED \
  --notes "Register fixed: formal → informal"
```

Or use batch JSON recording:
```bash
python translation/scripts/review-translations.py --record-review --from-json /tmp/{locale}-fixed.json
```

### Step 5: After all locales complete

Report summary:
- Total files fixed per locale
- Any files that failed validation after fix (need manual attention)
- Remaining FAIL files (skip list)

Remind user to commit:
```bash
git add -f i18n/*/docusaurus-plugin-content-docs/current/
git commit -m "Fix formal register in 194 translations (Sie→du, vous→tu, etc.)"
```

---

## Variable Reference

| Variable | DE | FR | ES | UK | IT | SWG | BAD | SAX | AUT |
|---|---|---|---|---|---|---|---|---|---|
| LOCALE | de | fr | es | uk | it | swg | bad | sax | aut |
| LANGUAGE | German | French | Spanish | Ukrainian | Italian | Swabian | Badisch | Saxon | Austrian |
| FROM_REGISTER | formal "Sie" | formal "vous" | formal "usted" | formal "Ви" | formal "voi/Lei" | formal "Se" | formal "Sie/Se" | formal "Se" | formal "S'/Sie" |
| TO_REGISTER | informal "du" | informal "tu" | informal "tú" | informal "ти" | informal "tu" | informal (du-form) | informal (du-form) | informal "de" | informal "du" |
| Files | 64 | 36 | 35 | 18 | 17 | 10 | 7 | 3 | 1 |
