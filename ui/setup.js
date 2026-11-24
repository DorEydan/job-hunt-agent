// First-run setup wizard. Loaded after app.js; uses its helpers (state, field, get, set, api, esc, go, render).
// It edits state.cfg like the tabs do, and saves once at the end.

const FIELDS = {
  software: { label: "Software development", titles: ["Full Stack Developer", "Backend Developer", "Frontend Developer", "Software Engineer"] },
  devops: { label: "DevOps / Cloud", titles: ["DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer", "Platform Engineer"] },
  data: { label: "Data / Analytics / ML", titles: ["Data Analyst", "Data Engineer", "BI Developer", "Machine Learning Engineer"] },
  qa: { label: "QA / Testing", titles: ["QA Engineer", "Automation Engineer", "Software Tester"] },
  it: { label: "IT / System administration", titles: ["System Administrator", "IT Support Engineer", "Network Engineer"] },
  security: { label: "Cyber security", titles: ["Security Analyst", "SOC Analyst", "Security Engineer"] },
  design: { label: "UX / UI design", titles: ["UX Designer", "UI Designer", "Product Designer"] },
  product: { label: "Product / Project management", titles: ["Product Manager", "Project Manager", "Product Owner"] },
  marketing: { label: "Marketing / Content / SEO", titles: ["Digital Marketing Specialist", "Content Writer", "SEO Specialist"] },
  sales: { label: "Sales / Customer success", titles: ["Sales Representative", "Customer Success Manager", "Account Manager"] },
  other: { label: "Something else", titles: [] },
};
const LEVELS = {
  student: { label: "Student / intern", prefix: "Student", years: 0 },
  entry: { label: "Entry level (no experience)", prefix: "Junior", years: 0 },
  junior: { label: "Junior (0–2 years)", prefix: "Junior", years: 2 },
  mid: { label: "Mid level (2–5 years)", prefix: "", years: 5 },
  senior: { label: "Senior (5+ years)", prefix: "Senior", years: 15 },
};
const SENIOR_WORDS = ["Senior", "Sr.", "Lead", "Team Leader", "Head", "Manager", "Principal", "Staff", "Architect", "Director"];

