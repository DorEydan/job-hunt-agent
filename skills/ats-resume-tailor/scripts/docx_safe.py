"""Safe reading of untrusted .docx files, shared by the other scripts.

- Bounded reads: a part's real decompressed size is capped (the size in the zip header can lie).
- Caps on entry count and total size, so a zip bomb can't exhaust memory or disk.
- The XML must be well-formed and have no DOCTYPE/ENTITY (rules out entity tricks, and means every tag is closed,
  which keeps the regex scanning in the other scripts linear).
- Macro-enabled content and external links to network or local paths are refused before Word or LibreOffice open the
  file (those can run code or leak Windows credentials).
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
import zlib

MAX_PART = 8_000_000
MAX_TOTAL = 40_000_000
MAX_ENTRIES = 600
ZIP_ERRORS = (zipfile.BadZipFile, KeyError, zlib.error, RuntimeError, NotImplementedError, UnicodeDecodeError,
              OSError, EOFError)


class DocxError(Exception):
    pass


def read_bounded(z, info, limit=MAX_PART):
    with z.open(info) as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise DocxError(f"{info.filename} is too large.")
    return data


def check_archive(z):
    infos = z.infolist()
    if len(infos) > MAX_ENTRIES:
        raise DocxError("Too many files inside the .docx.")
    if sum(i.file_size for i in infos) > MAX_TOTAL:
        raise DocxError("The .docx is too large once unpacked.")
    names = [i.filename for i in infos]
    if len(names) != len(set(names)):
        raise DocxError("The .docx has duplicate entries.")
    for n in names:
        if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/") or ":" in n:
            raise DocxError(f"Unsafe entry name inside the .docx: {n}")
    low = [n.lower() for n in names]
    if any(n.endswith("vbaproject.bin") or n.endswith(".bin") and "activex" in n for n in low):
        raise DocxError("This file contains macros or ActiveX. Save it as a plain .docx in Word first.")
    if "[content_types].xml" in low:
        ct = read_bounded(z, z.getinfo(names[low.index("[content_types].xml")])).decode("utf-8", "replace")
        if "macroEnabled" in ct:
            raise DocxError("This is a macro-enabled document. Save it as a plain .docx in Word first.")
    for n in names:
        if n.lower().endswith(".rels") or n.lower() == "[content_types].xml":
            parse_xml(read_bounded(z, z.getinfo(n)).decode("utf-8", "replace"), n)
        if not n.lower().endswith(".rels"):
            continue
        # Parsed as XML, so quotes, attribute order and character references can't hide anything.
        root = ET.fromstring(read_bounded(z, z.getinfo(n)))
        for rel in root.iter():
            if not rel.tag.endswith("Relationship") or rel.get("TargetMode", "").strip().lower() != "external":
                continue
            target, kind = rel.get("Target", "").strip(), rel.get("Type", "")
            if not (kind.endswith("/hyperlink") and target.lower().startswith(("http://", "https://", "mailto:"))):
                raise DocxError(f"The file loads something from outside ({kind.rsplit('/', 1)[-1]}: {target[:60]}). "
                                "Only web links are allowed. Remove it in Word (e.g. a linked template, image or object).")


def parse_xml(text, what):
    if re.search(r"<!DOCTYPE|<!ENTITY", text, re.I):
        raise DocxError(f"{what} has a DOCTYPE/ENTITY declaration, which a Word file never needs.")
    try:
        ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as e:
        raise DocxError(f"{what} is not well-formed XML ({e}).")


def open_docx(path):
    """Return (ZipFile, document.xml text) after all checks. The caller closes the ZipFile."""
    try:
        z = zipfile.ZipFile(path)
    except ZIP_ERRORS:
        raise DocxError(f"Not a valid Word file: {path}")
    try:
        check_archive(z)
        doc = read_bounded(z, z.getinfo("word/document.xml")).decode("utf-8")
        parse_xml(doc, "word/document.xml")
        return z, doc
    except DocxError:
        z.close()
        raise
    except ZIP_ERRORS as e:
        z.close()
        raise DocxError(f"Could not read the Word file ({type(e).__name__}).")


def read_text_part(z, name):
    try:
        text = read_bounded(z, z.getinfo(name)).decode("utf-8", "replace")
    except ZIP_ERRORS:
        raise DocxError(f"Could not read {name}.")
    parse_xml(text, name)
    return text


def die(msg, as_json=False):
    if as_json:
        import json
        print(json.dumps({"error": msg}, ensure_ascii=False))
    else:
        print(msg, file=sys.stderr)
    sys.exit(2)
