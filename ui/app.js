const TABS = [
  ["home", "Home"], ["profile", "Profile"], ["search", "Job search"], ["sources", "Sites"], ["resumes", "Resumes"], ["builder", "Resume builder"],
  ["answers", "Applying"], ["ai", "AI"], ["automate", "Schedule"], ["apps", "Applications"], ["manual", "Apply by hand"], ["prepare", "Prepare"], ["runs", "Run reports"],
];
const CONFIG_TABS = new Set(["profile", "search", "sources", "resumes", "answers", "automate"]);
const DAYS = [["sun", "Sun"], ["mon", "Mon"], ["tue", "Tue"], ["wed", "Wed"], ["thu", "Thu"], ["fri", "Fri"], ["sat", "Sat"]];
const JOB_TYPES = [["full_time", "Full-time"], ["part_time", "Part-time"], ["student", "Student positions"],
  ["internship", "Internships"], ["contract", "Contract"], ["freelance", "Freelance"]];
const APPLY_METHODS = [["easy_apply", "Quick apply on job sites (LinkedIn Easy Apply, Indeed, Glassdoor)"],
  ["job_board_send_cv", "Send-CV buttons on job boards"], ["ats_forms", "Company application forms (Comeet, Greenhouse, Lever…)"],
  ["email", "Email the resume from your mailbox"], ["social_dm", "Message the poster on Facebook / LinkedIn"]];
// Ready-made sites for "Add site". {query} {location} {days} {seconds} are filled in by the agent.
const PRESETS = [
  { id: "linkedin", name: "LinkedIn Jobs", needs_signin: true, search: "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&f_TPR=r{seconds}&f_E=1%2C2", apply: "Easy Apply, or the external link to the company site.", notes: "f_E=1,2 = internship + entry level. Work at a human pace." },
  { id: "indeed", name: "Indeed", needs_signin: false, search: "https://www.indeed.com/jobs?q={query}&l={location}&fromage={days}", apply: "Indeed Apply, or the company site.", notes: "Use your country's Indeed domain (e.g. il.indeed.com, uk.indeed.com)." },
  { id: "glassdoor", name: "Glassdoor", needs_signin: true, search: "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}&fromAge={days}", apply: "Easy Apply on Glassdoor when the job has it; otherwise apply on the company site.", notes: "Set your location once in Glassdoor's filter. Skip the run if a bot check appears." },
  { id: "wellfound", name: "Wellfound (startups)", needs_signin: true, search: "https://wellfound.com/jobs", apply: "Company ATS form, or skip if it needs an account.", notes: "" },
  { id: "builtin", name: "Built In", needs_signin: false, search: "https://builtin.com/jobs (filter: entry level)", apply: "Company ATS form.", notes: "" },
  { id: "welcome-to-the-jungle", name: "Welcome to the Jungle", needs_signin: false, search: "https://www.welcometothejungle.com/en/jobs?query={query}", apply: "Company form.", notes: "" },
  { id: "remoteok", name: "Remote OK", needs_signin: false, search: "https://remoteok.com/remote-{query}-jobs", apply: "The link in the post.", notes: "Remote jobs only." },
  { id: "weworkremotely", name: "We Work Remotely", needs_signin: false, search: "https://weworkremotely.com/remote-jobs/search?term={query}", apply: "The link in the post.", notes: "Remote jobs only." },
  { id: "hn-whos-hiring", name: "Hacker News: Who is hiring", needs_signin: false, search: "The latest 'Ask HN: Who is hiring?' thread on news.ycombinator.com; look for junior / entry-level posts in {location} or remote.", apply: "Email or link in the comment.", notes: "Monthly thread." },
  { id: "company-ats", name: "Company career pages (ATS)", needs_signin: false, search: "Web search: site:job-boards.greenhouse.io {query} {location} / site:jobs.lever.co {query} / site:jobs.ashbyhq.com {query} / site:comeet.com {query}", apply: "The company's form (never create an account).", notes: "" },
  { id: "gemini", name: "Gemini (Google search)", needs_signin: false, search: "Ask the Gemini tool to Google junior postings for {query} in {location} from the last {days} days; return company, title, location, URL, date only. Search terms only, never personal details.", apply: "Discovery only: open every link and apply at the original source.", notes: "Needs the Gemini CLI MCP server." },
  { id: "alljobs", name: "AllJobs (Israel)", needs_signin: true, search: "alljobs.co.il search box, newest first.", apply: "The site's send-CV button.", notes: "" },
  { id: "drushim", name: "Drushim (Israel)", needs_signin: true, search: "drushim.co.il search, newest first.", apply: "The site's send-CV button.", notes: "" },
  { id: "jobmaster", name: "JobMaster (Israel)", needs_signin: true, search: "jobmaster.co.il search.", apply: "The site's send-CV button.", notes: "" },
  { id: "misrotech", name: "MisroTech (Israel)", needs_signin: false, search: "https://misrotech.com/en/r/fullstack/junior", apply: "Follow the link to the company page.", notes: "Collects company career pages." },
  { id: "facebook-groups", name: "Facebook groups", needs_signin: true, search: "Recent posts in job groups you are already a member of.", apply: "Usually by email from the post.", notes: "Never joins, comments or posts." },
  { id: "telegram", name: "Telegram channel", needs_signin: false, search: "https://t.me/s/<channel-name>", apply: "The link or email in the post.", notes: "Replace <channel-name>." },
];
const LAYOUT_OPTIONS = [
  ["company_role", "Company › role", "applications/Acme/Junior DevOps Engineer/2026-03-01/", "Recommended: everything you sent one company in one place."],
  ["field_company_role", "Field › company › role", "applications/devops/Acme/Junior DevOps Engineer/2026-03-01/", "If you apply in more than one field."],
  ["role_company", "Role › company", "applications/Junior DevOps Engineer/Acme/2026-03-01/", "Compare how you applied to the same kind of role."],
  ["date_company_role", "One folder per job, by date", "applications/2026-03-01_Acme_Junior DevOps Engineer/", "Simple chronological list."],
];
function tailoringCard() {
  const rt = get("resume_tailoring") || { enabled: true, folder_layout: "company_role" };
  return `<div class="card"><h3>Tailoring per job</h3>
    ${field("resume_tailoring.enabled", "Tailor my resume for each job (reorder the skills to match the posting)", { type: "bool" })}
    <div class="hint" style="margin:-2px 0 10px">Off: the agent sends your resume as it is. It never adds skills or changes other text either way.</div>
    <label>Where each job's files are saved</label>
    <div class="opts" style="grid-template-columns:1fr">${LAYOUT_OPTIONS.map(([k, l, ex, why]) => `<label class="opt ${rt.folder_layout === k ? "on" : ""}">
      <input type="radio" name="layout" value="${k}" ${rt.folder_layout === k ? "checked" : ""}> <span><b>${l}</b> <span class="sub">${why}</span><br><code class="sub">${esc(ex)}</code></span></label>`).join("")}</div></div>`;
}
function reapplyCard() {
  const g = get("ghost_jobs") || {};
  return `<div class="card"><h3>Re-applying and ghost jobs</h3><div class="grid">
    ${field("dedup_days", "Don't apply to the same job again for (days)", { type: "int", hint: "After this, a job that is still posted may be offered again. 60–90 is common." })}
    ${field("pending_days", "Offer jobs you didn't answer again after (days)", { type: "int" })}
    </div>
    <div style="margin-top:10px">${field("ghost_jobs.ask_when_reposted", "Ask me whether a job that keeps being reposted is a ghost job (posted for show, not really hiring)", { type: "bool" })}</div>
    <div class="grid" style="margin-top:6px">
      ${field("ghost_jobs.repost_times", "Ask after it was posted this many times", { type: "int" })}
      <div><label for="ghostBlock">When I mark a job as fake, skip</label><select id="ghostBlock" data-path="ghost_jobs.block" data-kind="str">
        <option value="role" ${g.block !== "company" ? "selected" : ""}>That job only</option><option value="company" ${g.block === "company" ? "selected" : ""}>Everything from that company</option></select></div>
    </div>
    <div class="hint">Marked jobs get the status <i>ghost</i> in Applications and are never offered again. You can also set it there yourself.</div></div>`;
}
document.addEventListener("change", e => {
  if (e.target.name === "layout") { set("resume_tailoring", { ...(get("resume_tailoring") || { enabled: true }), folder_layout: e.target.value }); render(); }
});

