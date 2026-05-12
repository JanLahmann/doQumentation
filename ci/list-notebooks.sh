#!/usr/bin/env bash
# Emit notebook paths to test, interleaved across top-level English categories.
# Run from a checkout of the `notebooks` branch (or any tree that has the
# top-level English directories present).
#
# Output is stable: each category is sorted alphabetically, then round-robin
# merged so the first N lines cover all categories instead of just guides/.
set -euo pipefail

SKIP_FILE="${1:-ci/notebooks-skip.txt}"
CATEGORIES=(guides learning tutorials qiskit-addons workshop)

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

# Build the skip set as plain lines (strip comments/blanks).
if [[ -f "$SKIP_FILE" ]]; then
  grep -vE '^\s*(#|$)' "$SKIP_FILE" > "$workdir/skip.txt" || true
else
  : > "$workdir/skip.txt"
fi

for cat in "${CATEGORIES[@]}"; do
  if [[ -d "$cat" ]]; then
    find "$cat" -type f -name '*.ipynb' \
      | LC_ALL=C sort > "$workdir/$cat.txt"
  else
    : > "$workdir/$cat.txt"
  fi
  # Drop skipped entries.
  if [[ -s "$workdir/skip.txt" ]]; then
    grep -vxFf "$workdir/skip.txt" "$workdir/$cat.txt" > "$workdir/$cat.kept" || true
    mv "$workdir/$cat.kept" "$workdir/$cat.txt"
  fi
done

# Round-robin merge: paste -d'\n' alternates lines from each file; blank lines
# from shorter files get dropped.
paste -d'\n' \
  "$workdir/guides.txt" \
  "$workdir/learning.txt" \
  "$workdir/tutorials.txt" \
  "$workdir/qiskit-addons.txt" \
  "$workdir/workshop.txt" \
  | grep -v '^$' || true
