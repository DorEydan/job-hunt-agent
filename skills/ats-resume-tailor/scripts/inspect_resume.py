#!/usr/bin/env python3
"""Check a resume (.docx or .pdf) for things that break ATS parsing or hurt the candidate.

  python inspect_resume.py resume.docx
  python inspect_resume.py resume.pdf [--against tailored.docx]

.docx: tables, text boxes, columns, contact details in headers/footers, hidden or white or tiny text, images,
       page size, right-to-left text, personal details that some countries leave out.
.pdf:  real text layer, size, pages, the tool that made it, contact details readable; with --against, also that
       every paragraph of the .docx comes out of the PDF, in the same order, and that Hebrew/Arabic words are not
       reversed (a common PDF problem with right-to-left text).
The PDF text is read with pypdf, a stand-in for an ATS parser: if pypdf can't read it in order, many ATSs can't
either. Passing doesn't guarantee every ATS reads it.

Output is JSON: {"file", "kind", "facts": {...}, "issues": [{"level": "high|medium|info", "what", "fix"}]}.
Exit code 0 = no high issues, 1 = at least one high issue, 2 = could not read the file.
"""
import argparse
import html
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

MAX_PART = 8_000_000
EMAIL = re.compile(r"[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,5}")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,18}\d)(?!\d)")
RTL_CHAR = re.compile(r"[֐-׿؀-ۿ]")
RTL_WORD = re.compile(r"[֐-׿؀-ۿ]{3,}")
PERSONAL = re.compile(
    r"date of birth|\bborn\b|\bd\.o\.b\b|marital status|\bmarried\b|nationality|father'?s name|religion|"
    r"תאריך לידה|מצב משפחתי|נשוי|נשואה|גיל:|geburtsdatum|geboren|familienstand|staatsangehörigkeit|"
    r"data urodzenia|stan cywilny|date de naissance|situation familiale|geboortedatum|burgerlijke staat",
    re.I)
T_RE = re.compile(r"<w:t(?:\s[^>]*)?(?<!/)>([^<]*)</w:t>")
P_RE = re.compile(r"<w:p(?:\s[^>]*)?(?<!/)>.*?</w:p>", re.S)
R_RE = re.compile(r"<w:r(?:\s[^>]*)?(?<!/)>.*?</w:r>", re.S)
BOX_RE = re.compile(r"<w:txbxContent\b.*?</w:txbxContent>", re.S)
MAX_PDF_BYTES = 30_000_000
MAX_PDF_PAGES = 30
OFF = ("0", "false", "off")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_safe import DocxError, open_docx, read_text_part  # noqa: E402


def fail(msg):
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(2)


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def text_of(xml):
    xml = re.sub(r"<w:(?:tab|br|cr)\b[^>]*/>", "<w:t> </w:t>", xml)  # these separate words, like a space
    return "".join(html.unescape(t) for t in T_RE.findall(xml))


def tags(xml, name):
    """Every <w:name .../> or <w:name ...> opening tag, as {attribute: value} (any attribute order or quotes)."""
    out = []
    for m in re.finditer(r"<w:" + name + r"\b([^>]*)>", xml):
        out.append({k: v for k, _, v in re.findall(r"(\w+:\w+|\w+)\s*=\s*([\"'])(.*?)\2", m.group(1))} | {"_": 1})
    return out


def on(tag):  # <w:vanish/> or <w:vanish w:val="true"/>; w:val="0/false/off" means off
    return str(tag.get("w:val", "true")).lower() not in OFF


def docx_paragraphs(path):
    try:
        z, doc = open_docx(path)
    except DocxError as e:
        fail(str(e))
    z.close()
    return [t for t in (text_of(p).strip() for p in P_RE.findall(BOX_RE.sub("", doc))) if t]


def issue(level, what, fix):
    return {"level": level, "what": what, "fix": fix}


def light(color):
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", color or ""):
        return False
    return all(int(color[i:i + 2], 16) >= 0xF0 for i in (0, 2, 4))


