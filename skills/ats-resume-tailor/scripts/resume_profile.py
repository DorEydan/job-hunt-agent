#!/usr/bin/env python3
"""Read a .docx resume and guess as many settings as possible for the setup wizard.

Heuristics only: every value is a suggestion the user sees and can change.
Nothing here is sent anywhere; it runs on this computer.

    python resume_profile.py path/to/resume.docx
"""
import datetime as dt
import html
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

P_RE = re.compile(r"<w:p[ >].*?</w:p>", re.S)
T_RE = re.compile(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>")
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,5}")
PHONE = re.compile(r"(?<![\w])(\+?\d[\d\s().-]{7,18}\d)(?![\w])")
URL = re.compile(r"https?://[^\s<>\"']+|(?:www\.)?(?:linkedin\.com|github\.com)/[^\s<>\"']+", re.I)
YEAR_RANGE = re.compile(r"((?:19|20)\d{2})\s*[–—-]\s*((?:19|20)\d{2}|present|current|now|today|היום|כיום)", re.I)

COUNTRY_BY_PHONE = [("+972", "Israel"), ("+48", "Poland"), ("+49", "Germany"), ("+44", "United Kingdom"),
                    ("+91", "India"), ("+33", "France"), ("+31", "Netherlands"), ("+34", "Spain"), ("+61", "Australia"),
                    ("+1", "United States")]
COUNTRY_WORDS = {
    "Israel": ["israel", "tel aviv", "jerusalem", "haifa", "ישראל"], "Poland": ["poland", "polska", "warsaw", "kraków", "krakow", "wrocław", "gdańsk"],
    "Germany": ["germany", "deutschland", "berlin", "munich", "münchen", "hamburg"], "United Kingdom": ["united kingdom", "uk", "england", "london", "manchester"],
    "United States": ["usa", "united states", "new york", "california", "texas", ", ca", ", ny"], "Canada": ["canada", "toronto", "vancouver", "montreal"],
    "India": ["india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune"], "France": ["france", "paris", "lyon"],
    "Netherlands": ["netherlands", "amsterdam", "rotterdam", "utrecht"], "Spain": ["spain", "españa", "madrid", "barcelona"],
    "Australia": ["australia", "sydney", "melbourne", "brisbane"],
}
FIELD_WORDS = {
    "devops": ["devops", "kubernetes", "k8s", "docker", "terraform", "ansible", "ci/cd", "jenkins", "helm", "sre", "site reliability", "cloud engineer", "prometheus", "grafana"],
    "software": ["full stack", "full-stack", "fullstack", "frontend", "front-end", "backend", "back-end", "react", "angular", "vue", "node.js", "javascript", "typescript", "java", "c#", ".net", "asp.net", "python", "rest api", "software engineer", "developer"],
    "data": ["data analyst", "data engineer", "data scientist", "machine learning", "pandas", "power bi", "tableau", "spark", "etl", "bi developer", "analytics"],
    "qa": ["qa", "quality assurance", "selenium", "cypress", "playwright", "test automation", "manual testing", "tester"],
    "it": ["help desk", "helpdesk", "system administrator", "sysadmin", "active directory", "it support", "technician", "networking", "ccna"],
    "security": ["cyber", "security analyst", "soc", "siem", "penetration", "pentest", "infosec"],
    "design": ["ux", "ui designer", "figma", "sketch", "product designer", "user research"],
    "product": ["product manager", "product owner", "project manager", "roadmap", "scrum master"],
    "marketing": ["marketing", "seo", "content writer", "social media", "campaign", "copywriting"],
    "sales": ["sales", "account manager", "customer success", "business development", "crm"],
}
SKILL_HEADINGS = ["technical skills", "skills", "tech stack", "core skills", "key skills", "technologies", "skills & tools",
                  "tools & technologies", "כישורים", "מיומנויות"]
DEGREE = re.compile(r"\b(B\.?Sc|B\.?A|BA|BSc|B\.?Eng|M\.?Sc|MSc|M\.?A|MBA|Ph\.?D|Bachelor|Master|Diploma|תואר)\b", re.I)


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_PART = 8_000_000


def read_part(z, name, limit=MAX_PART):
    """Read one file from the .docx with a hard size cap (the zip header's size can lie)."""
    with z.open(name) as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{name} is too large.")
    return data


def paragraphs(xml):
    """Text of each paragraph, in linear time. Word tabs and line breaks become spaces; whitespace is collapsed.
    Callers reject DTDs/entities first (server.check_docx); ElementTree never fetches external entities."""
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    root = ET.fromstring(xml)
    out = []
    for p in root.iter(W + "p"):
        parts = []
        for r in p.iter(W + "r"):
            for el in r:
                if el.tag == W + "t" and el.text:
                    parts.append(el.text)
                elif el.tag in (W + "tab", W + "br"):
                    parts.append(" ")
        out.append(re.sub(r"\s+", " ", "".join(parts)).strip())
    return out


def links(z):
    try:
        root = ET.fromstring(read_part(z, "word/_rels/document.xml.rels", 1_000_000))
    except (KeyError, ET.ParseError, ValueError):
        return []
    return [el.get("Target", "") for el in root if el.get("Target", "").lower().startswith(("http://", "https://"))]


def detect_skills_heading(paras):
    """The heading followed by 2+ lines that look like 'Label: a, b, c'."""
    def skill_line(t):
        return ":" in t and len(t.split(":", 1)[0]) <= 40 and "," in t.split(":", 1)[1]
    for i, t in enumerate(paras):
        if t and ":" not in t and len(t) <= 40:
            nxt = [x for x in paras[i + 1:i + 4] if x]
            if len(nxt) >= 2 and all(skill_line(x) for x in nxt[:2]):
                return t
    for t in paras:
        if t.lower() in SKILL_HEADINGS:
            return t
    return None


