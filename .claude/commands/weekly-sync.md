---
description: Run the weekly English sync for all 17 locales and open its PR
---

Run the locale sync for the open "sync: upstream content …" PR (branch
`sync/upstream-content`, opened by `sync-upstream.yml` on Mondays). The
`sync-plan.yml` comment on that PR shows what to expect. Follow
`translation/v2/README.md`, *Running a sync*, and CLAUDE.md's hard rules.

1. If there is no open `sync/upstream-content` PR, stop and say so.
2. `python3 translation/v2/sync.py prepare --from sync/upstream-content`.
   If it says nothing needs a model, go to step 5.
3. `python3 translation/v2/sync.py bake`, then run the printed workflow with
   the Workflow tool. Sub-agents only fill batch files.
4. `python3 translation/v2/sync.py status`. For an unreadable output or a
   wrong count, delete that `.out.json`, `bake` again (it includes only
   unfilled batches) and run it.
5. `python3 translation/v2/sync.py finish`.
   - STOP for rejected entries: `sync.py redo --locales <those>`, then
     bake, fill, status, finish again. At most two redo rounds.
   - REPLACED-BY-ENGLISH warnings or new completeness-ratchet findings: do
     not accept them on your own. Show each to the user with the entry, the
     English, the translation and your recommendation, and ask. When the run
     is unattended (a routine), open the PR as a draft with that list.
6. Push the branch and open the PR to main: the upstream range, the pages
   changed, the per-locale counts from `finish`, and anything handled by
   hand. Enable auto-merge (merge commit) unless it is a draft. Close the
   bot's sync PR as superseded with a one-line comment linking the new PR.
   If CI's "Sidebar labels translated in every locale" step fails, upstream
   added sidebar categories: add the keys it lists to each
   `i18n/<locale>/docusaurus-plugin-content-docs/current.json` (translator
   agents fill the labels; product names stay English) and push to the PR.
7. Report what you did in a few sentences.

Never hand-edit PO files or rendered pages, never edit `docs/`, and never
push to main.
