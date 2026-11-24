"""Turn a .docx into a PDF with Microsoft Word (Windows) or LibreOffice (Docker, Linux, macOS).

Engine choice: the JOBHUNT_PDF_ENGINE environment variable ("word" or "libreoffice");
otherwise Word on Windows and LibreOffice everywhere else.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def engine():
    e = os.environ.get("JOBHUNT_PDF_ENGINE", "").strip().lower()
    if e in ("word", "libreoffice"):
        return e
    return "word" if sys.platform == "win32" else "libreoffice"


def soffice_path():
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    return str(mac) if mac.exists() else None


def export(docx: Path, pdf: Path, timeout=180):
    docx, pdf = Path(docx).resolve(), Path(pdf).resolve()
    if engine() == "word":
        ps1 = ROOT / "tools" / "docx_to_pdf.ps1"
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1),
                        "-Docx", str(docx), "-Pdf", str(pdf)], check=True, timeout=timeout)
    else:
        soffice = soffice_path()
        if not soffice:
            raise RuntimeError("LibreOffice is not installed (needed for PDF export). "
                               "Use the Docker image, install LibreOffice, or set JOBHUNT_PDF_ENGINE=word on Windows.")
        with tempfile.TemporaryDirectory() as tmp:
            # A private profile dir avoids clashes with a LibreOffice window that is already open.
            profile = Path(tmp, "profile").as_uri()
            subprocess.run([soffice, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
                            "--outdir", tmp, str(docx)], check=True, timeout=timeout,
                           capture_output=True)
            out = Path(tmp, docx.stem + ".pdf")
            if not out.exists():
                raise RuntimeError("LibreOffice did not produce a PDF.")
            shutil.move(str(out), pdf)
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise RuntimeError("PDF export failed.")
    return pdf
