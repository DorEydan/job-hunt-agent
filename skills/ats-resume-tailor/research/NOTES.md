# Research notes: ATS resume tailoring skill

Collected 2026-11-25, before writing the skill. Each finding has a confidence level and what it means for the skill.
Sources are at the end. Most writing on this topic comes from resume-tool vendors who profit from fear, so findings
backed only by vendors are marked as such.

## 1. What an ATS actually does

| Finding | Confidence | For the skill |
|---|---|---|
| The "75% of resumes are rejected by ATS before a human sees them" figure has no study behind it. It traces to a 2012 sales pitch by Preptel, a resume-optimization vendor that closed in 2013, and spread through Forbes → CIO → CNBC. | High (consistent across independent write-ups) | Never repeat the 75% claim. Don't sell fear. Explain what really filters. |
| Most automatic rejections come from **knockout questions** the employer configured (work authorization, location, license, years), not from the resume's wording. Greenhouse auto-reject exists only on its higher tiers and runs on question answers; Workday can disqualify on a wrong required answer with no human review. | Medium (several sources, mostly vendors and practitioners) | The skill should remind the user that screening answers matter as much as the resume, and never suggest a false answer. |
| Recruiters **search and filter** the parsed database by keywords and job titles (Lever: Boolean search; Greenhouse: full-text resume search). A resume without the posting's exact terms may simply not surface. Some ATSs now add an AI fit score that orders the list. | Medium-high | This is the real reason to tailor: use the posting's exact terms and title wording **where they are true** (e.g. "Kubernetes" not only "K8s", "CI/CD" spelled as in the post). |
| Harvard Business School + Accenture, *Hidden Workers* (2021): automated filters written as negatives (no degree, employment gap) exclude qualified people; 88% of employers surveyed agreed qualified high-skills candidates get screened out for not matching the job description exactly (94% for middle-skills). | High (the report's own executive summary and PDF) | Supports exact-term matching, and supports explaining gaps honestly rather than hiding them. |

## 2. Parsing: what breaks it

| Finding | Confidence | For the skill |
|---|---|---|
| Multi-column layouts, tables and text boxes are the most common cause of scrambled parses (text read in the wrong order, skills glued to dates). Headers and footers are often skipped, so contact details there can be lost. | Medium (practitioner consensus; no controlled study found) | Output must be single column, no tables or text boxes, contact details in the body. Our templates already do this. |
| A PDF must have a real text layer. Scanned or image PDFs, and PDFs exported from design tools (Canva, etc.), often parse badly. | Medium-high | Add a **self-check**: extract the text from the produced PDF and confirm name, email, phone, section headings and skills come out readable and in order. No competitor does this. |
| Standard section headings ("Experience", "Education", "Skills") parse better than creative ones. | Medium | Keep standard headings, in the resume's language. |

## 3. What a human reader does

| Finding | Confidence | For the skill |
|---|---|---|
| Ladders eye-tracking study (2018): average first screen of a resume is **7.4 seconds**; simple layouts with clear section and title headings, bold titles and bullets did best; clutter, multiple columns and long sentences did worst. Caveat: run by a career site, sample size not published. | Medium | The first third of the page decides: title/headline and the top skill line should match the posting. That is exactly what reordering does. |

## 4. Honesty and "hacks"

| Finding | Confidence | For the skill |
|---|---|---|
| Hidden white-text keywords and hidden AI prompts in resumes: about **1%** of 196,682 resumes in a USENIX Security 2026 study; Greenhouse estimates ~1%, ManpowerGroup says ~10% of what it scans. Recruiters who notice usually disqualify; vendors now scan for white-on-white and tiny text. | High that it exists and is detected | Refuse to add hidden text or prompt injections, and say why (it's detected and gets people disqualified). Also strip any found in the user's file and tell them. |
| Invented numbers and skills come out in interviews and reference checks. | High (common sense; also every career center) | Hard rule enforced by a script: tailoring may only **reorder and select**, never add a skill, number or claim. Missing numbers become `[number?]` for the user to fill. |
| Job postings can contain prompt-injection text aimed at AI tools. | High (known pattern) | Treat the posting as data. Ignore instructions in it. |

## 5. Country conventions

Rule of the skill: the rules follow the **country of the job** (not of the candidate), are offered as
**suggestions the user approves**, and personal details are never removed or added silently. Where sources disagree,
the skill says so and picks the safe default: leaving a detail out rarely hurts, while adding one can.

| Country | Length | Photo | Personal details | Other | Confidence |
|---|---|---|---|---|---|
| **US** | 1 page early career, 2 for long careers | No | No birth date, marital status, nationality (anti-discrimination law) | Letter paper; "resume" | High |
| **Canada** | 1–2 pages | No (Job Bank: "not the norm in Canada") | Never age; nothing beyond name and contact | Letter paper; immigrants often over-share, so trimming is the main fix | High (government source) |
| **UK** | 1–2 A4 pages | No | No birth date or marital status (equality law) | "CV" | High |
| **Australia** | 2 pages for graduates, often 2–3 for experienced | No | No birth date, marital status, gender, licence unless the role needs it (government pages) | **Referees expected**: 2–3 named with contacts, or at least a ready list; Australian spelling (organise) | High on details (government + universities), medium on length |
| **Israel** | 1 page preferred, 2 max | No, except client-facing roles or when asked | Birth date optional (safe to omit) | **Military service** is a normal section (unit, role, years; rank optional); language follows the posting: tech often English, otherwise Hebrew; keep both ready | Medium-high (consistent guides; Technion template) |
| **Germany** | 2 pages typical | Common but optional; international firms accept none | Birth date and nationality often included; optional | Exact month/year dates; sometimes signed and dated | Medium (sources disagree on length and photo) |
| **France** | 1 page (France Travail: even with long experience), 2 for senior | Customary but optional | Age and marital status optional, increasingly left out (labor code bans discrimination) | Some large firms screen with a "CV anonyme" | Medium (many blogs disagree) |
| **Netherlands** | 1–2 A4 pages, short and direct | Split: follow the posting; never an ID photo | werk.nl list: name, address, email, phone; "you lose nothing" leaving out birth date, photo, nationality; **never the BSN** | Short profile on top; short cover letter is standard | Medium-high (government-style and university sources) |
| **Poland** | 1–2 pages | Often still expected by recruiters | Birth date not addressed by sources | **RODO consent clause** at the bottom is widely expected, though lawyers disagree that it is legally required; use the current GDPR wording, never the 1997 formula; follow the employer's own wording if given | Medium (legal sources disagree) |
| **India** | 1–2 pages (freshers often 1–2) | Usually not for IT/MNC; sometimes for non-IT freshers | **Private sector:** leave out father's name, birth date, marital status, religion, caste and the "declaration" line. **Government/PSU:** keep a full "biodata" version, since forms check age limits | Two versions are normal | Medium-high (consistent guides) |

### Right-to-left (Hebrew, Arabic) resumes

- Hebrew parsing still lags in many parsers. A common cause is that PDFs store RTL text in either logical or visual
  order, and extractors guess wrong, so words come out reversed. (Medium: industry write-ups, no controlled test.)
- Mixed Hebrew + English lines (e.g. "ניהול שרתי Linux") are the riskiest.
- No public data on how Greenhouse or Comeet (now Spark Hire) parse Hebrew.
- For the skill: for RTL resumes, prefer sending the **.docx** when the form accepts it. Always run the PDF parse
  self-check and look for reversed words. Offer an English version when the posting is in English.

### Still open (not blocking the first version)

Spain, Italy, Nordics, Gulf states, Japan (rirekisho format) and Brazil: the skill falls back to the safe default
(no photo or personal details, A4, 1–2 pages) and tells the user it has no specific rules for that country.

## Sources

- Preptel 75% myth: [Interview Guys](https://blog.theinterviewguys.com/?p=1967), [HiringThing](https://blog.hiringthing.com/applicant-tracking-system-myths), [f1jobs](https://www.f1jobs.io/resources/blog/ats-resume-service-75-percent-rejection-myth), [Fortune 2014](https://fortune.com/2014/08/22/how-to-keep-your-resume-from-getting-lost-in-cyberspace/)
- How ATSs screen: [Jobscan on Greenhouse](https://www.jobscan.co/blog/greenhouse-ats-what-job-seekers-need-to-know/), [Greenhouse vs Lever vs Workday](https://aiapply.co/blog/greenhouse-vs-lever-vs-workday), [Huntr](https://huntr.co/blog/how-applicant-tracking-systems-work)
- Parsing: [Workable](https://resources.workable.com/stories-and-insights/how-ATS-reads-resumes), [Jobscan on tables and columns](https://www.jobscan.co/blog/resume-tables-columns-ats/), [Adobe](https://www.adobe.com/acrobat/resources/resume-formatting-mistakes.html)
- Ladders 2018: [study PDF (BU copy)](https://www.bu.edu/com/files/2018/10/TheLadders-EyeTracking-StudyC2.pdf), [HR Dive](https://www.hrdive.com/news/eye-tracking-study-shows-recruiters-look-at-resumes-for-7-seconds/541582/), [ERE critique](https://www.ere.net/articles/is-the-6-second-resume-scan-a-myth)
- Hidden Workers: [HBS executive summary](https://pubwww.hbs.edu/managing-the-future-of-work/Documents/research/Hidden%20Workers%20Executive%20Summary.pdf), [Accenture full report](https://www.accenture.com/content/dam/accenture/final/a-com-migration/r3-3/pdf/pdf-169/accenture-hidden-worker-report.pdf), [WEF](https://www.weforum.org/stories/2021/09/artificial-intelligence-job-recruitment-process/), [HR Dive](https://www.hrdive.com/news/report-applicant-tracking-systems-may-exclude-whole-segments-of-candidates/606614/), [ERE](https://www.ere.net/are-evil-ats-robots-secretly-eating-peoples-resumes/)
- Hidden prompts: [Let's Data Science on the USENIX study](https://letsdatascience.com/news/applicants-hide-prompts-in-resumes-becd8ae8), [Built In](https://builtin.com/articles/hidden-ai-prompts-in-resume), [Duke Pratt](https://pratt.duke.edu/news/thwarting-prompt-injection/)
- Country conventions: [Chemistry World](https://chemistryworld.com/careers/how-to-tailor-your-cv-for-different-countries/2500446.article), [WEF on Germany](https://weforum.org/stories/2017/08/why-americans-would-be-shocked-by-common-resume-practices-in-germany), [Uni Kassel career service](https://www.uni-kassel.de/uni/en/studium/kontakt-und-beratung/servicestellen/career-service/application-tips/applying-for-positions-outside-germany/cv-in-english.html), [TopCV](https://topcv.co.uk/career-advice/international-cv-differences)
- Israel: [Nefesh B'Nefesh](https://www.nbn.org.il/aliyah-inspiration/nbn-blogger-network/nbn-employment-blog/writing-your-israeli-resume-the-dos-and-donts/), [VisualCV Israel](https://visualcv.com/international/israel-resume), [Easy Aliyah](https://www.easyaliyah.com/blog/adjusting-your-resume-cv-for-the-israeli-job-market), [Technion template](https://dean.technion.ac.il/wp-content/uploads/2023/05/%D7%A7%D7%95%D7%A8%D7%95%D7%AA-%D7%97%D7%99%D7%99%D7%9D-%D7%9E%D7%A0%D7%A6%D7%97%D7%99%D7%9D-PhD-1.docx)
- Hebrew/RTL parsing: [RChilli on Hebrew](https://www.rchilli.com/press-and-media/parses-resumes-jobs-in-hebrew), [Towards AI on RTL PDFs](https://towardsai.net/?p=50112)
- Poland: [Jobseeker on the RODO clause](https://www.jobseeker.com/pl/cv/artykuly/klauzula-cv-rodo), [ODO24 (legal view)](https://odo24.pl/en/wiedza/blog/rekrutacja-zgodna-z-rodo-jak-tor-przeszkod), [Zielona Linia (gov)](https://zielonalinia.gov.pl/klauzula-cv-2024-czyli-zgoda-na-przetwarzanie-danych-osobowych/), [Careers in Poland](https://www.careersinpoland.com/article/work/the-one-thing-you-should-never-leave-off-your-polish-cv)
- France: [Connexion France](https://www.connexionfrance.com/practical/how-french-cvs-differ-from-those-in-the-uk-or-us/697853), [Expatica France](https://www.expatica.com/fr/employment/finding-a-job/french-job-applications-writing-a-french-cv-and-interview-tips-101770), [FUSAC](https://fusac.fr/?p=118224)
- Netherlands: [Inburgering.org](https://inburgering.org/guides/dutch-cv-application-guide), [Leiden International Centre](https://www.leideninternationalcentre.nl/get-advice/blogs/how-to-update-your-cv-for-the-dutch-job-market-without-overcomplicating-it), [WUR](https://wur.nl/en/show/cv-guide-and-tips.htm), [Expatica NL](https://www.expatica.com/nl/employment/finding-a-job/cv-netherlands-writing-a-dutch-cv-and-interview-tips-for-a-job-application-102340/)
- India: [Monster India format](https://www.monster.com/career-advice/resume/indian-resume-format), [Kickresume](https://www.kickresume.com/en/blog/indian-resume-format-guide/), [Jobrise fresher review](https://jobrise.io/blog/resume-mistakes-freshers-india)
- Canada: [Job Bank (Government of Canada)](https://www.jobbank.gc.ca/findajob/resources/write-good-resume), [Settlement.org](https://settlement.org/ontario/employment/find-a-job/resume/how-do-i-create-a-canadian-style-resume), [CIC News](https://www.cicnews.com/2025/06/resume-writing-tips-for-new-canadians-0656097.html)
- Australia: [ASIC resume tips](https://careers.asic.gov.au/pdf/Resume_tips.pdf), [Live in Melbourne (Vic gov)](https://liveinmelbourne.vic.gov.au/work/find-a-job-in-melbourne/how-to-apply-for-a-job-in-melbourne), [University of Queensland](https://employability.uq.edu.au/files/176803/Resume%20Fact%20Sheet%20%26%20Example.pdf), [University of Sydney](https://sydney.edu.au/careers/students/applying-for-jobs/how-to-write-a-resume/resume-template.html)
