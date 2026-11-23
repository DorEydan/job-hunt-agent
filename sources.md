# Job sources

Runs happen 3 times a week (Sun/Tue/Thu), so look at postings from the **last 3 days** (7 if a source has no date filter; the tracker drops duplicates).
"Chrome" = Claude in Chrome (the candidate's own Chrome, where they are signed in). Public = WebSearch / WebFetch / built-in browser.

| # | Source | How to search | Access | How to apply |
|---|--------|---------------|--------|--------------|
| 1 | LinkedIn Jobs | `https://www.linkedin.com/jobs/search/?keywords=<term>&location=Israel&f_TPR=r259200&f_E=1%2C2` (f_E=1,2 = internship + entry level, f_TPR = last 3 days) | Chrome (signed in) | Easy Apply, or the external link |
| 2 | Indeed Israel | `https://il.indeed.com/jobs?q=<term>&l=Israel&fromage=3` | Chrome / public | Indeed Apply or the company site. If a CAPTCHA / "verify you are human" appears: **stop, skip Indeed this run**, note it in the report |
| 3 | AllJobs | alljobs.co.il search box, Hebrew + English terms, sort by newest | Chrome (signed in) | "שליחת קורות חיים" on the job page |
| 4 | Facebook groups | Facebook search for posts/groups: `משרות הייטק`, `ג'וניור פיתוח`, `junior developer israel`, `DevOps Israel`, `משרות לסטודנטים הייטק`. Read recent posts in groups the candidate is already a member of | Chrome (signed in) | Usually by email from the post. Do **not** join groups, comment or post; list groups worth joining in the report |
| 5 | Drushim | drushim.co.il search, newest first | Chrome | Site's send-CV button |
| 6 | JobMaster | jobmaster.co.il search | Chrome | Site's send-CV button |
| 7 | Jobify360 | jobify360.co.il (aggregates many boards) | Public | Discovery only: apply at the original source it links to |
| 8 | Secret Tel Aviv Jobs | https://jobs.secrettelaviv.com/ (entry-level category) | Public | Link in the post |
| 9 | Built In Israel | https://builtin.com/jobs/mena/israel (filter: entry level / junior) | Public | Company ATS form |
| 10 | Wellfound | https://wellfound.com/location/israel | Public (apply needs login) | Company ATS form or skip |
| 11 | Telegram channels | Public previews: https://t.me/s/secretjuniordevelopers , https://t.me/s/hitech_jobs_in_israel | Public | Link / email in the post |
| 12 | Company career pages (ATS) | WebSearch: `site:comeet.com junior israel`, `site:job-boards.greenhouse.io junior tel aviv`, `site:jobs.lever.co junior israel`, `site:jobs.ashbyhq.com junior israel` | Public | The ATS form (no account creation) |
| 14 | Gemini (Google search) | `mcp__gemini-cli__ask-gemini` (load it with ToolSearch). Ask it to use Google search for junior Full-Stack/DevOps postings in Israel from the last 3 days, Hebrew + English terms, returning only: company, title, location, URL, posted date. Send search terms only, never the resume or the candidate's details | Discovery only | Open every URL yourself and keep it only if the job exists and is open; then apply at that source |
| 13 | University career center | Find its job board on the first run and write the URL here | Public / Chrome | As listed |

## Found during runs
<!-- The agent appends new useful sources here (Facebook groups, Telegram channels, boards), one line each with the date found. -->
- 2026-11-21: **MisroTech** – https://misrotech.com/en/r/devops/junior , /en/r/fullstack/junior , /en/r/backend/junior (public; scrapes company career pages, shows "Found" dates and links to the original ATS/email). Best public source on the first run.
- 2026-11-21: note – Indeed and Jobify360 show Cloudflare checks from the built-in browser; Built In geolocates to Greece; secrethunter.io job links (from the t.me/s/secretjuniordevelopers channel) need sign-in + reCAPTCHA, so search the company + title instead.
- 2026-11-22: note – Secret Tel Aviv entry-level list URL (/list/hi-tech/?job_type=entry-level) returns 404; find the new category URL. Gemini tool now runs on the "agy" backend (gemini-3.5-flash); avoid double quotes in the prompt (CLI arg error). Only 1 of 6 Gemini links was a real open job.
- 2026-11-22: apply tips – Comeet forms live in an iframe: open https://www.comeet.co/jobs/<company-uid>/<position-uid>/apply directly (uids are in the page HTML: comeet-company-uid / position-uid). matrix.co.il send-CV dialog has a reCAPTCHA → always `manual`. BambooHR (e.g. cyabra.bamboohr.com) shows a reCAPTCHA on submit → fill everything, then `manual`. hrmony.ai "Quick Apply" = name + email + CV only.