let state = { tab: "home", cfg: null, saved: null, exists: false, folder: "", apps: [], statuses: [], filter: "all", q: "" };

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const lines = a => (a || []).join("\n");
const unlines = s => s.split("\n").map(x => x.trim()).filter(Boolean);
const dirty = () => JSON.stringify(state.cfg) !== state.saved;

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({ error: "Bad response from the server." }));
  if (!r.ok && !data.problems) throw new Error(data.error || r.statusText);
  return data;
}
function toast(t) { const el = $("#toast"); el.textContent = t; el.classList.add("show"); setTimeout(() => el.classList.remove("show"), 2200); }
function updateSavebar() { $("#savebar").classList.toggle("show", !state.wizard && !state.builderReturn && (dirty() || !state.exists)); $("#savestate").textContent = state.exists ? "Unsaved changes" : "Settings not saved yet"; }

function renderNav() {
  const counts = { apps: state.apps.length };
  $("#nav").innerHTML = TABS.map(([id, name]) =>
    `<button data-tab="${id}" class="${state.tab === id ? "active" : ""}">${name}${counts[id] ? `<span class="n">${counts[id]}</span>` : ""}</button>`).join("");
}
$("#nav").addEventListener("click", e => { const b = e.target.closest("button"); if (b) go(b.dataset.tab); });
function go(tab) { if (state.wizard) return; state.tab = tab; try { localStorage.setItem("tab", tab); } catch (e) {} history.replaceState(null, "", "#" + tab); render(); }

