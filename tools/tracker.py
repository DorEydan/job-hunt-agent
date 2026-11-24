#!/usr/bin/env python3
"""Application log (applications.csv) with the "no re-send within 60 days" rule.

  python tools/tracker.py check  --company "Acme" --role "Junior DevOps" [--url URL]
      exit 0 + "OK"            -> allowed (a second line "REPOST ..." means it was seen before: maybe a ghost job)
      exit 3 + "DUPLICATE ..." -> already sent/skipped/pending, do not prepare it
      exit 3 + "GHOST ..."     -> the candidate marked this job (or company) as fake: never prepare it
  python tools/tracker.py add    --company ... --role ... --url ... --source linkedin
                                 --method "linkedin-easy-apply" --score 8 --folder applications/...
      prints the new id (status = prepared)
  python tools/tracker.py update --id 12 --status sent|skipped|manual|failed|ghost|interview|rejected|offer [--notes "..."]
  python tools/tracker.py folder --company "Acme" --role "Junior DevOps" [--field devops]
      prints the folder for this job's files, following config.json -> resume_tailoring.folder_layout
  python tools/tracker.py list   [--status prepared] [--days 60]

Windows (from config.json): sent/skipped block for dedup_days (60);
prepared/manual block for pending_days (14), after which an unanswered job may be offered again;
ghost (a job the candidate marked as fake, posted only for show) blocks forever.
"""
import argparse
import csv
import datetime as dt
import difflib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_config  # noqa: E402

CONFIG = load_config()
CSV_PATH = ROOT / "applications.csv"
FIELDS = ["id", "date_found", "date_sent", "status", "company", "role", "source", "job_url",
          "apply_method", "match_score", "folder", "notes", "company_key", "role_key"]
STATUSES = {"prepared", "sent", "skipped", "manual", "failed", "ghost", "interview", "rejected", "offer"}
GHOST = {"ask_when_reposted": True, "repost_times": 2, "block": "role", **(CONFIG.get("ghost_jobs") or {})}
LAYOUTS = {"date_company_role", "company_role", "field_company_role", "role_company"}

COMPANY_NOISE = re.compile(r"\b(ltd|inc|llc|corp|co|group|israel|technologies|בע\"?מ|בעמ)\b", re.I)


def norm(s):
    s = s.lower().replace("״", '"').replace("׳", "'")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def company_key(s):
    return norm(COMPANY_NOISE.sub(" ", s))


def role_key(s):
    return norm(s)


def url_key(u):
    if not u:
        return ""
    p = urlsplit(u.strip())
    host = p.netloc.lower().removeprefix("www.").removeprefix("il.").removeprefix("m.")
    path = p.path.rstrip("/")
    m = re.search(r"/jobs/view/(\d+)", path)  # LinkedIn: id only, drop tracking params
    if m:
        return f"linkedin/{m.group(1)}"
    return urlunsplit(("", host, path, p.query, ""))


def same_role(a, b):
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 10 and short in long_:
        return True
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and len(ta & tb) / len(ta | tb) >= 0.75:  # same words, any order
        return True
    return difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio() >= 0.85


def load():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    tmp = CSV_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(CSV_PATH)


def parse_date(s):
    try:
        return dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def matches(r, ck, rk, uk):
    return (uk and uk == url_key(r["job_url"])) or (ck and ck == r["company_key"] and same_role(rk, r["role_key"]))


def ghost_rows(rows, company, role, url):
    ck, rk, uk = company_key(company), role_key(role), url_key(url)
    return [r for r in rows if r["status"] == "ghost" and (
        matches(r, ck, rk, uk) or (GHOST.get("block") == "company" and ck and ck == r["company_key"]))]


def earlier_sightings(rows, company, role, url):
    """Earlier rows of the same job outside the blocking windows: the posting keeps coming back."""
    ck, rk, uk = company_key(company), role_key(role), url_key(url)
    return [r for r in rows if r["status"] != "ghost" and matches(r, ck, rk, uk)]


def blocking_rows(rows, company, role, url):
    today = dt.date.today()
    ck, rk, uk = company_key(company), role_key(role), url_key(url)
    hits = []
    for r in rows:
        if r["status"] == "ghost":
            continue  # handled by ghost_rows
        if r["status"] in ("sent", "skipped", "interview", "rejected", "offer"):
            ref, window = parse_date(r["date_sent"]) or parse_date(r["date_found"]), CONFIG["dedup_days"]
        elif r["status"] in ("prepared", "manual"):
            ref, window = parse_date(r["date_found"]), CONFIG["pending_days"]
        else:  # failed -> may retry
            continue
        if not ref or (today - ref).days >= window:
            continue
        if (uk and uk == url_key(r["job_url"])) or (
            ck and ck == r["company_key"] and same_role(rk, r["role_key"])
        ):
            hits.append(r)
    return hits


