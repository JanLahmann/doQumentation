#!/usr/bin/env python3
"""Downscale output images too wide for browsers to decode.

Some upstream notebooks draw whole circuits with `fold=-1`, and the
resulting images are up to 54,284 px wide. Chromium and Firefox refuse to
decode an image wider than 32,767 px, so the reader got a broken-image icon
(UX review 2026-10-09: 5 images on 4 pages). This shrinks every image wider
than --max-width (default 16,384) to that width, in place, keeping its file
name and format so the pages and their translations need no change.
plugins/content-fixes then shows such wide images in a scrollable box.

sync-content.py runs this after copying upstream's images into static/.

    python3 scripts/downscale-wide-images.py [DIR ...] [--max-width N] [--check]

--check only lists images over the limit and exits 1 if there are any.

Decoding: Pillow (>= 11.3, AVIF built in) for anything its AVIF decoder
accepts. libavif refuses images wider than 32,768 px, and so does ffmpeg
for the largest one, so those AVIFs are decoded with the `dav1d` CLI from
the AV1 payload in the file, plane by plane. Without Pillow-AVIF or dav1d
the image is reported and left as it is.
"""
from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_DIRS = ['static/docs/images', 'static/learning/images']
EXTS = ('.avif', '.png', '.webp', '.jpg', '.jpeg')


# ------------------------------------------------------------ dimensions

def image_dims(path: Path) -> tuple[int, int] | None:
    """Width and height from the file header, without decoding."""
    with path.open('rb') as f:
        head = f.read(4096)
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', head[16:24])
    if head[4:8] == b'ftyp':
        i = head.find(b'ispe')
        if i > 0:
            return struct.unpack('>II', head[i + 8:i + 16])
        return None
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


# ------------------------------------------------------------ AVIF boxes

