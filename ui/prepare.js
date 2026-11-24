// "Prepare" tab: interview prep per application and courses to close skill gaps.
// The research itself is done by the agent in Claude Code (it needs the web); this page gives the exact prompt
// to paste, the learning settings, and shows the pages the agent wrote (prep/*.md, learning/*.md).

const PLATFORM_LABELS = [["youtube", "YouTube"], ["official-docs", "Official docs & tutorials"], ["freecodecamp", "freeCodeCamp"],
  ["udemy", "Udemy"], ["coursera", "Coursera"], ["edx", "edX"], ["pluralsight", "Pluralsight"], ["linkedin-learning", "LinkedIn Learning"]];
const P = { prepFile: "", learnFile: "" };

async function noteViewer(kind, current) {
  const { files } = await api("/api/notes/" + kind);
  if (!files.length) return `<p class="sub">${kind === "prep" ? "No interview preps yet." : "No course lists yet."}</p>`;
  const pick = files.includes(current) ? current : files[0];
  const r = await api(`/api/notes/${kind}/${encodeURIComponent(pick)}`);
  return `<div class="row" style="margin-bottom:8px"><select data-note="${kind}" style="max-width:320px">${files.map(f => `<option ${f === pick ? "selected" : ""}>${esc(f)}</option>`).join("")}</select></div>
    <div class="report">${md(r.text)}</div>`;
}

