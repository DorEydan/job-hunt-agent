// Resume builder tab: start from scratch or redesign an existing resume, pick a template, edit with a live preview,
// then create Word + PDF and use it for applications. Loaded after app.js and setup.js.

const B = { data: null, template: null, templates: null, result: null, tips: null, busy: "", msg: "" };
const DRAFT_KEY = "builderDraft";
const SECTIONS = { experience: ["title", "company", "location", "dates"], projects: ["name", "role", "dates", "link"], education: ["degree", "school", "dates"] };
const SECTION_LABELS = { title: "Job title", company: "Company", location: "Location (optional)", dates: "Dates", name: "Project name", role: "Your role / type", link: "Link (optional)", degree: "Degree / course", school: "School" };

function recommendTemplate() {  // mirrors resume_builder.recommend()
  const f = get("field"), lv = get("experience_level");
  if (["student", "entry"].includes(lv)) return "graduate";
  if (["design", "marketing"].includes(f)) return "creative";
  if (["product", "sales"].includes(f) || lv === "senior") return "professional";
  return "tech";
}
function saveDraft() { try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ data: B.data, template: B.template })); } catch (e) {} }
function loadDraft() { try { const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); if (d && d.data) { B.data = d.data; B.template = d.template; } } catch (e) {} }

function blankResume() {  // from what the user already told us
  const c = get("candidate") || {}; const roles = get("target_roles") || [];
  const tech = ["software", "devops", "data", "qa", "it", "security"].includes(get("field"));
  return {
    name: c.full_name || "", headline: roles[0] || "",
    contact: { city: c.city || "", phone: c.phone || "", email: c.email || "", linkedin: c.linkedin || "", github: c.github || "", portfolio: c.portfolio || "" },
    summary: "", skills_heading: tech ? "Technical Skills" : "Skills",
    skills: [{ label: tech ? "Languages" : "Core skills", items: [] }, { label: "Tools", items: [] }],
    experience: [{ title: "", company: "", location: "", dates: "", bullets: [""] }],
    projects: [], education: [{ degree: "", school: "", dates: "", bullets: [] }], certifications: [], languages: "",
    page: ["United States", "Canada"].includes(get("country")) ? "Letter" : "A4",
  };
}

