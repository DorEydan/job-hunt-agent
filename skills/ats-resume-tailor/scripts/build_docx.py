#!/usr/bin/env python3
"""Build a clean, ATS-friendly resume (.docx) from structured data, in one of eight single-column templates.

The skills section is written as "Label: skill, skill" lines under a skills heading, the format
skills_docx.py reorders per job, so a resume made here can be tailored right away.
It can also read an existing .docx into the same structure, to redesign it.

    python build_docx.py data.json --template tech --out my-resume.docx
    python build_docx.py --parse old-resume.docx        # prints the structure as JSON
"""
import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resume_profile  # noqa: E402

TEMPLATES = {
    "tech": {
        "label": "Tech", "for": "Developers, DevOps, data, QA, IT: skills near the top, compact.",
        "font": "Calibri", "size": 21, "accent": "2F5597", "name_size": 44, "center": False,
        "order": ["summary", "skills", "experience", "projects", "education", "certifications", "languages"],
    },
    "graduate": {
        "label": "Graduate / junior", "for": "Students and first jobs: education and projects first.",
        "font": "Calibri", "size": 21, "accent": "1F7A6B", "name_size": 44, "center": False,
        "order": ["summary", "education", "projects", "skills", "experience", "certifications", "languages"],
    },
    "professional": {
        "label": "Professional", "for": "Experienced candidates, product, sales: experience first, classic look.",
        "font": "Georgia", "size": 20, "accent": "333333", "name_size": 40, "center": True,
        "order": ["summary", "experience", "skills", "education", "projects", "certifications", "languages"],
    },
    "creative": {
        "label": "Creative", "for": "Design, marketing, content: portfolio and projects up front.",
        "font": "Arial", "size": 20, "accent": "C2410C", "name_size": 48, "center": False, "name_accent": True,
        "order": ["summary", "projects", "experience", "skills", "education", "certifications", "languages"],
    },
    "modern": {
        "label": "Modern", "for": "Startups and tech companies: a colored accent bar, still plain text for ATS.",
        "font": "Calibri", "size": 21, "accent": "6D28D9", "name_size": 46, "center": False, "name_accent": True,
        "heading": "bar", "order": ["summary", "skills", "experience", "projects", "education", "certifications", "languages"],
    },
    "minimal": {
        "label": "Minimal", "for": "Conservative fields (finance, government, law): black and white, nothing extra.",
        "font": "Calibri", "size": 21, "accent": "222222", "name_size": 40, "center": True, "heading": "plain",
        "order": ["summary", "experience", "education", "skills", "projects", "certifications", "languages"],
    },
    "compact": {
        "label": "Compact", "for": "A lot to fit on one page: smaller margins and type, same clean layout.",
        "font": "Calibri", "size": 19, "accent": "1D4ED8", "name_size": 36, "center": False, "margin": 540,
        "order": ["summary", "skills", "experience", "projects", "education", "certifications", "languages"],
    },
    "career-change": {
        "label": "Career change", "for": "Moving into a new field: transferable skills and projects before past jobs.",
        "font": "Calibri", "size": 21, "accent": "0F766E", "name_size": 44, "center": False,
        "order": ["summary", "skills", "projects", "education", "certifications", "experience", "languages"],
    },
}
TITLES = {"summary": "Professional Summary", "skills": None, "experience": "Work Experience", "projects": "Projects",
          "education": "Education", "certifications": "Courses & Certifications", "languages": "Languages"}
LETTER_COUNTRIES = {"United States", "Canada"}
TECH_FIELDS = {"software", "devops", "data", "qa", "it", "security"}
BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def recommend(field, level):
    if level in ("student", "entry"):
        return "graduate"
    if field in ("design", "marketing"):
        return "creative"
    if field in ("product", "sales") or level == "senior":
        return "professional"
    return "tech"


# ---------- validation ----------

def _s(v, n=300):
    return isinstance(v, str) and len(v) <= n


