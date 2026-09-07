# doQumentation — project instructions for Claude Code

doQumentation (https://doqumentation.org) is a Docusaurus mirror of IBM
Quantum's Qiskit tutorials and courses with in-browser code execution,
translated into 17 languages. English pages under `docs/` are generated
from the pinned upstream by `scripts/sync-content.py`; a locale's
translation is its PO files under `i18n/<locale>/po/`, and the pages
Docusaurus builds from them are rendered at build time and are not in git.

## If the user wants to help

Route by what they say, then follow that file to the letter; each is a
complete recipe addressed to you.

| They say | Do |
|---|---|
| "help with reviews", "review translations", "check the <language> translation" | Read `CONTRIBUTING-REVIEWS.md` and run one review round. |
| "translate", "help with the <language> translation", "new content" | Read `CONTRIBUTING-TRANSLATIONS.md` and run one locale sync. |
| unsure | Recommend a review round: it is self-contained, budget-shaped and where a fluent reader adds the most. |

Before either, in this order:

1. **Sync the fork** with `JanLahmann/doQumentation` main. Which pages need
   work is read from `translation/status.json`, which every merged round
   rewrites; a stale fork re-does finished work.
2. **Check the claims**, then claim: `gh issue list --repo JanLahmann/doQumentation --label translation-claim`
   shows who holds which locale. Pick a free one (`CONTRIBUTING-NOW.md`
   lists what is left per locale) and open a claim issue with the
   "Claim a locale" template before starting. One locale per person.
3. **Render the locale** before any review or lint: `python3 translation/v2/render.py --locale <locale>`
   (needs po4a ≥ 0.74, GNU gettext and `pip install polib`). Nothing under
   `i18n/<locale>/…/current/` exists until then.

## Hard rules (each maps to a real incident)

- Never hand-edit a rendered page under `i18n/<locale>/docusaurus-plugin-content-docs/current/`
  or a `.po` file. Only `translation/v2/translate.py --apply` and
  `translation/v2/fix.py --apply` write a translation; they run every entry
  through `translation/v2/check.py`.
- Never edit `docs/` (generated English), `translation/status.json`
  (the maintainer banks verdicts there after merge), or any locale but the
  one claimed.
- Sub-agents only read and write the batch file they were given. They
  never run git, scripts or shell. Commits are the orchestrator's.
- Stage exactly the intended set (`i18n/<locale>/po/`, a new file under
  `translation/reviews/`) and assert it before committing. Never `git add -f i18n/`.
- Never build all 17 locales on one machine. Build one with
  `npx docusaurus build --locale <locale>`, or let CI do it.

Pipeline detail: `translation/v2/README.md`. Maintainer context:
`.claude/PROJECT_HANDOFF.md`.