// ---------- generic form binding ----------
function get(path) { return path.split(".").reduce((o, k) => (o ?? {})[k], state.cfg); }
function set(path, val) {
  const ks = path.split("."); let o = state.cfg;
  ks.slice(0, -1).forEach(k => { if (typeof o[k] !== "object" || o[k] === null) o[k] = {}; o = o[k]; });
  o[ks.at(-1)] = val; updateSavebar();
}
function field(path, label, opts = {}) {
  const v = get(path); const id = "f_" + path.replace(/\W/g, "_");
  if (opts.type === "lines") return `<div><label for="${id}">${label}</label><textarea id="${id}" data-path="${path}" data-kind="lines">${esc(lines(v))}</textarea>${opts.hint ? `<div class="hint">${opts.hint}</div>` : ""}</div>`;
  if (opts.type === "bool") return `<label class="check"><input type="checkbox" data-path="${path}" data-kind="bool" ${v ? "checked" : ""}> ${label}</label>`;
  if (opts.type === "text") return `<div><label for="${id}">${label}</label><textarea id="${id}" data-path="${path}" data-kind="str">${esc(v)}</textarea>${opts.hint ? `<div class="hint">${opts.hint}</div>` : ""}</div>`;
  const t = opts.type === "int" ? "number" : "text";
  return `<div><label for="${id}">${label}</label><input id="${id}" type="${t}" ${opts.type === "int" ? 'min="0" step="1"' : ""} data-path="${path}" data-kind="${opts.type || "str"}" value="${esc(v)}" placeholder="${esc(opts.ph || "")}">${opts.hint ? `<div class="hint">${opts.hint}</div>` : ""}</div>`;
}
document.addEventListener("input", e => {
  const el = e.target; if (!el.dataset || !el.dataset.path) return;
  const k = el.dataset.kind;
  set(el.dataset.path, k === "lines" ? unlines(el.value) : k === "bool" ? el.checked : k === "int" ? (el.value === "" ? 0 : parseInt(el.value, 10)) : el.value);
});
document.addEventListener("change", e => { if (e.target.dataset && e.target.dataset.kind === "bool") set(e.target.dataset.path, e.target.checked); });

// ---------- key/value editors (resumes, screening answers, cover notes) ----------
function kvEditor(objPath, keyLabel, valLabel, opts = {}) {
  const obj = get(objPath) || {};
  const rows = Object.entries(obj).filter(([k]) => !k.startsWith("_"));
  return `<div data-kv="${objPath}">
    <div class="kv sub"><span>${keyLabel}</span><span>${valLabel}</span><span></span></div>
    ${rows.map(([k, v], i) => `<div class="kv">
      <input type="text" data-kvkey="${i}" value="${esc(k)}" aria-label="${keyLabel}">
      ${opts.multiline ? `<textarea data-kvval="${i}" aria-label="${valLabel}">${esc(v)}</textarea>` : `<input type="text" data-kvval="${i}" value="${esc(v)}" aria-label="${valLabel}" placeholder="${esc(opts.ph || "")}">`}
      <button class="icon-btn" data-kvdel="${i}" title="Remove">×</button></div>`).join("")}
    <button class="btn" data-kvadd>+ Add</button></div>`;
}
function readKv(box) {
  const path = box.dataset.kv; const old = get(path) || {};
  const out = {}; Object.entries(old).filter(([k]) => k.startsWith("_")).forEach(([k, v]) => out[k] = v);
  box.querySelectorAll("[data-kvkey]").forEach(inp => {
    const i = inp.dataset.kvkey; const key = inp.value.trim(); const val = box.querySelector(`[data-kvval="${i}"]`).value;
    if (key) out[key] = val;
  });
  set(path, out);
}
document.addEventListener("input", e => { const box = e.target.closest && e.target.closest("[data-kv]"); if (box && (e.target.dataset.kvkey !== undefined || e.target.dataset.kvval !== undefined)) readKv(box); });
document.addEventListener("click", e => {
  const box = e.target.closest && e.target.closest("[data-kv]"); if (!box) return;
  if (e.target.dataset.kvdel !== undefined) { e.target.closest(".kv").remove(); readKv(box); render(); }
  if (e.target.dataset.kvadd !== undefined) { const path = box.dataset.kv; const o = { ...(get(path) || {}) }; let n = "new"; let i = 1; while (n in o) n = "new" + ++i; o[n] = ""; set(path, o); render(); }
});

// ---------- pages ----------
const pages = {};

pages.home = async () => {
  $("#main").innerHTML = `<h2>Welcome</h2><p class="lead">This agent searches job boards on a schedule, tailors your resume to each job and sends applications only after you approve them. Set it up once, top to bottom.</p>
    <div class="stats" id="stats"></div><div style="height:16px"></div>
    <div class="card health"><h3>Setup checklist</h3><ul id="health"><li><span></span><span class="sub">Checking… (the Word check can take a few seconds)</span></li></ul></div>`;
  const s = { prepared: 0, sent: 0, manual: 0, failed: 0 }; state.apps.forEach(r => { if (r.status in s) s[r.status]++; });
  $("#stats").innerHTML = [["sent", "Sent"], ["prepared", "Waiting for approval"], ["manual", "Need you"], ["failed", "Failed"]]
    .map(([k, l]) => `<div class="stat"><b>${s[k]}</b><span>${l}</span></div>`).join("");
  const { items } = await api("/api/health");
  const goTo = { config: "profile", profile: "profile", resumes: "resumes", sites: "sources" };
  $("#health").innerHTML = items.map(it => {
    const cls = it.ok === true ? (it.warn ? "warn" : "ok") : it.ok === null ? "na" : "bad";
    const mark = it.ok === true ? (it.warn ? "!" : "✓") : it.ok === null ? "–" : "✕";
    const fix = it.ok === true ? (it.warn || "") : it.fix;
    return `<li><span class="dot ${cls}">${mark}</span><div><b>${esc(it.label)}</b>${it.detail ? ` <span class="sub">· ${esc(it.detail)}</span>` : ""}
      ${fix ? `<div class="sub">${esc(fix)}${goTo[it.key] && it.ok !== true ? ` <a href="#" data-go="${goTo[it.key]}">Open</a>` : ""}${it.warn ? ` <a href="#" data-go="resumes">Open</a>` : ""}</div>` : ""}</div></li>`;
  }).join("") + `<li><span class="dot na">→</span><div><b>Schedule it</b><div class="sub">When everything above is green, set up the automatic runs. <a href="#" data-go="automate">Open</a></div></div></li>`;
  $("#main").insertAdjacentHTML("beforeend", `<p class="sub">Want to start over? <a href="#" id="rerunSetup">Run the setup wizard again</a> (your current settings are the starting point).</p>`);
  $("#rerunSetup").addEventListener("click", e => { e.preventDefault(); startSetup(); });
};
document.addEventListener("click", e => { const a = e.target.closest && e.target.closest("[data-go]"); if (a) { e.preventDefault(); go(a.dataset.go); } });

