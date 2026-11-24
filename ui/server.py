#!/usr/bin/env python3
"""Local control panel for the job-hunt agent.

Runs only on this computer (127.0.0.1) and serves one page: setup, resume check,
application log, run reports and automation setup. Standard library only.

    .venv\\Scripts\\python.exe ui\\server.py [--port 8765] [--no-browser]
    docker compose up   (see Dockerfile; listens on 0.0.0.0 inside the container only)
"""
import argparse
import base64
import io
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
import zipfile
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from common import CONFIG_PATH, EXAMPLE_PATH, resume_variants  # noqa: E402
import pdf_export  # noqa: E402
import resume_profile  # noqa: E402
import resume_builder  # noqa: E402
import ai  # noqa: E402
import match  # noqa: E402

UI_DIR = ROOT / "ui"
RUNS_DIR = ROOT / "runs"
CSV_PATH = ROOT / "applications.csv"
PREVIEW_DIR = ROOT / ".preview"
UPLOAD_DIR = ROOT / "uploads"
PY = sys.executable
MAX_BODY = 1_000_000
MAX_UPLOAD_BODY = 8_000_000  # base64 of a file up to ~5.5 MB
MAX_FILE = 5_000_000
MAX_XML = 8_000_000  # unpacked word/document.xml
_upload_slots = threading.BoundedSemaphore(2)
_ai_slots = threading.BoundedSemaphore(2)  # AI calls are slow and may cost money: no floods  # caps memory: each upload holds a few copies of the file
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
IN_DOCKER = os.environ.get("JOBHUNT_IN_DOCKER") == "1" or Path("/.dockerenv").exists()
UPLOAD_KINDS = {"resume": {".docx"}, "cover_letter": {".docx", ".pdf", ".txt", ".md"}}
STATUSES = ["prepared", "sent", "interview", "offer", "rejected", "manual", "failed", "skipped", "ghost"]
NOTE_DIRS = {"prep": ROOT / "prep", "learning": ROOT / "learning"}
NOTE_NAME = re.compile(r"[A-Za-z0-9][\w .()&+-]{0,100}\.md")  # always used with fullmatch
PLATFORMS = ["youtube", "official-docs", "freecodecamp", "udemy", "coursera", "edx", "pluralsight", "linkedin-learning"]
LAYOUTS = ["company_role", "date_company_role", "field_company_role", "role_company"]
RUN_NAME = re.compile(r"\d{4}-\d{2}-\d{2}[A-Za-z0-9_-]*\.md")  # always used with fullmatch
VARIANT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}")  # always used with fullmatch

_word_check = {"done": False, "ok": None, "detail": ""}
_tool_lock = threading.Lock()  # Word COM, the CSV and .preview are not safe for parallel use
_config_lock = threading.Lock()
_word_lock = threading.Lock()


# ---------- helpers ----------

def read_config():
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    if not CONFIG_PATH.exists():
        return example, False
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg.setdefault("setup_complete", True)  # configs from before the setup wizard are already set up
    for k, v in example.items():  # settings added in newer versions get their defaults
        cfg.setdefault(k, v)
    return cfg, True


STR_LISTS = ["target_roles", "search_terms_en", "search_terms_local"]
INTS = ["dedup_days", "pending_days", "max_new_jobs_per_run", "min_match_score"]


def check_file_path(label, path, exts):
    if not isinstance(path, str):
        return [f"{label}: must be text."]
    if path and not path.lower().endswith(tuple(exts)):
        return [f"{label}: must be a {' / '.join(sorted(exts))} file."]
    if path.strip().replace("\\", "/").startswith("//"):
        return [f"{label}: network paths are not allowed. Copy the file to this computer."]
    return []


def check_resume_path(name, path):
    if not isinstance(path, str) or not path.lower().endswith(".docx"):
        return [f"Resume '{name}': the path must point to a .docx file."]
    if path.strip().replace("\\", "/").startswith("//"):
        return [f"Resume '{name}': network paths are not allowed. Copy the file to this computer."]
    return []


def validate_config(cfg):
    """Return a list of problems (empty = OK). Types only; values are the user's choice."""
    errs = []
    if not isinstance(cfg, dict):
        return ["Config must be a JSON object."]
    cand = cfg.get("candidate", {})
    if not isinstance(cand, dict) or not all(isinstance(v, str) for v in cand.values()):
        errs.append("candidate: every field must be text.")
    for k in STR_LISTS:
        v = cfg.get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errs.append(f"{k}: must be a list of text lines.")
    for k in INTS:
        v = cfg.get(k)
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0 or v > 10000):
            errs.append(f"{k}: must be a whole number between 0 and 10000.")
    br = cfg.get("base_resumes", {})
    if not isinstance(br, dict):
        errs.append("base_resumes: must map a version name to a file path.")
    else:
        for name, path in br.items():
            if name.startswith("_"):
                continue
            if not VARIANT_NAME.fullmatch(name):
                errs.append(f"Resume version name '{name}': start with a letter or digit; then letters, digits, - or _.")
            errs += check_resume_path(name, path)
    if "base_resume" in cfg:
        errs += check_resume_path("base_resume", cfg["base_resume"])
    for k in ("screening_answers", "cover_note"):
        v = cfg.get(k, {})
        if not isinstance(v, dict) or not all(isinstance(x, str) for x in v.values()):
            errs.append(f"{k}: every value must be text.")
    sen = cfg.get("seniority", {})
    if not isinstance(sen, dict):
        errs.append("seniority: must be an object.")
    loc = cfg.get("locations", {})
    if not isinstance(loc, dict):
        errs.append("locations: must be an object.")
    errs += validate_extras(cfg)
    return errs


DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
TIME = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")
SOURCE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
BOOL_MAPS = ["job_types", "apply_methods"]
EXTRA_STR_LISTS = ["must_have_keywords", "exclude_keywords", "exclude_companies"]


