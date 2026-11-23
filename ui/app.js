const TABS = [
  ["home", "Home"], ["profile", "Profile"], ["search", "Job search"], ["resumes", "Resumes"],
  ["answers", "Answers & notes"], ["apps", "Applications"], ["runs", "Run reports"], ["automate", "Automate"],
];
const CONFIG_TABS = new Set(["profile", "search", "resumes", "answers"]);
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
function updateSavebar() { $("#savebar").classList.toggle("show", dirty() || !state.exists); $("#savestate").textContent = state.exists ? "Unsaved changes" : "Settings not saved yet"; }

function renderNav() {
  const counts = { apps: state.apps.length };
  $("#nav").innerHTML = TABS.map(([id, name]) =>
    `<button data-tab="${id}" class="${state.tab === id ? "active" : ""}">${name}${counts[id] ? `<span class="n">${counts[id]}</span>` : ""}</button>`).join("");
}
$("#nav").addEventListener("click", e => { const b = e.target.closest("button"); if (b) go(b.dataset.tab); });
function go(tab) { state.tab = tab; try { localStorage.setItem("tab", tab); } catch (e) {} history.replaceState(null, "", "#" + tab); render(); }

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
  const goTo = { config: "profile", profile: "profile", resumes: "resumes" };
  $("#health").innerHTML = items.map(it => {
    const cls = it.ok === true ? (it.warn ? "warn" : "ok") : it.ok === null ? "na" : "bad";
    const mark = it.ok === true ? (it.warn ? "!" : "✓") : it.ok === null ? "–" : "✕";
    const fix = it.ok === true ? (it.warn || "") : it.fix;
    return `<li><span class="dot ${cls}">${mark}</span><div><b>${esc(it.label)}</b>${it.detail ? ` <span class="sub">· ${esc(it.detail)}</span>` : ""}
      ${fix ? `<div class="sub">${esc(fix)}${goTo[it.key] && it.ok !== true ? ` <a href="#" data-go="${goTo[it.key]}">Open</a>` : ""}${it.warn ? ` <a href="#" data-go="resumes">Open</a>` : ""}</div>` : ""}</div></li>`;
  }).join("") + `<li><span class="dot na">→</span><div><b>Schedule it</b><div class="sub">When everything above is green, set up the automatic runs. <a href="#" data-go="automate">Open</a></div></div></li>`;
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
  $("#main").innerHTML = `<h2>Job search</h2><p class="lead">What to look for and what to skip. One item per line.</p>
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
  <div class="card"><h3>Location</h3><div class="grid">
    ${field("locations.preferred", "Preferred cities", { type: "lines" })}
    <div>${field("locations.accept_remote", "Remote jobs are OK", { type: "bool" })}${field("locations.accept_hybrid", "Hybrid jobs are OK", { type: "bool" })}</div>
  </div></div>
  <div class="card"><h3>Limits</h3><div class="grid">
    ${field("max_new_jobs_per_run", "Max new jobs per run", { type: "int" })}
    ${field("min_match_score", "Minimum match score (1–10)", { type: "int" })}
    ${field("dedup_days", "Don't re-apply to the same job for (days)", { type: "int" })}
    ${field("pending_days", "Offer unapproved jobs again after (days)", { type: "int" })}
  </div></div>`;
};

pages.resumes = () => {
  const variants = Object.keys(get("base_resumes") || {}).filter(k => !k.startsWith("_"));
  $("#main").innerHTML = `<h2>Resumes</h2><p class="lead">Your resume as a Word <code>.docx</code>. The agent only reorders the skills under the skills heading for each job, then exports a small PDF.</p>
  <div class="card"><h3>Resume versions</h3>
    <p class="sub" style="margin-top:-6px">One version is enough. Add more if you target different job types (e.g. <i>devops</i> and <i>fullstack</i>).</p>
    ${kvEditor("base_resumes", "Version name", "Path to the .docx file", { ph: "C:\\Users\\you\\Documents\\resume.docx" })}
    <div style="margin-top:12px">${field("_base_resumes_note", "Which jobs each version is for", { type: "text", hint: "The agent reads this to pick a version, e.g. “DevOps / Cloud jobs → devops. Developer jobs → fullstack.”" })}</div>
  </div>
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
  $("#main").innerHTML = `<h2>Answers & notes</h2><p class="lead">Application forms often ask the same questions. The agent answers only from here. If an answer is missing, it asks you instead of guessing.</p>
  <div class="card"><h3>Screening answers</h3>
    ${kvEditor("screening_answers", "Question (short key)", "Your answer", { ph: "e.g. 30 days" })}
    <div class="hint">Examples: <i>notice_period</i>, <i>salary_expectation</i>, <i>authorized_to_work</i>, <i>years_experience</i>, <i>willing_to_relocate</i>. Empty = the agent will ask you.</div>
  </div>
  <div class="card"><h3>Cover notes</h3>
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
      toast(r.message || "Saved"); const row = state.apps.find(x => x.id === sel.dataset.status); if (row) row.status = sel.value;
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

pages.automate = async () => {
  const s = await api("/api/schedule");
  $("#main").innerHTML = `<h2>Automate</h2><p class="lead">The agent runs inside Claude Code. Set it up once and it searches on its own; sending always waits for your approval.</p>
  <div class="card"><h3>1. Try one run now</h3><p class="sub">Open Claude Code in this folder and paste:</p>
    <pre class="prompt" id="prompt">${esc(s.prompt)}</pre><button class="btn" data-copy="prompt">Copy</button></div>
  <div class="card"><h3>2. Schedule it</h3><p class="sub">In Claude Code, paste this to create the schedule (Sunday, Tuesday and Thursday at 09:00 — change it if you like):</p>
    <pre class="prompt" id="sched">Create a scheduled task named "job-hunt-agent" that runs at cron "${esc(s.cron)}" with this prompt: ${esc(s.prompt)}</pre>
    <button class="btn" data-copy="sched">Copy</button></div>
  <div class="card"><h3>3. Before each run</h3><ol class="steps">
    <li><b>Computer on</b> and the Claude app open at the scheduled time.</li>
    <li><b>Chrome open</b> with the Claude in Chrome extension connected, for sites that need your sign-in (LinkedIn, job boards, Gmail).</li>
    <li><b>Signed in</b> to LinkedIn and your email in that Chrome. The agent never types passwords.</li>
    <li>When a run finishes you get the list of jobs. Reply e.g. <i>send 1,3,5</i> or <i>send all</i>.</li></ol></div>`;
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
window.addEventListener("beforeunload", e => { if (dirty()) { e.preventDefault(); e.returnValue = ""; } });

async function render() {
  renderNav();
  try { await pages[state.tab](); } catch (err) { $("#main").innerHTML = `<div class="card msg bad">${esc(err.message)}</div>`; }
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
  updateSavebar(); render();
})();
