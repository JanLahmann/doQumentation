"""update.py must list every fuzzy entry, also those translatable() rejects.

po4a renders a fuzzy entry as English. During the English sync to upstream
cda70faec, five strings went fuzzy in all 17 locales (80 entries) while
update.py printed "0 fuzzy", because the worklist only looked at entries
passing po4a_io.translatable():

  - tag-prefixed prose opening with inline code
    (`<Admonition type="note">\\n`NoiseLearner` only works with ...`);
  - code-fence chunks inside list items (```text host lists in
    guides/quickstart-steps-org, the ```bash curl block in
    guides/cloud-setup-untrusted).

Run: python3 -m pytest translation/v2/tests -q
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import po4a_io as io  # noqa: E402

needs_msgmerge = pytest.mark.skipif(shutil.which("msgmerge") is None, reason="gettext not installed")

ADM_OLD = ('<Admonition type="note">\n`NoiseLearner` only works with EstimatorV2 and '
           '`NoiseLearnerV3` only works with Executor.\n</Admonition>\n')
ADM_NEW = ('<Admonition type="note">\n`NoiseLearner` only works with EstimatorV2, and '
           '`NoiseLearnerV3` only works with the Executor.\n</Admonition>\n')
ADM_DE = ('<Admonition type="note">\n`NoiseLearner` funktioniert nur mit EstimatorV2 und '
          '`NoiseLearnerV3` nur mit Executor.\n</Admonition>\n')
FENCE_OLD = "    ```text\n    cloud.ibm.com\n    iam.cloud.ibm.com\n    globalcatalog.cloud.ibm.com\n    ```\n"
FENCE_NEW = ("    ```text\n    cloud.ibm.com\n    iam.cloud.ibm.com\n    globalcatalog.cloud.ibm.com\n"
             "    resource-controller.cloud.ibm.com\n    ```\n")
UNCHANGED = "This paragraph did not change at all between the two syncs.\n"


def _entry(msgid: str, msgstr: str = "x", comment: str = "type: Plain text"):
    import polib
    return polib.POEntry(msgid=msgid, msgstr=msgstr, comment=comment)


@pytest.mark.parametrize("msgid", [
    ADM_OLD,
    '<Admonition type="note">\n`GET /accounts/{id}` shows what is available to grant at the account level.',
    "</AccordionItem>\n</Accordion>\n[Exact simulation with Qiskit SDK primitives](/guides/x) demonstrates "
    "how to use the reference primitives.",
    '<Admonition type="caution">\n**Protect your API key!** Never include your key in source code or notebooks.',
    '<span id="local-jupyter"></span>\n1. If you want to run a Jupyter notebook with the packages you installed,',
    '</Admonition>\n- Running jobs requires the `writer` service access role and the `viewer` platform role.',
    '<span id="Reference1"></span>\n[\\[1\\]](#Reference1) D. J. Egger, J. Mareček, and S. Woerner, '
    '"Warm-starting quantum optimization", Quantum 5, 479 (2021).',
    "<ul>\n<li>– Ability to convert quantum market information into actionable insights.</li>\n</ul>",
])
def test_translatable_sees_prose_that_opens_with_inline_markup(msgid):
    assert io.translatable(_entry(msgid))


@pytest.mark.parametrize("msgid", [
    '<Admonition type="note">\n`NoiseLearner`\n',                        # too short to be running text
    "<head>\n  {/* SEO/social title override: keeps the visible H1 short while giving search engines more */}",
    '<Tabs>\n```python\nfrom qiskit import QuantumCircuit, transpile, and many more words here\n```',
    FENCE_OLD,
])
def test_translatable_still_rejects_non_prose(msgid):
    assert not io.translatable(_entry(msgid))


@needs_msgmerge
def test_worklist_lists_every_fuzzy_entry_including_hidden_ones(monkeypatch, tmp_path):
    """Real msgmerge: both kinds come back fuzzy and both are on the worklist,
    the fence chunk counted as outside translatable()."""
    import polib
    up = importlib.import_module("update")
    monkeypatch.setattr(io, "I18N", tmp_path / "i18n")
    monkeypatch.setattr(io, "POT_DIR", tmp_path / "pot")
    rel = "guides/hidden.mdx"
    old = polib.POFile(wrapwidth=0)
    old.metadata = {"Content-Type": "text/plain; charset=UTF-8", "Language": "de"}
    for msgid, msgstr in ((ADM_OLD, ADM_DE), (FENCE_OLD, FENCE_OLD), (UNCHANGED, "Unverändert.\n")):
        old.append(polib.POEntry(msgid=msgid, msgstr=msgstr, comment="type: Plain text", flags=["no-wrap"]))
    io.po_path("de", rel).parent.mkdir(parents=True)
    old.save(str(io.po_path("de", rel)))
    pot = polib.POFile(wrapwidth=0)
    pot.metadata = {"Content-Type": "text/plain; charset=UTF-8"}
    for msgid in (ADM_NEW, FENCE_NEW, UNCHANGED):
        pot.append(polib.POEntry(msgid=msgid, comment="type: Plain text", flags=["no-wrap"]))
    io.pot_path(rel).parent.mkdir(parents=True)
    pot.save(str(io.pot_path(rel)))

    items, counts, _ = up.worklist("de", [rel])

    merged = polib.pofile(str(io.po_path("de", rel)), wrapwidth=0)
    assert [e.msgid for e in merged if e.fuzzy] == [ADM_NEW, FENCE_NEW]
    by = {i["msgid"]: i for i in items}
    assert set(by) == {ADM_NEW, FENCE_NEW}
    assert by[ADM_NEW]["previous_msgstr"] == ADM_DE
    assert by[FENCE_NEW]["previous_msgid"] == FENCE_OLD
    assert counts["fuzzy"] == 2
    assert counts["hidden fuzzy"] == 1          # the fence chunk; the admonition is translatable now
    assert counts["translated"] == 1


def test_prepare_copies_a_fuzzy_fence_chunk_without_a_model(monkeypatch, tmp_path):
    """The listed fence chunk lands in translate.py's copy tier: msgid copied,
    fuzzy flag cleared, no batch written for it."""
    import polib
    tr = importlib.import_module("translate")
    monkeypatch.setattr(io, "I18N", tmp_path / "i18n")
    monkeypatch.setattr(io, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(io, "REPO", tmp_path)
    monkeypatch.setattr(tr, "instructions", lambda locale: "rules")
    rel = "guides/hidden.mdx"
    po = polib.POFile(wrapwidth=0)
    po.metadata = {"Content-Type": "text/plain; charset=UTF-8", "Language": "de"}
    po.append(polib.POEntry(msgid=FENCE_NEW, msgstr=FENCE_OLD, previous_msgid=FENCE_OLD,
                            comment="type: Plain text", flags=["fuzzy", "no-wrap"]))
    io.po_path("de", rel).parent.mkdir(parents=True)
    po.save(str(io.po_path("de", rel)))
    io.WORK_DIR.mkdir(parents=True)
    wl = io.WORK_DIR / "worklist-de.json"
    wl.write_text(json.dumps({"items": [{
        "id": f"{rel}#0", "page": rel, "type": "Plain text", "msgid": FENCE_NEW,
        "previous_msgid": FENCE_OLD, "previous_msgstr": FENCE_OLD}]}), encoding="utf-8")

    summary = tr.prepare("de", wl)

    assert summary["copy"] == 1 and summary["haiku"] == 0 and summary["sonnet"] == 0
    e = polib.pofile(str(io.po_path("de", rel)), wrapwidth=0)[0]
    assert e.msgstr == FENCE_NEW and not e.fuzzy


# A fence chunk keeps the list item's text after the fence in the same entry.
# When that text is prose, the entry is a translator's, however it begins.
@pytest.mark.parametrize("msgid", [
    "    ```bash\n    curl -X POST 'https://iam.cloud.ibm.com/identity/token'\n    ```\n"
    "    Copy and save the returned bearer token.\n",
    "    ```text\n    quantum.cloud.ibm.com\n    ```\n- IBM Quantum Compute Service - region eu-de:\n",
    "```python\nprint(result)\n```\nThen open your notebook as follows:\n",
])
def test_translatable_sees_prose_after_a_fence(msgid):
    assert io.translatable(_entry(msgid))


@pytest.mark.parametrize("msgid", [
    FENCE_NEW,
    "```python\nx = 1\n```\n</TabItem>\n</Tabs>\n",
    '```toml\n[x]\n```\n</TabItem>\n  <TabItem value="package-table-cfg" label="setup.cfg">\n',
    "```python\n# an open fence: the rest is code, whatever it says in comments\nx = 1\n",
])
def test_translatable_still_rejects_code_and_closers_after_a_fence(msgid):
    assert not io.translatable(_entry(msgid))


def test_update_summary_keeps_the_shape_sync_py_parses(monkeypatch, tmp_path, capsys):
    """sync.py finish reads "<n> fuzzy, <n> untranslated" off update.py's
    summary line; a note wedged between them made it read -1 entries left."""
    import re
    up = importlib.import_module("update")
    from collections import Counter
    monkeypatch.setattr(up, "worklist", lambda *a, **k: ([], Counter({"fuzzy": 4, "hidden fuzzy": 3, "untranslated": 9,
                                                                      "translated": 1, "entries": 14}), []))
    monkeypatch.setattr(sys, "argv", ["update.py", "--locale", "de", "--page", "guides/x.mdx"])
    up.main()
    out = capsys.readouterr().out
    m = re.search(r"^de: \d+ translated, (\d+) fuzzy, (\d+) untranslated", out, re.M)
    assert m and m.groups() == ("4", "9")
    assert "3 of the fuzzy outside translatable()" in out