def validate(d):
    """Problems with the data (empty list = OK). Limits keep files and requests small."""
    errs = []
    if not isinstance(d, dict):
        return ["Resume data must be an object."]
    for k in ("name", "headline", "summary", "languages", "skills_heading"):
        if k in d and not _s(d[k], 2000 if k == "summary" else 200):
            errs.append(f"{k}: text, up to {2000 if k == 'summary' else 200} characters.")
    c = d.get("contact", {})
    if not isinstance(c, dict) or len(c) > 10 or not all(_s(v, 300) for v in c.values()):
        errs.append("contact: every field must be short text.")
    sk = d.get("skills", [])
    if not isinstance(sk, list) or len(sk) > 15 or not all(
            isinstance(x, dict) and _s(x.get("label", ""), 60) and ":" not in x.get("label", "")
            and isinstance(x.get("items", []), list) and len(x.get("items", [])) <= 40
            and all(_s(i, 80) and "," not in re.sub(r"\([^()]*\)", "", i) for i in x.get("items", [])) for x in sk):
        errs.append("skills: up to 15 groups; labels without ':'; no commas in a skill except inside parentheses.")
    for sec, keys in (("experience", ("title", "company", "location", "dates")), ("projects", ("name", "role", "dates", "link")),
                      ("education", ("degree", "school", "dates"))):
        v = d.get(sec, [])
        if not isinstance(v, list) or len(v) > 25:
            errs.append(f"{sec}: up to 25 entries.")
            continue
        for i, e in enumerate(v, 1):
            if not isinstance(e, dict) or not all(_s(e.get(k, ""), 200) for k in keys) or \
                    not isinstance(e.get("bullets", []), list) or len(e.get("bullets", [])) > 12 or \
                    not all(_s(b, 600) for b in e.get("bullets", [])):
                errs.append(f"{sec} #{i}: short text fields, up to 12 bullet lines of 600 characters.")
    certs = d.get("certifications", [])
    if not isinstance(certs, list) or len(certs) > 30 or not all(_s(x, 200) for x in certs):
        errs.append("certifications: up to 30 lines.")
    for i, e in enumerate(d.get("experience", []) if isinstance(d.get("experience"), list) else [], 1):
        roles = e.get("roles", []) if isinstance(e, dict) else []
        if not isinstance(roles, list) or len(roles) > 8 or not all(
                isinstance(r, dict) and _s(r.get("title", ""), 200) and _s(r.get("dates", ""), 200)
                and isinstance(r.get("bullets", []), list) and len(r.get("bullets", [])) <= 12
                and all(_s(b, 600) for b in r.get("bullets", [])) for r in roles):
            errs.append(f"experience #{i} roles: up to 8 of {{title, dates, bullets}}.")
    ex = d.get("extra_sections", [])
    if not isinstance(ex, list) or len(ex) > 10 or not all(
            isinstance(x, dict) and _s(x.get("title", ""), 80) and x.get("title")
            and x.get("after", "end") in (*TITLES, "end")
            and isinstance(x.get("lines", []), list) and len(x.get("lines", [])) <= 25
            and all(_s(l, 600) for l in x.get("lines", [])) for x in ex):
        errs.append("extra_sections: up to 10 of {title, lines: [...], bullets: true/false, after: section or 'end'}.")
    if "footer_note" in d and not _s(d["footer_note"], 1500):
        errs.append("footer_note: text up to 1500 characters (e.g. a GDPR/RODO consent clause).")
    ti = d.get("titles", {})
    if not isinstance(ti, dict) or not all(k in TITLES and _s(v, 60) for k, v in ti.items()):
        errs.append("titles: section name -> heading text, e.g. {\"experience\": \"Doświadczenie\"}.")
    if d.get("page") not in (None, "A4", "Letter"):
        errs.append("page: A4 or Letter.")
    return errs


# ---------- writing the .docx ----------