// Local job sites per country. Global sites (LinkedIn, Indeed, Glassdoor, company pages, Gemini) are added for everyone.
const COUNTRIES = {
  "Israel": { indeed: "il.indeed.com", lang: "Hebrew", sites: ["alljobs", "drushim", "jobmaster", "misrotech", "telegram", "facebook-groups"] },
  "Poland": { indeed: "pl.indeed.com", lang: "Polish", sites: ["pracuj", "justjoinit", "nofluffjobs", "rocketjobs", "bulldogjob"] },
  "Germany": { indeed: "de.indeed.com", lang: "German", sites: ["stepstone-de", "arbeitsagentur", "xing", "berlinstartupjobs"] },
  "United Kingdom": { indeed: "uk.indeed.com", lang: "English", sites: ["reed", "totaljobs", "cv-library", "cwjobs"] },
  "United States": { indeed: "www.indeed.com", lang: "English", sites: ["dice", "builtin", "ziprecruiter", "handshake"] },
  "Canada": { indeed: "ca.indeed.com", lang: "English / French", sites: ["jobbank-ca", "eluta"] },
  "India": { indeed: "in.indeed.com", lang: "English", sites: ["naukri", "foundit", "instahyre"] },
  "France": { indeed: "fr.indeed.com", lang: "French", sites: ["welcome-to-the-jungle", "france-travail", "apec"] },
  "Netherlands": { indeed: "nl.indeed.com", lang: "Dutch", sites: ["nationale-vacaturebank", "werk-nl"] },
  "Spain": { indeed: "es.indeed.com", lang: "Spanish", sites: ["infojobs", "tecnoempleo"] },
  "Australia": { indeed: "au.indeed.com", lang: "English", sites: ["seek", "jora"] },
  "Other / remote only": { indeed: "www.indeed.com", lang: "", sites: ["remoteok", "weworkremotely", "wellfound"] },
};
const GLOBAL_SITES = ["linkedin", "indeed", "glassdoor", "company-ats", "gemini"];
const REMOTE_SITES = ["remoteok", "weworkremotely", "wellfound"];
// Country-specific presets, added to the Sites tab's PRESETS list.
const LOCAL_PRESETS = [
  { id: "pracuj", name: "Pracuj.pl (Poland)", needs_signin: true, search: "pracuj.pl search with {query}, location {location}, newest first.", apply: "The site's apply button (uses your Pracuj profile), or the company form.", notes: "Poland." },
  { id: "justjoinit", name: "Just Join IT (Poland)", needs_signin: false, search: "justjoin.it offers filtered by {query} and experience level.", apply: "The apply form on the offer.", notes: "Poland, tech jobs." },
  { id: "nofluffjobs", name: "No Fluff Jobs (Poland)", needs_signin: false, search: "nofluffjobs.com search: {query}, junior.", apply: "The apply form on the offer.", notes: "Poland, tech jobs. Salaries are shown." },
  { id: "rocketjobs", name: "RocketJobs (Poland)", needs_signin: false, search: "rocketjobs.pl search: {query}.", apply: "The apply form on the offer.", notes: "Poland, non-tech jobs too." },
  { id: "bulldogjob", name: "Bulldogjob (Poland)", needs_signin: false, search: "bulldogjob.pl search: {query}.", apply: "The apply form on the offer.", notes: "Poland, tech jobs." },
  { id: "stepstone-de", name: "StepStone (Germany)", needs_signin: true, search: "stepstone.de search: {query} in {location}, newest first.", apply: "The site's apply button or the company form.", notes: "Germany." },
  { id: "arbeitsagentur", name: "Jobbörse der Arbeitsagentur (Germany)", needs_signin: false, search: "arbeitsagentur.de Jobsuche: {query}, {location}.", apply: "The link or email in the posting.", notes: "Germany, public job board." },
  { id: "xing", name: "XING Jobs (Germany)", needs_signin: true, search: "xing.com/jobs search: {query} {location}.", apply: "The apply link in the posting.", notes: "Germany / DACH." },
  { id: "berlinstartupjobs", name: "Berlin Startup Jobs", needs_signin: false, search: "berlinstartupjobs.com, newest posts matching {query}.", apply: "The link in the post.", notes: "Berlin startups." },
  { id: "reed", name: "Reed (UK)", needs_signin: true, search: "reed.co.uk search: {query} in {location}, posted in the last {days} days.", apply: "Reed's apply button or the company site.", notes: "United Kingdom." },
  { id: "totaljobs", name: "Totaljobs (UK)", needs_signin: true, search: "totaljobs.com search: {query} in {location}, newest first.", apply: "The site's apply button.", notes: "United Kingdom." },
  { id: "cv-library", name: "CV-Library (UK)", needs_signin: true, search: "cv-library.co.uk search: {query} in {location}.", apply: "The site's apply button.", notes: "United Kingdom." },
  { id: "cwjobs", name: "CWJobs (UK, tech)", needs_signin: true, search: "cwjobs.co.uk search: {query} in {location}.", apply: "The site's apply button.", notes: "United Kingdom, IT and tech." },
  { id: "dice", name: "Dice (US, tech)", needs_signin: true, search: "dice.com search: {query} in {location}, posted in the last {days} days.", apply: "Easy Apply on Dice, or the company site.", notes: "United States, tech jobs." },
  { id: "ziprecruiter", name: "ZipRecruiter (US)", needs_signin: true, search: "ziprecruiter.com search: {query} in {location}.", apply: "1-Click Apply or the company site.", notes: "United States." },
  { id: "handshake", name: "Handshake (US students)", needs_signin: true, search: "joinhandshake.com jobs search: {query}.", apply: "Handshake's apply button.", notes: "Students and recent graduates; sign in with your school account." },
  { id: "jobbank-ca", name: "Job Bank (Canada)", needs_signin: false, search: "jobbank.gc.ca search: {query} in {location}.", apply: "The how-to-apply section of the posting.", notes: "Canada, government job board." },
  { id: "eluta", name: "Eluta (Canada)", needs_signin: false, search: "eluta.ca search: {query} {location}.", apply: "Follow the link to the employer site.", notes: "Canada, collects employer career pages." },
  { id: "naukri", name: "Naukri (India)", needs_signin: true, search: "naukri.com search: {query} in {location}, freshness = last {days} days.", apply: "Naukri's apply button or the company site.", notes: "India." },
  { id: "foundit", name: "foundit (India)", needs_signin: true, search: "foundit.in search: {query} in {location}.", apply: "The site's apply button.", notes: "India (formerly Monster India)." },
  { id: "instahyre", name: "Instahyre (India)", needs_signin: true, search: "instahyre.com opportunities matching {query}.", apply: "The site's apply / interested button.", notes: "India, tech." },
  { id: "france-travail", name: "France Travail (France)", needs_signin: false, search: "candidat.francetravail.fr offres: {query}, {location}.", apply: "The link or contact in the offer.", notes: "France, public job board." },
  { id: "apec", name: "Apec (France)", needs_signin: true, search: "apec.fr offres: {query}, {location}.", apply: "The apply button on the offer.", notes: "France, graduate and professional jobs." },
  { id: "nationale-vacaturebank", name: "Nationale Vacaturebank (NL)", needs_signin: false, search: "nationalevacaturebank.nl search: {query} in {location}.", apply: "The apply link in the posting.", notes: "Netherlands." },
  { id: "werk-nl", name: "werk.nl (NL)", needs_signin: false, search: "werk.nl vacatures: {query}, {location}.", apply: "The link or contact in the posting.", notes: "Netherlands, public job board." },
  { id: "infojobs", name: "InfoJobs (Spain)", needs_signin: true, search: "infojobs.net search: {query} in {location}, newest first.", apply: "InfoJobs' apply button.", notes: "Spain." },
  { id: "tecnoempleo", name: "Tecnoempleo (Spain, tech)", needs_signin: true, search: "tecnoempleo.com search: {query} {location}.", apply: "The site's apply button.", notes: "Spain, tech jobs." },
  { id: "seek", name: "SEEK (Australia)", needs_signin: true, search: "seek.com.au search: {query} in {location}, listed in the last {days} days.", apply: "Quick Apply on SEEK, or the company site.", notes: "Australia." },
  { id: "jora", name: "Jora (Australia)", needs_signin: false, search: "au.jora.com search: {query} in {location}.", apply: "Follow the link to the original posting.", notes: "Australia, collects postings." },
];
PRESETS.push(...LOCAL_PRESETS.filter(p => !PRESETS.some(x => x.id === p.id)));

