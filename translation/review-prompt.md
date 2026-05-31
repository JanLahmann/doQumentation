# Translation Review Prompt (for Haiku, Gemini Flash, or any fast LLM)

Use this prompt AFTER running `translation/scripts/validate-translation.py` (which handles structural checks). This prompt focuses purely on **linguistic quality** — register, word salad, verbosity, and accuracy.

## Usage

0. **Check freshness first** — only review files that are in sync with the
   current EN source. Reviewing a STALE/UNKNOWN file wastes effort because
   its prose may not match the English you're comparing against:
   `python translation/scripts/check-translation-freshness.py --locale {LOCALE}`
   Refresh + re-stamp any STALE/UNKNOWN file before reviewing it. (The
   `review-translations.py --next-chunk` orchestrator already holds these
   back automatically unless you pass `--include-stale`.)
1. Run structural validation: `python translation/scripts/validate-translation.py --locale {LOCALE} --file {FILE}`
2. Run MDX lint: `python translation/scripts/lint-translation.py --file {FILE} --en-file {EN_FILE}`
3. If all pass, paste the prompt below into the review model with both files
4. Replace `{LANGUAGE}` and the register section for your target language

**Review model:** Haiku is the validated production review model
(re-validated 2026-05-17: scored 8/8 vs ground truth across de/ja/ar
incl. a subtle accuracy+register discriminator, matching Sonnet/Opus,
zero false-FAILs on clean files). Gemini Flash also works. Do NOT use
Opus — no accuracy gain over Haiku, just cost.

---

## Prompt

```
You are a technical translation reviewer for quantum computing documentation (Qiskit SDK).
Compare the English source with its {LANGUAGE} translation. Perform ONLY these 4 linguistic checks.
Do NOT check code blocks, headings, image paths, or structural elements — those are validated separately.

## Register rules

{REGISTER_SECTION}

## Checks

### 1. REGISTER (Critical)
Scan for any formal register violations. Flag each with line number and the offending word.

### 2. WORD SALAD / HALLUCINATION (Critical)
For each prose paragraph (skip code, math, frontmatter), match it to the
corresponding English source paragraph, then flag:
- **Word salad** — same word or 2-word phrase repeated 3+ times; grammar
  breaking down (fragments trailing off, subject-verb disagreement);
  passage unintelligible. → FLAG (issue_type: Word Salad)
- **Hallucination / substitution** — the paragraph is *fluent and
  grammatical* but conveys content that is NOT in the corresponding
  source paragraph: a fabricated sentence, a substituted topic, or
  invented detail. This is the most dangerous case precisely because it
  reads well — do not let fluency mask it. Verify each translated
  paragraph actually corresponds to its source paragraph's meaning.
  → FLAG (issue_type: Word Salad; note "hallucination" in description)
Focus especially on the LAST 40% of the file — translation models
degrade toward the end — but check every paragraph for substitution.

### 3. VERBOSITY
For each prose paragraph, compare approximate length to the source:
- If a translation sentence is noticeably longer than needed to convey the same meaning → FLAG
- If a simple English concept is expanded into redundant phrasing (e.g., "denotes" → "denota y señala") → FLAG
Skip paragraphs under 10 words.

### 4. ACCURACY
- Any meaning drift (translation says something different from the source) → FLAG
- Any important detail dropped from the translation → FLAG
- Any information added that is not in the source → FLAG

## Output format

Return JSON:

{
  "verdict": "PASS | MINOR_ISSUES | FAIL",
  "issues": [
    {
      "line_number_approx": "Line NN",
      "issue_type": "Register | Word Salad | Verbosity | Accuracy",
      "description": "Brief explanation",
      "source_text": "Original English text",
      "translated_text": "Problematic translated text",
      "suggested_fix": "Corrected translation"
    }
  ],
  "summary": "1-2 sentence quality summary."
}

Verdict rules (apply in order; first match wins):
- **FAIL**: any word salad, any hallucination/substitution, any accuracy
  error, >2 register violations, or >3 verbosity flags.
- **MINOR_ISSUES**: 1–2 register slips and/or minor verbosity only — no
  word salad, no hallucination, no accuracy error. `issues[]` lists them.
- **PASS**: none of the above. A confidently-clean translation. If you
  note a purely cosmetic preference you are NOT sure is a defect, still
  return PASS and put it in `summary` (not `issues[]`) — do not inflate
  it to MINOR_ISSUES. "Zero defects" — not "zero opinions".

## English source:

[PASTE ENGLISH SOURCE HERE]

## {LANGUAGE} translation:

[PASTE TRANSLATION HERE]
```

