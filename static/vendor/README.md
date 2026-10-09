# Vendored browser assets

Served from the site itself instead of a CDN, so a Pi without internet can
still run code and render maths (#964).

## thebelab 0.4.0 (`thebelab/`)

From `https://unpkg.com/thebelab@0.4.0/lib/`: `index.js`, the lazy chunks
`1.index.js` and `2.index.js`, and the Font Awesome fonts (woff2, woff, ttf).
One edit in `index.js`: webpack's public path
`i.p="https://unpkg.com/thebelab@0.4.0/lib/"` is changed to
`i.p="/vendor/thebelab/"`, so the chunks and fonts load from here too.

thebelab still points cell outputs that contain LaTeX at MathJax on cdnjs;
offline, those outputs show raw LaTeX. Page maths uses KaTeX below.

## KaTeX (`katex/`)

`katex.min.css` and the woff2 fonts from `node_modules/katex/dist`, the
version rehype-katex renders with (0.16.28). Refresh both when rehype-katex
moves to a new KaTeX:

    cp node_modules/katex/dist/katex.min.css static/vendor/katex/
    cp node_modules/katex/dist/fonts/*.woff2 static/vendor/katex/fonts/

## Web fonts (`fonts/`)

IBM Plex Sans (variable) and IBM Plex Mono 400/500/600, plus Noto Sans
Arabic and Noto Sans Hebrew (variable) for the RTL sites, all under the SIL
Open Font License (`fonts/OFL.txt`). The woff2 files are the ones the Google
Fonts CSS API served for

    https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600;700&family=Noto+Sans+Hebrew:wght@400;500;600;700&display=swap

(fetched with a current Chrome user agent), keeping only the subsets the
locales need: Plex Sans latin, latin-ext, cyrillic, greek; Plex Mono latin,
latin-ext, cyrillic; Noto Sans Arabic arabic + latin (Latin text on the
Arabic and Hebrew sites renders in it, as before); Noto Sans Hebrew hebrew.
`fonts.css` copies Google's `@font-face` rules (same `unicode-range`s,
`font-display: swap`) with local file names, so a browser downloads a file
only when the page uses its characters. Japanese, Korean and Thai have never
had a web font and use the system font.