pages.profile = () => {
  $("#main").innerHTML = `<h2>Profile</h2><p class="lead">Used to fill in application forms and emails. Stays on this computer in <code>config.json</code>.</p>
  <div class="card"><h3>Contact details</h3><div class="grid">
    ${field("candidate.full_name", "Full name")}${field("candidate.email", "Email")}${field("candidate.phone", "Phone", { ph: "+972 50-000-0000" })}
    ${field("candidate.city", "City", { ph: "Tel Aviv, Israel" })}${field("candidate.linkedin", "LinkedIn URL")}${field("candidate.github", "GitHub URL")}
  </div></div>
  <div class="card"><h3>Reports</h3><div class="grid">${field("report_language", "Language of the run reports", { ph: "English", hint: "Any language, e.g. English or Hebrew." })}</div></div>`;
};

pages.search = () => {
  $("#main").innerHTML = `<h2>Job search</h2><p class="lead">What to look for and what to skip. One item per line. Why these settings: <a href="https://github.com/DorEydan/job-hunt-agent/blob/main/docs/JOB_SEARCH_GUIDE.md" target="_blank" rel="noopener noreferrer">job search guide</a>.</p>
  <div class="card"><h3>Roles and search terms</h3><div class="grid">
    ${field("target_roles", "Target roles", { type: "lines" })}
    ${field("search_terms_en", "Search terms (English)", { type: "lines" })}
    ${field("search_terms_local", "Search terms (local language)", { type: "lines", hint: "Optional. Same idea in the local language, e.g. Hebrew." })}
  </div></div>
  <div class="card"><h3>Seniority</h3><div class="grid">
    ${field("seniority.max_years_required", "Max years of experience a job may ask for", { type: "int" })}
    ${field("seniority.exclude_title_words", "Skip titles containing", { type: "lines" })}
    <div>${field("seniority.include_student_positions", "Include student positions", { type: "bool" })}</div>
  </div></div>
  <div class="card"><h3>Job types</h3><div class="grid">
    <div>${JOB_TYPES.slice(0, 3).map(([k, l]) => field("job_types." + k, l, { type: "bool" })).join("")}</div>
    <div>${JOB_TYPES.slice(3).map(([k, l]) => field("job_types." + k, l, { type: "bool" })).join("")}</div>
  </div></div>
  <div class="card"><h3>Keywords and companies</h3><div class="grid">
    ${field("must_have_keywords", "Must mention at least one of", { type: "lines", hint: "Optional. Empty = no requirement. E.g. React, Python." })}
    ${field("exclude_keywords", "Skip jobs that mention", { type: "lines", hint: "E.g. security clearance, night shifts." })}
    ${field("exclude_companies", "Never apply to these companies", { type: "lines", hint: "E.g. your current employer." })}
  </div></div>
  <div class="card"><h3>Location</h3><div class="grid">
    ${field("search_location", "Search location", { ph: "Israel", hint: "Used in site searches ({location})." })}
    ${field("locations.preferred", "Preferred cities", { type: "lines" })}
    <div>${field("locations.accept_remote", "Remote jobs are OK", { type: "bool" })}${field("locations.accept_hybrid", "Hybrid jobs are OK", { type: "bool" })}</div>
  </div></div>
  <div class="card"><h3>Limits</h3><div class="grid">
    ${field("search_window_days", "Look at postings from the last (days)", { type: "int", hint: "Match it to the longest gap between runs (see Schedule)." })}
    ${field("max_new_jobs_per_run", "Max new jobs per run", { type: "int" })}
    ${field("min_match_score", "Minimum match score (1–10)", { type: "int" })}
  </div></div>`;
};