def _find_box(b: bytes, typ: bytes, start: int = 0, end: int | None = None) -> tuple[int, int] | None:
    end = len(b) if end is None else end
    off = start
    while off + 8 <= end:
        size, t = struct.unpack('>I4s', b[off:off + 8])
        hdr = 8
        if size == 1:
            size = struct.unpack('>Q', b[off + 8:off + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - off
        if size < hdr:
            return None
        if t == typ:
            return off + hdr, off + size
        off += size
    return None


def avif_items(b: bytes) -> tuple[int, dict[int, bytes]]:
    """(primary item id, {item id: AV1 payload}) of a single-image AVIF."""
    meta = _find_box(b, b'meta')
    if not meta:
        raise ValueError('no meta box')
    ms, me = meta[0] + 4, meta[1]  # meta is a full box
    pitm = _find_box(b, b'pitm', ms, me)
    primary = struct.unpack('>H', b[pitm[0] + 4:pitm[0] + 6])[0] if pitm and b[pitm[0]] == 0 else 1
    iloc = _find_box(b, b'iloc', ms, me)
    if not iloc:
        raise ValueError('no iloc box')
    p = iloc[0]
    version = b[p]
    p += 4
    off_sz, len_sz = b[p] >> 4, b[p] & 15
    base_sz = b[p + 1] >> 4
    idx_sz = b[p + 1] & 15 if version in (1, 2) else 0
    p += 2

    def rd(n: int) -> int:
        nonlocal p
        v = int.from_bytes(b[p:p + n], 'big') if n else 0
        p += n
        return v

    count = rd(2) if version < 2 else rd(4)
    items = {}
    for _ in range(count):
        iid = rd(2) if version < 2 else rd(4)
        if version in (1, 2):
            if rd(2) & 15:
                raise ValueError('unsupported iloc construction method')
        rd(2)  # data reference index
        base = rd(base_sz)
        data = b''
        for _ in range(rd(2)):
            rd(idx_sz)
            eo, el = rd(off_sz), rd(len_sz)
            data += b[base + eo:base + eo + el]
        items[iid] = data
    return primary, items


def _read_y4m(path: Path):
    """(width, height, colourspace tag, {plane: (w, h, bytes)}) of a one-frame Y4M."""
    data = path.read_bytes()
    nl = data.index(b'\n')
    tags = data[:nl].split()
    w = h = 0
    cs = '420jpeg'
    full = None
    for t in tags[1:]:
        if t[:1] == b'W':
            w = int(t[1:])
        elif t[:1] == b'H':
            h = int(t[1:])
        elif t[:1] == b'C':
            cs = t[1:].decode()
        elif t.startswith(b'XCOLORRANGE='):
            full = t.endswith(b'FULL')
    if not cs.startswith(('420', '444', 'mono')):
        raise ValueError(f'unsupported Y4M colourspace C{cs}')
    p = data.index(b'\n', nl + 1) + 1  # past "FRAME\n"
    planes = {'Y': (w, h, data[p:p + w * h])}
    p += w * h
    if not cs.startswith('mono'):
        cw, ch = (w, h) if cs.startswith('444') else ((w + 1) // 2, (h + 1) // 2)
        planes['Cb'] = (cw, ch, data[p:p + cw * ch])
        p += cw * ch
        planes['Cr'] = (cw, ch, data[p:p + cw * ch])
    return w, h, cs, full, planes


def decode_avif_dav1d(path: Path, size: tuple[int, int]):
    """Decode an AVIF of any size with dav1d and resize it to `size`."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    primary, items = avif_items(path.read_bytes())
    with tempfile.TemporaryDirectory() as td:
        decoded = {}
        for iid, payload in items.items():
            obu = Path(td) / f'{iid}.obu'
            y4m = Path(td) / f'{iid}.y4m'
            obu.write_bytes(payload)
            r = subprocess.run(['dav1d', '-q', '-i', str(obu), '--demuxer', 'section5', '-o', str(y4m)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f'dav1d failed on item {iid}: {r.stderr.strip()[:200]}')
            decoded[iid] = _read_y4m(y4m)
            y4m.unlink()

    def plane(w, h, raw, full, chroma=False):
        im = Image.frombytes('L', (w, h), raw).resize(size, Image.LANCZOS)
        if full is False:  # limited ("TV") range → full range
            if chroma:
                im = im.point(lambda v: max(0, min(255, round((v - 128) * 255 / 224 + 128))))
            else:
                im = im.point(lambda v: max(0, min(255, round((v - 16) * 255 / 219))))
        return im

    _, _, cs, full, planes = decoded[primary]
    if full is None:
        full = True  # libavif's default for images converted from RGB
    if cs.startswith('mono'):
        rgb = plane(*planes['Y'], full).convert('RGB')
    else:
        ycc = Image.merge('YCbCr', [plane(*planes['Y'], full),
                                    plane(*planes['Cb'], full, chroma=True),
                                    plane(*planes['Cr'], full, chroma=True)])
        rgb = ycc.convert('RGB')
    for iid, (w, h, acs, afull, aplanes) in decoded.items():
        if iid != primary and acs.startswith('mono'):  # the alpha auxiliary image
            alpha = plane(*aplanes['Y'], True if afull is None else afull)
            rgb = rgb.convert('RGBA')
            rgb.putalpha(alpha)
            break
    return rgb


# -------------------------------------------------------------- shrinking

def pillow_avif() -> bool:
    try:
        from PIL import features
        return bool(features.check('avif'))
    except Exception:
        return False


def shrink(path: Path, dims: tuple[int, int], max_width: int) -> str:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    w, h = dims
    size = (max_width, max(1, round(h * max_width / w)))
    im = None
    try:
        with Image.open(path) as src:
            src.load()
            im = src.resize(size, Image.LANCZOS)
    except Exception:
        if path.suffix != '.avif':
            raise
        if not shutil.which('dav1d'):
            raise RuntimeError('too large for Pillow and no dav1d on PATH')
        im = decode_avif_dav1d(path, size)
    tmp = path.with_name(path.name + '.tmp')
    fmt = {'.avif': 'AVIF', '.png': 'PNG', '.webp': 'WEBP', '.jpg': 'JPEG', '.jpeg': 'JPEG'}[path.suffix.lower()]
    if fmt == 'JPEG' and im.mode == 'RGBA':
        im = im.convert('RGB')
    # AVIF at quality 50 / speed 8: ~13 s for a 16384×3156 circuit, and
    # still sharp for line art (IBM's own files are encoded harder).
    opts = {'AVIF': {'quality': 50, 'speed': 8}, 'WEBP': {'quality': 80}, 'JPEG': {'quality': 85}}
    im.save(tmp, fmt, **opts.get(fmt, {}))
    tmp.replace(path)
    return f'{w}×{h} → {size[0]}×{size[1]}'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dirs', nargs='*', default=DEFAULT_DIRS)
    ap.add_argument('--max-width', type=int, default=16384)
    ap.add_argument('--check', action='store_true', help='only list images over the limit; exit 1 if any')
    args = ap.parse_args()

    wide = []
    for d in args.dirs:
        root = Path(d)
        if not root.is_dir():
            continue
        for p in sorted(root.rglob('*')):
            if p.suffix.lower() in EXTS and p.is_file():
                dims = image_dims(p)
                if dims and dims[0] > args.max_width:
                    wide.append((p, dims))
    if args.check:
        for p, (w, h) in wide:
            print(f'too wide: {p} ({w}×{h})')
        print(f'downscale-wide-images: {len(wide)} image(s) wider than {args.max_width} px')
        return 1 if wide else 0
    if not wide:
        print(f'  ✓ no image wider than {args.max_width} px')
        return 0
    try:
        import PIL  # noqa: F401
    except ImportError:
        print(f'  Warning: {len(wide)} image(s) wider than {args.max_width} px left as they are '
              '(pip install "pillow>=11.3" to shrink them)')
        return 0
    if not pillow_avif() and any(p.suffix == '.avif' for p, _ in wide):
        print('  Warning: this Pillow has no AVIF support (pip install "pillow>=11.3")')
    failed = 0
    for p, dims in wide:
        try:
            print(f'  ✓ {p}: {shrink(p, dims, args.max_width)}', flush=True)
        except Exception as e:  # keep the sync going; the build still works
            failed += 1
            print(f'  Warning: {p} ({dims[0]}×{dims[1]}) left as it is: {e}')
    print(f'  {len(wide) - failed} image(s) downscaled, {failed} left as they are')
    return 0


if __name__ == '__main__':
    sys.exit(main())
