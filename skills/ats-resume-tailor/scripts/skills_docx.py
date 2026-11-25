#!/usr/bin/env python3
"""Reorder a .docx resume for one job, keeping everything else byte-for-byte.

Reordering is the only change this script can make: it never adds, removes, rewords or renames anything,
and it checks, paragraph by paragraph, that nothing else changed before it writes the output.

Skill lines ("Cloud & containers: AWS, Docker" under a skills heading):
  python skills_docx.py list resume.docx [--heading "Technical Skills"]
  python skills_docx.py reorder resume.docx --out DIR [--name NAME]
        --first "Scripting=Bash,Python" [--first ...] [--line-order "Scripting,Cloud & containers"]
Whole paragraphs (the bullets of one job, or a skills list with one skill per line):
  python skills_docx.py paras resume.docx                       # numbers every paragraph
  python skills_docx.py move resume.docx --out DIR --order 14,12,13 [--order 20,19]

Output is JSON. Exit code 2 = bad input or a failed check (message on stderr, nothing written), 0 = OK.
"""
import argparse
import html
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_safe import DocxError, open_docx, parse_xml, read_bounded  # noqa: E402

# Opening tags must not be self-closing (<w:p w:rsidR="1"/>), or the match would swallow the next paragraph.
P_RE = re.compile(r"<w:p(?:\s[^>]*)?(?<!/)>.*?</w:p>", re.S)
R_RE = re.compile(r"<w:r(?:\s[^>]*)?(?<!/)>.*?</w:r>", re.S)
T_RE = re.compile(r"<w:t(?:\s[^>]*)?(?<!/)>([^<]*)</w:t>")
RPR_RE = re.compile(r"<w:rPr>.*?</w:rPr>", re.S)
UNSAFE_IN_LINE = re.compile(r"<w:(hyperlink|ins|del|moveFrom|moveTo|sdt|fldChar|instrText|fldSimple|drawing|pict|"
                            r"object|txbxContent|smartTag|customXml)\b")
UNSAFE_IN_VALUE = re.compile(r"<w:(tab|br|cr|sym|noBreakHyphen|softHyphen|footnoteReference|commentReference)\b")
WIN_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
HEADINGS = {
    "skills", "technical skills", "core skills", "key skills", "skills & tools", "skills and tools", "tech stack",
    "technologies", "core competencies", "competencies", "tools & technologies", "skills summary",
    "כישורים", "כישורים טכניים", "מיומנויות", "מיומנויות טכניות", "ידע טכני", "כלים וטכנולוגיות",
    "umiejętności", "umiejętności techniczne", "kenntnisse", "fähigkeiten", "it-kenntnisse", "kompetenzen",
    "compétences", "compétences techniques", "vaardigheden", "habilidades", "competencias", "competenze",
}


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def text_of(xml):
    return "".join(html.unescape(t) for t in T_RE.findall(xml))


def split_items(rest):
    """Split on commas outside parentheses: 'AWS (EC2, S3), Docker' -> ['AWS (EC2, S3)', 'Docker']."""
    items, depth, cur = [], 0, ""
    for ch in rest:
        depth += ch in "([{"
        depth -= ch in ")]}" and depth > 0
        if ch == "," and depth == 0:
            items.append(cur)
            cur = ""
        else:
            cur += ch
    items.append(cur)
    return [i.strip() for i in items if i.strip()]


def is_skill_line(t):
    if ":" not in t:
        return False
    label, rest = t.split(":", 1)
    return 0 < len(label.strip()) <= 60 and bool(rest.strip())


def parse_line(text):
    label, rest = text.split(":", 1)
    return label.strip(), split_items(rest.strip().rstrip("."))


def load(path):
    p = Path(path)
    if not p.is_file() or p.suffix.lower() != ".docx":
        fail(f"Not a .docx file: {p}")
    try:
        z, doc = open_docx(p)
    except DocxError as e:
        fail(str(e))
    z.close()
    return doc


def find_skill_lines(doc_xml, heading=None):
    """([(match, label, items)], heading text) for the lines under the skills heading."""
    paras = list(P_RE.finditer(doc_xml))
    texts = [text_of(m.group(0)).strip() for m in paras]
    wanted = {heading.strip().lower().rstrip(":")} if heading else HEADINGS
    for i, t in enumerate(texts):
        if t.lower().rstrip(":").strip() in wanted:
            lines = []
            for m, nt in zip(paras[i + 1:], texts[i + 1:]):
                if not nt and not lines:
                    continue
                if not is_skill_line(nt):
                    break
                label, items = parse_line(nt)
                lines.append((m, label, items))
            if lines:
                return lines, t
    short = [t for t in texts if 0 < len(t) <= 40 and not is_skill_line(t)][:40]
    fail("No skills heading with 'Label: a, b' lines found. Pass --heading with the exact heading text.\n"
         "Short paragraphs in this file: " + json.dumps(short, ensure_ascii=False))