// Reading per field: neutral sources (university career centers, the US Bureau of Labor Statistics) plus our guides.
const OOH = ["Occupational Outlook Handbook (US BLS): what the job involves, pay, outlook", "https://www.bls.gov/ooh/"];
const FIELD_GUIDES = {
  tech: [["UCF Career Services: data, cybersecurity and IT paths", "https://career.ucf.edu/channels/data-analytics-cybersecurity-information-technology/"],
         ["UW–Madison Career Exploration Center: field guides", "https://cec.wisc.edu/?p=4439"]],
  marketing: [["UCF Career Services: marketing paths", "https://career.ucf.edu/channels/marketing/"],
              ["UChicago Career Advancement: industry guides", "https://careeradvancement.uchicago.edu/career-toolkit/discover-your-passion/industry-guides/"]],
  design: [["UChicago Social Sciences: career guides (incl. UX)", "https://socialsciences.uchicago.edu/exploration/career-guides"],
           ["UW–Madison Career Exploration Center: field guides", "https://cec.wisc.edu/?p=4439"]],
  business: [["UChicago Career Advancement: industry guides", "https://careeradvancement.uchicago.edu/career-toolkit/discover-your-passion/industry-guides/"],
             ["SJSU Career Center: career guides", "https://careercenter.sjsu.edu/resources/career-guides/"]],
};
const FIELD_GUIDE_GROUP = { software: "tech", devops: "tech", data: "tech", qa: "tech", it: "tech", security: "tech",
  marketing: "marketing", design: "design", product: "business", sales: "business", other: "business" };
function guidesCard() {
  const g = [...(FIELD_GUIDES[FIELD_GUIDE_GROUP[get("field")] || "business"] || []), OOH,
    ["Our job search guide", "https://github.com/DorEydan/job-hunt-agent/blob/main/docs/JOB_SEARCH_GUIDE.md"], ["Our resume guide", "https://github.com/DorEydan/job-hunt-agent/blob/main/docs/RESUME_GUIDE.md"],
    ["Our cover letter guide", "https://github.com/DorEydan/job-hunt-agent/blob/main/docs/COVER_LETTER_GUIDE.md"], ["Our interview guide", "https://github.com/DorEydan/job-hunt-agent/blob/main/docs/INTERVIEW_GUIDE.md"]];
  return `<div class="card"><h3>Guides for ${esc((FIELDS[get("field")] || FIELDS.other).label)}</h3>
    <ul class="review">${g.map(([t, u]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a></li>`).join("")}</ul>
    ${state.ai && state.ai.ready ? `<button class="btn" data-sug="tips">Tips for ${esc((FIELDS[get("field")] || FIELDS.other).label)} in ${esc(get("country") || "your country")} (AI)</button>
      <div id="sugTips" class="report" style="margin-top:8px">${wiz.tips ? md(wiz.tips) : ""}</div>` : `<p class="sub">Set up an AI on the AI tab later for tips specific to your field and country.</p>`}</div>`;
}

const COMMUTE = [[5, "Only my city"], [15, "Up to 15 km"], [30, "Up to 30 km"], [50, "Up to 50 km"], [100, "Up to 100 km"], [0, "Anywhere in the country"]];
const STEPS = ["Welcome", "Resume", "About you", "Your work", "Location", "Sites", "Applying", "Schedule", "Finish"];
const STEP_KEYS = ["welcome", "resume", "you", "work", "location", "sites", "applying", "schedule", "finish"];
const at = key => STEP_KEYS[wiz.step] === key;

const wiz = { step: 0, picked: null, resume: null, cover: null, msg: "" };

function presetFor(id) {
  const p = PRESETS.find(x => x.id === id); if (!p) return null;
  const c = COUNTRIES[get("country")] || COUNTRIES["Other / remote only"];
  const out = { ...p, enabled: true };
  if (id === "indeed") out.search = `https://${c.indeed}/jobs?q={query}&l={location}&fromage={days}`;
  return out;
}
function recommendedSites() {
  const c = COUNTRIES[get("country")] || COUNTRIES["Other / remote only"];
  const ids = [...GLOBAL_SITES, ...c.sites];
  if (get("locations.accept_remote")) REMOTE_SITES.forEach(x => ids.includes(x) || ids.push(x));
  return ids;
}
function generateSearch() {  // roles, search terms and seniority from the field + level
  const f = FIELDS[get("field")] || FIELDS.other; const lv = LEVELS[get("experience_level")] || LEVELS.junior;
  const roles = f.titles.map(t => (lv.prefix ? lv.prefix + " " : "") + t);
  set("target_roles", roles);
  set("search_terms_en", roles.map(r => r.toLowerCase()).concat(get("experience_level") === "entry" ? f.titles.slice(0, 2).map(t => "entry level " + t.toLowerCase()) : []));
  const sen = { ...(get("seniority") || {}) };
  sen.max_years_required = lv.years;
  sen.include_student_positions = ["student", "entry", "junior"].includes(get("experience_level"));
  sen.exclude_title_words = ["student", "entry", "junior"].includes(get("experience_level")) ? SENIOR_WORDS
    : get("experience_level") === "mid" ? ["Principal", "Director", "Head", "VP"] : ["Intern", "Student", "Junior"];
  set("seniority", sen);
  const jt = { ...(get("job_types") || {}) }; jt.student = jt.internship = get("experience_level") === "student" || get("experience_level") === "entry";
  set("job_types", jt);
}

