#!/usr/bin/env python3
"""Check that a tailored resume adds no facts: no new numbers, no new skills or tools, no new terms from the posting.

  python verify_facts.py ORIGINAL TAILORED [--posting posting.txt]

Files can be .docx, .pdf, .md or .txt. Rewording is allowed; what this catches
is content that wasn't in the original: a number, a percentage, an amount, a capitalized term or tool name, or a
word from the posting that the candidate never wrote. Placeholders like [number?] or [fill in] are fine.

Output is JSON {"ok", "added_numbers", "added_terms", "added_from_posting", "removed_lines"}.
Exit code 0 = nothing added, 1 = something was added (show it to the candidate), 2 = could not read a file.
"""
import argparse
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_safe import DocxError, open_docx  # noqa: E402

MAX_PART = 8_000_000
NUM = re.compile(r"\d+(?:[.,]\d+)*\s?%?")  # every digit run, with or without a unit after it
TERM = re.compile(r"(?<![\w.#+])(?:[A-Z][\w.#+/-]*[A-Z0-9#+][\w.#+/-]*|[A-Z][a-z]+[A-Z][\w]*|\.[A-Z]{2,}|[A-Z]{2,}[\w#+]*|[A-Z][a-z]{2,})(?![\w#+])")
PLACEHOLDER = re.compile(r"\[[^\]\[]{0,40}\?\]|\[(?:fill in|tbd|todo|add [^\]]{1,30})\]", re.I)
COMMON = {  # capitalized words that are not facts
    "The", "And", "For", "With", "From", "Into", "Over", "Under", "Built", "Led", "Ran", "Wrote", "Created", "Managed",
    "Improved", "Reduced", "Designed", "Developed", "Maintained", "Set", "Summary", "Profile", "Skills", "Experience",
    "Education", "Projects", "Languages", "Training", "Work", "Professional", "Technical", "Core", "Key", "Tools",
    "Present", "Current", "Now", "Today", "Remote", "Hybrid", "Junior", "Senior", "Responsible", "Supported", "Used",
    "Automated", "Deployed", "Configured", "Implemented", "Owned", "Delivered", "Launched", "Grew", "Cut", "Drove",
    "Collaborated", "Worked", "Helped", "Handled", "Analyzed", "Analysed", "Planned", "Coordinated", "Trained",
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
    "December", "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec",
}


def fail(msg):
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(2)


def read_text(path):
    p = Path(path)
    if not p.is_file():
        fail(f"File not found: {p}")
    if p.suffix.lower() == ".docx":
        try:
            z, xml = open_docx(p)
            z.close()
        except DocxError as e:
            fail(str(e))
        xml = re.sub(r"<w:(?:tab|br|cr)\b[^>]*/>", "<w:t> </w:t>", xml)  # these separate words: keep a space
        paras = re.findall(r"<w:p(?:\s[^>]*)?(?<!/)>.*?</w:p>", xml, re.S)
        return "\n".join("".join(html.unescape(t) for t in re.findall(r"<w:t(?:\s[^>]*)?(?<!/)>([^<]*)</w:t>", x))
                         for x in paras)
    if p.suffix.lower() in (".md", ".txt", ""):
        if p.stat().st_size > MAX_PART:
            fail(f"{p} is too large.")
        return p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() == ".pdf":  # e.g. the candidate's original was a design-tool PDF
        if p.stat().st_size > 30_000_000:
            fail(f"{p} is too large.")
        try:
            from pypdf import PdfReader
        except ImportError:
            fail("pypdf is needed to read a PDF: pip install pypdf")
        try:
            r = PdfReader(str(p))
            if len(r.pages) > 30:
                fail("The PDF has too many pages for a resume.")
            return "\n".join((pg.extract_text() or "")[:200_000] for pg in r.pages)
        except Exception as e:  # damaged or encrypted files
            fail(f"Could not read the PDF: {e}")
    fail(f"Use .docx, .pdf, .md or .txt (got {p.suffix}).")


def clean(s):
    s = unicodedata.normalize("NFKC", s)
    s = PLACEHOLDER.sub(" ", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)  # markdown links keep their text
    s = re.sub(r"(?m)^\s*#+\s*", "", s)  # markdown headings (C# and F# stay)
    return re.sub(r"[*_`>|]", " ", s)


def numbers(s):
    out = set()
    for m in NUM.finditer(s):
        n = re.sub(r"[\s,]", "", m.group(0)).lower().rstrip(".")
        if n:
            out.add(n)
    return out


def terms(s):
    return {m.group(0).strip(".") for m in TERM.finditer(s)} - COMMON


def posting_words(s):
    words = set()
    for m in re.finditer(r"(?<![\w#+])[A-Za-zÀ-ž֐-׿؀-ۿ][\w.#+/-]+", s):
        words.add(m.group(0).lower().strip("."))
    return words


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("tailored")
    ap.add_argument("--posting", help="the job posting as .txt/.md; flags posting words the original never used")
    a = ap.parse_args()
    old, new = clean(read_text(a.original)), clean(read_text(a.tailored))
    old_low = old.lower()

    added_numbers = sorted(numbers(new) - numbers(old))
    old_terms_low = {t.lower() for t in terms(old)}
    # whole words only: "Java" inside "JavaScript" or "AI" inside "email" doesn't count as already there
    added_terms = sorted(t for t in terms(new) if t.lower() not in old_terms_low
                         and not re.search(r"(?<![\w#+])" + re.escape(t.lower()) + r"(?![\w#+])", old_low))
    added_from_posting = []
    if a.posting:
        pw = posting_words(clean(read_text(a.posting)))
        new_words = posting_words(new)
        old_words = posting_words(old)
        added_from_posting = sorted(w for w in (new_words & pw) - old_words if w not in {x.lower() for x in COMMON})
    old_lines = [l.strip() for l in old.splitlines() if len(l.strip()) > 3]
    new_flat = re.sub(r"\s+", " ", new.lower())

    def items_key(line):  # "Label: a, b, c" in any order
        if ":" not in line:
            return None
        label, rest = line.lower().split(":", 1)
        return label.strip(), tuple(sorted(i.strip(" .") for i in rest.split(",") if i.strip(" .")))

    new_keys = {items_key(l) for l in new.splitlines()} - {None}
    removed = [l for l in old_lines if re.sub(r"\s+", " ", l.lower()) not in new_flat and items_key(l) not in new_keys]

    ok = not (added_numbers or added_terms or added_from_posting)
    print(json.dumps({"ok": ok, "added_numbers": added_numbers, "added_terms": added_terms,
                      "added_from_posting": added_from_posting, "removed_lines": removed[:40],
                      "note": "Added items need the candidate's confirmation that they are true. Removed lines are "
                              "fine only if the candidate approved removing them (reworded lines also show here)."},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
