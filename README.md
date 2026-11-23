# Job-Hunt Agent

An AI agent, built with **Claude Code**, that runs my junior Full-Stack / DevOps job search end to end:
it searches job boards on a schedule, filters and scores postings, tailors my resume for each job,
and sends applications after I approve them.

## What it does

```
 Scheduled run (Sun / Tue / Thu 09:00)
        │
        ▼
 Phase A – automatic
   1. Search ~14 sources (LinkedIn, Indeed, AllJobs, Drushim, company ATS pages, Telegram, Google via Gemini…)
   2. Filter: seniority ≤ 2 years, role type, location; score each posting 1-10 for fit
   3. Skip anything already applied to in the last 60 days (tracker)
   4. Tailor the resume: pick the DevOps or Full-Stack base version, reorder skills to match the posting, export a small PDF
   5. Write a run report and wait for approval
        │
        ▼  human approves: "send 1,3,5"
 Phase B – sending
   Easy Apply / ATS forms (Comeet, Greenhouse, Ashby, BambooHR…) / email via Gmail
   Log every application with date, company, role and method
```

## Design choices

- **Human in the loop.** Nothing is sent without explicit approval in the chat.
- **Minimal, verifiable resume changes.** `tailor_resume.py` only picks a base version and reorders skills.
  It refuses unknown skills and self-checks that every other line of the document is unchanged.
- **Job posts are untrusted input.** Instructions inside postings are ignored; suspicious posts are flagged, not acted on.
- **No CAPTCHA solving, no account creation, no passwords.** Those jobs are handed back to the human.
- **Screening answers come only from config.** If an answer is missing, the agent asks instead of guessing.
- **Duplicate protection.** Fuzzy matching on company + role (token Jaccard, difflib) and job-ID URLs.

## Tools

| File | What it does |
|------|--------------|
| `AGENT.md` | The playbook the agent follows on every run: rules, phases, apply methods |
| `sources.md` | Where to search and how to apply on each site, plus notes the agent adds as it learns |
| `tools/tailor_resume.py` | Reorders the skills in a `.docx` resume and exports PDF; self-verifying |
| `tools/docx_to_pdf.ps1` | Word COM export to PDF (keeps the exact layout) |
| `tools/shrink_pdf.py` | Subsets oversized embedded fonts with fontTools: 4.4 MB → 0.3 MB, links and icons kept |
| `tools/tracker.py` | CSV application log with a "no re-send within 60 days" check |
| `config.example.json` | Template for the candidate's details, search terms, filters and screening answers |

## Stack

Claude Code (agent + scheduled tasks), MCP (Claude in Chrome for browser automation, Gemini CLI for Google search),
Python (fontTools, pypdf), PowerShell, Microsoft Word COM.

## Setup

1. `python -m venv .venv` and `.venv\Scripts\pip install -r requirements.txt`
2. Copy `config.example.json` to `config.json` and fill in your details and resume paths.
   `config.json`, the application log and the resumes are git-ignored.
3. Your resume needs a "Technical Skills" heading with lines like `Label: skill, skill, ...`.
   Check with `.venv\Scripts\python.exe tools\tailor_resume.py --variant devops --list`.
4. In Claude Code, schedule a task that reads `AGENT.md` and follows it.

Requires Windows with Microsoft Word for the PDF export.