WIN_RESERVED = re.compile(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", re.I)


def safe_part(s, n=60):
    """One folder name from untrusted text (company or role from a posting): no separators, no '..', no device names."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "-", s).strip(" .")
    s = s[:n].rstrip(" .") or "unknown"
    if WIN_RESERVED.fullmatch(s.split(".", 1)[0].strip()):
        s = "_" + s
    return s


def job_folder(company, role, field="", date=""):
    """applications/<...> for one job's files, in the layout the candidate chose."""
    if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("date must look like 2026-01-31")
    day = dt.date.fromisoformat(date).isoformat() if date else dt.date.today().isoformat()
    layout = (CONFIG.get("resume_tailoring") or {}).get("folder_layout", "date_company_role")
    c, r = safe_part(company), safe_part(role)
    parts = {"company_role": [c, r, day], "field_company_role": [safe_part(field or CONFIG.get("field") or "general"), c, r, day],
             "role_company": [r, c, day]}.get(layout, [f"{day}_{c}_{r}"])
    return "applications/" + "/".join(parts)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("--company", required=True)
    c.add_argument("--role", required=True)
    c.add_argument("--url", default="")

    a = sub.add_parser("add")
    for f in ("company", "role"):
        a.add_argument(f"--{f}", required=True)
    for f in ("url", "source", "method", "score", "folder", "notes"):
        a.add_argument(f"--{f}", default="")
    a.add_argument("--force", action="store_true", help="add even if it is a duplicate")

    u = sub.add_parser("update")
    u.add_argument("--id", required=True)
    u.add_argument("--status", required=True, choices=sorted(STATUSES))
    u.add_argument("--notes", default=None)
    u.add_argument("--method", default=None)

    fo = sub.add_parser("folder")
    fo.add_argument("--company", required=True)
    fo.add_argument("--role", required=True)
    fo.add_argument("--field", default="")
    fo.add_argument("--date", default="")

    l = sub.add_parser("list")
    l.add_argument("--status")
    l.add_argument("--days", type=int)

    args = ap.parse_args()
    rows = load()

    if args.cmd == "check":
        ghosts = ghost_rows(rows, args.company, args.role, args.url)
        if ghosts:
            g = ghosts[0]
            print(f"GHOST id={g['id']} company={g['company']} role={g['role']} - marked as a fake job, skip it")
            sys.exit(3)
        hits = blocking_rows(rows, args.company, args.role, args.url)
        if hits:
            h = hits[0]
            print(f"DUPLICATE id={h['id']} status={h['status']} company={h['company']} "
                  f"role={h['role']} found={h['date_found']} sent={h['date_sent']}")
            sys.exit(3)
        print("OK")
        seen = earlier_sightings(rows, args.company, args.role, args.url)
        if seen and len(seen) + 1 >= int(GHOST.get("repost_times", 2)):
            last = max((r["date_found"] for r in seen), default="")
            print(f"REPOST times={len(seen) + 1} last={last} ids={','.join(r['id'] for r in seen)}"
                  + (" - ask the candidate whether this is a ghost job" if GHOST.get("ask_when_reposted") else ""))

    elif args.cmd == "folder":
        print(job_folder(args.company, args.role, args.field, args.date))

    elif args.cmd == "add":
        hits = blocking_rows(rows, args.company, args.role, args.url)
        if hits and not args.force:
            print(f"DUPLICATE id={hits[0]['id']} - not added")
            sys.exit(3)
        new_id = str(max((int(r["id"]) for r in rows), default=0) + 1)
        rows.append({
            "id": new_id, "date_found": dt.date.today().isoformat(), "date_sent": "",
            "status": "prepared", "company": args.company, "role": args.role,
            "source": args.source, "job_url": args.url, "apply_method": args.method,
            "match_score": args.score, "folder": args.folder, "notes": args.notes,
            "company_key": company_key(args.company), "role_key": role_key(args.role),
        })
        save(rows)
        print(new_id)

    elif args.cmd == "update":
        for r in rows:
            if r["id"] == args.id:
                r["status"] = args.status
                if args.status == "sent":
                    r["date_sent"] = dt.date.today().isoformat()
                if args.notes is not None:
                    r["notes"] = (r["notes"] + " | " if r["notes"] else "") + args.notes
                if args.method:
                    r["apply_method"] = args.method
                save(rows)
                print(f"updated id={args.id} -> {args.status}")
                break
        else:
            sys.exit(f"id {args.id} not found")

    elif args.cmd == "list":
        today = dt.date.today()
        for r in rows:
            if args.status and r["status"] != args.status:
                continue
            d = parse_date(r["date_sent"]) or parse_date(r["date_found"])
            if args.days and d and (today - d).days > args.days:
                continue
            print(f"{r['id']:>4} | {r['status']:<8} | found {r['date_found']} | sent {r['date_sent'] or '-':<10} | "
                  f"{r['company']} | {r['role']} | {r['source']} | {r['job_url']}")


if __name__ == "__main__":
    main()