pages.resumes = () => {
  const variants = Object.keys(get("base_resumes") || {}).filter(k => !k.startsWith("_"));
  $("#main").innerHTML = `<h2>Resumes</h2><p class="lead">Your resume as a Word <code>.docx</code>. The agent only reorders the skills under the skills heading for each job, then exports a small PDF.</p>
  <div class="card"><h3>Need a new resume or a new design?</h3><p class="sub" style="margin:0">The <a href="#" data-go="builder">Resume builder</a> makes a clean one-page resume in a template that fits your field, from scratch or from your current one.</p></div>
  <div class="card"><h3>Resume versions</h3>
    <p class="sub" style="margin-top:-6px">One version is enough. Add more if you target different job types (e.g. <i>devops</i> and <i>fullstack</i>).</p>
    ${kvEditor("base_resumes", "Version name", "Path to the .docx file", { ph: "C:\\Users\\you\\Documents\\resume.docx" })}
    <div style="margin-top:12px">${field("_base_resumes_note", "Which jobs each version is for", { type: "text", hint: "The agent reads this to pick a version, e.g. “DevOps / Cloud jobs → devops. Developer jobs → fullstack.”" })}</div>
  </div>
  ${tailoringCard()}
  <div class="card"><h3>Format</h3><div class="grid">
    ${field("skills_heading", "Skills heading in your resume", { ph: "Technical Skills", hint: "Under it, one line per group: <code>Label: skill, skill, skill</code>" })}
    ${field("resume_output_name", "Name of the PDF that gets sent", { ph: "Jane Doe resume" })}
  </div></div>
  <div class="card"><h3>Check a version</h3>
    ${variants.length ? `<div class="row"><select id="variant" style="max-width:220px">${variants.map(v => `<option>${esc(v)}</option>`).join("")}</select>
      <button class="btn" id="readSkills">Read skills</button><button class="btn primary" id="testPdf">Test PDF export</button></div>
      <div id="resumeOut" class="msg"></div>` : `<p class="sub">Add a resume version above and save.</p>`}
  </div>`;
  const out = () => $("#resumeOut");
  $("#readSkills")?.addEventListener("click", async () => {
    if (dirty()) return (out().className = "msg warn", out().textContent = "Save your settings first.");
    out().className = "msg"; out().textContent = "Reading…";
    const r = await api("/api/resume/skills?variant=" + encodeURIComponent($("#variant").value));
    if (!r.ok) { out().className = "msg bad"; out().textContent = r.error; return; }
    out().innerHTML = `<ul class="skills">${Object.entries(r.skills).map(([k, v]) => `<li><b>${esc(k)}:</b> ${esc(v.join(", "))}</li>`).join("")}</ul><div class="sub">These are the lines the agent may reorder. Nothing else in the resume changes.</div>`;
  });
  $("#testPdf")?.addEventListener("click", async e => {
    if (dirty()) return (out().className = "msg warn", out().textContent = "Save your settings first.");
    const b = e.target; b.disabled = true; out().className = "msg"; out().textContent = "Exporting with Word… (10–30 seconds)";
    try {
      const v = $("#variant").value; const r = await api("/api/resume/test", { variant: v });
      if (!r.ok) { out().className = "msg bad"; out().textContent = r.error; return; }
      out().className = "msg " + (r.warning ? "warn" : "ok");
      out().innerHTML = `PDF ready: ${r.pdf_mb} MB. ${r.warning ? esc(r.warning) : "Small enough for any upload form."} <a href="/api/resume/preview.pdf?variant=${encodeURIComponent(v)}" target="_blank" rel="noopener">Open the PDF</a>`;
    } catch (err) { out().className = "msg bad"; out().textContent = err.message; } finally { b.disabled = false; }
  });
};

pages.answers = () => {
  $("#main").innerHTML = `<h2>Applying</h2><p class="lead">How the agent may apply, and what it answers on forms. It answers only from here; if an answer is missing, it asks you instead of guessing.</p>
  <div class="card"><h3>Allowed ways to apply</h3>
    ${APPLY_METHODS.map(([k, l]) => field("apply_methods." + k, l, { type: "bool" })).join("")}
    <div class="hint">Jobs that can only be applied to in a way you switched off are listed for you to apply yourself.</div>
  </div>
  ${reapplyCard()}
  <div class="card"><h3>Options</h3>
    ${field("cover_note_in_forms", "Paste the cover note into optional cover-letter fields", { type: "bool" })}
    ${field("notifications", "Notify me when a run finds jobs", { type: "bool" })}
    <div class="check sub"><span class="dot ok" style="width:16px;height:16px;font-size:10px">✓</span> Always on: nothing is sent until you approve it in the chat.</div>
  </div>
  <div class="card"><h3>Screening answers</h3>
    ${kvEditor("screening_answers", "Question (short key)", "Your answer", { ph: "e.g. 30 days" })}
    <div class="hint">Examples: <i>notice_period</i>, <i>salary_expectation</i>, <i>authorized_to_work</i>, <i>years_experience</i>, <i>willing_to_relocate</i>. Empty = the agent will ask you.</div>
  </div>
  <div class="card"><h3>Cover notes</h3><p class="sub" style="margin-top:-6px">How to write them: <a href="https://github.com/DorEydan/job-hunt-agent/blob/main/docs/COVER_LETTER_GUIDE.md" target="_blank" rel="noopener noreferrer">cover letter guide</a>.</p>
    ${kvEditor("cover_note", "Language", "Text", { multiline: true })}
    <div class="hint">Used as the email body. Placeholders: <code>{role}</code>, <code>{top_skills}</code>, <code>{phone}</code>, <code>{full_name}</code>. Language keys like <i>en</i>, <i>he</i>.</div>
  </div>`;
};