function stepper() {
  return `<ol class="stepper">${STEPS.map((s, i) => `<li class="${i === wiz.step ? "on" : i < wiz.step ? "done" : ""}">${i < wiz.step ? "✓" : i + 1}<span>${s}</span></li>`).join("")}</ol>`;
}
function navButtons(nextLabel = "Next") {
  return `<div class="wiznav">${wiz.step > 0 ? `<button class="btn" data-wiz="back">Back</button>` : `<span></span>`}
    <span class="sub" id="wizmsg">${esc(wiz.msg)}</span>
    <button class="btn primary" data-wiz="next">${nextLabel}</button></div>`;
}
const radio = (name, value, label, checked, extra = "") => `<label class="opt ${checked ? "on" : ""}"><input type="radio" name="${name}" value="${esc(value)}" ${checked ? "checked" : ""}> <span>${label}</span>${extra}</label>`;

const steps = {};
steps.welcome = () => `<div class="card"><h3>Let's set up your job hunt</h3>
  <p>About 5 minutes. First upload your resume: the wizard reads it and fills in what it can. Then you'll confirm your field, where you want to work and how far you'll travel, the job sites for your country, your resume and how often to search.</p>
  <p class="sub">Everything stays on your computer in <code>config.json</code>. You can change any of it later in the tabs on the left.</p>
  <p><a href="#" data-wiz="skip">Skip, I'll set it up myself</a></p></div>${navButtons("Start")}`;

