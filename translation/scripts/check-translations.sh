#!/usr/bin/env bash
# Check which files from a batch are genuinely translated (no fallback marker).
# Usage: ./scripts/check-translations.sh <locale> <file1> <file2> ...
# Example: ./scripts/check-translations.sh de guides/DAG-representation.mdx guides/access-groups.mdx
#
# Or pipe a list:
#   cat batch-files.txt | xargs ./scripts/check-translations.sh de

LOCALE="$1"
shift

if [ -z "$LOCALE" ]; then
  echo "Usage: $0 <locale> <file1.mdx> [file2.mdx ...]"
  exit 1
fi

BASE="i18n/${LOCALE}/docusaurus-plugin-content-docs/current"
MARKER="doqumentation-untranslated-fallback"

ok=0
fail=0
missing=0
fail_list=""

for f in "$@"; do
  target="${BASE}/${f}"
  if [ ! -f "$target" ]; then
    echo "MISSING:   $f"
    missing=$((missing + 1))
    fail_list="${fail_list} ${f}"
  elif grep -q "$MARKER" "$target"; then
    echo "FALLBACK:  $f"
    fail=$((fail + 1))
    fail_list="${fail_list} ${f}"
  else
    echo "OK:        $f"
    ok=$((ok + 1))
  fi
done

total=$((ok + fail + missing))
echo ""
echo "Results: ${ok}/${total} translated, ${fail} still fallback, ${missing} missing"

if [ -n "$fail_list" ]; then
  echo ""
  echo "Files needing (re-)translation:"
  for f in $fail_list; do
    echo "  $f"
  done
fi