def years_of_experience(text, today=None):
    """Union of 'YYYY – YYYY/Present' ranges, in whole years (education lines are skipped by the caller)."""
    today = today or dt.date.today()
    spans = []
    for a, b in YEAR_RANGE.findall(text):
        start = int(a)
        end = today.year if not b[:1].isdigit() else int(b)
        if 1970 <= start <= end <= today.year + 1:
            spans.append((start, end))
    covered = set()
    for s, e in spans:
        covered.update(range(s, max(e, s + 1)))
    return len(covered)


def guess_field(text):
    low = text.lower()
    scores = {f: sum(low.count(w) for w in ws) for f, ws in FIELD_WORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else None


def level_for(years, text):
    low = text.lower()
    if re.search(r"\bstudent\b|expected graduation|סטודנט", low) and years < 2:
        return "student"
    if years < 1:
        return "entry"
    if years <= 2:
        return "junior"
    if years <= 5:
        return "mid"
    return "senior"


def profile(data: bytes, today=None):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = read_part(z, "word/document.xml")
        hrefs = links(z)
    paras = paragraphs(xml)
    nonempty = [p for p in paras if p]
    text = "\n".join(nonempty)
    out = {}

    # Name: the first short line without digits, @ or a colon (resumes start with the name).
    for t in nonempty[:5]:
        if 2 <= len(t) <= 50 and not re.search(r"[\d@:|/]", t) and len(t.split()) <= 5:
            out["full_name"] = t
            break
    # Headline: the line right after the name, if it's short (e.g. "Full-Stack Developer | AI").
    if "full_name" in out:
        i = nonempty.index(out["full_name"])
        if i + 1 < len(nonempty) and len(nonempty[i + 1]) <= 80 and not EMAIL.search(nonempty[i + 1]):
            out["headline"] = nonempty[i + 1]

    m = EMAIL.search(text)
    if m:
        out["email"] = m.group(0)
    for line in nonempty[:12]:  # contact lines are at the top
        pm = PHONE.search(EMAIL.sub("", line))
        if pm and sum(c.isdigit() for c in pm.group(1)) >= 9 and not YEAR_RANGE.search(pm.group(1)):
            out["phone"] = re.sub(r"\s+", " ", pm.group(1)).strip()
            break
    urls = hrefs + URL.findall(text)
    for u in urls:
        lu = u.lower()
        full = u if lu.startswith("http") else "https://" + u
        if "linkedin.com/in/" in lu and "linkedin" not in out:
            out["linkedin"] = full.rstrip(".,)")
        elif "github.com/" in lu and "github" not in out:
            out["github"] = full.rstrip(".,)")
        elif "portfolio" not in out and not any(x in lu for x in ("linkedin.", "github.", "mailto:", "google.", "microsoft.")):
            out["portfolio"] = full.rstrip(".,)")

    # Country: phone prefix first, then place names near the top.
    phone = out.get("phone", "").replace(" ", "")
    for pre, c in COUNTRY_BY_PHONE:
        if phone.startswith(pre):
            out["country"] = c
            break
    top = " ".join(nonempty[:8]).lower()
    if "country" not in out:
        for c, words in COUNTRY_WORDS.items():
            if any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", top) for w in words):
                out["country"] = c
                break
    # City: the part of a contact line that names a place (e.g. "📍 Haifa, Israel | 📞 …").
    for line in nonempty[:6]:
        for part in re.split(r"\s*[|•·]\s*", line):
            clean = re.sub(r"^[^\w]+", "", part).strip()
            if "," in clean and not EMAIL.search(clean) and not re.search(r"\d{3}", clean) and len(clean) <= 60:
                out["city"] = clean
                break
        if "city" in out:
            break

    heading = detect_skills_heading(paras)
    if heading:
        out["skills_heading"] = heading

    # Experience years: date ranges outside the education section.
    edu_words = ("education", "degree", "university", "college", "השכלה", "certific")
    lines = []
    in_edu = False
    for t in nonempty:
        low = t.lower()
        if len(t) <= 40 and ":" not in t:  # a heading changes the section
            in_edu = any(w in low for w in edu_words)
        if not in_edu and not DEGREE.search(t):  # a job "at X University" is still a job
            lines.append(t)
    f = guess_field(out.get("headline", "")) or guess_field(text)  # the headline says what they want
    if f:
        out["field"] = f
    # Relevant experience: only jobs whose line names the field (a developer's support job doesn't count).
    words = FIELD_WORDS.get(f, []) + ["developer", "engineer", "programmer"] if f in ("software", "devops", "data", "qa") \
        else FIELD_WORDS.get(f, [])
    relevant = [t for t in lines if YEAR_RANGE.search(t) and any(w in t.lower() for w in words)]
    out["years_experience_total"] = years_of_experience("\n".join(lines), today)
    years = years_of_experience("\n".join(relevant), today) if words else out["years_experience_total"]
    out["years_experience"] = years
    out["experience_level"] = level_for(years, text)
    # Degree: prefer a short line that starts with the degree (the education entry, not a summary sentence).
    cands = [re.sub(r"\s+", " ", t) for t in nonempty if DEGREE.search(t) and len(t) <= 160]
    best = [t for t in cands if DEGREE.match(t) or (DEGREE.search(t[:12]) and not t.endswith("."))]
    if best or cands:
        out["degree"] = (best or cands)[0]
    langs = next((t for t in nonempty if re.match(r"(?i)^(english|hebrew|polish|german|french|spanish)\s*[:\-–]", t)), None)
    if langs:
        out["languages"] = langs
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(profile(Path(sys.argv[1]).read_bytes()), ensure_ascii=False, indent=2))