def inspect_docx(path):
    try:
        z, doc = open_docx(path)
        with z:
            names = z.namelist()
            hf = {n: text_of(read_text_part(z, n)) for n in names
                  if re.fullmatch(r"word/(header|footer)\d{0,3}\.xml", n)}
            media = [n for n in names if n.startswith("word/media/")]
            app = read_text_part(z, "docProps/app.xml") if "docProps/app.xml" in names else ""
            styles = read_text_part(z, "word/styles.xml") if "word/styles.xml" in names else ""
    except DocxError as e:
        fail(str(e))
    # Text boxes are counted separately: an email only inside a box still counts as missing from the body.
    body = "\n".join(t for t in (text_of(p) for p in P_RE.findall(BOX_RE.sub("", doc))) if t)
    facts, issues = {}, []

    tables = len(tags(doc, "tbl"))
    boxes = len(re.findall(r"<w:txbxContent\b", doc))
    cols = [int(t["w:num"]) for t in tags(doc, "cols") if str(t.get("w:num", "")).isdigit()]
    facts.update(tables=tables, text_boxes=boxes, columns=max(cols or [1]), images=len(media))
    if tables:
        issues.append(issue("high" if tables > 1 else "medium", f"{tables} table(s). Many ATS parsers read tables out of order.",
                            "Move the content out of tables into plain paragraphs (one column)."))
    if boxes:
        box_text = " ".join(text_of(b) for b in BOX_RE.findall(doc))
        lost = "contact details" if EMAIL.search(box_text) or PHONE.search(box_text) else "text"
        issues.append(issue("high", f"{boxes} text box(es) with {lost} inside. Many parsers skip text boxes.",
                            "Put that text in normal paragraphs."))
    if max(cols or [1]) > 1:
        issues.append(issue("high", f"{max(cols)}-column layout. Parsers often mix the columns together.",
                            "Use a single-column layout."))
    for n, t in hf.items():
        if EMAIL.search(t) or PHONE.search(t):
            issues.append(issue("high", f"Contact details in the {'header' if 'header' in n else 'footer'}. Some parsers skip headers and footers.",
                                "Move name, email and phone into the first lines of the body."))
            break
    if not EMAIL.search(body):
        issues.append(issue("medium", "No email address found in the body.", "Add it near the top, as plain text."))

    def hidden_kind(rpr):
        kinds = set()
        if any(on(t) for t in tags(rpr, "vanish") + tags(rpr, "webHidden")):
            kinds.add("hidden")
        colors = [t.get("w:val", "") for t in tags(rpr, "color")]
        fills = [t.get("w:fill", "") for t in tags(rpr, "shd")]
        dark_fill = any(re.fullmatch(r"[0-9A-Fa-f]{6}", f) and not light(f) for f in fills)
        if any(light(c) for c in colors) and not dark_fill:
            kinds.add("white")
        sizes = [int(t["w:val"]) for t in tags(rpr, "sz") + tags(rpr, "szCs") if str(t.get("w:val", "")).isdigit()]
        if sizes and min(sizes) <= 8:  # half-points: 8 = 4 pt
            kinds.add("tiny")
        return kinds

    # Styles that hide text count too (text using such a style is hidden even with no formatting on the run).
    hiding_styles = set()
    for m in re.finditer(r"<w:style\b[^>]*w:styleId=\"([^\"]+)\"[^>]*>(.*?)</w:style>", styles, re.S):
        if hidden_kind(m.group(2)) & {"hidden", "tiny"}:  # a white style may sit on a dark banner, so not that
            hiding_styles.add(m.group(1))
    hidden = white = tiny = 0
    for r in R_RE.findall(doc):
        t = text_of(r).strip()
        if not t:
            continue
        rpr = r.split("<w:t", 1)[0]
        kinds = hidden_kind(rpr)
        if any(s.get("w:val") in hiding_styles for s in tags(rpr, "rStyle")):
            kinds.add("hidden")
        hidden += len(t) * ("hidden" in kinds)
        white += len(t) * ("white" in kinds)
        tiny += len(t) * ("tiny" in kinds)
    facts.update(hidden_chars=hidden, white_chars=white, tiny_chars=tiny)
    if hidden or white or tiny:
        issues.append(issue("high", f"Hidden text found: {hidden} hidden, {white} white/near-white, {tiny} tiny (≤4 pt) characters. "
                                    "ATS vendors and recruiters look for this and usually reject the candidate.",
                            "Remove it (check with the candidate first, it may be leftover from a template)."))

    pg = [t.get("w:w") for t in tags(doc, "pgSz") if t.get("w:w")]
    facts["page"] = {"11906": "A4", "11907": "A4", "12240": "Letter"}.get(pg[0], pg[0]) if pg else "unknown"
    tracked = len(re.findall(r"<w:(?:ins|del)\b", doc))
    comments = "word/comments.xml" in names
    facts.update(tracked_changes=tracked, comments=comments)
    if tracked or comments:
        issues.append(issue("medium", ("Tracked changes" if tracked else "Comments") + " left in the file. Some ATSs "
                            "and every recruiter who opens the Word file can see them.",
                            "In Word: Review > Accept All Changes, and delete all comments, before sending."))
    p = re.search(r"<Pages>(\d+)</Pages>", app)
    facts["pages"] = int(p.group(1)) if p else None
    facts["words"] = len(body.split())
    facts["right_to_left"] = bool(RTL_CHAR.search(body) or any(on(t) for t in tags(doc, "bidi") + tags(doc, "rtl")))
    if facts["right_to_left"]:
        issues.append(issue("info", "Right-to-left text (Hebrew/Arabic). Some parsers reverse it in PDFs.",
                            "After exporting, run this script on the PDF with --against the .docx; send the .docx if words come out reversed."))
    pd = sorted({m.group(0).lower() for m in PERSONAL.finditer(body)})
    facts["personal_details"] = pd
    if pd:
        issues.append(issue("info", "Personal details found: " + ", ".join(pd) + ". Expected in some countries, left out in others.",
                            "Check the job's country rules (references/countries.md) and ask the candidate."))
    if media:
        issues.append(issue("info", f"{len(media)} image(s) (a photo or icons?).",
                            "A photo is left out in the US, UK, Canada, Australia, Israel. Icons are fine if the same info is also text."))
    return facts, issues


