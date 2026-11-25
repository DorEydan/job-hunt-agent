# Tailoring guide

How to make the true resume fit one posting. Everything here works inside hard rules 1–5 of `SKILL.md`.

## Order (level 1, no approval needed)

- **Inside each skill line:** the skills the posting names go first, must-haves before nice-to-haves, in the order
  the posting stresses them (title, then the first requirements). Skills the posting doesn't name keep their order.
- **The lines themselves:** the line with the most posting matches goes first. A junior DevOps posting → the
  cloud/containers or scripting line first, not "Operating systems".
- Use `--first "Label=a,b"` with the **exact labels and items** from `skills_docx.py list`. Matching is not
  case-sensitive, but the script rejects anything that isn't already in that line.
- **Bullets inside each job:** the bullets that prove the posting's must-haves go first, most important first. This
  has more effect than the skills list, because recruiters read the top bullets of the latest job. Use
  `skills_docx.py paras` to see the numbers, then `move --order` once per job. Don't move bullets between jobs.
- **Plain skills lists** (one skill per line, or competency bullets, common in sales, finance, healthcare and
  operations): reorder them the same way with `move`.

## Scope and titles (level 2)

- Recruiters compare scope: individual contributor or manager, team size, company type, B2B or B2C. Point out a real
  mismatch honestly in the report ("the role leads a team of 5; your resume shows no people management").
- Internal titles that say nothing outside the company ("Associate II", "MTS 2") may get a plain clarification in
  brackets: "Associate II (Backend Engineer)". Keep the real title, which must match references and background
  checks. Do this only with approval, and only when it describes the actual work.

## Exact terms (level 2)

Recruiters search with the posting's words. When the resume has the same thing under another name, align the
spelling and keep both if useful: "K8s" → "Kubernetes (K8s)", "GA4" → "Google Analytics 4 (GA4)", "JS" →
"JavaScript". Only for the **same** thing: "Docker" doesn't become "Kubernetes", "SQL" doesn't become "PostgreSQL"
unless the candidate confirms it.

## Headline (level 2)

The line under the name. Mirror the posting's title when the candidate is that role or is clearly moving into it:

- Matches: "Junior DevOps Engineer".
- Career change: "Data Analyst (career change from logistics)" or "Data Analyst | SQL, Python, Power BI". It must
  not read as if they already held a job titled that. Offer two options and let the candidate pick.
- Never a seniority level they don't have ("Senior …").

## Summary (level 2)

2–3 lines, from existing facts only: **who they are** (role and level) + **the 2–3 strongest matches with the
posting** + **one proof** (a project, a result, a domain). Example from the fictional Noa Levi:

> IT support technician moving into DevOps: automates server work with Bash and Python, and built a Jenkins pipeline
> that deploys a Dockerized app to AWS EC2.

No adjectives that can't be shown ("passionate", "results-driven"). No numbers that aren't in the resume.

## Bullets

Don't rewrite experience bullets by default: their wording is the candidate's. If asked to improve them:
action verb + what + tool + result. Missing results become `[number?]`, `[%?]` or `[how many users?]`, with a list of
what to look up. Run `verify_facts.py` afterwards.

## Section order (level 2)

| Candidate | Order |
|---|---|
| Student / first job | Summary, Education, Projects, Skills, Experience |
| Junior with some experience | Summary, Skills, Experience, Projects, Education |
| Career changer | Summary, Skills, Projects/Training, Experience (framed as transferable), Education |
| Experienced | Summary, Experience, Skills, Education |

## Length

Follow `countries.md`. To shorten, cut in this order:
1. Older or unrelated jobs down to one line each (title, company, dates).
2. School projects, once there is real work.
3. Duplicate skills.
4. Hobbies.

For a long career, keep roughly the last 10–15 years in detail, and add an "Earlier experience" line with titles and
companies only. Never cut the evidence for a must-have. Trimming is selecting, so it needs approval (level 2).

## Dates, promotions, contract work, gaps

- **Promotions at one company:** the company once, then each title with its own dates underneath. Then the ATS and
  the reader count it as one employer, not as job hopping. In the JSON, use one experience entry with `company`,
  `location`, the overall `dates`, and `roles: [{title, dates, bullets}, …]`, newest first.
- **Contract or freelance work:** group short gigs under one entry ("Freelance web developer, 2022 – 2024") with the
  main clients as bullets, if the candidate is allowed to name them.
- **Gaps:** a one-line entry in the timeline, in the candidate's own words ("Career break: parental leave, 2023").
  Offer it; don't add it unasked.
- **Dates:** month/year in one style throughout. Year-only dates can hide gaps, but many ATSs miscount tenure from
  them, so suggest month/year when the candidate knows the months.

## Gaps

Missing must-have → say so in the report with the honest options (SKILL.md step 4). Don't hide gaps in vague words
("exposure to cloud technologies" for no cloud experience). A strong project is the honest bridge: suggest one the
candidate could build in a weekend if the gap matters.

## Clean rebuild: JSON for `build_docx.py`

```json
{
  "name": "Noa Levi",
  "headline": "Junior DevOps Engineer",
  "contact": {"city": "Haifa, Israel", "phone": "+972-50-000-0000", "email": "noa.levi@example.com",
              "linkedin": "linkedin.com/in/example-noa", "github": "", "portfolio": ""},
  "summary": "…",
  "skills_heading": "Technical Skills",
  "skills": [{"label": "Scripting", "items": ["Bash", "Python", "PowerShell"]}],
  "experience": [{"title": "IT Support Technician", "company": "Example Systems Ltd", "location": "Haifa",
                  "dates": "2023 – present", "bullets": ["…"]}],
  "projects": [{"name": "Home lab CI pipeline", "role": "", "dates": "", "link": "", "bullets": ["…"]}],
  "education": [{"degree": "B.Sc. Information Systems", "school": "Example University", "dates": "2023", "bullets": []}],
  "certifications": ["…"],
  "languages": "Hebrew (native), English (fluent)",
  "page": "A4",
  "titles": {"summary": "Profil", "experience": "Doświadczenie", "education": "Wykształcenie"},
  "extra_sections": [{"title": "Military Service", "lines": ["Network operations technician, 2016 – 2019"],
                      "bullets": false, "after": "experience"}],
  "footer_note": "Wyrażam zgodę na przetwarzanie moich danych osobowych …"
}
```

- `titles` overrides section headings when the resume isn't in English (keys: summary, experience, projects,
  education, certifications, languages; the skills heading is `skills_heading`).
- `extra_sections` holds anything the template has no section for: military service, volunteering, awards,
  publications, referees, training. Each gets `title`, `lines`, `bullets` (default true) and `after` (a section
  name, or "end"). Nothing from the original may be dropped for lack of a field.
- `footer_note` holds a small text at the end, such as the Polish RODO clause.
- Labels can't contain ':'. A skill can contain a comma only inside parentheses ("AWS (EC2, S3)").
- `page`: "Letter" for the US, Canada, Mexico and the Philippines; otherwise "A4" (see `countries.md`).
- Templates (`--template`): `tech` (skills near the top), `graduate` (education and projects first), `professional`
  (experience first, classic), `creative` (projects first, accent color), `modern` (accent bar), `minimal` (black and
  white, conservative fields), `compact` (fits more on one page), `career-change` (skills and projects before past
  jobs). All are single column with real text.
- The builder writes left-to-right only: for Hebrew or Arabic resumes keep the candidate's own `.docx`.