def split_label_run(p_xml):
    """If the label and the values share one run ("Languages: A, B"), split it in two after the ': '."""
    acc = ""
    for r in R_RE.finditer(p_xml):
        t = text_of(r.group(0))
        if ":" in acc + t:
            cut = t.index(":") + 1 if ":" in t else 0
            while cut < len(t) and t[cut] == " ":
                cut += 1
            if cut == 0 or cut >= len(t) or "<w:t" not in r.group(0):
                return p_xml
            rpr_m = RPR_RE.search(r.group(0))
            rpr = rpr_m.group(0) if rpr_m else ""
            two = (f'<w:r>{rpr}<w:t xml:space="preserve">{escape(t[:cut])}</w:t></w:r>'
                   f'<w:r>{rpr}<w:t xml:space="preserve">{escape(t[cut:])}</w:t></w:r>')
            return p_xml[:r.start()] + two + p_xml[r.end():]
        acc += t
    return p_xml


def rebuild_paragraph(p_xml, items, label):
    """Keep the label runs (and their formatting), replace the value runs with one run of the same format."""
    if UNSAFE_IN_LINE.search(p_xml):
        fail(f"The skill line '{label}' contains a link, field, tracked change or object. Accept the changes or "
             "remove the link in Word, or use the clean rebuild (build_docx.py). Nothing was written.")
    end_dot = text_of(p_xml).rstrip().endswith(".")
    p_xml = split_label_run(p_xml)
    runs = list(R_RE.finditer(p_xml))
    acc, label_end = "", None
    for idx, r in enumerate(runs):
        acc += text_of(r.group(0))
        if ":" in acc:
            label_end = idx
            break
    if label_end is None:
        fail(f"Could not find the ':' after '{label}'.")
    while label_end + 1 < len(runs) and text_of(runs[label_end + 1].group(0)).strip() == "":
        label_end += 1
    value_runs = runs[label_end + 1:]
    if not value_runs:
        fail(f"No skills after the label '{label}'.")
    if any(UNSAFE_IN_VALUE.search(r.group(0)) for r in value_runs):
        fail(f"The skill line '{label}' has tabs, line breaks or symbols between the skills, which reordering "
             "would lose. Reorder it by hand, or use the clean rebuild (build_docx.py). Nothing was written.")
    first_text = text_of(value_runs[0].group(0))
    lead = first_text[:len(first_text) - len(first_text.lstrip())]
    rpr_m = RPR_RE.search(value_runs[0].group(0))
    rpr = rpr_m.group(0) if rpr_m else ""  # no formatting before = no formatting after
    value = lead + ", ".join(items) + ("." if end_dot else "")
    new_run = f'<w:r>{rpr}<w:t xml:space="preserve">{escape(value)}</w:t></w:r>'
    start, end = value_runs[0].start(), value_runs[-1].end()
    leftover = R_RE.sub("", p_xml[start:end])  # keep bookmarks, proofErr and similar empty markers
    return p_xml[:start] + new_run + leftover + p_xml[end:]


def reorder(items, first, label):
    rest = list(items)
    picked = []
    for want in first:
        key = want.strip().lower()
        if not key:
            continue
        hit = next((i for i in rest if i.lower() == key), None)
        if hit is None:
            if any(i.lower() == key for i in picked):
                continue
            fail(f"'{want.strip()}' is not a skill in line '{label}'. This script only reorders. Valid: {items}")
        rest.remove(hit)
        picked.append(hit)
    return picked + rest


def safe_name(s):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip(" .")[:80] or "resume"
    return "_" + s if s.split(".")[0].lower() in WIN_RESERVED else s


def cmd_list(a):
    lines, heading = find_skill_lines(load(a.docx), a.heading)
    print(json.dumps({"heading": heading, "skills": {lbl: items for _, lbl, items in lines}}, ensure_ascii=False, indent=2))


