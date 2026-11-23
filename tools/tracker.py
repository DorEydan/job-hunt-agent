#!/usr/bin/env python3
"""Application log (applications.csv) with the "no re-send within 60 days" rule.

  python tools/tracker.py check  --company "Acme" --role "Junior DevOps" [--url URL]
      exit 0 + "OK"            -> allowed
      exit 3 + "DUPLICATE ..." -> already sent/skipped/pending, do not prepare it
  python tools/tracker.py add    --company ... --role ... --url ... --source linkedin
                                 --method "linkedin-easy-apply" --score 8 --folder applications/...
      prints the new id (status = prepared)
  python tools/tracker.py update --id 12 --status sent|skipped|manual|failed [--notes "..."]
  python tools/tracker.py list   [--status prepared] [--days 60]

Windows (from config.json): sent/skipped block for dedup_days (60);
prepared/manual block for pending_days (14), after which an unanswered job may be offered again.
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

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
CSV_PATH = ROOT / "applications.csv"
FIELDS = ["id", "date_found", "date_sent", "status", "company", "role", "source", "job_url",
          "apply_method", "match_score", "folder", "notes", "company_key", "role_key"]
STATUSES = {"prepared", "sent", "skipped", "manual", "failed"}

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


def blocking_rows(rows, company, role, url):
    today = dt.date.today()
    ck, rk, uk = company_key(company), role_key(role), url_key(url)
    hits = []
    for r in rows:
        if r["status"] in ("sent", "skipped"):
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

    l = sub.add_parser("list")
    l.add_argument("--status")
    l.add_argument("--days", type=int)

    args = ap.parse_args()
    rows = load()

    if args.cmd == "check":
        hits = blocking_rows(rows, args.company, args.role, args.url)
        if hits:
            h = hits[0]
            print(f"DUPLICATE id={h['id']} status={h['status']} company={h['company']} "
                  f"role={h['role']} found={h['date_found']} sent={h['date_sent']}")
            sys.exit(3)
        print("OK")

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
