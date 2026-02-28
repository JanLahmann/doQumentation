#!/bin/bash
#
# setup-satellite-repo.sh — Initialize a satellite deployment repo for a locale
#
# Usage:
#   ./.claude/scripts/setup-satellite-repo.sh <locale-code> <label>
#
# Example:
#   ./.claude/scripts/setup-satellite-repo.sh ksh "Kölsch"
#
# Creates:
#   - main branch with LICENSE, LICENSE-DOCS, NOTICE, README.md
#   - gh-pages branch with CNAME + placeholder index.html
#
# Prerequisites:
#   - `gh` CLI authenticated
#   - Repo JanLahmann/doqumentation-{locale} already created on GitHub
#   - Run from the main doQumentation repo root

set -e

LOCALE="$1"
LABEL="$2"

if [ -z "$LOCALE" ] || [ -z "$LABEL" ]; then
  echo "Usage: $0 <locale-code> <label>"
  echo "Example: $0 ksh \"Kölsch\""
  exit 1
fi

REPO="JanLahmann/doqumentation-$LOCALE"
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
WORKDIR="$(mktemp -d)"

echo "=== Setting up $LOCALE ($LABEL) ==="
echo "Source: $SRC"
echo "Work dir: $WORKDIR"

cd "$WORKDIR"

# Clone empty repo
git clone "https://github.com/$REPO.git" "$LOCALE" 2>/dev/null || {
  mkdir "$LOCALE" && cd "$LOCALE" && git init
  git remote add origin "https://github.com/$REPO.git"
  cd ..
}

cd "$LOCALE"

# Ensure we're on main
git checkout -b main 2>/dev/null || git checkout main 2>/dev/null || true

# Copy license files from main repo
cp "$SRC/LICENSE" .
cp "$SRC/LICENSE-DOCS" .
cp "$SRC/NOTICE" .

# Create README
cat > README.md << EOF
# doQumentation — $LABEL

This is a deployment repository for [$LOCALE.doqumentation.org](https://$LOCALE.doqumentation.org), the $LABEL version of [doQumentation](https://doqumentation.org).

The \`gh-pages\` branch contains the built site, automatically deployed by CI from the main repository.

## Source

All source code, translations, and build infrastructure live in the main repository:
**[JanLahmann/doQumentation](https://github.com/JanLahmann/doQumentation)**

## License

- **Code** (scripts, source files, code snippets): [Apache License 2.0](LICENSE)
- **Content** (tutorials, guides, courses, media): [CC BY-SA 4.0](LICENSE-DOCS)

[Qiskit documentation](https://github.com/Qiskit/documentation) content © IBM Corp.
doQumentation is part of the [RasQberry](https://rasqberry.org/) project.
EOF

git add -A
git commit -m "Initial setup: licenses and README"
git push origin main

echo "  Main branch pushed for $LOCALE"

# Create gh-pages branch
git checkout --orphan gh-pages
git rm -rf . 2>/dev/null || true
echo "<h1>Deploying...</h1>" > index.html
echo "$LOCALE.doqumentation.org" > CNAME
git add -A
git commit -m "Init gh-pages"
git push origin gh-pages

echo "  gh-pages branch pushed for $LOCALE"

# Clean up
rm -rf "$WORKDIR"
echo "=== $LOCALE done ==="