def cmd_reorder(a):
    src = Path(a.docx)
    doc_xml = load(src)
    lines, heading = find_skill_lines(doc_xml, a.heading)
    labels = [lbl for _, lbl, _ in lines]
    if len({l.lower() for l in labels}) != len(labels):
        fail(f"Two skill lines have the same label ({labels}). Rename one in Word first.")
    by_label = {lbl.lower(): lbl for lbl in labels}
    new_items = {lbl: items for _, lbl, items in lines}
    for spec in a.first:
        if "=" not in spec:
            fail(f"--first must look like LABEL=a,b,c (got {spec!r})")
        lbl, vals = spec.split("=", 1)
        real = by_label.get(lbl.strip().lower())
        if not real:
            fail(f"Unknown skill line '{lbl}'. Valid: {labels}")
        new_items[real] = reorder(new_items[real], split_items(vals), real)

    new_paras = {lbl: rebuild_paragraph(m.group(0), new_items[lbl], lbl) for m, lbl, _ in lines}
    order = labels
    if a.line_order:
        wanted = [by_label.get(x.strip().lower()) for x in split_items(a.line_order)]
        if None in wanted:
            fail(f"--line-order has an unknown label. Valid: {labels}")
        order = list(dict.fromkeys(wanted)) + [l for l in labels if l not in wanted]

    if order == labels:  # replace each line in place
        out_xml, pos = "", 0
        for m, lbl, _ in lines:
            out_xml += doc_xml[pos:m.start()] + new_paras[lbl]
            pos = m.end()
        out_xml += doc_xml[pos:]
    else:
        first_m, last_m = lines[0][0], lines[-1][0]
        gaps = [doc_xml[lines[k][0].end():lines[k + 1][0].start()] for k in range(len(lines) - 1)]
        if any(g.strip() for g in gaps):
            fail("The skill lines are not next to each other in the file, so changing their order is not safe here. "
                 "Reorder the skills inside each line only (drop --line-order).")
        out_xml = doc_xml[:first_m.start()] + "".join(new_paras[l] for l in order) + doc_xml[last_m.end():]

    # Self-check, by position: every paragraph is identical except the skill lines, which hold the same label and
    # exactly the same skills (as a multiset) in their new order.
    try:
        parse_xml(out_xml, "the new document")
    except DocxError as e:
        fail(f"Self-check failed: {e} Nothing was written.")
    old_p = [text_of(p) for p in P_RE.findall(doc_xml)]
    new_p = [text_of(p) for p in P_RE.findall(out_xml)]
    starts = [m.start() for m in P_RE.finditer(doc_xml)]
    idx = [starts.index(m.start()) for m, _, _ in lines]
    expected = list(old_p)
    for k, lbl in zip(idx, order):
        expected[k] = None  # a skill line goes here; checked below
    if len(new_p) != len(old_p) or any(e is not None and e != n for e, n in zip(expected, new_p)):
        fail("Self-check failed: text outside the skills lines changed. Nothing was written.")
    for k, lbl in zip(idx, order):
        got_label, got_items = parse_line(new_p[k])
        if got_label != lbl or sorted(got_items) != sorted(dict((l, i) for _, l, i in lines)[lbl]) \
                or got_items != new_items[lbl]:
            fail(f"Self-check failed: the line '{lbl}' would change more than its order. Nothing was written.")

    dst = write_docx(src, out_xml, a.out, a.name)
    old = {lbl: items for _, lbl, items in lines}
    changes = [f"Line order: {', '.join(order)}"] if order != labels else []
    changes += [f"{l}: {', '.join(new_items[l])}" for l in order if new_items[l] != old[l]]
    print(json.dumps({"docx": str(dst), "heading": heading, "skills": {l: new_items[l] for l in order},
                      "changes": changes or ["No change: the order already fits."]}, ensure_ascii=False, indent=2))


def write_docx(src, out_xml, out, name):
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{safe_name(name or src.stem)}.docx"
    if dst.exists() and (os.path.samefile(dst, src) or dst.is_symlink()):
        fail("The output would overwrite the original resume (or a link to it). Choose another --out or --name.")
    fd, tmp = tempfile.mkstemp(suffix=".docx", dir=out_dir)
    os.close(fd)
    try:
        with zipfile.ZipFile(src) as zs, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zd:
            for info in zs.infolist():
                if info.filename.endswith("/"):
                    continue
                if info.filename == "word/document.xml":
                    zd.writestr(zipfile.ZipInfo("word/document.xml", info.date_time), out_xml.encode("utf-8"),
                                compress_type=zipfile.ZIP_DEFLATED)
                else:
                    zd.writestr(info, read_bounded(zs, info))
        os.replace(tmp, dst)
    except Exception as e:
        Path(tmp).unlink(missing_ok=True)
        fail(f"Could not write the output: {e}")
    return dst


