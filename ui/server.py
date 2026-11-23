#!/usr/bin/env python3
"""Local control panel for the job-hunt agent.

Runs only on this computer (127.0.0.1) and serves one page: setup, resume check,
application log, run reports and automation setup. Standard library only.

    .venv\\Scripts\\python.exe ui\\server.py [--port 8765] [--no-browser]
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from common import CONFIG_PATH, EXAMPLE_PATH, resume_variants  # noqa: E402

UI_DIR = ROOT / "ui"
RUNS_DIR = ROOT / "runs"
CSV_PATH = ROOT / "applications.csv"
PREVIEW_DIR = ROOT / ".preview"
PY = sys.executable
MAX_BODY = 1_000_000
STATUSES = ["prepared", "sent", "manual", "failed", "skipped"]
RUN_NAME = re.compile(r"\d{4}-\d{2}-\d{2}[A-Za-z0-9_-]*\.md")  # always used with fullmatch
VARIANT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}")  # always used with fullmatch
SCHEDULE_CRON = "0 9 * * 0,2,4"

_word_check = {"done": False, "ok": None, "detail": ""}
_tool_lock = threading.Lock()  # Word COM, the CSV and .preview are not safe for parallel use
_config_lock = threading.Lock()
_word_lock = threading.Lock()


# ---------- helpers ----------

def read_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")), True
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8")), False


STR_LISTS = ["target_roles", "search_terms_en", "search_terms_local"]
INTS = ["dedup_days", "pending_days", "max_new_jobs_per_run", "min_match_score"]


def check_resume_path(name, path):
    if not isinstance(path, str) or not path.lower().endswith(".docx"):
        return [f"Resume '{name}': the path must point to a .docx file."]
    if path.startswith(("\\\\", "//")):
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
    return errs


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

    add("python", "Python environment", sys.version_info >= (3, 10),
        f"Python {sys.version.split()[0]}", "Install Python 3.10 or newer, then run start.bat again.")
    missing = []
    for mod in ("fontTools", "pypdf"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    add("packages", "Python packages", not missing, "fontTools, pypdf" if not missing else "",
        f"Missing: {', '.join(missing)}. Run start.bat again (it installs requirements.txt).")
    w = check_word()
    add("word", "Microsoft Word (for PDF export)", bool(w["ok"]), w["detail"],
        "Install Microsoft Word on this computer. It is used to turn the resume into a PDF.")
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
    claude = shutil.which("claude")
    add("claude", "Claude Code installed", True if claude else None,
        "claude CLI found" if claude else "Using the Claude desktop app is fine too.",
        "Install Claude Code (desktop app or CLI). The agent runs inside it.")
    return items


def read_applications():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    keep = ["id", "date_found", "date_sent", "status", "company", "role", "source", "job_url",
            "apply_method", "match_score", "folder", "notes"]
    return [{k: r.get(k, "") for k in keep} for r in rows]


def schedule_prompt():
    return (f"Open the folder {ROOT} and follow AGENT.md in it: run Phase A (search and prepare), "
            "write the run report, then stop and wait for my approval before sending anything.")


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

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
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
            if path == "/app.js":
                return self._send(200, (UI_DIR / "app.js").read_bytes(), "text/javascript; charset=utf-8")
            if path == "/api/config":
                cfg, exists = read_config()
                return self._send(200, {"config": cfg, "exists": exists, "folder": str(ROOT)})
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
            if path == "/api/schedule":
                return self._send(200, {"prompt": schedule_prompt(), "cron": SCHEDULE_CRON, "folder": str(ROOT)})
            return self._send(404, {"error": "Not found"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:  # keep the panel alive and show the problem
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        if not self._allowed():
            n = int(self.headers.get("Content-Length") or 0)
            if 0 < n <= MAX_BODY:
                self.rfile.read(n)  # drain, so the client gets the 403 instead of a reset
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
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Job-Hunt Agent control panel: {url}  (Ctrl+C to stop)")
    threading.Thread(target=check_word, daemon=True).start()  # warm up the slow Word check
    if not args.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
