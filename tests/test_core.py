"""Tests for the parts that matter most: dedup, resume tailoring and the local server's guards.

Run:  python -m unittest discover -s tests -v
No Microsoft Word needed (PDF export is skipped with --no-pdf).
"""
import http.client
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
_created_config = False
if not CONFIG.exists():  # CI / fresh clone: use the example settings
    shutil.copy(ROOT / "config.example.json", CONFIG)
    _created_config = True

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "ui"))
import tracker  # noqa: E402
import server  # noqa: E402


def tearDownModule():
    if _created_config:
        CONFIG.unlink(missing_ok=True)


class TrackerMatching(unittest.TestCase):
    def test_same_role_any_word_order(self):
        a, b = tracker.role_key("DevOps Engineer - Junior"), tracker.role_key("Junior DevOps Engineer")
        self.assertTrue(tracker.same_role(a, b))

    def test_different_roles(self):
        a, b = tracker.role_key("Junior Frontend Developer"), tracker.role_key("Senior Data Scientist")
        self.assertFalse(tracker.same_role(a, b))

    def test_company_noise_removed(self):
        self.assertEqual(tracker.company_key("Acme Technologies Ltd."), tracker.company_key("acme"))

    def test_linkedin_url_ignores_tracking(self):
        u1 = "https://www.linkedin.com/jobs/view/123456/?trk=abc&refId=x"
        u2 = "https://il.linkedin.com/jobs/view/123456"
        self.assertEqual(tracker.url_key(u1), tracker.url_key(u2))

    def test_blocking_window(self):
        import datetime as dt
        today = dt.date.today().isoformat()
        old = (dt.date.today() - dt.timedelta(days=tracker.CONFIG["dedup_days"] + 1)).isoformat()
        row = {"status": "sent", "date_sent": today, "date_found": today, "job_url": "",
               "company_key": tracker.company_key("Acme"), "role_key": tracker.role_key("Junior DevOps Engineer")}
        self.assertTrue(tracker.blocking_rows([row], "Acme", "DevOps Engineer - Junior", ""))
        row["date_sent"] = row["date_found"] = old
        self.assertFalse(tracker.blocking_rows([row], "Acme", "DevOps Engineer - Junior", ""))


def tailor(*args):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "tailor_resume.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=ROOT)


class TailorResume(unittest.TestCase):
    def test_list_reads_sample(self):
        p = tailor("--list")
        self.assertEqual(p.returncode, 0, p.stderr)
        skills = json.loads(p.stdout)
        self.assertIn("React", skills["Frameworks"])

    def test_reorder_changes_only_skills(self):
        with tempfile.TemporaryDirectory() as d:
            p = tailor("--out", d, "--no-pdf", "--first", "Frameworks=React,Express", "--line-order", "Frameworks")
            self.assertEqual(p.returncode, 0, p.stderr)
            res = json.loads(p.stdout)
            self.assertEqual(list(res["skills"])[0], "Frameworks")
            self.assertEqual(res["skills"]["Frameworks"][:2], ["React", "Express"])
            with zipfile.ZipFile(res["docx"]) as z:
                xml = z.read("word/document.xml").decode("utf-8")
            self.assertIn("Frameworks: ", xml.replace("</w:t></w:r><w:r>", "").replace(
                '<w:t xml:space="preserve">', ""))

    def test_unknown_skill_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = tailor("--out", d, "--no-pdf", "--first", "Frameworks=Kubernetes")
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("not a skill", p.stdout + p.stderr)


class ServerValidation(unittest.TestCase):
    def test_example_config_is_valid(self):
        cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(server.validate_config(cfg), [])

    def test_bad_values_rejected(self):
        errs = server.validate_config({"max_new_jobs_per_run": "lots", "base_resumes": {"-h": "x.docx", "ok": "x.pdf"}})
        self.assertEqual(len(errs), 3, errs)

    def test_variant_name_rules(self):
        for bad in ("..", "-h", "a b", "devops\n", "../tools", ""):
            self.assertIsNone(server.VARIANT_NAME.fullmatch(bad), bad)
        for good in ("devops", "full-stack", "v2_en"):
            self.assertIsNotNone(server.VARIANT_NAME.fullmatch(good), good)

    def test_network_paths_rejected(self):
        self.assertTrue(server.check_resume_path("x", r"\\evil\share\cv.docx"))
        self.assertTrue(server.check_resume_path("x", "//evil/share/cv.docx"))
        self.assertFalse(server.check_resume_path("x", r"C:\docs\cv.docx"))


