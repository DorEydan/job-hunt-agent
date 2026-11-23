#!/usr/bin/env python3
"""Reorder the skills in the base resume to fit one job, and export it as PDF.

Minimal change by design: it only reorders the items inside the existing
"Technical Skills" lines (and, optionally, the order of those lines).
It never adds, removes or renames a skill, and it verifies that every other
paragraph of the resume is unchanged before writing the output.

Usage:
  python tools/tailor_resume.py --variant devops --list
  python tools/tailor_resume.py --variant devops --out "applications/<folder>" \
      --first "Languages=Python,JavaScript" \
      --first "Tools/Platforms=AWS,GitHub,SQL" \
      [--line-order "Tools/Platforms,Languages,AI"]

--first  LABEL=a,b,c   puts a, b, c first in that line (in that order); the
                       remaining items keep their original order.
--line-order a,b,c     reorders the skill lines themselves (optional).
--no-pdf               write only the .docx (the PDF is what gets sent).
"""
import argparse
import html
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_config, resume_variants  # noqa: E402

CONFIG = load_config()

P_RE = re.compile(r"<w:p[ >].*?</w:p>", re.S)
R_RE = re.compile(r"<w:r[ >].*?</w:r>", re.S)
T_RE = re.compile(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>")
RPR_RE = re.compile(r"<w:rPr>.*?</w:rPr>", re.S)
DEFAULT_RPR = '<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>'


def text_of(xml):
    return "".join(html.unescape(t) for t in T_RE.findall(xml))


def parse_line(text):
    label, rest = text.split(":", 1)
    items = [s.strip() for s in rest.strip().rstrip(".").split(",") if s.strip()]
    return label.strip(), items


def find_skill_lines(doc_xml):
    """Return [(match, label, items)] for the lines under the skills heading."""
    heading = CONFIG["skills_heading"].strip().lower()
    paras = list(P_RE.finditer(doc_xml))
    for i, m in enumerate(paras):
        if text_of(m.group(0)).strip().lower() == heading:
            lines = []
            for n in paras[i + 1:]:
                t = text_of(n.group(0))
                if ":" not in t:
                    break
                label, items = parse_line(t)
                lines.append((n, label, items))
            if not lines:
                sys.exit(f"No skill lines found under '{CONFIG['skills_heading']}'.")
            return lines
    sys.exit(f"Heading '{CONFIG['skills_heading']}' not found in the base resume.")


def split_label_run(p_xml):
    """If the label and the values share one run ("Languages: A, B"), split it in two at the ':'."""
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


def rebuild_paragraph(p_xml, items):
    """Keep the bold label runs, replace the value runs with one run."""
    p_xml = split_label_run(p_xml)
    runs = list(R_RE.finditer(p_xml))
    acc, label_end = "", None
    for idx, r in enumerate(runs):
        acc += text_of(r.group(0))
        if ":" in acc:
            label_end = idx
            break
    if label_end is None:
        raise ValueError("label ':' not found in paragraph")
    # keep whitespace-only runs right after the label (the space after ':')
    while label_end + 1 < len(runs) and text_of(runs[label_end + 1].group(0)).strip() == "":
        label_end += 1
    value_runs = runs[label_end + 1:]
    if not value_runs:
        raise ValueError("no value runs after the label")
    rpr_m = RPR_RE.search(value_runs[0].group(0))
    rpr = rpr_m.group(0) if rpr_m else DEFAULT_RPR
    new_run = f'<w:r>{rpr}<w:t xml:space="preserve">{escape(", ".join(items) + ".")}</w:t></w:r>'
    start, end = value_runs[0].start(), value_runs[-1].end()
    leftover = R_RE.sub("", p_xml[start:end])  # keep bookmarks/proofErr etc.
    return p_xml[:start] + new_run + leftover + p_xml[end:]


def reorder(items, first, label):
    lookup = {i.lower(): i for i in items}
    picked = []
    for want in first:
        key = want.strip().lower()
        if key not in lookup:
            sys.exit(f"'{want}' is not a skill in line '{label}'. Valid: {items}")
        if lookup[key] not in picked:
            picked.append(lookup[key])
    return picked + [i for i in items if i not in picked]


def safe_name(s):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip(" .")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print the current skill lines")
    ap.add_argument("--out", help="output folder (created if missing)")
    ap.add_argument("--first", action="append", default=[], metavar="LABEL=a,b,c")
    ap.add_argument("--line-order", help="comma-separated labels")
    ap.add_argument("--no-pdf", action="store_true")
    variants = resume_variants(CONFIG)
    if not variants:
        sys.exit("No base resume set. Add one in the setup page (config.json -> base_resumes).")
    ap.add_argument("--variant", choices=sorted(variants), default=None,
                    help="which base resume to use (config.json -> base_resumes); optional if there is only one")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if args.variant is None:
        if len(variants) > 1:
            ap.error(f"--variant is required, one of: {', '.join(sorted(variants))}")
        args.variant = next(iter(variants))
    base = Path(variants[args.variant])
    if not base.exists():
        sys.exit(f"Base resume not found: {base}")
    with zipfile.ZipFile(base) as z:
        doc_xml = z.read("word/document.xml").decode("utf-8")
    lines = find_skill_lines(doc_xml)

    if args.list:
        print(json.dumps({lbl: items for _, lbl, items in lines}, ensure_ascii=False, indent=2))
        return
    if not args.out:
        ap.error("--out is required (or use --list)")

    by_label = {lbl.lower(): (m, lbl, items) for m, lbl, items in lines}
    new_items = {lbl: items for _, lbl, items in lines}
    for spec in args.first:
        if "=" not in spec:
            ap.error(f"--first must look like LABEL=a,b,c (got {spec!r})")
        lbl, vals = spec.split("=", 1)
        if lbl.strip().lower() not in by_label:
            sys.exit(f"Unknown skill line '{lbl}'. Valid: {[l for _, l, _ in lines]}")
        real = by_label[lbl.strip().lower()][1]
        new_items[real] = reorder(new_items[real], vals.split(","), real)

    new_paras = {lbl: rebuild_paragraph(m.group(0), new_items[lbl]) for m, lbl, _ in lines}

    order = [l for _, l, _ in lines]
    if args.line_order:
        wanted = [by_label.get(x.strip().lower(), (None, None))[1] for x in args.line_order.split(",")]
        if None in wanted:
            sys.exit(f"--line-order has an unknown label. Valid: {order}")
        order = wanted + [l for l in order if l not in wanted]

    first_m, last_m = lines[0][0], lines[-1][0]
    between = doc_xml[first_m.start():last_m.end()]
    for m, _, _ in lines:
        between = between.replace(m.group(0), "", 1)
    if between.strip() and args.line_order:
        sys.exit("Skill lines are not adjacent in the XML; --line-order is not safe here.")
    block = "".join(new_paras[l] for l in order) + between
    out_xml = doc_xml[:first_m.start()] + block + doc_xml[last_m.end():]

    # Self-check: same skills per line, every other paragraph untouched.
    check = find_skill_lines(out_xml)
    for _, lbl, items in check:
        orig = next(i for _, l, i in lines if l == lbl)
        if sorted(items) != sorted(orig):
            sys.exit(f"Self-check failed: skills changed in '{lbl}'.")
    skill_texts = {text_of(m.group(0)) for m, _, _ in lines} | {text_of(m.group(0)) for m, _, _ in check}
    rest_old = [text_of(p) for p in P_RE.findall(doc_xml) if text_of(p) not in skill_texts]
    rest_new = [text_of(p) for p in P_RE.findall(out_xml) if text_of(p) not in skill_texts]
    if rest_old != rest_new:
        sys.exit("Self-check failed: text outside the skills section changed.")

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    name = safe_name(CONFIG.get("resume_output_name", base.stem))
    docx_path = out_dir / f"{name}.docx"
    with zipfile.ZipFile(base) as src, zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename.endswith("/"):
                continue
            data = out_xml.encode("utf-8") if info.filename == "word/document.xml" else src.read(info)
            dst.writestr(info, data)

    result = {"variant": args.variant, "base": str(base), "docx": str(docx_path), "skills": {l: new_items[l] for l in order}}
    if not args.no_pdf:
        pdf_path = out_dir / f"{name}.pdf"
        ps1 = ROOT / "tools" / "docx_to_pdf.ps1"
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1),
             "-Docx", str(docx_path.resolve()), "-Pdf", str(pdf_path.resolve())],
            check=True,
        )
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            sys.exit("PDF export failed.")
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            from shrink_pdf import shrink  # needs the project's .venv (fonttools, pypdf)
            shrink(pdf_path)
        except ImportError:
            result["warning"] = "PDF not shrunk: run this script with .venv\\Scripts\\python.exe"
        result["pdf"] = str(pdf_path)
        result["pdf_mb"] = round(pdf_path.stat().st_size / 1e6, 2)
        if result["pdf_mb"] > 2:
            result["warning"] = "PDF is over 2 MB - LinkedIn and some sites will reject it."
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