class Doc:
    def __init__(self, t, page):
        self.t, self.page = t, page
        self.body, self.links = [], []
        w = 12240 if page == "Letter" else 11906
        self.margin = t.get("margin", 720)
        self.width = w - 2 * self.margin

    def link(self, url):
        self.links.append(url)
        return f"rId{100 + len(self.links)}"

    def run(self, text, bold=False, italic=False, size=None, color=None, caps=False):
        text = BAD_XML.sub("", text)  # characters XML 1.0 does not allow (often pasted from PDFs)
        if "\t" in text:  # a real Word tab, so the right-aligned tab stop works everywhere
            return "<w:r><w:tab/></w:r>".join(self.run(x, bold, italic, size, color, caps) if x else "" for x in text.split("\t"))
        rpr = "".join([("<w:b/>" if bold else ""), ("<w:i/>" if italic else ""), ("<w:caps/>" if caps else ""),
                       (f'<w:color w:val="{color}"/>' if color else ""),
                       (f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else "")])
        return f'<w:r>{"<w:rPr>" + rpr + "</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'

    def hyper(self, text, url):
        text = BAD_XML.sub("", text)
        if not re.match(r"(?i)^(https?://|mailto:)\S+$", url) or BAD_XML.search(url):
            return self.run(text)
        rid = self.link(url)
        return (f'<w:hyperlink r:id="{rid}"><w:r><w:rPr><w:color w:val="{self.t["accent"]}"/></w:rPr>'
                f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:hyperlink>')

    def para(self, runs, after=40, before=0, center=False, indent=None, tab_right=False, border=False, keep=False):
        ppr = [f'<w:spacing w:before="{before}" w:after="{after}"/>']
        if center:
            ppr.append('<w:jc w:val="center"/>')
        if indent:
            ppr.append(f'<w:ind w:left="{indent[0]}" w:hanging="{indent[1]}"/>')
        if tab_right:
            ppr.append(f'<w:tabs><w:tab w:val="right" w:pos="{self.width}"/></w:tabs>')
        if border:
            ppr.append(f'<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="{self.t["accent"]}"/></w:pBdr>')
        if keep:
            ppr.append("<w:keepNext/>")
        self.body.append(f'<w:p><w:pPr>{"".join(ppr)}</w:pPr>{"".join(runs)}</w:p>')

    def heading(self, text):
        style = self.t.get("heading", "border")
        runs = [self.run(text, bold=True, size=self.t["size"] + 3, color=self.t["accent"], caps=True)]
        if style == "bar":  # a thick colored bar on the left
            self.body.append(f'<w:p><w:pPr><w:keepNext/><w:pBdr><w:left w:val="single" w:sz="24" w:space="6" '
                             f'w:color="{self.t["accent"]}"/></w:pBdr><w:spacing w:before="200" w:after="80"/>'
                             f'<w:ind w:left="120"/></w:pPr>{"".join(runs)}</w:p>')
        else:
            self.para(runs, before=200, after=80, border=style == "border", keep=True)

    def bullet(self, text):
        self.para([self.run("•\t" + text.strip().lstrip("•-–* ").strip())], after=20, indent=(360, 240))

    def entry(self, left_bold, left_rest, right):
        runs = [self.run(left_bold, bold=True)]
        if left_rest:
            runs.append(self.run(" | " + left_rest))
        if right:
            runs.append(self.run("\t" + right, color="555555"))
        self.para(runs, before=80, after=30, tab_right=True, keep=True)

    def xml(self):
        w, h = (12240, 15840) if self.page == "Letter" else (11906, 16838)
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'
                + "".join(self.body) +
                f'<w:sectPr><w:pgSz w:w="{w}" w:h="{h}"/>'
                f'<w:pgMar w:top="{self.margin}" w:right="{self.margin}" w:bottom="{self.margin}" w:left="{self.margin}" w:header="0" w:footer="0" w:gutter="0"/>'
                '</w:sectPr></w:body></w:document>')


def short_url(u):
    return re.sub(r"^(https?://)?(www\.)?", "", u).rstrip("/")


def extra(doc, x):
    """A section the templates don't have: military service, volunteering, awards, referees, publications…"""
    doc.heading(x["title"].strip())
    for line in x.get("lines", []):
        if line.strip():
            doc.bullet(line) if x.get("bullets", True) else doc.para([doc.run(line.strip())], after=30)