def validate_extras(cfg):
    """The customization settings: schedule, rules, apply methods and the site list."""
    errs = []
    sch = cfg.get("schedule", {"days": ["mon"], "time": "09:00"})
    if not isinstance(sch, dict) or not isinstance(sch.get("days"), list) or not sch["days"] \
            or any(d not in DAYS for d in sch["days"]):
        errs.append("schedule: pick at least one day.")
    if not isinstance(sch, dict) or not isinstance(sch.get("time"), str) or not TIME.fullmatch(sch["time"]):
        errs.append("schedule: time must look like 09:00.")
    w = cfg.get("search_window_days", 3)
    if not isinstance(w, int) or isinstance(w, bool) or not 1 <= w <= 60:
        errs.append("search_window_days: a whole number from 1 to 60.")
    for k in BOOL_MAPS:
        v = cfg.get(k, {})
        if not isinstance(v, dict) or not all(isinstance(x, bool) for x in v.values()):
            errs.append(f"{k}: every option must be on or off.")
    for k in EXTRA_STR_LISTS:
        v = cfg.get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errs.append(f"{k}: must be a list of text lines.")
    for k in ("search_location", "country", "field", "experience_level"):
        if not isinstance(cfg.get(k, ""), str) or len(cfg.get(k, "")) > 100:
            errs.append(f"{k}: must be text (up to 100 characters).")
    if not isinstance(cfg.get("setup_complete", True), bool):
        errs.append("setup_complete: must be on or off.")
    loc = cfg.get("locations")
    km = loc.get("max_commute_km", 0) if isinstance(loc, dict) else 0
    if not isinstance(km, int) or isinstance(km, bool) or not 0 <= km <= 5000:
        errs.append("locations.max_commute_km: a whole number from 0 (no limit) to 5000.")
    errs += check_file_path("cover_letter_file", cfg.get("cover_letter_file", ""), UPLOAD_KINDS["cover_letter"])
    rt = cfg.get("resume_tailoring", {"enabled": True, "folder_layout": "company_role"})
    if not isinstance(rt, dict) or not isinstance(rt.get("enabled", True), bool) or \
            rt.get("folder_layout", "company_role") not in LAYOUTS:
        errs.append("resume_tailoring: on/off, and a folder layout from the list.")
    a = cfg.get("ai", {})
    if not isinstance(a, dict) or a.get("provider", "none") not in ai.PROVIDERS or \
            not all(isinstance(a.get(k, ""), str) and len(a.get(k, "")) <= 300 for k in ("model", "base_url", "api_key_env")) or \
            (a.get("api_key_env") and not ai.KEY_NAME.fullmatch(a["api_key_env"])) or \
            (a.get("base_url") and ai.check_url(a["base_url"])):
        errs.append("ai: a provider from the list; https address (http only for localhost); key name like OPENAI_API_KEY.")
    lr = cfg.get("learning", {})
    if not isinstance(lr, dict) or not isinstance(lr.get("suggest_in_runs", True), bool) or \
            not isinstance(lr.get("free_only", False), bool) or not isinstance(lr.get("language", ""), str) or \
            len(lr.get("language", "")) > 100 or not isinstance(lr.get("platforms", []), list) or \
            len(lr.get("platforms", [])) > len(PLATFORMS) or any(x not in PLATFORMS for x in lr.get("platforms", [])):
        errs.append("learning: on/off options, a language, and platforms from the list.")
    gj = cfg.get("ghost_jobs", {})
    rt_n = gj.get("repost_times", 2) if isinstance(gj, dict) else None
    if not isinstance(gj, dict) or not isinstance(gj.get("ask_when_reposted", True), bool) or \
            not isinstance(rt_n, int) or isinstance(rt_n, bool) or not 2 <= rt_n <= 20 or \
            gj.get("block", "role") not in ("role", "company"):
        errs.append("ghost_jobs: ask on/off, repost count 2-20, block 'role' or 'company'.")
    for k in ("cover_note_in_forms", "notifications"):
        if not isinstance(cfg.get(k, True), bool):
            errs.append(f"{k}: must be on or off.")
    sources = cfg.get("sources", [])
    if not isinstance(sources, list):
        return errs + ["sources: must be a list of sites."]
    seen = set()
    for i, s in enumerate(sources, 1):
        if not isinstance(s, dict):
            errs.append(f"Site {i}: invalid entry.")
            continue
        sid, name = s.get("id"), s.get("name")
        if not isinstance(sid, str) or not SOURCE_ID.fullmatch(sid):
            errs.append(f"Site {i}: id must be lowercase letters, digits or -.")
        elif sid in seen:
            errs.append(f"Site {i}: id '{sid}' is used twice.")
        seen.add(sid)
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            errs.append(f"Site {i}: needs a name (up to 80 characters).")
        for b in ("enabled", "needs_signin"):
            if not isinstance(s.get(b), bool):
                errs.append(f"Site {i}: '{b}' must be on or off.")
        for t in ("search", "apply", "notes"):
            if not isinstance(s.get(t, ""), str) or len(s.get(t, "")) > 2000:
                errs.append(f"Site {i}: '{t}' must be text (up to 2000 characters).")
    return errs


def schedule_info(cfg):
    """Cron line, a readable summary and the longest gap between runs (for the search window)."""
    sch = cfg.get("schedule") or {}
    days = [d for d in DAYS if d in (sch.get("days") or [])] or ["sun", "tue", "thu"]
    t = sch.get("time") if isinstance(sch.get("time"), str) and TIME.fullmatch(sch.get("time")) else "09:00"
    hh, mm = t.split(":")
    idx = [DAYS.index(d) for d in days]
    gaps = [((idx[(i + 1) % len(idx)] - idx[i]) % 7) or 7 for i in range(len(idx))]
    return {"cron": f"{int(mm)} {int(hh)} * * {','.join(map(str, idx))}",
            "days": days, "time": t, "max_gap_days": max(gaps)}


def write_config(cfg):
    with _config_lock:
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(CONFIG_PATH)


def run_tool(args, timeout=180, before=None):
    env = {**os.environ, "PYTHON_COLORS": "0", "NO_COLOR": "1", "PYTHONIOENCODING": "utf-8"}
    with _tool_lock:
        if before:
            before()
        p = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, env=env)
    err = p.stderr
    if "Traceback" in err:  # show the last line, not the whole stack
        err = err.strip().splitlines()[-1]
    return p.returncode, p.stdout, err


def check_word():
    with _word_lock:
        return _check_word()