steps.you = () => `<div class="card"><h3>About you</h3><p class="sub" style="margin-top:-6px">Used to fill in application forms.</p><div class="grid">
  ${field("candidate.full_name", "Full name")}${field("candidate.email", "Email")}${field("candidate.phone", "Phone", { ph: "+1 555 000 0000" })}
  <div><label for="w_country">Country you're looking in</label><select id="w_country">${Object.keys(COUNTRIES).map(c => `<option ${get("country") === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></div>
  ${field("candidate.city", "Your city", { ph: "Kraków, Poland", hint: "Distances are measured from here." })}
  ${field("candidate.linkedin", "LinkedIn URL", { ph: "https://www.linkedin.com/in/…" })}
  ${field("candidate.github", "GitHub URL (optional)")}
  ${field("candidate.portfolio", "Portfolio or project site (optional)", { ph: "https://…", hint: "Given in forms that ask for a website or portfolio." })}
  ${field("report_language", "Language of the run reports", { ph: "English" })}
  </div></div>${navButtons()}`;

steps.work = () => {
  const f = get("field"), lv = get("experience_level");
  return `<div class="card"><h3>What kind of job?</h3><div class="opts">${Object.entries(FIELDS).map(([k, v]) => radio("w_field", k, v.label, f === k)).join("")}</div></div>
  <div class="card"><h3>Your level</h3><div class="opts">${Object.entries(LEVELS).map(([k, v]) => radio("w_level", k, v.label, lv === k)).join("")}</div></div>
  <div class="card"><h3>Job titles and search terms</h3><p class="sub" style="margin-top:-6px">Filled in from your choices. Edit freely, one per line.</p><div class="grid">
    ${field("target_roles", "Job titles you want", { type: "lines" })}
    ${field("search_terms_en", "Search terms (English)", { type: "lines" })}
    ${field("search_terms_local", "Search terms in the local language", { type: "lines", hint: COUNTRIES[get("country")]?.lang && COUNTRIES[get("country")].lang !== "English" ? `Optional, in ${esc(COUNTRIES[get("country")].lang)}. Local boards find more with local terms.` : "Optional." })}
  </div>${state.ai && state.ai.ready ? `<button class="btn" data-sug="terms" style="margin-top:8px">Suggest local-language search terms (AI)</button>` : ""}</div>
  ${guidesCard()}
  <div class="card"><h3>Job types</h3><div class="grid"><div>${JOB_TYPES.slice(0, 3).map(([k, l]) => field("job_types." + k, l, { type: "bool" })).join("")}</div><div>${JOB_TYPES.slice(3).map(([k, l]) => field("job_types." + k, l, { type: "bool" })).join("")}</div></div></div>
  ${navButtons()}`;
};

steps.location = () => {
  const km = get("locations.max_commute_km") ?? 30;
  return `<div class="card"><h3>How far will you travel?</h3><p class="sub" style="margin-top:-6px">From ${esc(get("candidate.city") || "your city")}. The agent skips on-site and hybrid jobs farther than this.</p>
    <div class="opts">${COMMUTE.map(([v, l]) => radio("w_km", v, l, km === v)).join("")}</div>
    <div class="grid" style="margin-top:12px">
      ${field("search_location", "Search location used on job sites", { ph: get("country") || "Israel", hint: "Usually your country or region, e.g. “Poland” or “Greater London”." })}
      ${field("locations.preferred", "Preferred cities (optional)", { type: "lines", hint: "Jobs here rank higher." })}
    </div></div>
  <div class="card"><h3>Work setup</h3>
    ${field("locations.accept_remote", "Remote jobs are OK", { type: "bool" })}${field("locations.accept_hybrid", "Hybrid jobs are OK", { type: "bool" })}
    <div><label class="check"><input type="checkbox" id="w_reloc" ${get("screening_answers.willing_to_relocate") === "yes" ? "checked" : ""}> I'm willing to relocate for the right job</label></div>
  </div>${navButtons()}`;
};

steps.sites = () => {
  if (!wiz.picked) wiz.picked = new Set(recommendedSites());
  const rec = recommendedSites(); const c = get("country") || "";
  const extra = PRESETS.filter(p => !rec.includes(p.id));
  const row = p => `<label class="check"><input type="checkbox" data-site="${esc(p.id)}" ${wiz.picked.has(p.id) ? "checked" : ""}> <b>${esc(p.name)}</b> <span class="pill">${p.needs_signin ? "sign-in" : "public"}</span> <span class="sub">${esc(p.notes || "")}</span></label>`;
  return `<div class="card"><h3>Recommended for ${esc(c)}</h3><p class="sub" style="margin-top:-6px">Global sites plus the local boards people in ${esc(c)} actually use. Sites marked “sign-in” open in your own Chrome, signed in.</p>
    ${rec.map(id => PRESETS.find(p => p.id === id)).filter(Boolean).map(row).join("")}</div>
    ${state.ai && state.ai.ready ? `<div class="card"><button class="btn" data-sug="sites">Suggest more sites for ${esc(c)} and ${esc((FIELDS[get("field")] || FIELDS.other).label)} (AI)</button>
      <div class="hint">Suggestions are added unchecked: check the ones you know and trust. The agent verifies each site on its first run.</div></div>` : ""}
    <details class="card"><summary><b>More sites</b> <span class="sub">(other countries, remote boards)</span></summary><div style="margin-top:10px">${extra.map(row).join("")}</div></details>
    <p class="sub">You can reorder, edit or add custom sites later in the Sites tab.</p>${navButtons()}`;
};

steps.resume = () => {
  const r = wiz.resume; const cv = wiz.cover;
  const skills = r && r.skills ? `<ul class="skills">${Object.entries(r.skills).map(([k, v]) => `<li><b>${esc(k)}:</b> ${esc(v.join(", "))}</li>`).join("")}</ul>
      <div class="msg ok">Found ${Object.keys(r.skills).length} skill lines. For each job the agent only reorders these; nothing else in your resume changes.</div>` : "";
  return `<div class="card"><h3>Your resume</h3>
    <p class="sub" style="margin-top:-6px">The wizard reads your resume and fills in as much as it can: contact details, country, field, level, job titles, skills. A Word <code>.docx</code> (up to 5 MB). Under a heading such as <i>Technical Skills</i>, one line per group: <code>Label: skill, skill, skill</code>. That's the only part the agent reorders per job.</p>
    <div class="row"><input type="file" id="w_resume" accept=".docx"><span class="sub">${r ? `Saved as <code>${esc(r.path)}</code>` : ""}</span></div>
    <div class="grid" style="margin-top:12px">${field("skills_heading", "Skills heading in your resume", { ph: "Technical Skills" })}${field("resume_output_name", "Name of the PDF that gets sent", { ph: "Jane Doe resume" })}</div>
    ${r && r.skills_error ? `<div class="msg bad">${esc(r.skills_error)}</div><button class="btn" data-wiz="reread">Read again with this heading</button>` : ""}
    ${skills}
    ${wiz.filled && wiz.filled.length ? `<div class="msg ok">Filled in from your resume: ${esc(wiz.filled.join(", "))}. You'll check each one in the next steps.</div>` : ""}
    <p class="sub">${r ? "Want a fresh design?" : "No resume yet, or want a new design?"} <a href="#" data-wiz="builder">Build one with the resume builder</a>${r ? "" : ` · or <a href="#" data-wiz="sample">continue with the sample resume</a> for now`}.</p>
  </div>
  <div class="card"><h3>Cover letter <span class="sub">(optional)</span></h3>
    <p class="sub" style="margin-top:-6px">Attached when a form has a cover-letter field. <code>.docx</code>, <code>.pdf</code> or <code>.txt</code>.</p>
    <div class="row"><input type="file" id="w_cover" accept=".docx,.pdf,.txt,.md"><span class="sub">${get("cover_letter_file") ? `Saved as <code>${esc(get("cover_letter_file"))}</code> <a href="#" data-wiz="nocover">Remove</a>` : ""}</span></div>
    ${cv && cv.text ? `<pre class="prompt" style="max-height:140px;overflow:auto">${esc(cv.text.slice(0, 600))}${cv.text.length > 600 ? "…" : ""}</pre>` : ""}
    ${field("cover_note.en", "Short email note (used when applying by email)", { type: "text", hint: "Placeholders: {role}, {top_skills}, {phone}, {full_name}." })}
  </div>${navButtons()}`;
};

steps.applying = () => `${tailoringCard()}${reapplyCard()}<div class="card"><h3>How may the agent apply?</h3>${APPLY_METHODS.map(([k, l]) => field("apply_methods." + k, l, { type: "bool" })).join("")}
    <div class="hint">Jobs that need a method you switched off are listed for you to apply yourself.</div></div>
  <div class="card"><h3>Common form questions</h3><p class="sub" style="margin-top:-6px">The agent answers only from here. Leave blank to be asked.</p><div class="grid">
    ${field("screening_answers.notice_period", "Notice period / start date", { ph: "e.g. 30 days, immediately" })}
    ${field("screening_answers.salary_expectation", "Salary expectation", { ph: "e.g. 60,000 EUR / year" })}
    ${field("screening_answers.authorized_to_work", "Authorized to work in " + (get("country") || "the country") + "?", { ph: "yes / no / needs visa" })}
    ${field("screening_answers.years_experience", "Years of relevant experience", { ph: "e.g. 1" })}
    ${field("screening_answers.degree_status", "Degree", { ph: "e.g. BSc Computer Science, completed" })}
  </div></div>
  <div class="card">${field("cover_note_in_forms", "Paste the cover letter / note into optional fields", { type: "bool" })}${field("notifications", "Notify me when a run finds jobs", { type: "bool" })}
    <div class="check sub">✓ Always on: nothing is sent until you approve it.</div></div>${navButtons()}`;

steps.schedule = () => {
  const sch = get("schedule") || {}; const info = scheduleInfo();
  return `<div class="card"><h3>How often to search?</h3>
    <div class="opts">
      ${[["sun,mon,tue,wed,thu,fri,sat", "Every day"], ["mon,tue,wed,thu,fri", "Workdays (Mon–Fri)"], ["sun,mon,tue,wed,thu", "Workdays (Sun–Thu)"], ["sun,tue,thu", "3× a week"], ["mon,thu", "2× a week"], ["mon", "Once a week"]]
        .map(([d, l]) => radio("w_freq", d, l, (sch.days || []).join(",") === d)).join("")}
    </div>
    <div class="row" style="margin-top:12px" id="dayPick">${DAYS.map(([k, l]) => `<label class="daychip"><input type="checkbox" value="${k}" ${(sch.days || []).includes(k) ? "checked" : ""}> ${l}</label>`).join("")}</div>
    <div class="row" style="margin-top:12px"><label for="w_time" style="margin:0">Time</label><input type="time" id="w_time" value="${esc(sch.time || "09:00")}" style="max-width:140px">
      <span class="sub">Each run looks back ${info.maxGap} day${info.maxGap === 1 ? "" : "s"}, the longest gap between runs.</span></div>
    <div class="grid" style="margin-top:12px">${field("max_new_jobs_per_run", "Max new jobs per run", { type: "int", hint: "Fewer per run = quicker to review. Daily: 5–8 is plenty." })}</div>
  </div>${navButtons()}`;
};

steps.finish = () => {
  const sites = (get("sources") || []).filter(s => s.enabled).map(s => s.name);
  const info = scheduleInfo(); const km = get("locations.max_commute_km");
  const li = (k, v) => `<li><b>${k}:</b> ${v}</li>`;
  return `<div class="card"><h3>Review</h3><ul class="review">
    ${li("You", esc([get("candidate.full_name"), get("candidate.email"), get("candidate.city")].filter(Boolean).join(" · ")))}
    ${li("Looking for", esc((FIELDS[get("field")] || {}).label || "") + " · " + esc((LEVELS[get("experience_level")] || {}).label || ""))}
    ${li("Job titles", esc((get("target_roles") || []).join(", ")))}
    ${li("Where", esc(get("search_location") || "") + " · " + esc((COMMUTE.find(c => c[0] === km) || [0, km + " km"])[1]) + (get("locations.accept_remote") ? " · remote OK" : ""))}
    ${li("Sites", esc(sites.join(", ")))}
    ${li("Resume", esc(Object.values(get("base_resumes") || {}).filter(v => typeof v === "string" && !v.startsWith("_")).join(", ") || "none"))}
    ${li("Cover letter", esc(get("cover_letter_file") || "none"))}
    ${li("Schedule", esc(info.days.map(d => DAYS.find(x => x[0] === d)[1]).join(", ")) + " at " + esc(info.time))}
  </ul></div>
  <div class="card"><h3>After you finish</h3><ol class="steps">
    <li>On the Schedule tab, copy the prompt into Claude Code to create the scheduled runs.</li>
    <li>Keep Chrome open with the Claude in Chrome extension, signed in to the “sign-in” sites.</li>
    <li>After each run you get a list of jobs. Reply e.g. <i>send 1,3</i>. Nothing is sent before that.</li></ol></div>
  ${navButtons("Save and finish")}`;
};

const PLACEHOLDER = /^(|Your Name|you@example\.com|Your City.*|.*your-profile.*|.*your-user.*|\+\d+ 50-000-0000|Your Name resume)$/;
function applyProfile(p) {  // fill only empty or example values; returns the list of what was filled
  const filled = [];
  const put = (path, val, label) => {
    if (val === undefined || val === null || val === "") return;
    const cur = get(path); if (cur === undefined || PLACEHOLDER.test(String(cur))) { set(path, val); filled.push(label); }
  };
  put("candidate.full_name", p.full_name, "name"); put("candidate.email", p.email, "email"); put("candidate.phone", p.phone, "phone");
  put("candidate.city", p.city, "city"); put("candidate.linkedin", p.linkedin, "LinkedIn"); put("candidate.github", p.github, "GitHub");
  put("candidate.portfolio", p.portfolio, "portfolio site");
  if (p.full_name) put("resume_output_name", p.full_name + " resume", "PDF name");
  if (p.skills_heading) { set("skills_heading", p.skills_heading); filled.push("skills heading"); }
  if (p.country && COUNTRIES[p.country] && get("country") !== p.country) {
    set("country", p.country); set("search_location", p.country); set("search_terms_local", []);
    set("locations", { ...(get("locations") || {}), preferred: [] }); wiz.picked = null;
  }
  if (p.country && COUNTRIES[p.country]) filled.push("country");
  if (p.field && FIELDS[p.field]) { set("field", p.field); filled.push("field"); }
  if (p.experience_level && LEVELS[p.experience_level]) { set("experience_level", p.experience_level); filled.push("level"); }
  if (p.field || p.experience_level) {
    generateSearch();
    const head = (p.headline || "").split(/[|•·,]/)[0].trim();  // e.g. "Full-Stack Developer"
    if (head && head.length <= 50) {
      const pre = (LEVELS[get("experience_level")] || {}).prefix;
      const title = pre && !new RegExp("\\b" + pre + "\\b", "i").test(head) ? pre + " " + head : head;
      if (!get("target_roles").some(r => r.toLowerCase() === title.toLowerCase())) {
        set("target_roles", [title, ...get("target_roles")]); set("search_terms_en", [title.toLowerCase(), ...get("search_terms_en")]);
      }
    }
    filled.push("job titles and search terms");
  }
  if (p.years_experience !== undefined) { set("screening_answers.years_experience", String(p.years_experience)); filled.push("years of experience"); }
  if (p.degree) { set("screening_answers.degree_status", p.degree); filled.push("degree"); }
  return filled;
}

function readFileB64(file) {
  return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(",")[1] || ""); r.onerror = () => rej(new Error("Could not read the file.")); r.readAsDataURL(file); });
}
async function upload(kind, file) {
  if (file.size > 5_000_000) throw new Error("The file is larger than 5 MB.");
  return api("/api/upload", { kind, filename: file.name, data: await readFileB64(file), heading: get("skills_heading") || "Technical Skills", variant: "default" });
}

function validateStep() {
  if (at("you")) {
    if (!(get("candidate.full_name") || "").trim() || /Your Name/.test(get("candidate.full_name"))) return "Enter your name.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(get("candidate.email") || "") || /@example\.com$/.test(get("candidate.email"))) return "Enter your email.";
  }
  if (at("work") && !(get("target_roles") || []).length) return "Add at least one job title.";
  if (at("sites") && !wiz.picked.size) return "Pick at least one site.";
  if (at("schedule") && !(get("schedule.days") || []).length) return "Pick at least one day.";
  const hasResume = Object.entries(get("base_resumes") || {}).some(([k, v]) => !k.startsWith("_") && v && !/sample-resume\.docx$/.test(v));
  if (at("resume") && !wiz.resume && !wiz.sample && !hasResume) return "Upload your resume, or continue with the sample.";
  return "";
}
function applySites() {
  const old = get("sources") || []; const keep = new Map(old.map(s => [s.id, s]));
  const order = [...recommendedSites(), ...PRESETS.map(p => p.id)].filter((id, i, a) => a.indexOf(id) === i);
  const chosen = order.filter(id => wiz.picked.has(id)).map(id => ({ ...(keep.get(id) || presetFor(id)), ...(id === "indeed" ? { search: presetFor("indeed").search } : {}), enabled: true }));
  const off = old.filter(s => !wiz.picked.has(s.id)).map(s => ({ ...s, enabled: false }));
  set("sources", [...chosen, ...off]);
}

async function finish() {
  if (!(get("resume_output_name") || "").trim()) set("resume_output_name", (get("candidate.full_name") || "My") + " resume");
  set("setup_complete", true);
  const r = await api("/api/config", { config: state.cfg });
  if (r.problems) throw new Error("Not saved:\n" + r.problems.join("\n"));
  state.saved = JSON.stringify(state.cfg); state.exists = true; state.wizard = false; wiz.step = 0;
  document.body.classList.remove("wizard"); toast("All set");
  go("automate");
}

pages.setup = () => {
  document.body.classList.add("wizard");
  $("#main").innerHTML = `<h2>Setup</h2>${stepper()}<div id="wizbody">${steps[STEP_KEYS[wiz.step]]()}</div>`;
  if (at("you")) $("#w_country").addEventListener("change", e => {
    const before = get("country");
    set("country", e.target.value); if (!get("search_location") || Object.keys(COUNTRIES).includes(get("search_location"))) set("search_location", e.target.value.startsWith("Other") ? "Remote" : e.target.value);
    if (before !== e.target.value) {  // the example's local terms and cities belong to the old country
      set("search_terms_local", []); set("locations", { ...(get("locations") || {}), preferred: [] });
    }
    wiz.picked = null;
  });
  if (at("location")) $("#w_reloc").addEventListener("change", e => set("screening_answers.willing_to_relocate", e.target.checked ? "yes" : "no"));
  if (at("schedule")) {
    const setDays = days => set("schedule", { ...(get("schedule") || {}), days });
    $("#dayPick").addEventListener("change", () => { setDays([...$("#dayPick").querySelectorAll("input:checked")].map(i => i.value)); render(); });
    $("#w_time").addEventListener("change", e => set("schedule", { ...(get("schedule") || {}), time: e.target.value }));
  }
  if (at("resume")) {
    $("#w_resume").addEventListener("change", async e => {
      const f = e.target.files[0]; if (!f) return; wiz.msg = "Uploading…"; $("#wizmsg").textContent = wiz.msg;
      try { const r = await upload("resume", f); wiz.resume = r; set("base_resumes", { default: r.path }); wiz.filled = applyProfile(r.profile || {}); wiz.msg = ""; }
      catch (err) { wiz.msg = err.message; } render();
    });
    $("#w_cover").addEventListener("change", async e => {
      const f = e.target.files[0]; if (!f) return;
      try { const r = await upload("cover_letter", f); wiz.cover = r; set("cover_letter_file", r.path); wiz.msg = ""; }
      catch (err) { wiz.msg = err.message; } render();
    });
  }
};

document.addEventListener("change", e => {
  if (!state.wizard) return;
  const t = e.target;
  if (t.name === "w_field") { set("field", t.value); generateSearch(); render(); }
  if (t.name === "w_level") { set("experience_level", t.value); generateSearch(); render(); }
  if (t.name === "w_km") { set("locations.max_commute_km", +t.value); render(); }
  if (t.name === "w_freq") {
    const days = t.value.split(","); set("schedule", { ...(get("schedule") || {}), days });
    const info = scheduleInfo(); set("search_window_days", Math.max(1, info.maxGap));
    set("max_new_jobs_per_run", days.length >= 5 ? 8 : days.length >= 3 ? 12 : 15); render();
  }
  if (t.dataset && t.dataset.site) { t.checked ? wiz.picked.add(t.dataset.site) : wiz.picked.delete(t.dataset.site); }
});
document.addEventListener("click", async e => {
  const b = e.target.closest && e.target.closest("[data-wiz]"); if (!b || !state.wizard) return;
  e.preventDefault(); const a = b.dataset.wiz;
  try {
    if (a === "back") { wiz.step--; wiz.msg = ""; return render(); }
    if (a === "skip") { set("setup_complete", true); state.wizard = false; document.body.classList.remove("wizard"); await api("/api/config", { config: state.cfg }).then(r => { if (!r.problems) { state.saved = JSON.stringify(state.cfg); state.exists = true; } }); return go("home"); }
    if (a === "builder") { return openBuilderFromSetup(); }
    if (a === "sample") { set("base_resumes", { default: "examples/sample-resume.docx" }); wiz.sample = true; wiz.step++; wiz.msg = ""; return render(); }
    if (a === "nocover") { set("cover_letter_file", ""); wiz.cover = null; return render(); }
    if (a === "reread" && wiz.resume) { const r = await api("/api/resume/inspect", { path: wiz.resume.path, heading: get("skills_heading") || "" }); wiz.resume = { ...wiz.resume, ...r }; return render(); }
    if (a === "next") {
      const problem = validateStep(); if (problem) { wiz.msg = problem; return render(); }
      if (at("work") && !get("search_location")) set("search_location", get("country") || "");
      if (at("sites")) applySites();
      if (at("schedule")) { const info = scheduleInfo(); if ((get("search_window_days") || 0) < info.maxGap) set("search_window_days", info.maxGap); }
      if (wiz.step === STEPS.length - 1) return await finish();
      wiz.step++; wiz.msg = ""; render(); window.scrollTo(0, 0);
    }
  } catch (err) { wiz.msg = err.message; render(); }
});

function startSetup() {
  // Example values ("Your Name", "you@example.com"…) look like real data in the form: start those fields empty.
  const cand = { ...(get("candidate") || {}) };
  Object.keys(cand).forEach(k => { if (PLACEHOLDER.test(String(cand[k]))) cand[k] = ""; });
  state.cfg.candidate = cand;
  if (PLACEHOLDER.test(String(get("resume_output_name") || ""))) state.cfg.resume_output_name = "";
  state.wizard = true; wiz.step = 0; wiz.picked = null; state.tab = "setup"; render(); }

// AI suggestions while filling the settings (only shown when an AI is set up). Results are suggestions to check.
document.addEventListener("click", async e => {
  const b = e.target.closest && e.target.closest("[data-sug]"); if (!b || !state.wizard) return;
  e.preventDefault(); const kind = b.dataset.sug; b.disabled = true; const label = b.textContent; b.textContent = "Asking the AI…";
  try {
    const r = await api("/api/ai/suggest", { kind, country: get("country") || "", field: (FIELDS[get("field")] || FIELDS.other).label,
      level: (LEVELS[get("experience_level")] || {}).label || "", roles: get("target_roles") || [] });
    if (!r.ok) { wiz.msg = r.error; return render(); }
    if (kind === "terms") set("search_terms_local", [...new Set([...(get("search_terms_local") || []), ...r.terms])]);
    if (kind === "tips") wiz.tips = r.text;
    if (kind === "sites") r.sites.forEach(s => {
      const id = s.domain.replace(/[^a-z0-9]+/g, "-").slice(0, 40).replace(/^-|-$/g, "");
      if (!PRESETS.some(p => p.id === id)) PRESETS.push({ id, name: s.name, needs_signin: s.needs_signin,
        search: `${s.domain} search: {query}, {location}, newest first.`, apply: "The site's apply button or the company site.",
        notes: `Suggested by AI for ${get("country")}: ${s.notes} Verify on the first run.` });
    });
    wiz.msg = "";
  } catch (err) { wiz.msg = err.message; } finally { b.disabled = false; b.textContent = label; }
  render();
});