def build(d, template="tech"):
    """Return the .docx bytes."""
    errs = validate(d)
    if errs:
        raise ValueError("; ".join(errs))
    t = TEMPLATES.get(template) or TEMPLATES["tech"]
    doc = Doc(t, d.get("page") or "A4")
    c = d.get("contact", {})
    center = t["center"]
    doc.para([doc.run(d.get("name") or "Your Name", bold=True, size=t["name_size"],
                      color=t["accent"] if t.get("name_accent") else None)], after=0, center=center)
    if d.get("headline"):
        doc.para([doc.run(d["headline"], size=t["size"] + 5, color=t["accent"])], after=60, center=center)
    parts = []
    for key in ("city", "phone"):
        if c.get(key):
            parts.append(doc.run(c[key]))
    if c.get("email"):
        parts.append(doc.hyper(c["email"], "mailto:" + c["email"]))
    for key in ("linkedin", "github", "portfolio"):
        if c.get(key):
            url = c[key] if c[key].lower().startswith("http") else "https://" + c[key]
            parts.append(doc.hyper(short_url(c[key]), url))
    if parts:
        sep = doc.run("  |  ", color="999999")
        doc.para([x for i, p in enumerate(parts) for x in ((sep, p) if i else (p,))], after=120, center=center)

    heading = d.get("skills_heading") or "Technical Skills"
    titles = d.get("titles") or {}  # section headings in the resume's language
    for sec in t["order"]:
        if sec == "summary" and d.get("summary"):
            doc.heading(titles.get(sec) or TITLES[sec])
            doc.para([doc.run(d["summary"].strip())], after=40)
        elif sec == "skills" and d.get("skills"):
            doc.heading(heading)
            for g in d["skills"]:
                if g.get("items"):
                    doc.para([doc.run(g["label"].strip() + ": ", bold=True), doc.run(", ".join(i.strip() for i in g["items"]) + ".")],
                             after=30)
        elif sec == "experience" and d.get("experience"):
            doc.heading(titles.get(sec) or TITLES[sec])
            for e in d["experience"]:
                if e.get("roles"):  # promotions at one employer: the company once, then each role
                    doc.entry(e.get("company", ""), e.get("location", ""), e.get("dates", ""))
                    for r in e["roles"]:
                        doc.entry(r.get("title", ""), "", r.get("dates", ""))
                        for b in r.get("bullets", []):
                            if b.strip():
                                doc.bullet(b)
                    continue
                rest = " | ".join(x for x in (e.get("company", ""), e.get("location", "")) if x)
                doc.entry(e.get("title", ""), rest, e.get("dates", ""))
                for b in e.get("bullets", []):
                    if b.strip():
                        doc.bullet(b)
        elif sec == "projects" and d.get("projects"):
            doc.heading(titles.get(sec) or TITLES[sec])
            for p in d["projects"]:
                runs = [doc.run(p.get("name", ""), bold=True)]
                if p.get("role"):
                    runs.append(doc.run(" | " + p["role"]))
                if p.get("link"):
                    url = p["link"] if p["link"].lower().startswith("http") else "https://" + p["link"]
                    runs += [doc.run(" | "), doc.hyper(short_url(p["link"]), url)]
                if p.get("dates"):
                    runs.append(doc.run("\t" + p["dates"], color="555555"))
                doc.para(runs, before=80, after=30, tab_right=True, keep=True)
                for b in p.get("bullets", []):
                    if b.strip():
                        doc.bullet(b)
        elif sec == "education" and d.get("education"):
            doc.heading(titles.get(sec) or TITLES[sec])
            for e in d["education"]:
                doc.entry(e.get("degree", ""), e.get("school", ""), e.get("dates", ""))
                for b in e.get("bullets", []):
                    if b.strip():
                        doc.bullet(b)
        elif sec == "certifications" and d.get("certifications"):
            doc.heading(titles.get(sec) or TITLES[sec])
            doc.para([doc.run(" | ".join(x.strip() for x in d["certifications"] if x.strip()))], after=40)
        elif sec == "languages" and d.get("languages"):
            doc.heading(titles.get(sec) or TITLES[sec])
            doc.para([doc.run(d["languages"].strip())], after=40)
        for x in d.get("extra_sections", []):
            if x.get("after", "end") == sec:
                extra(doc, x)
    for x in d.get("extra_sections", []):
        if x.get("after", "end") == "end" or x.get("after") not in t["order"]:
            extra(doc, x)
    if d.get("footer_note"):
        doc.para([doc.run(d["footer_note"].strip(), size=t["size"] - 4, color="555555")], before=240, after=0)

    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults>'
              f'<w:rPrDefault><w:rPr><w:rFonts w:ascii="{t["font"]}" w:hAnsi="{t["font"]}" w:cs="{t["font"]}" w:eastAsia="{t["font"]}"/>'
              f'<w:sz w:val="{t["size"]}"/><w:szCs w:val="{t["size"]}"/><w:lang w:val="en-US"/></w:rPr></w:rPrDefault>'
              '<w:pPrDefault><w:pPr><w:spacing w:after="40" w:line="252" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
              '</w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
              '</w:styles>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            + "".join(f'<Relationship Id="rId{101 + i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                      f'Target="{escape(u, {chr(34): "&quot;"})}" TargetMode="External"/>' for i, u in enumerate(doc.links))
            + '</Relationships>')
    ctypes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
              '</Types>')
    root = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", root)
        z.writestr("word/document.xml", doc.xml())
        z.writestr("word/styles.xml", styles)
        z.writestr("word/_rels/document.xml.rels", rels)
    return buf.getvalue()