def _check_word():
    if _word_check["done"]:
        return _word_check
    ps = ("try { $w = New-Object -ComObject Word.Application; $v = $w.Version; $w.Quit(); "
          "Write-Output \"ok $v\" } catch { Write-Output 'missing' }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                             text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = "missing"
    _word_check.update(done=True, ok=out.startswith("ok"),
                       detail=f"Microsoft Word {out[3:]}" if out.startswith("ok") else "")
    return _word_check


def health():
    cfg, exists = read_config()
    items = []

    def add(key, label, ok, detail="", fix=""):
        items.append({"key": key, "label": label, "ok": ok, "detail": detail, "fix": fix})

    add("python", "Python environment", sys.version_info >= (3, 11),
        f"Python {sys.version.split()[0]}", "Install Python 3.11 or newer, then run start.bat again.")
    missing = []
    for mod in ("fontTools", "pypdf"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    add("packages", "Python packages", not missing, "fontTools, pypdf" if not missing else "",
        f"Missing: {', '.join(missing)}. Run start.bat again (it installs requirements.txt).")
    if pdf_export.engine() == "word":
        w = check_word()
        add("word", "Microsoft Word (for PDF export)", bool(w["ok"]), w["detail"],
            "Install Microsoft Word, or use Docker / LibreOffice (see README). It turns the resume into a PDF.")
    else:
        so = pdf_export.soffice_path()
        add("word", "LibreOffice (for PDF export)", bool(so), "LibreOffice" if so else "",
            "Install LibreOffice, or run the panel with Docker (it includes LibreOffice).")
    add("config", "Settings saved", exists, "config.json" if exists else "",
        "Fill in the Profile tab and press Save.")
    cand = cfg.get("candidate", {})
    filled = exists and cand.get("full_name") not in ("", "Your Name") and "@example.com" not in cand.get("email", "")
    add("profile", "Your details filled in", bool(filled), cand.get("full_name", "") if filled else "",
        "Profile tab: name, email, phone, LinkedIn.")
    variants = resume_variants(cfg)
    bad = [n for n, p in variants.items() if not Path(p).exists()]
    sample = any(Path(p).name == "sample-resume.docx" for p in variants.values())
    add("resumes", "Resume file(s) found", bool(variants) and not bad,
        ", ".join(variants) + (" (sample resume)" if sample else "") if variants and not bad else "",
        "Resumes tab: set the path of your .docx resume." + (f" Not found: {', '.join(bad)}." if bad else ""))
    if sample and not bad:
        items[-1]["warn"] = "You are still using the sample resume. Point this to your own .docx."
    srcs = cfg.get("sources") or []
    on = [s.get("name", "") for s in srcs if isinstance(s, dict) and s.get("enabled")]
    add("sites", "Sites to search", bool(on), f"{len(on)} of {len(srcs)} on" if on else "",
        "Sites tab: switch on at least one site.")
    st = ai.status(cfg)
    add("ai", "AI for the control panel (optional)", True if st["ready"] else None,
        f"{st['label']} · {st['model']}" if st["ready"] else "Not set up: offline features only.",
        "AI tab: pick OpenAI, Gemini, Claude, a local model (Ollama, LM Studio) or another provider.")
    agents = [n for n, exe in (("Claude Code", "claude"), ("Codex", "codex"), ("Gemini CLI", "gemini"), ("Aider", "aider"))
              if shutil.which(exe)]
    if IN_DOCKER:
        add("claude", "An agent tool on your computer", None, "",
            "The automatic agent runs in an agent tool on your computer (Claude Code, Codex, Gemini CLI…), in this folder.")
    else:
        add("claude", "Agent tool for automatic runs (optional)", True if agents else None,
            ", ".join(agents) + " found" if agents else "None found. Everything in this panel still works.",
            "For automatic search and applying, install an agent tool (Claude Code, Codex, Gemini CLI…). "
            "It follows AGENTS.md in this folder.")
    return items


def read_applications():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    keep = ["id", "date_found", "date_sent", "status", "company", "role", "source", "job_url",
            "apply_method", "match_score", "folder", "notes"]
    return [{k: r.get(k, "") for k in keep} for r in rows]


def host_folder():
    """The project folder as seen by Claude Code on the user's computer."""
    env = os.environ.get("JOBHUNT_HOST_FOLDER", "").strip()
    if env:
        return env
    return "<this project's folder on your computer>" if IN_DOCKER else str(ROOT)


def schedule_prompt():
    return (f"Open the folder {host_folder()} and follow AGENTS.md in it: run Phase A (search and prepare), "
            "write the run report, then stop and wait for my approval before sending anything.")


# ---------- uploads (setup wizard) ----------

def docx_text(data: bytes, limit=20000):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = resume_profile.read_part(z, "word/document.xml")
    return "\n".join(resume_profile.paragraphs(xml)).strip()[:limit]


def check_docx(data: bytes):
    """A real Word file: a zip with word/document.xml, not huge when unpacked (zip bombs),
    no DTDs and no links to local files or network shares (LibreOffice/Word could follow them)."""
    too_big = "This .docx is unusually large inside. Re-save it in Word and try again."
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > 2000 or sum(i.file_size for i in infos) > 100_000_000:
                raise ValueError(too_big)
            if "word/document.xml" not in z.namelist():
                raise ValueError("This is not a Word document (.docx).")
            with z.open("word/document.xml") as f:  # the header's size can lie: read with a hard cap
                xml = f.read(MAX_XML + 1)
            if len(xml) > MAX_XML:
                raise ValueError(too_big)
            if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                raise ValueError("This .docx has unusual content. Re-save it in Word and try again.")
            rel_names = [n for n in z.namelist() if n.endswith(".rels")]
            if len(rel_names) > 200:
                raise ValueError(too_big)
            for name in rel_names:
                with z.open(name) as f:
                    rels = f.read(1_000_001)
                if len(rels) > 1_000_000:
                    raise ValueError(too_big)
                if b"<!DOCTYPE" in rels or b"<!ENTITY" in rels:
                    raise ValueError("This .docx has unusual content. Re-save it in Word and try again.")
                try:
                    root = ET.fromstring(rels)
                except ET.ParseError:
                    raise ValueError("This .docx is damaged. Re-save it in Word and try again.")
                for el in root:
                    if el.get("TargetMode") != "External":
                        continue
                    t = el.get("Target", "").strip().lower().replace("\\", "/")
                    if not t.startswith(("http://", "https://", "mailto:")):
                        raise ValueError("This .docx links to a local file or network share. "
                                         "Remove that link (or re-save the file) and try again.")
    except zipfile.BadZipFile:
        raise ValueError("This is not a Word document (.docx).")


def read_skills(target: Path, heading: str):
    code, out, err = run_tool(["tools/tailor_resume.py", f"--docx={target}", f"--heading={heading}", "--list"],
                              timeout=60)
    if code == 0:
        return {"skills": json.loads(out), "skills_error": None}
    return {"skills": None, "skills_error": (err or out).strip()[-500:]}


def check_heading(heading):
    if not isinstance(heading, str) or not heading.strip() or len(heading) > 100 or CONTROL.search(heading):
        raise ValueError("Bad skills heading.")
    return heading.strip()


def save_upload(body):
    """Save a resume or cover letter from the setup wizard into uploads/. Returns info for the UI."""
    kind = body.get("kind")
    if kind not in UPLOAD_KINDS:
        raise ValueError("Unknown file kind.")
    name = body.get("filename")
    ext = Path(name).suffix.lower() if isinstance(name, str) else ""
    if ext not in UPLOAD_KINDS[kind]:
        raise ValueError(f"Choose a {' / '.join(sorted(UPLOAD_KINDS[kind]))} file.")
    variant = body.get("variant") or "default"
    if not isinstance(variant, str) or not VARIANT_NAME.fullmatch(variant):
        raise ValueError("Bad resume version name.")
    data = body.get("data")
    if not isinstance(data, str):
        raise ValueError("The file could not be read.")
    try:
        data = base64.b64decode(data, validate=True)
    except ValueError:
        raise ValueError("The file could not be read.")
    if not data:
        raise ValueError("The file is empty.")
    if len(data) > MAX_FILE:
        raise ValueError("The file is larger than 5 MB.")
    info = {}
    if ext == ".docx":
        check_docx(data)
    elif ext == ".pdf" and not data.startswith(b"%PDF"):
        raise ValueError("This is not a PDF file.")
    elif ext in (".txt", ".md"):
        try:
            info["text"] = data.decode("utf-8-sig")[:20000]
        except UnicodeDecodeError:
            raise ValueError("Save the text file as UTF-8 and try again.")
    heading = check_heading(body.get("heading") or "Technical Skills") if kind == "resume" else None
    # Our own file names only: nothing from the uploaded file name reaches the disk path.
    target = UPLOAD_DIR / (f"resume-{variant}.docx" if kind == "resume" else f"cover-letter{ext}")
    with _tool_lock:
        UPLOAD_DIR.mkdir(exist_ok=True)
        if kind == "cover_letter":
            for old in UPLOAD_DIR.glob("cover-letter.*"):
                old.unlink()
        target.write_bytes(data)
    info["path"] = target.relative_to(ROOT).as_posix()
    if kind == "resume":
        try:
            info["profile"] = resume_profile.profile(data)  # suggestions for the wizard, from the resume text
        except Exception:
            info["profile"] = {}
        if info["profile"].get("skills_heading"):
            heading = check_heading(info["profile"]["skills_heading"])
        info.update(read_skills(target, heading))
    elif ext == ".docx":
        info["text"] = docx_text(data)
    elif ext == ".pdf":
        try:
            from pypdf import PdfReader
            info["text"] = "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages[:3])[:20000]
        except Exception:
            info["text"] = ""
    return info


def upload_path(path):
    """A relative path that stays inside uploads/. Absolute and network paths are refused before touching them."""
    if not isinstance(path, str) or not path or "\x00" in path or Path(path).is_absolute() or \
            path.strip().replace("\\", "/").startswith(("/", "//")) or re.match(r"^[A-Za-z]:", path):
        raise ValueError("Unknown file.")
    target = (ROOT / path).resolve()
    if not target.is_relative_to(UPLOAD_DIR.resolve()):
        raise ValueError("Unknown file.")
    return target


def reread_skills(body):
    """Read an uploaded resume's skills again (after the user changes the heading)."""
    path, heading = body.get("path"), check_heading(body.get("heading"))
    target = upload_path(path)
    if not target.is_relative_to(UPLOAD_DIR.resolve()) or target.suffix.lower() != ".docx" or not target.is_file():
        raise ValueError("Unknown file.")
    return read_skills(target, heading)


# ---------- resume builder ----------

BUILT = UPLOAD_DIR / "built-resume.docx"
BUILDER_PREVIEW = PREVIEW_DIR / "builder"
COMMON_SKILLS = {
    "software": ["Git", "REST API", "SQL", "JavaScript", "TypeScript", "React", "Node.js", "Docker", "Python"],
    "devops": ["Linux", "Docker", "Kubernetes", "Terraform", "CI/CD", "AWS", "Python", "Bash", "Git", "Monitoring"],
    "data": ["SQL", "Python", "Excel", "Power BI", "Tableau", "Pandas", "ETL"],
    "qa": ["Test automation", "Selenium", "Cypress", "API testing", "SQL", "Jira", "Python"],
    "it": ["Windows Server", "Active Directory", "Networking", "Linux", "PowerShell", "Microsoft 365"],
    "security": ["SIEM", "Networking", "Linux", "Python", "Incident response"],
    "design": ["Figma", "Prototyping", "User research", "Design systems"],
    "product": ["Jira", "Roadmap", "Analytics", "A/B testing", "SQL"],
    "marketing": ["SEO", "Google Analytics", "Content", "Social media", "HubSpot"],
    "sales": ["CRM", "Salesforce", "HubSpot", "Negotiation"],
}


def builder_source(body):
    """The .docx to redesign: a configured resume version, or a file uploaded in the wizard."""
    cfg, _ = read_config()
    if body.get("variant"):
        v = body["variant"]
        variants = resume_variants(cfg)
        if not isinstance(v, str) or not VARIANT_NAME.fullmatch(v) or v not in variants:
            raise ValueError("Unknown resume version.")
        target = Path(variants[v])
    else:
        target = upload_path(body.get("path"))
    if target.suffix.lower() != ".docx" or not target.is_file():
        raise ValueError("Resume file not found. Check its path on the Resumes tab.")
    if target.stat().st_size > MAX_FILE:
        raise ValueError("The resume file is larger than 5 MB.")
    data = target.read_bytes()
    check_docx(data)
    return data


def builder_build(body):
    data, template = body.get("data"), body.get("template")
    if template not in resume_builder.TEMPLATES:
        raise ValueError("Unknown template.")
    errs = resume_builder.validate(data)
    if errs:
        raise ValueError("; ".join(errs))
    heading = check_heading(data.get("skills_heading") or "Technical Skills")
    docx = resume_builder.build(data, template)
    with _tool_lock:
        UPLOAD_DIR.mkdir(exist_ok=True)
        BUILT.write_bytes(docx)
        if BUILDER_PREVIEW.exists():
            shutil.rmtree(BUILDER_PREVIEW)
        BUILDER_PREVIEW.mkdir(parents=True)
        pdf, pdf_error = BUILDER_PREVIEW / "resume.pdf", None
        try:
            pdf_export.export(BUILT, pdf)
            try:
                from shrink_pdf import shrink
                shrink(pdf)
            except ImportError:
                pass
        except Exception as e:
            pdf_error = f"PDF preview not available: {e}"
    out = {"path": BUILT.relative_to(ROOT).as_posix(), "heading": heading, "pdf_error": pdf_error}
    out.update(read_skills(BUILT, heading))  # proves the agent can tailor it
    return out


def builder_tips(body):
    data = body.get("data")
    errs = resume_builder.validate(data)
    if errs:
        raise ValueError("; ".join(errs))
    # The resume's own headline says the field best ("Junior Data Analyst"); the setup's choice is the fallback.
    field = resume_profile.guess_field(data.get("headline") or "") or \
        (body.get("field") if body.get("field") in COMMON_SKILLS else None)
    role = body.get("role") if isinstance(body.get("role"), str) and len(body.get("role")) <= 100 else ""
    return {"tips": resume_builder.tips(data, COMMON_SKILLS.get(field, [])),
            "prompt": resume_builder.claude_prompt(data, role)}


# ---------- AI features and their offline versions ----------

def resume_skills(variant=None):
    cfg, _ = read_config()
    variants = resume_variants(cfg)
    if not variants:
        raise ValueError("Add a resume first (Resumes tab or setup).")
    v = variant if variant in variants else next(iter(variants))
    code, out, err = run_tool(["tools/tailor_resume.py", f"--variant={v}", "--list"], timeout=60)
    if code != 0:
        raise ValueError((err or out).strip()[-300:])
    return v, json.loads(out)


def check_text(t, name, n=60_000):
    if not isinstance(t, str) or not t.strip() or len(t) > n:
        raise ValueError(f"Paste the {name} (up to {n // 1000}k characters).")
    return t


def match_posting(body):
    """Order the resume's skills for one posting. Offline keyword match; with AI, the AI may refine the order and score."""
    cfg, _ = read_config()
    posting = check_text(body.get("posting"), "job posting")
    variant, skills = resume_skills(body.get("variant"))
    res = match.match(skills, posting, cfg.get("field"))
    res.update(variant=variant, skills=skills, ai_used=False)
    if body.get("use_ai") and ai.available(cfg):
        j = ai.chat_json(cfg, "You help a candidate tailor a resume. " + ai.UNTRUSTED,
                         "Resume skill lines (JSON): " + json.dumps(skills, ensure_ascii=False) +
                         "\nReturn {\"score\": 1-10 fit, \"reason\": one sentence, \"first\": {label: [skills from "
                         "that line the posting values, most important first]}, \"line_order\": [labels, most relevant "
                         "first], \"gaps\": [skills the posting asks for that are not in the resume]}. Use only skills that "
                         "already appear in the resume lines for first and line_order.\n<posting>\n" + posting[:20_000] + "\n</posting>")
        if not isinstance(j, dict):
            j = {}
        lst = lambda v: v if isinstance(v, list) else []  # noqa: E731
        # keep only real skills from the resume: the AI may suggest an order, never new skills
        fj = j.get("first") if isinstance(j.get("first"), dict) else {}
        first = {l: [i for i in lst(fj.get(l)) if isinstance(i, str) and i in skills[l]] for l in skills}
        order = [l for l in lst(j.get("line_order")) if isinstance(l, str) and l in skills]
        sc = j.get("score")
        res.update(first={l: v for l, v in first.items() if v} or res["first"],
                   line_order=list(dict.fromkeys(order + list(skills))),
                   score=sc if isinstance(sc, int) and not isinstance(sc, bool) and 1 <= sc <= 10 else res["score"],
                   reason=str(j.get("reason", ""))[:300],
                   gaps=[str(g)[:60] for g in (lst(j.get("gaps")) or res["gaps"])][:15], ai_used=True)
    return res


def prepare_for_posting(body):
    """Make the tailored PDF for a pasted posting and log it, like the agent does (method: manual)."""
    company, role = body.get("company"), body.get("role")
    for v, n in ((company, "company"), (role, "role")):
        if not isinstance(v, str) or not v.strip() or len(v) > 120 or CONTROL.search(v):
            raise ValueError(f"Enter the {n} (one line).")
    url = body.get("url") or ""
    if not isinstance(url, str) or (url and not re.match(r"https?://\S+$", url)) or len(url) > 500:
        raise ValueError("The link must start with http:// or https://.")
    res = match_posting({**body, "use_ai": body.get("use_ai")})
    code, out, err = run_tool(["tools/tracker.py", "check", f"--company={company}", f"--role={role}", f"--url={url}"], timeout=30)
    if code == 3:
        return {"duplicate": out.strip()}
    if code != 0:
        raise ValueError((err or out).strip()[-300:] or "The application log could not be checked.")
    code, folder, err = run_tool(["tools/tracker.py", "folder", f"--company={company}", f"--role={role}"], timeout=30)
    folder = folder.strip()
    if code != 0 or not folder or not (ROOT / folder).resolve().is_relative_to((ROOT / "applications").resolve()):
        raise ValueError("Could not make a folder for this job.")
    cfg, _ = read_config()
    args = ["tools/tailor_resume.py", f"--variant={res['variant']}", f"--out={folder}"]
    if (cfg.get("resume_tailoring") or {}).get("enabled", True):
        args += [f"--first={l}={','.join(v)}" for l, v in res["first"].items()]
        args.append("--line-order=" + ",".join(res["line_order"]))
    code, out, err = run_tool(args)
    if code != 0:
        raise ValueError((err or out).strip()[-300:])
    pdf = json.loads(out[out.index("{"):]).get("pdf", "")
    (ROOT / folder / "job.md").write_text(
        f"# {role} - {company}\n\n- URL: {url}\n- Score: {res['score']}/10 {res.get('reason', '')}\n"
        f"- Matched: {', '.join(res['matched'])}\n- Gaps: {', '.join(res['gaps'])}\n- Apply method: manual\n"
        f"- Resume variant: {res['variant']}\n\n## Posting\n\n{body['posting'][:20_000]}\n", encoding="utf-8")
    code, new_id, err = run_tool(["tools/tracker.py", "add", f"--company={company}", f"--role={role}", f"--url={url}",
                                  "--source=manual", "--method=manual", f"--score={res['score']}", f"--folder={folder}"], timeout=30)
    if code != 0:
        raise ValueError((err or new_id).strip()[-300:] or "Could not log the application.")
    return {"folder": folder, "pdf": Path(pdf).name if pdf else "", "id": new_id.strip(), **{k: res[k] for k in ("score", "matched", "gaps")}}


def ai_polish(body):
    cfg, _ = read_config()
    data = body.get("data")
    errs = resume_builder.validate(data)
    if errs:
        raise ValueError("; ".join(errs))
    j = ai.chat_json(cfg, "You are a careful resume editor. Keep every fact exactly; never invent numbers, tools, titles "
                     "or results. Where a number would help but isn't given, write [number?]. Start bullets with an action "
                     "verb; one or two lines each.",
                     "Rewrite the summary and bullets of this resume for the role: " + str(body.get("role", ""))[:100] +
                     ". Return {\"summary\": str, \"experience\": [[bullets for each job, same count of jobs]], "
                     "\"projects\": [[bullets for each project]]}.\n" + json.dumps(
                         {k: data.get(k) for k in ("summary", "experience", "projects")}, ensure_ascii=False)[:30_000],
                     max_tokens=2500)
    if not isinstance(j, dict):
        raise ai.AIError("The AI answer had the wrong shape.")
    out = {"summary": str(j.get("summary", ""))[:2000]}
    for sec in ("experience", "projects"):
        rows = j.get(sec) if isinstance(j.get(sec), list) else []
        out[sec] = [[str(b)[:600] for b in r][:12] if isinstance(r, list) else [] for r in rows][:len(data.get(sec, []))]
    return out


def ai_prep(body):
    """Interview prep from the posting and the resume, without web research (the agent can add that)."""
    cfg, _ = read_config()
    posting = check_text(body.get("posting"), "job posting")
    company, role = str(body.get("company", ""))[:120], str(body.get("role", ""))[:120]
    if not company.strip() or not role.strip():
        raise ValueError("Enter the company and the role.")
    variant, skills = resume_skills(None)
    guide = (ROOT / "docs" / "INTERVIEW_GUIDE.md").read_text(encoding="utf-8")[:8000] if (ROOT / "docs" / "INTERVIEW_GUIDE.md").exists() else ""
    text = ai.chat(cfg, "You prepare a candidate for a job interview. Use only facts from the resume skills and the posting; "
                   "never invent experience; write [fill in] where the candidate must add a detail. " + ai.UNTRUSTED +
                   " Write Markdown in " + str(cfg.get("report_language") or "English") + ".",
                   f"Role: {role} at {company}. Field: {cfg.get('field', '')}.\nResume skills: {json.dumps(skills, ensure_ascii=False)}\n"
                   "Sections: The role in 3 lines; Likely technical questions (6-10); Likely behavioral questions (4-6); "
                   "STAR story outlines from the candidate's facts; Do's and don'ts for this field; Questions to ask them; "
                   "Gaps to brush up. Note at the top that this was made without web research.\n"
                   f"General guide:\n{guide}\n<posting>\n{posting[:20_000]}\n</posting>", max_tokens=3000)
    stem = re.sub(r"[^\w .()&+-]", "-", f"{company} - {role}")[:90].strip(" .-") or "interview"
    if not re.match(r"[A-Za-z0-9]", stem) or re.fullmatch(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", stem.split(".", 1)[0].strip(), re.I):
        stem = "prep " + stem
    name = stem + ".md"
    d = NOTE_DIRS["prep"]
    d.mkdir(exist_ok=True)
    target = (d / name).resolve()
    if not NOTE_NAME.fullmatch(name) or not target.is_relative_to(d.resolve()):
        raise ValueError("Could not name the prep file; try a simpler company or role name.")
    target.write_text(text, encoding="utf-8")
    return {"file": name}


def ai_suggest(body):
    """Suggestions while filling the settings: local job sites, local-language search terms, field tips."""
    cfg, _ = read_config()
    kind = body.get("kind")
    country, field, level = (str(body.get(k, ""))[:60] for k in ("country", "field", "level"))
    roles = [str(r)[:80] for r in (body.get("roles") or [])][:8]
    if kind == "sites":
        j = ai.chat_json(cfg, "You know the job market well and only name real, well-known job sites.",
                         f"Job seeker in {country}, field {field}, level {level}. List up to 6 job sites people in {country} "
                         "actually use for this (not LinkedIn/Indeed/Glassdoor). Return [{\"name\", \"domain\" (like "
                         "example.com), \"needs_signin\": bool, \"notes\": one line}].")
        out = []
        for s in j if isinstance(j, list) else []:
            dom = str(s.get("domain", "")).lower().strip() if isinstance(s, dict) else ""
            dom = re.sub(r"^https?://|/.*$", "", dom)
            if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", dom):
                out.append({"name": str(s.get("name", dom))[:60], "domain": dom, "needs_signin": bool(s.get("needs_signin")),
                            "notes": str(s.get("notes", ""))[:200]})
        return {"sites": out[:6]}
    if kind == "terms":
        j = ai.chat_json(cfg, "You translate job titles the way local job boards write them.",
                         f"Country {country}. Job titles: {roles}. Return [search terms in the main local language of "
                         f"{country}, as people search on local job boards, up to 10].")
        return {"terms": [str(t)[:80] for t in (j if isinstance(j, list) else [])][:10]}
    if kind == "tips":
        text = ai.chat(cfg, "You are a career adviser. Be concrete and brief. Say when something depends on the country.",
                       f"A {level} candidate looking for {field} jobs in {country}. Give 6-8 bullet tips for the job search, "
                       "the resume and interviews specific to this field and country, then 3 well-known guides or "
                       "communities to look at (names only, no invented links). Markdown.", max_tokens=900)
        return {"text": text[:6000]}
    raise ValueError("Unknown suggestion.")


def offline_searches():
    """Search links for every enabled site and term, to search by hand when no agent runs."""
    cfg, _ = read_config()
    terms = (cfg.get("search_terms_en") or [])[:6] + (cfg.get("search_terms_local") or [])[:4]
    loc, days = cfg.get("search_location", ""), int(cfg.get("search_window_days") or 3)
    out = []
    for s in cfg.get("sources") or []:
        if not isinstance(s, dict) or not s.get("enabled"):
            continue
        tpl = s.get("search", "")
        m = re.search(r"https?://[^\s,]+", tpl)
        if m and "{query}" in m.group(0):
            links = [{"term": t, "url": m.group(0).replace("{query}", quote(t)).replace("{location}", quote(loc))
                      .replace("{days}", str(days)).replace("{seconds}", str(days * 86400))} for t in terms]
        else:
            dom = m.group(0) if m else (re.search(r"[a-z0-9-]+(\.[a-z0-9-]+)+\.[a-z]{2,}|[a-z0-9-]+\.[a-z]{2,}", tpl.lower()) or [None])[0]
            url = dom if (dom or "").startswith("http") else (f"https://{dom}" if dom else "")
            links = [{"term": "open the site", "url": url}] if url else []
        out.append({"name": s.get("name", ""), "how": tpl[:300], "apply": s.get("apply", ""), "links": links})
    return {"sites": out, "terms": terms}


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "JobHuntAgent"
    timeout = 30  # drop clients that stall mid-request

    def log_message(self, fmt, *args):  # quiet console
        pass

    # Only accept requests addressed to this local server (blocks DNS-rebinding and
    # cross-site requests from other pages open in the browser).
    def _allowed(self):
        port = self.server.server_address[1]
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in hosts:
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{h}" for h in hosts}:
            return False
        if self.path.startswith("/api/") and self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            return False  # e.g. <img src="http://127.0.0.1:8765/api/..."> on another site
        if self.command == "POST" and \
                self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return False
        return True

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else (
            json.dumps(body, ensure_ascii=False).encode("utf-8") if ctype.startswith("application/json")
            else body.encode("utf-8"))
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _body_limit(self):
        return MAX_UPLOAD_BODY if urlsplit(self.path).path == "/api/upload" else MAX_BODY

    def _json_body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("Bad Content-Length.")
        if n <= 0 or n > self._body_limit():
            raise ValueError("Empty or too large request.")
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _variant_path(self, name):
        cfg, _ = read_config()
        if not isinstance(name, str) or not VARIANT_NAME.fullmatch(name) or name not in resume_variants(cfg):
            raise ValueError("Unknown resume version.")
        return name

    def do_GET(self):
        if not self._allowed():
            return self._send(403, {"error": "Forbidden"})
        url = urlsplit(self.path)
        path, q = url.path, parse_qs(url.query)
        try:
            if path == "/":
                return self._send(200, (UI_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/api/ping":
                return self._send(200, {"ok": True})
            if path in ("/app.js", "/setup.js", "/builder.js", "/prepare.js", "/ai.js"):
                return self._send(200, (UI_DIR / path[1:]).read_bytes(), "text/javascript; charset=utf-8")
            if path == "/api/config":
                cfg, exists = read_config()
                return self._send(200, {"config": cfg, "exists": exists, "folder": host_folder(),
                                        "in_docker": IN_DOCKER, "pdf_engine": pdf_export.engine()})
            if path == "/api/health":
                return self._send(200, {"items": health()})
            if path == "/api/applications":
                return self._send(200, {"rows": read_applications(), "statuses": STATUSES})
            if path == "/api/runs":
                files = sorted((p for p in RUNS_DIR.glob("*.md") if RUN_NAME.fullmatch(p.name)), reverse=True) \
                    if RUNS_DIR.exists() else []
                return self._send(200, {"runs": [p.name for p in files]})
            if path.startswith("/api/runs/"):
                name = path.rsplit("/", 1)[1]
                if not RUN_NAME.fullmatch(name) or not (RUNS_DIR / name).is_file():
                    return self._send(404, {"error": "Report not found."})
                return self._send(200, {"name": name, "text": (RUNS_DIR / name).read_text(encoding="utf-8")})
            if path == "/api/resume/skills":
                v = self._variant_path(q.get("variant", [""])[0])
                code, out, err = run_tool(["tools/tailor_resume.py", f"--variant={v}", "--list"], timeout=60)
                if code != 0:
                    return self._send(200, {"ok": False, "error": (err or out).strip()})
                return self._send(200, {"ok": True, "skills": json.loads(out)})
            if path == "/api/resume/preview.pdf":
                v = self._variant_path(q.get("variant", [""])[0])
                pdfs = list((PREVIEW_DIR / v).glob("*.pdf"))
                if not pdfs:
                    return self._send(404, {"error": "Run the PDF test first."})
                return self._send(200, pdfs[0].read_bytes(), "application/pdf",
                                  {"Content-Disposition": "inline; filename=preview.pdf"})
            if path in ("/api/builder/preview.pdf", "/api/builder/resume.docx"):
                f = BUILDER_PREVIEW / "resume.pdf" if path.endswith(".pdf") else BUILT
                if not f.is_file():
                    return self._send(404, {"error": "Create the resume first."})
                if path.endswith(".pdf"):
                    return self._send(200, f.read_bytes(), "application/pdf", {"Content-Disposition": "inline; filename=resume.pdf"})
                return self._send(200, f.read_bytes(),
                                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                  {"Content-Disposition": "attachment; filename=resume.docx"})
            if path == "/api/builder/templates":
                return self._send(200, {"templates": {k: {"label": v["label"], "for": v["for"], "accent": v["accent"],
                                                          "font": v["font"], "order": v["order"], "center": v["center"],
                                                          "heading": v.get("heading", "border"),
                                                          "name_accent": bool(v.get("name_accent")),
                                                          "compact": v.get("margin", 720) < 720}
                                                      for k, v in resume_builder.TEMPLATES.items()}})
            if path in ("/api/notes/prep", "/api/notes/learning"):
                d = NOTE_DIRS[path.rsplit("/", 1)[1]]
                files = sorted((f.name for f in d.glob("*.md") if NOTE_NAME.fullmatch(f.name)), key=str.lower) \
                    if d.exists() else []
                return self._send(200, {"files": files})
            if path.startswith(("/api/notes/prep/", "/api/notes/learning/")):
                kind, name = path.split("/")[3], unquote(path.split("/", 4)[4])
                if not NOTE_NAME.fullmatch(name):  # before building any path (no UNC lookups, no traversal)
                    return self._send(404, {"error": "Not found."})
                d = NOTE_DIRS[kind].resolve()
                f = (d / name).resolve()
                if not f.is_relative_to(d) or not f.is_file():
                    return self._send(404, {"error": "Not found."})
                with f.open("r", encoding="utf-8", errors="replace") as fp:
                    text = fp.read(300_000)
                return self._send(200, {"name": name, "text": text})
            if path == "/api/ai":
                cfg, _ = read_config()
                return self._send(200, {"status": ai.status(cfg), "providers": [
                    {"id": k, "label": v[0], "base_url": v[2], "model": v[3], "key_env": v[4], "needs_key": v[5], "local": v[6]}
                    for k, v in ai.PROVIDERS.items()]})
            if path == "/api/offline/searches":
                return self._send(200, offline_searches())
            if path == "/api/offline/learn":
                skill = q.get("skill", [""])[0].strip()
                if not skill or len(skill) > 60:
                    raise ValueError("Enter a skill.")
                return self._send(200, {"links": match.learning_links(skill)})
            if path == "/api/schedule":
                cfg, _ = read_config()
                return self._send(200, {"prompt": schedule_prompt(), "folder": host_folder(), **schedule_info(cfg)})
            return self._send(404, {"error": "Not found"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:  # keep the panel alive and show the problem
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        if not self._allowed():
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if 0 < n <= 65536:
                self.rfile.read(n)  # drain small bodies, so the client gets the 403 instead of a reset
            self.close_connection = True
            return self._send(403, {"error": "Forbidden"})
        path = urlsplit(self.path).path
        try:
            body = self._json_body()
            if path == "/api/config":
                cfg = body.get("config") if isinstance(body, dict) else None
                errs = validate_config(cfg)
                if errs:
                    return self._send(400, {"error": "Not saved.", "problems": errs})
                write_config(cfg)
                return self._send(200, {"ok": True})
            if path == "/api/resume/test":
                if not CONFIG_PATH.exists():
                    return self._send(400, {"error": "Save your settings first."})
                v = self._variant_path(body.get("variant"))
                out_dir = (PREVIEW_DIR / v).resolve()
                if not out_dir.is_relative_to(PREVIEW_DIR.resolve()) or out_dir == PREVIEW_DIR.resolve():
                    raise ValueError("Unknown resume version.")

                def clear():
                    if out_dir.exists():
                        shutil.rmtree(out_dir)
                code, out, err = run_tool(["tools/tailor_resume.py", f"--variant={v}", f"--out={out_dir}"], before=clear)
                if code != 0:
                    return self._send(200, {"ok": False, "error": (err or out).strip()[-2000:]})
                res = json.loads(out[out.index("{"):])
                return self._send(200, {"ok": True, "pdf_mb": res.get("pdf_mb"), "warning": res.get("warning")})
            if path == "/api/upload":
                if not isinstance(body, dict):
                    raise ValueError("Bad request.")
                if not _upload_slots.acquire(blocking=False):
                    return self._send(429, {"error": "Another upload is in progress. Try again in a moment."})
                try:
                    return self._send(200, {"ok": True, **save_upload(body)})
                finally:
                    _upload_slots.release()
            if path == "/api/resume/inspect":
                if not isinstance(body, dict):
                    raise ValueError("Bad request.")
                return self._send(200, {"ok": True, **reread_skills(body)})
            if path == "/api/ai/key":
                if not isinstance(body, dict):
                    raise ValueError("Bad request.")
                name, value = body.get("name"), body.get("value", "")
                ai.set_key(name, value)
                return self._send(200, {"ok": True, "key_set": bool(ai.get_key(name))})
            if path.startswith("/api/ai/") or path in ("/api/match", "/api/match/prepare"):
                if not isinstance(body, dict):
                    raise ValueError("Bad request.")
                if not _ai_slots.acquire(blocking=False):
                    return self._send(429, {"error": "Busy with another AI request. Try again in a moment."})
                try:
                    cfg, _ = read_config()
                    if path == "/api/ai/test":
                        return self._send(200, {"ok": True, "answer": ai.chat(cfg, "You are a connection test.",
                                                                              "Reply with one word: ready", max_tokens=20)[:100]})
                    handler = {"/api/match": match_posting, "/api/match/prepare": prepare_for_posting,
                               "/api/ai/polish": ai_polish, "/api/ai/prep": ai_prep, "/api/ai/suggest": ai_suggest}.get(path)
                    if not handler:
                        return self._send(404, {"error": "Not found"})
                    return self._send(200, {"ok": True, **handler(body)})
                except ai.AIError as e:
                    return self._send(200, {"ok": False, "error": str(e)})
                finally:
                    _ai_slots.release()
            if path in ("/api/builder/parse", "/api/builder/build", "/api/builder/tips"):
                if not isinstance(body, dict):
                    raise ValueError("Bad request.")
                if path.endswith("parse"):
                    if not _upload_slots.acquire(blocking=False):
                        return self._send(429, {"error": "Busy reading another file. Try again in a moment."})
                    try:
                        return self._send(200, {"ok": True, "data": resume_builder.parse(builder_source(body))})
                    finally:
                        _upload_slots.release()
                if path.endswith("build"):
                    return self._send(200, {"ok": True, **builder_build(body)})
                return self._send(200, {"ok": True, **builder_tips(body)})
            if path == "/api/applications/status":
                rid, status = str(body.get("id", "")), body.get("status")
                note = body.get("note", "")
                if not rid.isdigit() or status not in STATUSES or not isinstance(note, str) or len(note) > 500:
                    return self._send(400, {"error": "Bad id, status or note."})
                args = ["tools/tracker.py", "update", f"--id={rid}", f"--status={status}"]
                if note.strip():
                    args.append(f"--notes={note.strip()}")
                code, out, err = run_tool(args, timeout=30)
                return self._send(200 if code == 0 else 400, {"ok": code == 0, "message": (out or err).strip()})
            return self._send(404, {"error": "Not found"})
        except (ValueError, json.JSONDecodeError) as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--host", default="127.0.0.1",
                    help="address to listen on; use 0.0.0.0 only inside Docker (publish it on 127.0.0.1)")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Job-Hunt Agent control panel: {url}  (Ctrl+C to stop)")
    if pdf_export.engine() == "word":
        threading.Thread(target=check_word, daemon=True).start()  # warm up the slow Word check
    if not args.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
