#!/usr/bin/env python3
"""Shrink a Word-exported PDF by subsetting fonts Word embedded in full.

Word cannot subset color fonts such as Segoe UI Emoji (used by the icons in the
resume header), so it embeds the whole 8 MB font and the PDF becomes ~4.4 MB -
above the 2 MB limit of LinkedIn Easy Apply and similar forms.
This keeps only the glyphs the pages actually draw (glyph ids are retained, so
the content streams stay valid and the page looks exactly the same).

  python shrink_pdf.py in.pdf [out.pdf]   (default: in place)
"""
import io
import logging
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, NameObject, NumberObject

MIN_FONT_BYTES = 300_000  # only touch fonts that are this big when embedded
logging.getLogger("fontTools").setLevel(logging.ERROR)


def _big_type0_fonts(page):
    """resource name -> (descendant font dict, FontFile2 stream) for big embedded fonts."""
    out = {}
    res = page.get("/Resources")
    fonts = res.get_object().get("/Font") if res else None
    if not fonts:
        return out
    for name, ref in fonts.get_object().items():
        f = ref.get_object()
        if f.get("/Subtype") != "/Type0":
            continue
        desc = f["/DescendantFonts"][0].get_object()
        fd = desc.get("/FontDescriptor")
        ff = fd.get_object().get("/FontFile2") if fd else None
        if ff is None:
            continue
        stream = ff.get_object()
        if len(stream.get_data()) >= MIN_FONT_BYTES:
            out[name] = (desc, stream)
    return out


def _used_codes(page, reader, wanted):
    """font resource name -> set of 2-byte CIDs shown with it on this page."""
    used = {n: set() for n in wanted}
    content = page.get_contents()
    if content is None:
        return used
    current = None
    for operands, op in ContentStream(content, reader).operations:
        if op == b"Tf":
            current = operands[0]
        elif current in used and op in (b"Tj", b"'", b'"', b"TJ"):
            items = operands[0] if op == b"TJ" else [operands[-1]]
            for s in items:
                if isinstance(s, (int, float)):
                    continue
                b = s.original_bytes if hasattr(s, "original_bytes") else bytes(s)
                for i in range(0, len(b) - 1, 2):
                    used[current].add((b[i] << 8) | b[i + 1])
    return used


def shrink(src, dst=None):
    src = Path(src)
    dst = Path(dst) if dst else src
    reader = PdfReader(str(src))
    writer = PdfWriter(clone_from=reader)

    targets = {}  # id(stream) -> [desc, stream, gids]
    for page in writer.pages:
        big = _big_type0_fonts(page)
        if not big:
            continue
        for name, cids in _used_codes(page, writer, big).items():
            desc, stream = big[name]
            entry = targets.setdefault(id(stream), [desc, stream, set()])
            cid2gid = desc.get("/CIDToGIDMap")
            if cid2gid is None or cid2gid == "/Identity":
                entry[2] |= cids
            else:
                m = cid2gid.get_object().get_data()
                entry[2] |= {(m[2 * c] << 8) | m[2 * c + 1] for c in cids if 2 * c + 1 < len(m)}

    before = src.stat().st_size
    for desc, stream, gids in targets.values():
        if not gids:
            continue  # font not drawn by any page content we can see -> leave it alone
        font = TTFont(io.BytesIO(stream.get_data()), lazy=False)
        opts = subset.Options()
        opts.retain_gids = True          # glyph ids in the page content stay valid
        opts.notdef_outline = True
        opts.name_IDs = ["*"]
        opts.name_languages = ["*"]
        opts.drop_tables += ["SVG ", "sbix", "CBDT", "CBLC", "EBDT", "EBLC", "DSIG"]
        sub = subset.Subsetter(opts)
        sub.populate(gids=sorted(gids | {0}))
        sub.subset(font)
        buf = io.BytesIO()
        font.save(buf)
        data = buf.getvalue()
        stream.set_data(data)
        stream[NameObject("/Length1")] = NumberObject(len(data))

    writer.compress_identical_objects()
    tmp = dst.with_suffix(".tmp.pdf")
    with tmp.open("wb") as f:
        writer.write(f)
    tmp.replace(dst)
    return before, dst.stat().st_size


if __name__ == "__main__":
    b, a = shrink(*sys.argv[1:3])
    print(f"{b/1e6:.2f} MB -> {a/1e6:.2f} MB")