# ---------- reading an existing resume (redesign) ----------

SECTION_WORDS = [
    ("summary", ("summary", "profile", "about", "objective", "תקציר", "פרופיל")),
    ("skills", ("skill", "technolog", "tech stack", "tools", "כישורים", "מיומנויות")),
    ("experience", ("experience", "employment", "work history", "career", "ניסיון")),
    ("projects", ("project", "פרויקט")),
    ("education", ("education", "academic", "השכלה")),
    ("certifications", ("certific", "course", "training", "קורס", "הסמכ")),
    ("languages", ("language", "שפות")),
]
SPLIT = re.compile(r"\s*[|•·]\s*|\s+[–—-]\s+")


def section_of(t):
    low = t.lower().strip()
    if not t or len(t) > 45 or ":" in t or low.endswith("."):
        return None
    for sec, words in SECTION_WORDS:
        if any(low.startswith(w) or w in low.split(" &")[0] for w in words):
            return sec
    return None


def _dates(t):
    m = resume_profile.YEAR_RANGE.search(t)
    if m:
        return m.group(0), (t[:m.start()] + t[m.end():]).strip(" |,–—-")
    m = re.search(r"\b(19|20)\d{2}\b", t)
    if m and len(t) < 120:
        return m.group(0), (t[:m.start()] + t[m.end():]).strip(" |,–—-")
    return "", t


def parse(data: bytes):
    """Best-effort structure of an existing resume. The user reviews everything in the form."""
    prof = resume_profile.profile(data)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        paras = resume_profile.paragraphs(resume_profile.read_part(z, "word/document.xml"))
    d = {"name": prof.get("full_name", ""), "headline": prof.get("headline", ""),
         "contact": {k: prof.get(k, "") for k in ("city", "phone", "email", "linkedin", "github", "portfolio")},
         "summary": "", "skills_heading": prof.get("skills_heading") or "Technical Skills", "skills": [],
         "experience": [], "projects": [], "education": [], "certifications": [], "languages": ""}
    sec, summary = None, []
    for t in paras:
        t = t.strip()
        if not t:
            continue
        s = section_of(t)
        if s:
            sec = s
            continue
        if sec is None:
            continue
        if sec == "summary":
            summary.append(t)
        elif sec == "skills":
            if ":" in t:
                label, items = t.split(":", 1)
                d["skills"].append({"label": label.strip()[:60], "items": [i.strip().rstrip(".")[:80] for i in items.split(",") if i.strip()][:40]})
            else:
                d["skills"].append({"label": "Skills", "items": [i.strip().rstrip(".") for i in re.split(r"[,|•·]", t) if i.strip()][:40]})
        elif sec in ("experience", "projects", "education"):
            dates, rest = _dates(t)
            items = d[sec]
            is_entry = bool(dates) or (" | " in t and len(t) < 140) or \
                (sec == "education" and resume_profile.DEGREE.match(t)) or \
                (sec == "projects" and len(t) <= 70 and not t.endswith("."))
            if items and re.match(r"(?i)^[•*\s-]*(earlier|previous|also)\b", t):  # "Earlier: X | Y" is a note
                is_entry = False
            if is_entry or not items:
                parts = [p.strip() for p in re.split(r"\s*[|•·\t]\s*", rest) if p.strip()]
                if len(parts) == 1:  # "Title – Company" or "Title at Company"
                    parts = [p for p in re.split(r"\s+[–—-]\s+|\s+at\s+", rest, maxsplit=1) if p]
                a, b = (parts + ["", ""])[:2]
                if sec == "experience":
                    items.append({"title": a, "company": b, "location": " | ".join(parts[2:])[:200], "dates": dates, "bullets": []})
                elif sec == "projects":
                    items.append({"name": a, "role": b, "dates": dates, "link": "", "bullets": []})
                else:
                    items.append({"degree": a, "school": " | ".join(parts[1:])[:200], "dates": dates, "bullets": []})
            else:
                items[-1]["bullets"].append(t.lstrip("•-–* ").strip()[:600])
        elif sec == "certifications":
            d["certifications"] += [x.strip() for x in re.split(r"\s*\|\s*", t) if x.strip()]
        elif sec == "languages":
            d["languages"] = (d["languages"] + " | " + t).strip(" |")
    d["summary"] = " ".join(summary)[:2000]
    for sec in ("experience", "projects", "education"):
        for e in d[sec]:
            e["bullets"] = e["bullets"][:12]
        d[sec] = d[sec][:25]
    d["skills"] = [g for g in d["skills"] if g["items"]][:15]
    for g in d["skills"]:
        g["label"] = g["label"].replace(":", "")
        g["items"] = [i.replace(",", " ") for i in g["items"]]
    d["certifications"] = d["certifications"][:30]
    return d