class Customization(unittest.TestCase):
    def cfg(self):
        return json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))

    def test_example_has_glassdoor_and_settings(self):
        c = self.cfg()
        self.assertIn("glassdoor", [s["id"] for s in c["sources"]])
        for k in ("schedule", "search_window_days", "job_types", "apply_methods", "exclude_companies"):
            self.assertIn(k, c)

    def test_schedule_cron_and_gap(self):
        info = server.schedule_info({"schedule": {"days": ["thu", "mon"], "time": "18:30"}})
        self.assertEqual(info["cron"], "30 18 * * 1,4")
        self.assertEqual(info["max_gap_days"], 4)  # Thursday -> Monday
        self.assertEqual(server.schedule_info({"schedule": {"days": ["wed"], "time": "07:05"}})["max_gap_days"], 7)

    def test_bad_schedule_rejected(self):
        c = self.cfg()
        c["schedule"] = {"days": [], "time": "25:00"}
        self.assertEqual(len(server.validate_extras(c)), 2)
        c["schedule"] = {"days": ["funday"], "time": "09:00"}
        self.assertEqual(len(server.validate_extras(c)), 1)

    def test_bad_sources_rejected(self):
        c = self.cfg()
        c["sources"][0]["id"] = "Bad Id"
        c["sources"].append(dict(c["sources"][1]))  # duplicate id
        c["sources"][2]["enabled"] = "yes"
        errs = server.validate_extras(c)
        self.assertEqual(len(errs), 3, errs)

    def test_old_config_gets_new_defaults(self):
        backup = CONFIG.read_text(encoding="utf-8")
        try:
            old = json.loads(backup)
            for k in ("sources", "schedule", "job_types"):
                old.pop(k, None)
            CONFIG.write_text(json.dumps(old), encoding="utf-8")
            cfg, exists = server.read_config()
            self.assertTrue(exists)
            self.assertIn("sources", cfg)
            self.assertEqual(server.validate_config(cfg), [])
        finally:
            CONFIG.write_text(backup, encoding="utf-8")


def make_docx(paragraphs):
    """A minimal Word file in memory."""
    import io
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


class ResumeProfile(unittest.TestCase):
    def setUp(self):
        import resume_profile
        self.rp = resume_profile

    def test_sample_resume(self):
        p = self.rp.profile((ROOT / "examples" / "sample-resume.docx").read_bytes())
        self.assertEqual(p["full_name"], "Jane Doe")
        self.assertEqual(p["email"], "jane@example.com")
        self.assertEqual(p["country"], "Israel")
        self.assertEqual(p["field"], "software")
        self.assertEqual(p["skills_heading"], "Technical Skills")
        self.assertTrue(p["degree"].startswith("BSc"))

    def test_only_relevant_experience_counts(self):
        import datetime as dt
        data = make_docx(["Anna Nowak", "Junior DevOps Engineer", "Warsaw, Poland | anna@test.dev | +48 600 100 200",
                          "Technical Skills", "Cloud: AWS, Docker", "Scripting: Python, Bash", "Experience",
                          "DevOps Intern | Acme | 2025 – Present", "Waiter | Cafe | 2015 – 2022",
                          "Education", "BSc Computer Science | Some University | 2020 – 2024"])
        p = self.rp.profile(data, today=dt.date(2026, 6, 1))
        self.assertEqual(p["country"], "Poland")
        self.assertEqual(p["field"], "devops")
        self.assertEqual(p["years_experience"], 1)  # the waiter job and the degree years don't count
        self.assertEqual(p["experience_level"], "junior")
        self.assertEqual(p["phone"], "+48 600 100 200")


