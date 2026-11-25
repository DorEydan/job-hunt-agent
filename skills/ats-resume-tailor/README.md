# ATS Resume Tailor

An agent skill that tailors a resume to one job posting **without inventing anything**, checks that ATS systems can
read it, and adapts it to the job's country. Works with Claude Code, Codex, Cursor, Gemini CLI and other agents that
read `SKILL.md`.

## What it does

- **Reorders, never invents.** The skills the posting asks for go first, and so do the bullets that prove them. The
  scripts refuse to add a skill and check, paragraph by paragraph, that nothing else changed. Your own Word design is
  kept.
- **Checks the file the way a parser reads it:**
  - columns, tables, text boxes, contact details in headers;
  - hidden, white or tiny text (which gets candidates rejected);
  - tracked changes;
  - garbled PDF characters;
  - right-to-left text that comes out scrambled.
- **Country rules** for the US, Canada, UK, Australia, Israel, Germany, France, the Netherlands, Poland and India:
  photo, personal details, length, paper size, military service, the Polish RODO clause and more. Offered as
  suggestions you approve.
- **An honest match report:** each requirement, the proof for it in your resume, the gaps and what to do about
  them, plus knockout warnings (e.g. "US-based only").
- **Facts, not myths:** no "75% of resumes are rejected by ATS" (that figure has no source). The rules come
  from researched guidance (university career centers, government job sites, ATS documentation), with sources and
  how sure each one is in `research/NOTES.md`.
- **Output:** a `.docx` plus a small PDF (Word or LibreOffice), with a fact check showing that no number or skill
  was added.

## Install

Unzip into your agent's skills folder (for Claude Code: `~/.claude/skills/ats-resume-tailor/`). Requires Python 3.9+.
Optional: `pip install pypdf fonttools` (PDF checks, smaller PDFs), and Microsoft Word or LibreOffice (PDF export).

## Use

> Tailor my resume for this job: resume.docx, and here's the posting: …

The first reply delivers the reordered file, the match report and one numbered approval list. You answer
"1, 3, 4", and the second reply applies those changes.

## Quality

- **Tested against no skill:** 19 cases, each run with and without the skill on Claude Sonnet (38 runs).
  - **Expectations met:** 81/83 with the skill, 59/83 without.
  - **Word + PDF delivered:** 16/16 tailoring runs with the skill, 2/16 without.
  - **Content the candidate never wrote:** 0 runs with the skill, 10 runs without.

  These are a self-assessment: the grader knew which run used the skill, only the first reply was tested, and
  "0 runs" excludes a "Personal details" heading the skill added twice. Full results, the caveats and what the
  skill doesn't change are in [evals/RESULTS.md](evals/RESULTS.md).
- `tests/`: 18 automated tests of the scripts, including bypass attempts (macro files, external links, hidden
  text, invented skills).
- `evals/`: the 19 cases: prompt injection in a posting, "just add
  Kubernetes", white-text requests, lying on screening questions, Hebrew, India, Japan, a non-tech resume and a
  4-page senior resume. Plus 19 trigger checks.
- `research/NOTES.md`: the research behind every rule, with sources.

Your resume stays on your computer: the skill sends nothing anywhere.

Part of the open-source [Job-Hunt Agent](https://github.com/DorEydan/job-hunt-agent) project. MIT license.