// ---------- live HTML preview (close to the Word output; the PDF button shows the exact one) ----------
function previewHtml() {
  const d = B.data, t = B.templates[B.template]; const a = "#" + t.accent;
  const c = d.contact || {};
  const hs = t.heading === "bar" ? `border:0;border-left:4px solid ${a};padding-left:6px` : t.heading === "plain" ? "border:0" : `border-color:${a}`;
  const head = s => `<div class="pv-h" style="color:${a};${hs}">${esc(s)}</div>`;
  const bullets = l => (l || []).filter(x => x.trim()).length ? `<ul>${l.filter(x => x.trim()).map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
  const line = (bold, rest, right) => `<div class="pv-e"><span><b>${esc(bold)}</b>${rest ? " | " + esc(rest) : ""}</span><span class="pv-d">${esc(right || "")}</span></div>`;
  const sec = {
    summary: () => d.summary ? head("Professional Summary") + `<p>${esc(d.summary)}</p>` : "",
    skills: () => (d.skills || []).some(g => g.items.length) ? head(d.skills_heading || "Technical Skills") + d.skills.filter(g => g.items.length).map(g => `<p><b>${esc(g.label)}:</b> ${esc(g.items.join(", "))}.</p>`).join("") : "",
    experience: () => (d.experience || []).length ? head("Work Experience") + d.experience.map(e => line(e.title, [e.company, e.location].filter(Boolean).join(" | "), e.dates) + bullets(e.bullets)).join("") : "",
    projects: () => (d.projects || []).length ? head("Projects") + d.projects.map(p => line(p.name, [p.role, p.link].filter(Boolean).join(" | "), p.dates) + bullets(p.bullets)).join("") : "",
    education: () => (d.education || []).length ? head("Education") + d.education.map(e => line(e.degree, e.school, e.dates) + bullets(e.bullets)).join("") : "",
    certifications: () => (d.certifications || []).length ? head("Courses & Certifications") + `<p>${esc(d.certifications.join(" | "))}</p>` : "",
    languages: () => d.languages ? head("Languages") + `<p>${esc(d.languages)}</p>` : "",
  };
  const contact = [c.city, c.phone, c.email, ...["linkedin", "github", "portfolio"].map(k => (c[k] || "").replace(/^(https?:\/\/)?(www\.)?/, "").replace(/\/$/, ""))].filter(Boolean);
  return `<div class="pv" style="font-family:${esc(t.font)},sans-serif;text-align:left;${t.compact ? "font-size:9.5px;padding:16px 18px" : ""}">
    <div style="text-align:${t.center ? "center" : "left"}"><div class="pv-n" ${t.name_accent ? `style="color:${a}"` : ""}>${esc(d.name || "Your Name")}</div>
    ${d.headline ? `<div class="pv-t" style="color:${a}">${esc(d.headline)}</div>` : ""}
    <div class="pv-c">${contact.map(esc).join(" &nbsp;|&nbsp; ")}</div></div>
    ${t.order.map(s => sec[s]()).join("")}</div>`;
}

// ---------- form ----------
const inp = (path, label, ph = "") => `<div><label>${label}</label><input type="text" data-b="${path}" value="${esc(bget(path) ?? "")}" placeholder="${esc(ph)}"></div>`;
const area = (path, label, hint = "", rows = 3) => `<div style="grid-column:1/-1"><label>${label}</label><textarea data-b="${path}" data-blines="${path.endsWith("bullets") || path === "certifications" ? 1 : ""}" style="min-height:${rows * 22 + 16}px">${esc(Array.isArray(bget(path)) ? bget(path).join("\n") : bget(path) ?? "")}</textarea>${hint ? `<div class="hint">${hint}</div>` : ""}</div>`;
function bget(path) { return path.split(".").reduce((o, k) => (o ?? {})[k], B.data); }
function bset(path, val) {
  const ks = path.split("."); let o = B.data;
  ks.slice(0, -1).forEach(k => { o = o[k]; }); o[ks.at(-1)] = val; saveDraft(); B.result = null;
  const pv = $("#pvBox"); if (pv) pv.innerHTML = previewHtml();
}

function entryCards(sec) {
  const list = B.data[sec] || [];
  return list.map((e, i) => `<div class="b-entry"><div class="row" style="justify-content:space-between"><b>${esc(e[SECTIONS[sec][0]] || "New entry")}</b>
      <span><button class="icon-btn" data-bmv="${sec}:${i}:-1" title="Move up" ${i ? "" : "disabled"}>↑</button><button class="icon-btn" data-bmv="${sec}:${i}:1" title="Move down" ${i < list.length - 1 ? "" : "disabled"}>↓</button><button class="icon-btn" data-bdel="${sec}:${i}" title="Remove">×</button></span></div>
      <div class="grid">${SECTIONS[sec].map(k => inp(`${sec}.${i}.${k}`, SECTION_LABELS[k], k === "dates" ? "2024 – Present" : "")).join("")}
      ${area(`${sec}.${i}.bullets`, "What you did (one line each)", "Start with a verb, add a number where you can: “Built…, cutting load time by 40%”.", 3)}</div></div>`).join("")
    + `<button class="btn" data-badd="${sec}">+ Add ${sec === "experience" ? "job" : sec === "projects" ? "project" : "education"}</button>`;
}

function builderForm() {
  const d = B.data;
  return `
  <div class="card"><h3>Header</h3><div class="grid">${inp("name", "Full name")}${inp("headline", "Headline", "Junior Full-Stack Developer")}
    ${inp("contact.city", "City")}${inp("contact.phone", "Phone")}${inp("contact.email", "Email")}${inp("contact.linkedin", "LinkedIn")}${inp("contact.github", "GitHub (optional)")}${inp("contact.portfolio", "Portfolio / website (optional)")}
    <div><label>Page size</label><select data-b="page"><option ${d.page !== "Letter" ? "selected" : ""}>A4</option><option ${d.page === "Letter" ? "selected" : ""}>Letter</option></select></div></div></div>
  <div class="card"><h3>Summary</h3><div class="grid">${area("summary", "2–3 lines: who you are, your main skills, what you're looking for", "", 3)}</div></div>
  <div class="card"><h3>Skills</h3><div class="grid">${inp("skills_heading", "Section heading", "Technical Skills")}</div>
    ${d.skills.map((g, i) => `<div class="kv"><input type="text" data-b="skills.${i}.label" value="${esc(g.label)}" aria-label="Group"><input type="text" data-bskills="${i}" value="${esc(g.items.join(", "))}" aria-label="Skills" placeholder="Python, SQL, Docker"><button class="icon-btn" data-bdel="skills:${i}" title="Remove">×</button></div>`).join("")}
    <button class="btn" data-badd="skills">+ Add group</button><div class="hint">One group per line, skills separated by commas. For each job the agent reorders the skills inside these lines.</div></div>
  <div class="card"><h3>Experience</h3>${entryCards("experience")}</div>
  <div class="card"><h3>Projects</h3>${entryCards("projects")}</div>
  <div class="card"><h3>Education</h3>${entryCards("education")}</div>
  <div class="card"><h3>More</h3><div class="grid">${area("certifications", "Courses and certifications (one per line)", "", 2)}${inp("languages", "Languages", "English: Fluent | Spanish: Native")}</div></div>`;
}

pages.builder = async () => {
  if (!B.templates) B.templates = (await api("/api/builder/templates")).templates;
  if (!B.data) loadDraft();
  const variants = Object.keys(resume_variants_client());
  if (!B.data) {
    $("#main").innerHTML = `<h2>Resume builder</h2><p class="lead">Make a clean, one-page resume that applicant-tracking systems can read, in a design that fits the jobs you want. It works with the agent right away.</p>
      <div class="opts" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr))">
        <button class="opt start" data-bstart="scratch"><span><b>Start from scratch</b><br><span class="sub">No resume yet. Your details from the setup are filled in.</span></span></button>
        <button class="opt start" data-bstart="redesign" ${variants.length ? "" : "disabled"}><span><b>Redesign my resume</b><br><span class="sub">${variants.length ? "Reads your current resume into the form, then pick a new design." : "Add a resume first (Resumes tab or setup)."}</span></span></button>
      </div>
      ${variants.length > 1 ? `<div class="row" style="margin-top:10px"><label for="bVar" style="margin:0">Redesign which version?</label><select id="bVar" style="max-width:200px">${variants.map(v => `<option>${esc(v)}</option>`).join("")}</select></div>` : ""}
      <div class="msg bad">${esc(B.msg)}</div>${state.builderReturn ? `<p><a href="#" data-bback>← Back to setup</a></p>` : ""}`;
    return;
  }
  if (!B.template) B.template = recommendTemplate();
  const rec = recommendTemplate();
  $("#main").innerHTML = `<h2>Resume builder</h2>
    <div class="row" style="margin:-4px 0 14px">${state.builderReturn ? `<a href="#" data-bback>← Back to setup</a>` : ""}<span class="sub">Saved as you type.</span><a href="#" data-brestart>Start over</a></div>
    <div class="tpl">${Object.entries(B.templates).map(([k, t]) => `<label class="tplc ${B.template === k ? "on" : ""}"><input type="radio" name="btpl" value="${k}" ${B.template === k ? "checked" : ""}>
      <span class="sw" style="background:#${t.accent}"></span><span><b>${esc(t.label)}</b>${k === rec ? ` <span class="pill">recommended</span>` : ""}<br><span class="sub">${esc(t.for)}</span></span></label>`).join("")}</div>
    <details class="card guide"><summary><b>Quick guide</b> <span class="sub">what recruiters and screening systems look for</span></summary>
      <ul class="review">
        <li><b>One page, one column</b>, standard headings, a common font. No tables, text boxes or photos of text, so screening software can read it.</li>
        <li><b>Bullets: verb + what you did + result.</b> “Built a dashboard used by 30 managers”, not “Responsible for reports”.</li>
        <li><b>Numbers</b> make it real: users, %, time saved, size. Estimate carefully; never invent.</li>
        <li><b>Order by your strongest proof:</b> experience first if you have it; education and projects first if you're starting out.</li>
        <li><b>Use the posting's words</b> where they're true for you. The agent reorders your skills for each job and never adds one you don't have.</li>
        <li><b>Summary:</b> 2–3 lines: who you are, main skills, what you want. Mention your degree early if it's your strongest asset.</li>
      </ul>
      <p class="sub">Full guide with sources: <a href="https://github.com/DorEydan/job-hunt-agent/blob/main/docs/RESUME_GUIDE.md" target="_blank" rel="noopener noreferrer">docs/RESUME_GUIDE.md</a></p></details>
    <div class="bwrap"><div class="bform">${builderForm()}</div>
      <div class="bside"><div class="card pvcard"><div id="pvBox">${previewHtml()}</div></div>
        <div class="card"><div class="row"><button class="btn primary" data-bbuild ${B.busy ? "disabled" : ""}>${B.busy === "build" ? "Creating…" : "Create Word + PDF"}</button><button class="btn" data-btips ${B.busy ? "disabled" : ""}>Check my resume</button>
          ${state.ai && state.ai.ready ? `<button class="btn" data-bpolish ${B.busy ? "disabled" : ""}>${B.busy === "polish" ? "Polishing…" : "Polish wording with AI"}</button>` : ""}</div>
          <div id="bOut">${resultHtml()}</div></div></div></div>`;
};

function resultHtml() {
  let h = B.msg ? `<div class="msg bad">${esc(B.msg)}</div>` : "";
  const r = B.result;
  if (r) {
    h += `<div class="msg ${r.skills ? "ok" : "warn"}">${r.skills ? `Ready. The agent can tailor it (${Object.keys(r.skills).length} skill lines).` : esc(r.skills_error || "")}</div>
      <div class="row" style="margin-top:8px">${r.pdf_error ? `<span class="sub">${esc(r.pdf_error)}</span>` : `<a class="btn" href="/api/builder/preview.pdf" target="_blank" rel="noopener">Open PDF</a>`}
      <a class="btn" href="/api/builder/resume.docx">Download Word</a><button class="btn primary" data-buse>Use it for job applications</button></div>`;
  }
  if (B.polish) {
    h += `<h3 style="margin-top:14px">AI suggestions</h3><p class="sub">Facts kept; <i>[number?]</i> marks where a number would help. Review before applying.</p>
      ${B.polish.summary ? `<p><b>Summary:</b> ${esc(B.polish.summary)}</p>` : ""}
      ${["experience", "projects"].map(sec => (B.polish[sec] || []).map((bl, i) => bl.length ? `<p class="sub"><b>${esc((B.data[sec][i] || {}).title || (B.data[sec][i] || {}).name || "")}</b></p><ul>${bl.map(b => `<li>${esc(b)}</li>`).join("")}</ul>` : "").join("")).join("")}
      <button class="btn primary" data-bapply>Apply these changes</button>`;
  }
  if (B.tips) {
    h += `<h3 style="margin-top:14px">Suggestions</h3>${B.tips.tips.length ? `<ul class="review">${B.tips.tips.map(t => `<li>${esc(t)}</li>`).join("")}</ul>` : `<p class="msg ok">Looks good.</p>`}
      <p class="sub">Want better wording? Copy this into Claude. It keeps your facts and marks where a number would help.</p>
      <pre class="prompt" id="bPrompt" style="max-height:160px;overflow:auto">${esc(B.tips.prompt)}</pre><button class="btn" data-copy="bPrompt">Copy prompt</button>`;
  }
  return h;
}
function resume_variants_client() { return Object.fromEntries(Object.entries(get("base_resumes") || {}).filter(([k, v]) => !k.startsWith("_") && v)); }

document.addEventListener("input", e => {
  const t = e.target; if (!B.data || !t.closest || !t.closest(".bform")) return;
  if (t.dataset.b) bset(t.dataset.b, t.dataset.blines ? t.value.split("\n") : t.value);
  if (t.dataset.bskills !== undefined) bset(`skills.${t.dataset.bskills}.items`, t.value.split(",").map(x => x.trim()).filter(Boolean));
});
document.addEventListener("change", e => {
  const t = e.target;
  if (t.name === "btpl") { B.template = t.value; saveDraft(); B.result = null; render(); }
  if (t.dataset && t.dataset.b === "page") bset("page", t.value);
});
document.addEventListener("click", async e => {
  const el = e.target.closest && e.target.closest("[data-bstart],[data-badd],[data-bdel],[data-bmv],[data-bbuild],[data-btips],[data-buse],[data-brestart],[data-bback],[data-bpolish],[data-bapply]");
  if (!el || state.tab !== "builder") return;
  e.preventDefault();
  const d = el.dataset;
  try {
    if (d.bstart === "scratch") { B.data = blankResume(); B.template = null; B.msg = ""; saveDraft(); return render(); }
    if (d.bstart === "redesign") {
      const v = $("#bVar") ? $("#bVar").value : Object.keys(resume_variants_client())[0];
      el.disabled = true; B.msg = "";
      const r = await api("/api/builder/parse", { variant: v });
      B.data = { ...blankResume(), ...r.data, page: blankResume().page }; B.template = null; saveDraft(); return render();
    }
    if (d.brestart !== undefined) { if (!confirm("Clear the builder and start over?")) return; B.data = null; B.result = B.tips = null; try { localStorage.removeItem(DRAFT_KEY); } catch (err) {} return render(); }
    if (d.bback !== undefined) { state.builderReturn = false; state.wizard = true; return render(); }
    if (d.badd) {
      const s = d.badd;
      if (s === "skills") B.data.skills.push({ label: "", items: [] });
      else B.data[s].push(Object.fromEntries([...SECTIONS[s].map(k => [k, ""]), ["bullets", [""]]]));
      saveDraft(); return render();
    }
    if (d.bdel) { const [s, i] = d.bdel.split(":"); B.data[s].splice(+i, 1); saveDraft(); return render(); }
    if (d.bmv) { const [s, i, dir] = d.bmv.split(":"); const a = B.data[s]; const j = +i + +dir; [a[+i], a[j]] = [a[j], a[+i]]; saveDraft(); return render(); }
    if (d.bbuild !== undefined) {
      B.busy = "build"; B.msg = ""; render();
      try { B.result = await api("/api/builder/build", { data: B.data, template: B.template }); }
      catch (err) { B.msg = err.message; } finally { B.busy = ""; }
      return render();
    }
    if (d.bpolish !== undefined) {
      B.busy = "polish"; B.msg = ""; render();
      try { const r = await api("/api/ai/polish", { data: B.data, role: (get("target_roles") || [])[0] || "" }); if (r.ok) B.polish = r; else B.msg = r.error; }
      catch (err) { B.msg = err.message; } finally { B.busy = ""; }
      return render();
    }
    if (d.bapply !== undefined && B.polish) {
      if (B.polish.summary) B.data.summary = B.polish.summary;
      ["experience", "projects"].forEach(sec => (B.polish[sec] || []).forEach((bl, i) => { if (B.data[sec][i] && bl.length) B.data[sec][i].bullets = bl; }));
      B.polish = null; B.result = null; saveDraft(); toast("Applied. Check the [number?] marks."); return render();
    }
    if (d.btips !== undefined) {
      B.tips = await api("/api/builder/tips", { data: B.data, field: get("field") || "", role: (get("target_roles") || [])[0] || "" });
      return render();
    }
    if (d.buse !== undefined && B.result) {
      set("base_resumes", { ...resume_variants_client(), default: B.result.path });
      set("skills_heading", B.result.heading);
      if (!(get("resume_output_name") || "").trim() || /Your Name/.test(get("resume_output_name"))) set("resume_output_name", (B.data.name || "My") + " resume");
      if (state.builderReturn) {  // back into the setup wizard, resume step done
        wiz.resume = { path: B.result.path, skills: B.result.skills, skills_error: B.result.skills_error };
        const c = B.data.contact || {};  // what was typed in the builder fills the setup too
        wiz.filled = applyProfile({ full_name: B.data.name, email: c.email, phone: c.phone, city: c.city, linkedin: c.linkedin, github: c.github, portfolio: c.portfolio });
        state.builderReturn = false; state.wizard = true; return render();
      }
      const r = await api("/api/config", { config: state.cfg });
      if (r.problems) { B.msg = r.problems.join(" "); return render(); }
      state.saved = JSON.stringify(state.cfg); state.exists = true; updateSavebar(); toast("Now used for applications");
    }
  } catch (err) { B.msg = err.message; render(); }
});

// The setup wizard links here: "No resume, or want a new design?"
function openBuilderFromSetup() { state.builderReturn = true; state.wizard = false; document.body.classList.remove("wizard"); state.tab = "builder"; render(); }
