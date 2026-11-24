# Job-Hunt Agent

[![tests](https://github.com/DorEydan/job-hunt-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/DorEydan/job-hunt-agent/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

An AI agent, built on **Claude Code**, that runs a job search end to end: it searches the job boards of your
country on your schedule, filters and scores postings, tailors the resume for each job, and sends applications
**only after you approve them**. A local control panel handles setup and tracking, and a first-run wizard sets
everything up from your resume.

![Control panel – home](docs/screenshot-home.png)

## Quick start

1. **Get it:** `git clone https://github.com/DorEydan/job-hunt-agent.git` (or Code → Download ZIP).
2. **Open the control panel**, either way:
   - **Windows:** double-click `start.bat`. The first time it creates a Python environment and installs two packages.
   - **Docker (any OS):** `docker compose up -d`, then open <http://localhost:8765>. See [Docker](#docker).
3. **Follow the setup wizard** that opens on the first run (about 5 minutes):

   | Step | What happens |
   |------|--------------|
   | Resume | Upload your `.docx`. The wizard **reads it and fills in** your name, contact details, LinkedIn/GitHub/portfolio, country and city, field, level and years of relevant experience, degree, job titles and the skills it may reorder. You confirm each one in the next steps |
   | About you | Check the details; pick the country you're looking in |
   | Your work | Field (software, DevOps, data, QA, IT, security, design, product, marketing, sales…) and level (student to senior) → suggested job titles and search terms |
   | Location | How far you'll travel (your city only, 15/30/50/100 km or anywhere), remote / hybrid / relocation |
   | Sites | **The job boards of your country**, e.g. Pracuj.pl and Just Join IT for Poland, StepStone for Germany, Naukri for India, Drushim and AllJobs for Israel (12 countries), plus LinkedIn, Indeed (your country's domain), Glassdoor and remote boards |
   | Cover letter | Optional: upload a `.docx`/`.pdf`/`.txt` cover letter; it's attached where a form asks for one |
   | Applying | Allowed ways to apply and the common form answers (notice period, salary, work permit) |
   | Schedule | Every day, workdays, 3×/2×/once a week, and the time; the look-back window follows automatically |

   No resume yet? Continue with the fictional [sample resume](examples/sample-resume.docx) and swap it later.
4. **Schedule it:** the *Schedule* tab gives you the exact prompt to paste into Claude Code.

| You need | For |
|----------|-----|
| Python 3.11+ (Windows) **or** Docker | The tools and the control panel |
| Microsoft Word (Windows) **or** LibreOffice (included in the Docker image) | Exporting the tailored resume to PDF |
| [Claude Code](https://claude.com/claude-code) (desktop app or CLI) | The agent itself |
| Claude in Chrome extension | Sites that need your sign-in: LinkedIn, job boards, Gmail |

## Docker

The image runs the control panel and the resume tools, with LibreOffice for PDF export, so you don't need Python
or Word on your computer.

```
docker compose up -d          # build and start; open http://localhost:8765
docker compose logs -f        # see what it's doing
docker compose down           # stop
```

- The project folder is mounted into the container, so your settings, uploaded resume, applications and run
  reports stay in this folder on your computer, where Claude Code (which runs the agent) reads them too.
- The panel is published on `127.0.0.1` only: other devices on your network can't reach it.
- Optional: set `JOBHUNT_HOST_FOLDER` to this folder's path (e.g. in a `.env` file) so the copy-ready prompts
  show it, since the container sees the folder as `/app`.
- The agent itself is not in the container: it runs in Claude Code on your computer and uses your own browser for
  job sites that need your sign-in.

## How it works

```
 Scheduled run (your days and time; default Sun / Tue / Thu 09:00)
        │
        ▼
 Phase A – automatic
   1. Search the sites you switched on (LinkedIn, Indeed, Glassdoor, local boards, company ATS pages, Telegram…)
   2. Filter: role, seniority, job type, location, keywords, companies; score each posting 1–10 for fit
   3. Skip anything already applied to in the last 60 days
   4. Tailor the resume: pick the right base version, reorder skills to match the posting, export a small PDF
   5. Write a run report and wait
        │
        ▼  you reply: "send 1,3,5"
 Phase B – sending
   LinkedIn Easy Apply / ATS forms (Comeet, Greenhouse, Ashby, BambooHR…) / email
   Every application is logged: date, company, role, method
```

| Sites | Job search rules | Applications |
|---|---|---|
| ![Sites](docs/screenshot-sources.png) | ![Job search](docs/screenshot-search.png) | ![Applications](docs/screenshot-apps.png) |
| **Run reports** | **Resumes** | |
| ![Run reports](docs/screenshot-runs.png) | ![Resumes](docs/screenshot-resumes.png) | |

See a full [sample run report](examples/sample-run-report.md) and a [sample application log](examples/sample-applications.csv).

## Engineering highlights

- **Human in the loop by design.** Phase A is automatic; nothing is sent until you approve specific jobs in the chat.
- **Self-verifying resume edits.** `tailor_resume.py` edits the Word XML directly, only reorders existing skills,
  refuses any skill not already on the resume, and checks that the text of every other paragraph is unchanged
  before writing.
- **PDF size fix.** Word embeds the whole emoji font (4.4 MB PDFs, rejected by many forms). `shrink_pdf.py`
  subsets oversized fonts with fontTools while keeping glyph IDs, links and color icons: **4.4 MB → 0.3 MB**.
- **Prompt-injection aware.** Job posts are treated as untrusted data; instructions inside them are ignored and
  scam patterns (payment, ID numbers, WhatsApp-only contacts) are flagged, not acted on.
- **Duplicate protection.** Fuzzy matching on company + role (token Jaccard, difflib) plus LinkedIn job IDs.
- **Locked-down local server.** The control panel binds to `127.0.0.1` (published only on `127.0.0.1` in Docker),
  rejects foreign `Host`/`Origin` and cross-site requests (DNS-rebinding and CSRF), uses a strict CSP, and validates
  every input. Uploads are size-capped, type-checked (a `.docx` must be a real Word zip, not a zip bomb) and saved
  under fixed names, so nothing from the uploaded file name reaches the disk path. Tested in CI.
- **Resume-driven setup.** `resume_profile.py` reads the Word XML (and its hyperlinks) to pre-fill the wizard,
  counting only *relevant* experience (a developer's old help-desk job doesn't make them mid-level).

## Project layout

```
AGENT.md                 the playbook the agent follows on every run
sources.md               search tips and notes the agent learns while running
config.example.json      template settings  →  copied to config.json on first start
start.bat / start.ps1    one-click setup + control panel
ui/                      local control panel and setup wizard (Python standard library, no framework)
Dockerfile, docker-compose.yml   control panel + tools in a container (LibreOffice for PDFs)
tools/
  tailor_resume.py       reorder skills in a .docx, export + shrink the PDF
  resume_profile.py      reads an uploaded resume to pre-fill the setup wizard
  pdf_export.py          Word (Windows) or LibreOffice (Docker, Linux, macOS)
  tracker.py             application log with the "no re-send within 60 days" rule
  shrink_pdf.py          font subsetting for small PDFs
  docx_to_pdf.ps1        Word export to PDF
examples/                fictional sample resume, run report and application log
tests/                   unit tests (run in GitHub Actions on Windows and Linux)

git-ignored, stays on your computer:
  config.json  applications.csv  applications/  runs/  uploads/  your resumes
```

## Customize

Everything is in the control panel; under the hood it edits `config.json`. Settings added in newer versions
get their defaults automatically, so an older `config.json` keeps working.

| Tab | What you can change |
|-----|---------------------|
| **Home** | Setup checklist; *Run the setup wizard again* |
| **Profile** | Contact details used in forms and emails (incl. portfolio site); the language of run reports |
| **Job search** | Target roles; search terms in English and your local language; max years of experience; words that disqualify a title; job types (full-time, part-time, student, internship, contract, freelance); keywords a job must mention or must not mention; companies to never apply to; search location, cities, maximum travel distance, remote/hybrid; how many days back to look; max jobs per run; minimum match score; re-apply and re-offer windows |
| **Sites** | Switch each site on or off, reorder them (the agent searches in this order), edit how each one is searched and applied to, or add new ones: 17 ready-made sites (LinkedIn, Indeed, Glassdoor, Wellfound, Built In, Welcome to the Jungle, Remote OK, We Work Remotely, Hacker News "Who is hiring", company ATS pages, Gemini search, Telegram, Facebook groups, and Israeli boards) local boards for 12 countries, or any custom site. Search links take `{query}`, `{location}`, `{days}` and `{seconds}` |
| **Resumes** | One or more resume versions (e.g. `devops`, `fullstack`) and which jobs each is for; the skills heading; the name of the sent PDF; a test export |
| **Applying** | Which ways of applying are allowed (quick apply, job-board send-CV, company forms, email, social messages); whether to paste the cover note into optional fields; notifications; screening answers; cover notes per language |
| **Schedule** | Days and time (presets: 3× a week, 2× a week, workdays, daily). It generates the exact text to paste into Claude Code to create or update the scheduled task, and warns if the look-back window is shorter than the gap between runs |

Fixed on purpose: nothing is sent without your approval, and the agent never solves CAPTCHAs, creates accounts or
types passwords. New sites the agent discovers are added switched off, for you to review.

## Command line

```
.venv\Scripts\python.exe tools\tailor_resume.py --list
.venv\Scripts\python.exe tools\tailor_resume.py --out out\test --first "Frameworks=React" --line-order "Frameworks"
.venv\Scripts\python.exe tools\tracker.py list --days 60
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Rules the agent keeps

No CAPTCHA solving, no account creation, no passwords: those jobs are handed back to you.
A capped number of new jobs per run (default 15), at a human pace on LinkedIn. Details in [AGENT.md](AGENT.md).

## License

[MIT](LICENSE)