pages.apps = async () => {
  const d = await api("/api/applications"); state.apps = d.rows; state.statuses = d.statuses; renderNav();
  const draw = () => {
    const q = state.q.toLowerCase();
    const rows = state.apps.filter(r => (state.filter === "all" || r.status === state.filter) && (!q || (r.company + " " + r.role + " " + r.source).toLowerCase().includes(q)))
      .sort((a, b) => (+b.id) - (+a.id));
    $("#appsTable").innerHTML = rows.length ? `<table><thead><tr><th>#</th><th>Company</th><th>Role</th><th>Status</th><th>Found</th><th>Sent</th><th>Score</th><th>Source</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td class="num">${esc(r.id)}</td><td>${esc(r.company)}</td>
        <td>${r.job_url && /^https?:\/\//.test(r.job_url) ? `<a href="${esc(r.job_url)}" target="_blank" rel="noopener noreferrer">${esc(r.role)}</a>` : esc(r.role)}${r.notes ? `<div class="sub">${esc(r.notes)}</div>` : ""}</td>
        <td><select data-status="${esc(r.id)}" aria-label="Status">${state.statuses.map(s => `<option ${s === r.status ? "selected" : ""}>${s}</option>`).join("")}</select></td>
        <td class="num">${esc(r.date_found)}</td><td class="num">${esc(r.date_sent || "–")}</td><td class="num">${esc(r.match_score)}</td><td>${esc(r.source)}</td></tr>`).join("")}
      </tbody></table>` : `<div class="empty">${state.apps.length ? "Nothing matches the filter." : "No applications yet. They appear here after the first run."}</div>`;
  };
  const counts = {}; state.apps.forEach(r => counts[r.status] = (counts[r.status] || 0) + 1);
  $("#main").innerHTML = `<h2>Applications</h2><p class="lead">Everything the agent prepared or sent. Change a status here if you applied yourself (e.g. after solving a CAPTCHA).</p>
    <div class="card"><div class="row" style="margin-bottom:12px">
      <select id="filter" style="max-width:200px"><option value="all">All (${state.apps.length})</option>${state.statuses.map(s => `<option value="${s}" ${state.filter === s ? "selected" : ""}>${s} (${counts[s] || 0})</option>`).join("")}</select>
      <input type="text" id="q" placeholder="Search company or role" style="max-width:280px" value="${esc(state.q)}">
    </div><div class="tablewrap" id="appsTable"></div></div>`;
  $("#filter").value = state.filter;
  $("#filter").addEventListener("change", e => { state.filter = e.target.value; draw(); });
  $("#q").addEventListener("input", e => { state.q = e.target.value; draw(); });
  $("#appsTable").addEventListener("change", async e => {
    const sel = e.target.closest("[data-status]"); if (!sel) return;
    try { const r = await api("/api/applications/status", { id: sel.dataset.status, status: sel.value, note: "changed in the control panel" });
      toast(sel.value === "interview" ? "Good luck! The Prepare tab can make an interview prep." : (r.message || "Saved"));
      const row = state.apps.find(x => x.id === sel.dataset.status); if (row) row.status = sel.value;
    } catch (err) { toast(err.message); }
  });
  draw();
};

function md(text) {  // tiny, safe Markdown renderer for run reports (escapes first)
  const inline = s => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  const out = []; const ls = text.split("\n"); let i = 0;
  while (i < ls.length) {
    const l = ls[i];
    if (/^\|/.test(l)) { const t = []; while (i < ls.length && /^\|/.test(ls[i])) t.push(ls[i++]);
      const cells = r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const body = t.filter(r => !/^\|[\s:|-]+\|$/.test(r));
      out.push(`<div class="tablewrap"><table><thead><tr>${cells(body[0]).map(c => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body.slice(1).map(r => `<tr>${cells(r).map(c => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`); continue; }
    if (/^\s*[-*] /.test(l)) { const it = []; while (i < ls.length && /^\s*[-*] /.test(ls[i])) it.push(ls[i++].replace(/^\s*[-*] /, ""));
      out.push(`<ul>${it.map(x => `<li>${inline(x)}</li>`).join("")}</ul>`); continue; }
    const h = l.match(/^(#{1,4}) (.*)/); if (h) { out.push(`<h${h[1].length + 1}>${inline(h[2])}</h${h[1].length + 1}>`); i++; continue; }
    if (l.trim()) out.push(`<p>${inline(l)}</p>`); i++;
  }
  return out.join("");
}
pages.runs = async () => {
  const { runs } = await api("/api/runs");
  $("#main").innerHTML = `<h2>Run reports</h2><p class="lead">One report per run: what was found, what needs you, which sources failed.</p>
    ${runs.length ? `<div class="row" style="margin-bottom:12px"><select id="run" style="max-width:240px">${runs.map(r => `<option>${esc(r)}</option>`).join("")}</select></div><div class="card report" id="report"></div>`
      : `<div class="card empty">No runs yet. After the first run, its report shows up here.</div>`}`;
  const show = async n => { const r = await api("/api/runs/" + encodeURIComponent(n)); $("#report").innerHTML = md(r.text); };
  if (runs.length) { $("#run").addEventListener("change", e => show(e.target.value)); show(runs[0]); }
};

function scheduleInfo() {  // mirrors schedule_info() in server.py
  const sch = get("schedule") || {};
  const days = DAYS.map(d => d[0]).filter(d => (sch.days || []).includes(d));
  const time = /^([01]\d|2[0-3]):[0-5]\d$/.test(sch.time || "") ? sch.time : "09:00";
  const idx = days.map(d => DAYS.findIndex(x => x[0] === d));
  const gaps = idx.map((v, i) => ((idx[(i + 1) % idx.length] - v + 7) % 7) || 7);
  const [hh, mm] = time.split(":").map(Number);
  return { days, time, cron: `${mm} ${hh} * * ${idx.join(",")}`, maxGap: gaps.length ? Math.max(...gaps) : 0 };
}

pages.automate = async () => {
  const s = await api("/api/schedule");
  const draw = () => {
    const info = scheduleInfo(); const sch = get("schedule") || {};
    const names = info.days.map(d => DAYS.find(x => x[0] === d)[1]).join(", ");
    const win = get("search_window_days");
    $("#schedOut").innerHTML = info.days.length ? `
      <p class="sub">Runs <b>${esc(names)}</b> at <b>${esc(info.time)}</b> · cron <code>${esc(info.cron)}</code>
      ${win < info.maxGap ? `<br><span class="msg warn">The longest gap between runs is ${info.maxGap} days, but searches look back only ${win}. <a href="#" id="fixWin">Set it to ${info.maxGap}</a></span>` : ""}</p>
      <p class="sub" style="margin-top:14px">New schedule: paste in your agent tool (Claude Code, Codex, Gemini CLI…)</p>
      <pre class="prompt" id="sched">Create a scheduled task named "job-hunt-agent" that runs at cron "${esc(info.cron)}" with this prompt: ${esc(s.prompt)}</pre>
      <button class="btn" data-copy="sched">Copy</button>
      <p class="sub" style="margin-top:14px">Already scheduled? Paste this to change it</p>
      <pre class="prompt" id="resched">Update the scheduled task "job-hunt-agent" to run at cron "${esc(info.cron)}".</pre>
      <button class="btn" data-copy="resched">Copy</button>`
      : `<p class="msg warn">Pick at least one day.</p>`;
    $("#fixWin")?.addEventListener("click", e => { e.preventDefault(); set("search_window_days", info.maxGap); draw(); });
  };
  const sch = get("schedule") || {};
  $("#main").innerHTML = `<h2>Schedule</h2><p class="lead">The automatic agent runs in an agent tool that follows <code>AGENTS.md</code> (Claude Code, OpenAI Codex, Gemini CLI, Cursor…). Sending always waits for your approval. No agent tool? Use <a href="#" data-go="manual">Apply by hand</a>.</p>
  <div class="card"><h3>When to search</h3>
    <div class="row" id="dayPick">${DAYS.map(([k, l]) => `<label class="daychip"><input type="checkbox" value="${k}" ${(sch.days || []).includes(k) ? "checked" : ""}> ${l}</label>`).join("")}</div>
    <div class="row" style="margin-top:12px"><label for="schedTime" style="margin:0">Time</label>
      <input type="time" id="schedTime" value="${esc(sch.time || "09:00")}" style="max-width:140px">
      <span class="sub">Presets:</span>
      <button class="btn" data-preset="sun,tue,thu">3× a week</button><button class="btn" data-preset="mon,thu">2× a week</button>
      <button class="btn" data-preset="sun,mon,tue,wed,thu">Workdays (Sun–Thu)</button><button class="btn" data-preset="mon,tue,wed,thu,fri">Workdays (Mon–Fri)</button>
      <button class="btn" data-preset="sun,mon,tue,wed,thu,fri,sat">Daily</button></div>
    <div id="schedOut" style="margin-top:12px"></div>
  </div>
  <div class="card"><h3>Try one run now</h3><p class="sub">Open your agent tool in this folder and paste:</p>
    <pre class="prompt" id="prompt">${esc(s.prompt)}</pre><button class="btn" data-copy="prompt">Copy</button></div>
  <div class="card"><h3>Before each run</h3><ol class="steps">
    <li><b>Computer on</b> and the Claude app open at the scheduled time.</li>
    <li><b>Chrome open</b> with the Claude in Chrome extension connected, for sites marked "sign-in" (LinkedIn, Glassdoor, job boards, Gmail).</li>
    <li><b>Signed in</b> to those sites in that Chrome. The agent never types passwords.</li>
    <li>When a run finishes you get the list of jobs. Reply e.g. <i>send 1,3,5</i> or <i>send all</i>.</li></ol></div>`;
  const setDays = days => { set("schedule", { ...(get("schedule") || {}), days }); };
  $("#dayPick").addEventListener("change", () => { setDays([...$("#dayPick").querySelectorAll("input:checked")].map(i => i.value)); draw(); });
  $("#schedTime").addEventListener("input", e => { set("schedule", { ...(get("schedule") || {}), time: e.target.value }); draw(); });
  $("#main").querySelectorAll("[data-preset]").forEach(b => b.addEventListener("click", () => {
    const days = b.dataset.preset.split(","); setDays(days);
    $("#dayPick").querySelectorAll("input").forEach(i => i.checked = days.includes(i.value)); draw();
  }));
  draw();
};

pages.sources = () => {
  const list = get("sources") || [];
  const have = new Set(list.map(s => s.id));
  const on = list.filter(s => s.enabled).length;
  $("#main").innerHTML = `<h2>Sites</h2><p class="lead">Where the agent searches, in this order. Switch sites on or off, edit how each is searched, or add new ones. ${on} of ${list.length} on.</p>
  <div class="card"><div class="row">
    <select id="preset" style="max-width:300px"><option value="">Add a ready-made site…</option>
      ${PRESETS.filter(p => !have.has(p.id)).map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select>
    <button class="btn" id="addPreset">Add</button><button class="btn" id="addCustom">+ Custom site</button>
  </div>
  <div class="hint" style="margin-top:8px">In search links, <code>{query}</code> is a search term, <code>{location}</code> your search location, <code>{days}</code> the look-back window (<code>{seconds}</code> in seconds).</div></div>
  <div id="srcList">${list.map((s, i) => `
    <div class="card src ${s.enabled ? "" : "off"}" data-i="${i}">
      <div class="row">
        <label class="switch" title="On / off"><input type="checkbox" data-sf="enabled" ${s.enabled ? "checked" : ""}><span></span></label>
        <b style="flex:1;min-width:140px">${esc(s.name)}</b>
        ${s.needs_signin ? `<span class="pill">sign-in</span>` : `<span class="pill">public</span>`}
        <button class="icon-btn mv" data-mv="-1" title="Move up" ${i === 0 ? "disabled" : ""}>↑</button>
        <button class="icon-btn mv" data-mv="1" title="Move down" ${i === list.length - 1 ? "disabled" : ""}>↓</button>
        <button class="btn" data-edit>${state.openSrc === s.id ? "Close" : "Edit"}</button>
        <button class="icon-btn" data-del title="Remove">×</button>
      </div>
      ${state.openSrc === s.id ? `<div class="grid" style="margin-top:12px">
        <div><label>Name</label><input type="text" data-sf="name" value="${esc(s.name)}"></div>
        <div><label>Id</label><input type="text" data-sf="id" value="${esc(s.id)}"><div class="hint">Lowercase letters, digits, -.</div></div>
        <div style="grid-column:1/-1"><label>How to search (link or instructions)</label><textarea data-sf="search" style="min-height:70px">${esc(s.search)}</textarea></div>
        <div><label>How to apply</label><textarea data-sf="apply" style="min-height:70px">${esc(s.apply)}</textarea></div>
        <div><label>Notes for the agent</label><textarea data-sf="notes" style="min-height:70px">${esc(s.notes)}</textarea></div>
        <div><label class="check"><input type="checkbox" data-sf="needs_signin" ${s.needs_signin ? "checked" : ""}> Needs my sign-in (opened in my Chrome)</label></div>
      </div>` : `<div class="sub" style="margin-top:6px;overflow-wrap:anywhere">${esc(s.search)}</div>`}
    </div>`).join("") || `<div class="card empty">No sites yet. Add one above.</div>`}</div>`;

  const save = arr => set("sources", arr);
  const copy = () => (get("sources") || []).map(x => ({ ...x }));
  $("#addPreset").addEventListener("click", () => {
    const p = PRESETS.find(x => x.id === $("#preset").value); if (!p) return;
    save([...copy(), { ...p, enabled: true }]); state.openSrc = p.id; render();
  });
  $("#addCustom").addEventListener("click", () => {
    let id = "custom", n = 1; const ids = new Set(copy().map(x => x.id)); while (ids.has(id)) id = "custom-" + ++n;
    save([...copy(), { id, name: "New site", enabled: true, needs_signin: false, search: "https://", apply: "", notes: "" }]);
    state.openSrc = id; render();
  });
  $("#srcList").addEventListener("click", e => {
    const card = e.target.closest("[data-i]"); if (!card) return; const i = +card.dataset.i; const arr = copy();
    if (e.target.closest("[data-del]")) { if (confirm(`Remove ${arr[i].name}?`)) { arr.splice(i, 1); save(arr); render(); } }
    else if (e.target.closest("[data-mv]")) { const j = i + +e.target.closest("[data-mv]").dataset.mv; [arr[i], arr[j]] = [arr[j], arr[i]]; save(arr); render(); }
    else if (e.target.closest("[data-edit]")) { state.openSrc = state.openSrc === arr[i].id ? null : arr[i].id; render(); }
  });
  const onField = e => {
    const el = e.target.closest("[data-sf]"); if (!el) return;
    const card = el.closest("[data-i]"); const i = +card.dataset.i; const arr = copy(); const k = el.dataset.sf;
    arr[i][k] = el.type === "checkbox" ? el.checked : el.value;
    if (k === "id") state.openSrc = el.value;
    save(arr);
    if (k === "enabled") card.classList.toggle("off", !el.checked);
  };
  $("#srcList").addEventListener("input", onField);
  $("#srcList").addEventListener("change", e => { onField(e); if (e.target.dataset.sf === "enabled" || e.target.dataset.sf === "needs_signin") render(); });
};

document.addEventListener("click", async e => {
  const b = e.target.closest && e.target.closest("[data-copy]"); if (!b) return;
  try { await navigator.clipboard.writeText($("#" + b.dataset.copy).textContent); toast("Copied"); } catch (err) { toast("Select the text and copy it"); }
});

// ---------- save / load ----------
$("#save").addEventListener("click", async () => {
  try {
    const r = await api("/api/config", { config: state.cfg });
    if (r.problems) { alert("Not saved:\n\n" + r.problems.join("\n")); return; }
    state.saved = JSON.stringify(state.cfg); state.exists = true; updateSavebar(); toast("Settings saved");
    if (state.tab === "home") render();
  } catch (err) { alert(err.message); }
});
$("#discard").addEventListener("click", () => { state.cfg = JSON.parse(state.saved); updateSavebar(); render(); });
window.addEventListener("hashchange", () => {
  const t = location.hash.slice(1); if (t !== state.tab && TABS.some(x => x[0] === t)) go(t);
});
window.addEventListener("beforeunload", e => { if (dirty()) { e.preventDefault(); e.returnValue = ""; } });

async function render() {
  renderNav(); updateSavebar();
  try { await pages[state.wizard ? "setup" : state.tab](); } catch (err) { $("#main").innerHTML = `<div class="card msg bad">${esc(err.message)}</div>`; }
}
(async () => {
  const d = await api("/api/config");
  state.cfg = d.config; state.saved = JSON.stringify(d.config); state.exists = d.exists; state.folder = d.folder;
  $("#folder").textContent = d.folder.split(/[\\/]/).pop();
  $("#folder").title = d.folder;
  try { const a = await api("/api/applications"); state.apps = a.rows; state.statuses = a.statuses; } catch (e) {}
  try { const t = localStorage.getItem("tab"); if (t && TABS.some(x => x[0] === t)) state.tab = t; } catch (e) {}
  const hashTab = location.hash.slice(1);
  if (TABS.some(x => x[0] === hashTab)) state.tab = hashTab;
  else if (!d.exists) state.tab = "home";
  if (!d.exists || d.config.setup_complete === false) { startSetup(); return; }
  updateSavebar(); render();
})();