---

## Register sections by language

### Spanish (es)
```
Use informal "tú" register throughout.
- "tú/tu/tus" NOT "usted/su(s)"
- Imperatives: "consulta, usa, ejecuta, configura, conecta" NOT "consulte, use, ejecute, configure, conecte"
- Flag: Consulte, utilice, puede usted, ejecute, ingrese, seleccione, verifique, Configure
```

### German (de)
```
Use informal "du" register throughout.
- "du/dein/deine" NOT "Sie/Ihr/Ihre"
- Flag: Sie, Ihr, Ihnen, Bitte beachten Sie, Verwenden Sie
```

### French (fr)
```
Use informal "tu" register throughout.
- "tu/ton/ta/tes" NOT "vous/votre/vos"
- Flag: vous, votre, vos, veuillez
```

### Italian (it)
```
Use informal "tu" register throughout.
- "tu/tuo/tua" NOT "Lei/Suo/Sua"
- Flag: Lei, Suo, Sua, consulti, utilizzi, verifichi
```

### Portuguese (pt)
```
Use informal "voce" (casual) register.
- Flag: o senhor, a senhora, vossa
```

### Ukrainian (uk)
```
Use informal "ти" register throughout.
- "ти/твій/твоя" NOT "Ви/Ваш/Ваша"
- Flag: Ви, Вам, Ваш, Вашого
```

### Japanese (ja)
```
Use polite (desu/masu) but not overly formal. No keigo/humble forms.
- Flag: ございます, いただく (humble), ご覧ください (honorific)
```

### Tagalog (tl)
```
Casual register, no po/opo formality markers.
- Flag: po, opo, ninyo, naman po
```

### Arabic (ar)
```
Informal register. Use "anta/anti" (you-singular-informal).
- Flag: formal "antum" (you-plural-formal)
```

### Hebrew (he)
```
Informal register.
- Flag: overly formal phrasing or biblical Hebrew register
```

### Thai (th)
```
Casual register, no polite particles.
- Flag: ครับ, ค่ะ, ขอรับ
```

### Korean (ko)
```
Use 해요체 (informal-polite) — friendly but not casual. Avoid 합쇼체/하소서체 (formal/honorific).
- Flag: 하십시오, 하시오, 드립니다, 십시오, ~사옵니다, ~옵소서, deferential subject honorifics on the reader
- Prefer: 하세요, 해요, ~합니다 only in neutral declarative contexts
```

### Polish (pl)
```
Informal "ty" register. Avoid "Pan/Pani" (formal address) and the impersonal "się" passive when a direct imperative fits.
- Flag: Pan, Pani, Państwo, Państwa, Panu, Pani, proszę uprzejmie
- Prefer informal imperatives: zrobić → zrób, użyć → użyj, sprawdź, otwórz
```

### Czech (cs)
```
Informal "ty" register. Avoid the formal "vy/Vám" addressed to a single reader, and the impersonal infinitive ("je třeba…") when a direct verb-form is natural.
- Flag: Vy, Vám, Vás, Váš, Prosím (laskavě), račte
- Prefer: ty/tvůj/tvoje + 2nd-person singular imperatives (udělej, použij, zkontroluj)
```

### Romanian (ro)
```
Informal "tu" register. Avoid the polite plural "dumneavoastră/voi" addressed to a single reader.
- Flag: dumneavoastră, dvs., vă rog, vă rugăm, dumneata, vă invităm
- Prefer: tu, tău, ta + 2nd-person singular imperatives (consultă, folosește, verifică)
```

### Malay (ms)
```
Casual register. Avoid overly formal markers and Malay-Arabic deference forms.
- Flag: tuan/puan, kebawah/yang berhormat, sila berkenan, saudara/saudari
- Prefer: anda + plain imperatives (lihat, semak, jalankan)
```

### Indonesian (id)
```
Casual "kamu/Anda" register — Anda is acceptable as the conventional written 2nd-person; bapak/ibu deferential is too formal for technical docs.
- Flag: Bapak, Ibu, Saudara, mohon dengan hormat, dipersilakan
- Prefer: Anda or kamu + plain imperatives (lihat, periksa, jalankan)
```
