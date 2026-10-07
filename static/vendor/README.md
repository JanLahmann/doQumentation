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