def ppr_kind(p_xml):
    """The paragraph's formatting (style, numbering, indent), without revision ids, plus whether it starts with a bullet."""
    m = re.search(r"<w:pPr>.*?</w:pPr>", p_xml, re.S)
    ppr = re.sub(r'\s+w:rsid\w*="[^"]*"', "", m.group(0)) if m else ""
    return ppr, text_of(p_xml).lstrip()[:1] in "•-–·*▪"


def cmd_paras(a):
    """Number every non-empty paragraph, so bullets (or a plain skills list) can be reordered with `move`."""
    doc = load(a.docx)
    out = []
    for i, m in enumerate(P_RE.finditer(doc)):
        t = text_of(m.group(0)).strip()
        if t:
            out.append({"i": i, "bullet": "<w:numPr>" in m.group(0) or t.startswith(("•", "-", "–", "·", "*", "▪")),
                        "text": t[:160]})
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_move(a):
    """Reorder whole paragraphs inside a block of neighbours: e.g. the bullets of one job, most relevant first."""
    src = Path(a.docx)
    doc = load(src)
    paras = list(P_RE.finditer(doc))
    texts = [text_of(m.group(0)) for m in paras]
    out_xml, last, done = "", 0, set()
    blocks = []
    for spec in a.order:
        try:
            idx = [int(x) for x in spec.split(",") if x.strip()]
        except ValueError:
            fail(f"--order takes paragraph numbers from `paras`, like 12,10,11 (got {spec!r}).")
        if len(idx) < 2 or len(set(idx)) != len(idx) or sorted(idx) != list(range(min(idx), max(idx) + 1)):
            fail(f"--order {spec}: give every paragraph of one block of neighbours exactly once (e.g. 10,11,12 in a new order).")
        if done & set(idx) or max(idx) >= len(paras):
            fail(f"--order {spec}: numbers overlap another block or don't exist.")
        lo, hi = min(idx), max(idx)
        for k in range(lo, hi):
            if doc[paras[k].end():paras[k + 1].start()].strip():
                fail(f"--order {spec}: paragraphs {k} and {k + 1} are not next to each other (a table or other "
                     "content sits between them).")
        kinds = {ppr_kind(paras[k].group(0)) for k in idx}
        if len(kinds) > 1:
            fail(f"--order {spec}: these paragraphs are formatted differently (a heading or a job title among "
                 "bullets?). Only reorder paragraphs of the same kind, inside one job or one list.")
        done |= set(idx)  # whole paragraphs move with everything inside them; the XML check below catches the rest
        blocks.append((lo, hi, idx))
    for lo, hi, idx in sorted(blocks):
        out_xml += doc[last:paras[lo].start()] + "".join(paras[k].group(0) for k in idx)
        last = paras[hi].end()
    out_xml += doc[last:]
    try:
        parse_xml(out_xml, "the new document")
    except DocxError as e:
        fail(f"Self-check failed: {e} Nothing was written.")
    expected = list(texts)
    for lo, _, idx in blocks:
        for n, k in enumerate(idx):
            expected[lo + n] = texts[k]
    if [text_of(p) for p in P_RE.findall(out_xml)] != expected:
        fail("Self-check failed: the result is not just a reordering. Nothing was written.")
    dst = write_docx(src, out_xml, a.out, a.name)
    changes = [f"Moved to the top: {texts[idx[0]].strip()[:90]}" for _, _, idx in blocks if idx[0] != min(idx)]
    print(json.dumps({"docx": str(dst), "changes": changes or ["Order changed inside the blocks."]},
                     ensure_ascii=False, indent=2))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("list")
    pl.add_argument("docx")
    pl.add_argument("--heading")
    pr = sub.add_parser("reorder")
    pr.add_argument("docx")
    pr.add_argument("--out", required=True)
    pr.add_argument("--name", help="output file name without extension (default: the input's name)")
    pr.add_argument("--heading")
    pr.add_argument("--first", action="append", default=[], metavar="LABEL=a,b,c")
    pr.add_argument("--line-order")
    pp = sub.add_parser("paras")
    pp.add_argument("docx")
    pm = sub.add_parser("move")
    pm.add_argument("docx")
    pm.add_argument("--out", required=True)
    pm.add_argument("--name")
    pm.add_argument("--order", action="append", required=True, metavar="12,10,11",
                    help="one block of neighbouring paragraphs in the new order (repeat for each job)")
    a = ap.parse_args()
    {"list": cmd_list, "reorder": cmd_reorder, "paras": cmd_paras, "move": cmd_move}[a.cmd](a)


if __name__ == "__main__":
    main()