# ---------- writing tips ----------

WEAK = re.compile(r"(?i)^(responsible for|worked on|helped|assisted|duties included|in charge of|participated in)\b")


def tips(d, target_words=()):
    """Short, actionable notes about the content (not about the design)."""
    out = []
    bullets = [b for sec in ("experience", "projects") for e in d.get(sec, []) for b in e.get("bullets", []) if b.strip()]
    weak = [b for b in bullets if WEAK.match(b.strip())]
    if weak:
        out.append(f"{len(weak)} bullet(s) start with a weak phrase (e.g. “{weak[0][:40]}…”). Start with an action verb: built, led, cut, automated.")
    nums = [b for b in bullets if re.search(r"\d", b)]
    if bullets and len(nums) < max(1, len(bullets) // 3):
        out.append("Few bullets have numbers. Add results where you can: users, % faster, time saved, size.")
    long = [b for b in bullets if len(b) > 220]
    if long:
        out.append(f"{len(long)} bullet(s) are long. Keep each to one or two lines.")
    if not d.get("summary"):
        out.append("Add a 2–3 line summary: who you are, your main stack, what you're looking for.")
    elif len(d["summary"]) > 600:
        out.append("The summary is long. Two or three lines are enough.")
    skills = {i.lower() for g in d.get("skills", []) for i in g.get("items", [])}
    everything = json.dumps(d, ensure_ascii=False).lower()
    missing = [w for w in target_words if w.lower() not in skills and w.lower() not in everything]
    if missing:
        out.append("Common in the jobs you target but not on your resume (add only if true): " + ", ".join(missing[:8]) + ".")
    words = len(json.dumps(d).split())
    if words > 700:
        out.append("It's probably longer than one page. Junior resumes work best on one page.")
    return out


def claude_prompt(d, role):
    """A prompt to paste into Claude to polish the wording, without inventing anything."""
    lines = []
    for sec in ("experience", "projects"):
        for e in d.get(sec, []):
            head = e.get("title") or e.get("name") or ""
            lines.append(f"## {head} {('| ' + (e.get('company') or e.get('role') or '')) if (e.get('company') or e.get('role')) else ''}".strip())
            lines += [f"- {b}" for b in e.get("bullets", []) if b.strip()]
    return ("Improve the wording of my resume for " + (role or "the jobs I'm applying to") + ".\n"
            "Rules: keep every fact exactly as it is; do not invent numbers, tools, titles or results; if a bullet would "
            "be stronger with a number I didn't give, add [number?] for me to fill in. Start each bullet with an action "
            "verb, one or two lines each. Return the same structure (## headings and - bullets) and a new 2–3 line summary.\n\n"
            f"Current summary:\n{d.get('summary', '')}\n\n" + "\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data", nargs="?", help="resume data as JSON")
    ap.add_argument("--template", default="tech", choices=sorted(TEMPLATES))
    ap.add_argument("--out", help="output .docx")
    ap.add_argument("--parse", help="read this .docx and print its structure as JSON")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from docx_safe import DocxError, open_docx
    if a.parse:
        try:  # untrusted file: size, zip-bomb and XML checks first
            z, _ = open_docx(a.parse)
            z.close()
        except DocxError as e:
            sys.exit(str(e))
        print(json.dumps(parse(Path(a.parse).read_bytes()), ensure_ascii=False, indent=2))
    elif a.data and a.out:
        out = Path(a.out)
        if out.suffix.lower() != ".docx" or out.is_symlink():
            sys.exit("--out must be a .docx file path (not a link).")
        try:
            data = build(json.loads(Path(a.data).read_text(encoding="utf-8")), a.template)
        except (ValueError, OSError) as e:
            sys.exit(f"Could not build the resume: {e}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        print(out)
    else:
        ap.error("give data.json --out file.docx, or --parse file.docx")
