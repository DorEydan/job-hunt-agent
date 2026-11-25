# ATS facts and myths

Use this to answer questions about how applications are screened. Say how sure each fact is when it matters.
Sources are listed in `research/NOTES.md`.

## What really filters candidates

1. **Knockout questions:** work authorization, location, years of experience, license, language. A "no", or the
   wrong answer, can reject an application automatically. This happens on the job board (LinkedIn Easy Apply and
   Indeed screening questions) as well as inside the employer's ATS (Workday can do it with no human review;
   Greenhouse's auto-reject runs on question answers and only on higher plans). It is the most common automatic
   rejection.
2. **Recruiter search and ranking.** Recruiters search parsed resumes by keywords and job titles (Lever: Boolean
   search; Greenhouse: full-text search). A resume without the posting's terms may never come up. Many ATSs add a
   match or AI fit score that sets the reading order. Mainstream ATSs (Greenhouse, Lever, Workday, Ashby) don't
   reject on a keyword-match percentage, but some high-volume enterprise setups can be configured with score
   thresholds. So "usually ranked lower", not "never filtered".
3. **Volume.** Popular postings get hundreds of applications, and recruiters stop when they have enough good ones.
   Applying early helps.
4. **A human in seconds.** Ladders' eye-tracking study (2018) measured about 7.4 seconds for a first screen. Clear
   headings, the title, and bullets did best; columns and clutter did worst. Caveats: a small lab study by a career
   site.

## Myths, and what to say instead

| Myth | Reality |
|---|---|
| "75% of resumes are rejected by ATS before a human sees them." | No study behind it. It comes from a 2012 sales pitch by Preptel, a resume-optimization vendor that closed in 2013, and spread through articles citing each other. |
| "Under an 80% match score you're auto-rejected." | Mainstream ATSs don't reject on a match percentage; tools like Jobscan only estimate one. Their useful part is the list of missing keywords that are **true** for you. |
| "Hide keywords in white text to beat the ATS." | ATSs show recruiters plain text, where it becomes visible, and vendors scan for it. Recruiters usually reject for it. |
| "ATS can't read PDFs." | Modern ATSs read PDFs with a real text layer. Scans, image PDFs and some design-tool exports are the problem, and so are PDFs whose characters come out garbled (e.g. "fi" ligatures or icon fonts). `inspect_resume.py` checks for this. |
| "You need a special 'ATS template'." | Any single-column layout works: standard headings, no tables or text boxes, contact details in the body. |
| "Fancy design gets noticed." | For the ATS, design is risk with no benefit; for the human, clarity wins. Design and marketing candidates can link to a designed portfolio. |

## What makes a file parse well

- One column. No tables, text boxes, or content in headers and footers.
- Standard section headings in the resume's language ("Experience", "Education", "Skills").
- Real text, not images of text. Icons only if the same information is also in plain text.
- Month/year dates in one consistent style (many ATSs compute years of experience from them).
- `.docx`, or a text-based PDF under 2 MB.
- Right-to-left resumes (Hebrew, Arabic): lines mixing Hebrew or Arabic with English often come out scrambled from
  PDFs. Check with `inspect_resume.py <pdf> --against <docx>`, and prefer sending the `.docx` when it fails.

## Hidden Workers (Harvard Business School + Accenture, 2021)

88% of the executives surveyed said qualified high-skills candidates are screened out because they don't match the
job description's exact criteria (94% for middle-skills candidates). The criteria are typically hard filters such as a
degree, years of experience, or a gap in employment.

What this means:
- Use the posting's words for what the candidate really has.
- Write dates so tenure is counted correctly.
- A one-line entry for a long break (parental leave, caregiving, study) helps the human reader. It doesn't stop an
  automatic gap filter.
