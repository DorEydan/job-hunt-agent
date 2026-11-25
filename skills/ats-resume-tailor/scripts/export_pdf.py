#!/usr/bin/env python3
"""Turn a .docx into a small PDF: Microsoft Word on Windows (exact layout), LibreOffice elsewhere.

  python export_pdf.py resume.docx [resume.pdf] [--engine word|libreoffice]

The .docx is checked first (docx_safe.py): files with macros, or with links to network or local paths, are refused,
since Word or LibreOffice would act on them. Word runs with macros force-disabled.
If the PDF is over 1 MB and fontTools + pypdf are installed, oversized embedded fonts are subset (shrink_pdf.py).
Output is JSON {"pdf", "mb", "engine", "shrunk", "warning"?}. Exit code 2 = export failed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from docx_safe import DocxError, open_docx  # noqa: E402


def fail(msg):
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(2)


def powershell():
    p = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(p) if p.exists() else None


def soffice_path():
    cwd = Path.cwd().resolve()
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p and Path(p).resolve().parent != cwd:  # never a copy sitting in the current folder
            return p
    for p in (Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
              Path(r"C:\Program Files\LibreOffice\program\soffice.exe")):
        if p.exists():
            return str(p)
    return None


def with_word(docx, pdf, timeout):
    ps = powershell()
    if not ps:
        raise RuntimeError("PowerShell not found.")
    subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "docx_to_pdf.ps1"),
                    "-Docx", str(docx), "-Pdf", str(pdf)], check=True, timeout=timeout, capture_output=True)


def with_libreoffice(docx, pdf, timeout):
    soffice = soffice_path()
    if not soffice:
        raise RuntimeError("LibreOffice is not installed. Install it (libreoffice.org) or use Word on Windows.")
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp, "profile").as_uri()  # private profile: no clash with an open LibreOffice window
        subprocess.run([soffice, f"-env:UserInstallation={profile}", "--headless", "--norestore", "--nolockcheck",
                        "--convert-to", "pdf", "--outdir", tmp, str(docx)], check=True, timeout=timeout,
                       capture_output=True)
        out = Path(tmp, docx.stem + ".pdf")
        if not out.exists():
            raise RuntimeError("LibreOffice did not produce a PDF.")
        shutil.move(str(out), pdf)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx")
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--engine", choices=("word", "libreoffice"))
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()
    docx = Path(a.docx).resolve()
    if not docx.is_file() or docx.suffix.lower() != ".docx":
        fail(f"Not a .docx file: {docx}")
    try:
        z, _ = open_docx(docx)
        z.close()
    except DocxError as e:
        fail(str(e))
    pdf = Path(a.pdf).resolve() if a.pdf else docx.with_suffix(".pdf")
    if pdf.suffix.lower() != ".pdf":
        fail("The output must end in .pdf.")
    if pdf == docx or pdf.is_symlink():
        fail("Choose another output path.")
    pdf.parent.mkdir(parents=True, exist_ok=True)

    engines = [a.engine] if a.engine else (["word", "libreoffice"] if sys.platform == "win32" else ["libreoffice"])
    errors, used = [], None
    fd, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=pdf.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        for e in engines:
            tmp.unlink(missing_ok=True)
            try:
                (with_word if e == "word" else with_libreoffice)(docx, tmp, a.timeout)
                if tmp.exists() and tmp.stat().st_size:
                    used = e
                    break
            except Exception as ex:  # Word missing, LibreOffice missing, timeout
                errors.append(f"{e}: {str(ex)[:300]}")
        if not used:
            fail("PDF export failed. " + " | ".join(errors))
        os.replace(tmp, pdf)
    finally:
        tmp.unlink(missing_ok=True)

    result = {"pdf": str(pdf), "engine": used, "shrunk": False}
    if pdf.stat().st_size > 1_000_000:
        try:
            from shrink_pdf import shrink
            shrink(pdf)
            result["shrunk"] = True
        except ImportError:
            result["warning"] = "PDF not shrunk: pip install fonttools pypdf"
        except Exception as ex:  # an unusual font: keep the unshrunk PDF
            result["warning"] = f"PDF not shrunk ({type(ex).__name__}); the file is still valid."
    result["mb"] = round(pdf.stat().st_size / 1e6, 2)
    if result["mb"] > 2:
        result["warning"] = "PDF is over 2 MB: LinkedIn and many forms reject it. Remove large images or emoji icons."
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