class Uploads(unittest.TestCase):
    def setUp(self):
        self.made_dir = not server.UPLOAD_DIR.exists()

    def tearDown(self):
        for f in ("resume-default.docx", "cover-letter.txt"):
            (server.UPLOAD_DIR / f).unlink(missing_ok=True)
        if self.made_dir and server.UPLOAD_DIR.exists() and not any(server.UPLOAD_DIR.iterdir()):
            server.UPLOAD_DIR.rmdir()

    def up(self, **kw):
        import base64
        body = {"kind": "resume", "filename": "cv.docx", **kw}
        if isinstance(body.get("data"), bytes):
            body["data"] = base64.b64encode(body["data"]).decode()
        return server.save_upload(body)

    def test_resume_saved_under_fixed_name_and_read(self):
        r = self.up(filename="../../evil name.docx", data=(ROOT / "examples" / "sample-resume.docx").read_bytes())
        self.assertEqual(r["path"], "uploads/resume-default.docx")
        self.assertIn("Frameworks", r["skills"])
        self.assertEqual(r["profile"]["full_name"], "Jane Doe")

    def test_bad_files_rejected(self):
        for kw in ({"filename": "cv.pdf", "data": b"%PDF-1"}, {"data": b"not a zip"}, {"data": b""},
                   {"kind": "evil", "data": b"x"}, {"variant": "../x", "data": b"x"},
                   {"data": "@@not base64@@"}, {"data": b"x" * (server.MAX_FILE + 1)},
                   {"kind": "cover_letter", "filename": "c.pdf", "data": b"not a pdf"}):
            with self.assertRaises(ValueError, msg=str(kw)[:60]):
                self.up(**kw)

    def test_zip_without_word_rejected(self):
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("hello.txt", "hi")
        with self.assertRaises(ValueError):
            self.up(data=buf.getvalue())

    def test_docx_with_local_link_or_dtd_rejected(self):
        import io
        for name, content in (("word/_rels/document.xml.rels",
                               '<Relationships><Relationship Id="r1" Target="file:///etc/passwd" TargetMode="External"/></Relationships>'),
                              ("word/_rels/document.xml.rels",
                               '<Relationships><Relationship Id="r1" TargetMode="External" Target="\\\\host\\share\\x.png"/></Relationships>')):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr("word/document.xml", "<w:document/>")
                z.writestr(name, content)
            with self.assertRaises(ValueError):
                self.up(data=buf.getvalue())
        with self.assertRaises(ValueError):
            self.up(data=make_docx(["x"]).replace(b"<?xml", b"<!DOCTYPE x><?xml"))

    def test_heading_with_control_chars_rejected(self):
        with self.assertRaises(ValueError):
            self.up(data=make_docx(["x"]), heading="Skills\x00")

    def test_mixed_slash_network_paths_rejected(self):
        for p in ("\\/host\\share\\cv.docx", "/\\host\\share\\cv.docx", " \\\\host\\share\\cv.docx"):
            self.assertTrue(server.check_resume_path("x", p), p)

    def test_cover_letter_text(self):
        r = self.up(kind="cover_letter", filename="letter.txt", data="Dear team".encode())
        self.assertEqual(r["path"], "uploads/cover-letter.txt")
        self.assertEqual(r["text"], "Dear team")

    def test_inspect_stays_in_uploads(self):
        for path in ("../config.example.json", "examples/sample-resume.docx", "uploads/../README.md"):
            with self.assertRaises(ValueError):
                server.reread_skills({"path": path, "heading": "Technical Skills"})


class SetupSettings(unittest.TestCase):
    def cfg(self):
        return json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))

    def test_new_fields_validated(self):
        c = self.cfg()
        c["locations"]["max_commute_km"] = -5
        c["cover_letter_file"] = r"\\server\share\letter.docx"
        c["setup_complete"] = "yes"
        self.assertEqual(len(server.validate_extras(c)), 3)

    def test_example_starts_setup_but_old_configs_do_not(self):
        self.assertIs(self.cfg()["setup_complete"], False)
        backup = CONFIG.read_text(encoding="utf-8")
        try:
            old = json.loads(backup)
            old.pop("setup_complete", None)
            CONFIG.write_text(json.dumps(old), encoding="utf-8")
            self.assertIs(server.read_config()[0]["setup_complete"], True)
        finally:
            CONFIG.write_text(backup, encoding="utf-8")

    def test_pdf_engine_choice(self):
        import os
        import pdf_export
        old = os.environ.get("JOBHUNT_PDF_ENGINE")
        try:
            os.environ["JOBHUNT_PDF_ENGINE"] = "libreoffice"
            self.assertEqual(pdf_export.engine(), "libreoffice")
            os.environ["JOBHUNT_PDF_ENGINE"] = ""
            self.assertEqual(pdf_export.engine(), "word" if sys.platform == "win32" else "libreoffice")
        finally:
            os.environ.pop("JOBHUNT_PDF_ENGINE", None)
            if old is not None:
                os.environ["JOBHUNT_PDF_ENGINE"] = old


class ServerGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, method, path, headers=None, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"127.0.0.1:{self.port}", **(headers or {})}
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        r.read()
        return r.status

    def test_normal_request_ok(self):
        self.assertEqual(self.req("GET", "/api/config"), 200)

    def test_foreign_host_blocked(self):  # DNS rebinding
        self.assertEqual(self.req("GET", "/api/config", {"Host": "evil.example"}), 403)

    def test_cross_site_get_blocked(self):
        self.assertEqual(self.req("GET", "/api/runs", {"Sec-Fetch-Site": "cross-site"}), 403)

    def test_foreign_origin_post_blocked(self):
        self.assertEqual(self.req("POST", "/api/config", {"Origin": "http://evil.example",
                                  "Content-Type": "application/json"}, "{}"), 403)

    def test_post_needs_json(self):
        self.assertEqual(self.req("POST", "/api/config", {"Content-Type": "text/plain"}, "{}"), 403)

    def test_run_report_traversal(self):
        self.assertEqual(self.req("GET", "/api/runs/..%2Fconfig.json"), 404)


if __name__ == "__main__":
    unittest.main()
