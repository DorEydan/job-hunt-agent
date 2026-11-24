"""Shared helpers: project paths and config loading with friendly errors."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_PATH = ROOT / "config.example.json"


def load_config(allow_example=False):
    if not CONFIG_PATH.exists() and allow_example:
        return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    if not CONFIG_PATH.exists():
        sys.exit("config.json not found. Run start.bat (it creates one from config.example.json "
                 "and opens the setup page), or copy config.example.json to config.json.")
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"config.json is not valid JSON (line {e.lineno}, column {e.colno}): {e.msg}")


def resume_variants(cfg):
    """{name: path} of base resumes. Accepts the old single `base_resume` key too."""
    variants = {k: v for k, v in (cfg.get("base_resumes") or {}).items() if v and not k.startswith("_")}
    if not variants and cfg.get("base_resume"):
        variants = {"default": cfg["base_resume"]}
    # relative paths are relative to the project folder
    return {k: str(p if (p := Path(v).expanduser()).is_absolute() else ROOT / p) for k, v in variants.items()}