pages.prepare = async () => {
  const d = await api("/api/applications"); state.apps = d.rows;
  const live = state.apps.filter(r => ["interview", "sent", "offer"].includes(r.status)).sort((a, b) => (+b.id) - (+a.id));
  const lr = get("learning") || {};
  const fieldName = get("field") || "your field";
  $("#main").innerHTML = `<h2>Prepare</h2><p class="lead">Get ready for interviews and learn what the jobs ask for. The agent does the research in Claude Code and saves it here.</p>
  <div class="card"><h3>Interview prep</h3>
    <p class="sub" style="margin-top:-6px">For one application: likely questions, STAR stories from your resume, do's and don'ts for ${esc(fieldName)} and for this company, and questions to ask them. Mark an application as <i>interview</i> in Applications and the agent offers it on its own.</p>
    ${live.length ? `<div class="row"><select id="prepApp" style="max-width:420px">${live.map(r => `<option value="${esc(r.id)}">#${esc(r.id)} ${esc(r.company)} – ${esc(r.role)} (${esc(r.status)})</option>`).join("")}</select></div>
      <p class="sub" style="margin-top:10px">With web research, by your agent tool:</p>
      <pre class="prompt" id="prepPrompt"></pre><button class="btn" data-copy="prepPrompt">Copy prompt for your agent</button>`
      : `<p class="sub">No sent applications yet. You can still ask in Claude Code: <i>prep for a Junior DevOps interview at Acme</i>.</p>`}
    <p class="sub" style="margin-top:12px">General tips: <a href="https://github.com/DorEydan/job-hunt-agent/blob/main/docs/INTERVIEW_GUIDE.md" target="_blank" rel="noopener noreferrer">docs/INTERVIEW_GUIDE.md</a></p>
    ${state.ai && state.ai.ready ? `<details class="b-entry" style="margin-top:12px"><summary><b>Or make it here with ${esc(state.ai.status.label)}</b> <span class="sub">(from the posting and your resume, no web research)</span></summary>
      <div class="grid" style="margin-top:8px"><div><label>Company</label><input type="text" id="apCompany"></div><div><label>Role</label><input type="text" id="apRole"></div>
      <div style="grid-column:1/-1"><label>Job posting</label><textarea id="apPosting" style="min-height:120px"></textarea></div></div>
      <div class="row" style="margin-top:8px"><button class="btn primary" id="apGo">Make interview prep</button><span id="apMsg" class="msg"></span></div></details>`
      : `<p class="sub" style="margin-top:10px">No agent or AI? The general guide covers the format, STAR stories and do's and don'ts by field.</p>`}
    <div id="prepView" style="margin-top:12px"></div></div>

  <div class="card"><h3>Learn a skill</h3>
    <p class="sub" style="margin-top:-6px">Find courses and tutorials, e.g. Docker, on the platforms you choose. The agent checks each link, says what's free, and never buys or signs up for anything.</p>
    <div class="row"><input type="text" id="skill" placeholder="e.g. Docker" style="max-width:260px"></div>
    <div class="row" style="margin-top:8px"><button class="btn" id="learnLinks">Show course search links</button><span class="sub">Works without AI.</span></div><div id="learnLinksOut"></div>
    <p class="sub" style="margin-top:10px">Or let the agent research and check the courses (Claude Code, Codex, Gemini CLI…):</p>
    <pre class="prompt" id="learnPrompt"></pre><button class="btn" data-copy="learnPrompt">Copy prompt for your agent</button>
    <h3 style="margin-top:16px">Settings</h3>
    <div class="grid"><div>${PLATFORM_LABELS.map(([k, l]) => `<label class="check"><input type="checkbox" data-platform="${k}" ${(lr.platforms || []).includes(k) ? "checked" : ""}> ${l}</label>`).join("")}</div>
      <div>${field("learning.free_only", "Free courses only", { type: "bool" })}${field("learning.suggest_in_runs", "Suggest courses in run reports when 3+ jobs ask for a skill I don't have", { type: "bool" })}
        ${field("learning.language", "Course language", { ph: "English" })}</div></div>
    <div id="learnView" style="margin-top:12px"></div></div>`;

  const prepPrompt = () => { const s = $("#prepApp"); if (s) $("#prepPrompt").textContent = `Open ${state.folder} and follow AGENTS.md, section "Interview prep", for application ${s.value}.`; };
  const learnPrompt = () => { const sk = ($("#skill").value || "Docker").trim();
    $("#learnPrompt").textContent = `Open ${state.folder} and follow AGENTS.md, section "Learning": find courses for ${sk}.`; };
  $("#prepApp")?.addEventListener("change", prepPrompt); $("#skill").addEventListener("input", learnPrompt);
  prepPrompt(); learnPrompt();
  $("#learnLinks").addEventListener("click", async () => {
    const sk = ($("#skill").value || "").trim(); if (!sk) { $("#skill").focus(); return; }
    const r = await api("/api/offline/learn?skill=" + encodeURIComponent(sk)); const lr = get("learning") || {};
    const want = (lr.platforms && lr.platforms.length) ? lr.platforms : Object.keys(r.links);
    $("#learnLinksOut").innerHTML = `<div class="row" style="margin-top:8px">${want.filter(k => r.links[k]).map(k => `<a class="btn" href="${esc(r.links[k])}" target="_blank" rel="noopener noreferrer">${esc((PLATFORM_LABELS.find(x => x[0] === k) || [k, k])[1])}</a>`).join("")}</div>
      <p class="sub">Tip: prefer recent courses with many good reviews, and start with a short one before a long one.${lr.free_only ? " On Udemy, filter Price → Free." : ""}</p>`;
  });
  $("#apGo")?.addEventListener("click", async e => {
    e.target.disabled = true; $("#apMsg").className = "msg"; $("#apMsg").textContent = "Writing… (up to a minute)";
    try { const r = await api("/api/ai/prep", { company: $("#apCompany").value, role: $("#apRole").value, posting: $("#apPosting").value });
      if (!r.ok) { $("#apMsg").className = "msg bad"; $("#apMsg").textContent = r.error; return; }
      P.prepFile = r.file; $("#apMsg").className = "msg ok"; $("#apMsg").textContent = "Saved: prep/" + r.file; $("#prepView").innerHTML = await noteViewer("prep", r.file);
    } catch (err) { $("#apMsg").className = "msg bad"; $("#apMsg").textContent = err.message; } finally { e.target.disabled = false; }
  });
  $("#prepView").innerHTML = await noteViewer("prep", P.prepFile);
  $("#learnView").innerHTML = await noteViewer("learning", P.learnFile);
};

document.addEventListener("change", async e => {
  const t = e.target;
  if (t.dataset && t.dataset.platform) {
    const lr = { ...(get("learning") || {}) }; const s = new Set(lr.platforms || []);
    t.checked ? s.add(t.dataset.platform) : s.delete(t.dataset.platform);
    lr.platforms = PLATFORM_LABELS.map(x => x[0]).filter(k => s.has(k)); set("learning", lr);
  }
  if (t.dataset && t.dataset.note) {
    P[t.dataset.note === "prep" ? "prepFile" : "learnFile"] = t.value;
    $(t.dataset.note === "prep" ? "#prepView" : "#learnView").innerHTML = await noteViewer(t.dataset.note, t.value);
  }
});