def pdf_text(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        fail("pypdf is not installed: pip install pypdf")
    if path.stat().st_size > MAX_PDF_BYTES:
        fail(f"The PDF is over {MAX_PDF_BYTES // 1_000_000} MB, too big for a resume.")
    try:
        r = PdfReader(str(path))
        if len(r.pages) > MAX_PDF_PAGES:
            fail(f"The PDF has {len(r.pages)} pages, too many for a resume.")
        pages = [(pg.extract_text() or "")[:200_000] for pg in r.pages]
        meta = r.metadata or {}
        tool = " / ".join(str(meta.get(k)) for k in ("/Creator", "/Producer") if meta.get(k))
    except Exception as e:  # damaged or encrypted files
        fail(f"Could not read the PDF: {e}")
    return pages, tool


def column_share(path):
    """Share of lines whose second text block starts at the same position (two-column layouts).
    Tested on the eval PDFs: two-column 0.69, single-column with right-aligned dates at most 0.14."""
    from collections import Counter
    try:
        from pypdf import PdfReader
        lines = []
        for pg in PdfReader(str(path)).pages[:MAX_PDF_PAGES]:
            lines += [l for l in (pg.extract_text(extraction_mode="layout") or "")[:200_000].splitlines() if l.strip()]
    except Exception:  # older pypdf without layout mode, or an unusual file: skip this check
        return 0.0
    # A real left column has some text before the gap: a bullet with a hanging indent ("•     Built…") doesn't count.
    starts = Counter(round(m.end() / 3) for l in lines for m in re.finditer(r"\S {5,}(?=\S)", l[:2000])
                     if len(l[:m.start() + 1].strip()) >= 8)
    if not lines or not starts:
        return 0.0
    top = starts.most_common(1)[0][0]
    near = sum(v for k, v in starts.items() if abs(k - top) <= 1)
    return round(near / len(lines), 2) if near >= 5 else 0.0


def inspect_pdf(path, against=None):
    pages, tool = pdf_text(path)
    text = "\n".join(pages)
    facts = {"pages": len(pages), "mb": round(path.stat().st_size / 1e6, 2), "made_with": tool,
             "chars_per_page": [len(p.strip()) for p in pages]}
    issues = []
    if not text.strip() or min(facts["chars_per_page"] or [0]) < 50:
        issues.append(issue("high", "Little or no text layer: the PDF is (partly) an image. An ATS reads nothing from it.",
                            "Export from Word/LibreOffice, not from a scan, a screenshot or a design tool."))
    if facts["mb"] > 2:
        issues.append(issue("high", f"PDF is {facts['mb']} MB. LinkedIn and many forms reject files over 2 MB.",
                            "Re-export; export_pdf.py shrinks oversized fonts."))
    if re.search(r"canva|illustrator|indesign|figma|photoshop", tool, re.I):
        issues.append(issue("medium", f"Made with a design tool ({tool}). These PDFs often parse in the wrong order.",
                            "Rebuild it as a single-column Word file (build_docx.py)."))
    cols = column_share(path)
    facts["column_layout_share"] = cols
    if cols >= 0.35:
        issues.append(issue("high", "The PDF looks like a two-column layout: many lines have a second block of text "
                                    "starting at the same position. Many ATSs read such columns mixed together.",
                            "Rebuild it as a single-column file (build_docx.py)."))
    garbled = len(re.findall(r"\(cid:\d+\)|�|[-]", text))
    facts["garbled_chars"] = garbled
    if garbled > 5:
        issues.append(issue("high", f"{garbled} characters come out of the PDF as garbage (missing font mapping, "
                                    "often ligatures like 'fi' or icon fonts). Words with them can't be searched.",
                            "Export again from Word or LibreOffice with standard fonts, or send the .docx."))
    facts["email_found"] = bool(EMAIL.search(text))
    facts["phone_found"] = bool(PHONE.search(text))
    if not facts["email_found"]:
        issues.append(issue("high", "The email address can't be read from the PDF.", "Put it in the body as plain text."))

    if against:
        paras = [p for p in docx_paragraphs(against) if len(norm(p)) >= 3]
        flat = norm(text)
        flat_nospace = flat.replace(" ", "")
        pos, missing, out_of_order = -1, [], []
        for p in paras:
            key = norm(p)
            i = flat.find(key, max(pos, 0))  # look after the previous paragraph first (repeated short lines)
            if i < 0:
                i = flat.find(key)
            if i < 0:
                j = flat_nospace.find(key.replace(" ", ""))
                i = j if j >= 0 else -1
                # positions in the no-space text aren't comparable, so the order check skips this one
                if i < 0:
                    missing.append(p)
                continue
            if i < pos:
                out_of_order.append(p)
            pos = max(pos, i)
        reversed_words = []
        pdf_words = set(RTL_WORD.findall(text))
        for p in paras:
            for w in RTL_WORD.findall(p):
                if w not in pdf_words and w[::-1] in pdf_words and w != w[::-1]:
                    reversed_words.append(w)
        rtl_missing = [p for p in missing if RTL_CHAR.search(p)]
        missing = [p for p in missing if not RTL_CHAR.search(p)]
        facts.update(paragraphs=len(paras), missing=len(missing), rtl_scrambled=len(rtl_missing),
                     out_of_order=len(out_of_order), reversed_rtl_words=len(set(reversed_words)))
        if rtl_missing:
            mixed = sum(1 for p in rtl_missing if re.search(r"[A-Za-z]", p))
            issues.append(issue("high", f"{len(rtl_missing)} right-to-left paragraphs come out of the PDF scrambled "
                                        f"({mixed} of them mix Hebrew/Arabic with English), e.g. "
                                + json.dumps(rtl_missing[:2], ensure_ascii=False),
                                "Send the .docx where the form accepts it (ATSs read Word text in logical order). If only "
                                "a PDF is accepted, keep it, but for an English posting offer an English version."))
        if missing:
            issues.append(issue("high" if len(missing) > max(2, len(paras) // 10) else "medium",
                                f"{len(missing)} of {len(paras)} paragraphs don't come out of the PDF as written, e.g. "
                                + json.dumps(missing[:3], ensure_ascii=False),
                                "Usually columns, tables or text boxes. Use a single-column layout."))
        if out_of_order:
            issues.append(issue("high", f"{len(out_of_order)} paragraphs come out in the wrong order, e.g. "
                                + json.dumps(out_of_order[:3], ensure_ascii=False),
                                "Use a single-column layout without tables or text boxes."))
        if reversed_words:
            issues.append(issue("high", f"{len(set(reversed_words))} Hebrew/Arabic words come out reversed, e.g. "
                                + ", ".join(sorted(set(reversed_words))[:5]),
                                "Send the .docx where the form accepts it, and try exporting the PDF from Word."))
    return facts, issues


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--against", help="the .docx this PDF was made from (checks order and right-to-left words)")
    a = ap.parse_args()
    path = Path(a.file)
    if not path.is_file():
        fail(f"File not found: {path}")
    kind = path.suffix.lower().lstrip(".")
    if kind == "docx":
        facts, issues = inspect_docx(path)
    elif kind == "pdf":
        against = Path(a.against) if a.against else None
        if against and (not against.is_file() or against.suffix.lower() != ".docx"):
            fail(f"--against must be a .docx file: {against}")
        facts, issues = inspect_pdf(path, against)
    else:
        fail("Give a .docx or .pdf file.")
    order = {"high": 0, "medium": 1, "info": 2}
    issues.sort(key=lambda i: order[i["level"]])
    print(json.dumps({"file": str(path), "kind": kind, "facts": facts, "issues": issues}, ensure_ascii=False, indent=2))
    sys.exit(1 if any(i["level"] == "high" for i in issues) else 0)


if __name__ == "__main__":
    main()
