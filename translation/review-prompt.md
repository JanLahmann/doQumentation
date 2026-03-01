# Translation Review Prompt (for Haiku, Gemini Flash, or any fast LLM)

Use this prompt AFTER running `translation/scripts/validate-translation.py` (which handles structural checks). This prompt focuses purely on **linguistic quality** — register, word salad, verbosity, and accuracy.

## Usage

1. Run structural validation first: `python translation/scripts/validate-translation.py --locale {LOCALE} --file {FILE}`
2. If structural checks pass, paste the prompt below into Haiku / Gemini Flash with both files
3. Replace `{LANGUAGE}` and the register section for your target language

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
For each prose paragraph (skip code, math, frontmatter):
- Any sentence with the same word or 2-word phrase repeated 3+ times → FLAG
- Any sentence where grammar breaks down (fragments trailing off, subject-verb disagreement) → FLAG
- Any passage that is unintelligible or does not convey the meaning of the source → FLAG
Focus especially on the LAST 40% of the file — translation models degrade toward the end.

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

Verdict rules:
- PASS: Zero issues
- MINOR_ISSUES: Only 1-2 register slips or minor verbosity (easily fixable)
- FAIL: Any word salad, any accuracy error, >2 register violations, or >3 verbosity flags

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
