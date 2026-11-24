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
      <pre class="prompt" id="prepPrompt" style="margin-top:10px"></pre><button class="btn" data-copy="prepPrompt">Copy prompt for Claude Code</button>`
      : `<p class="sub">No sent applications yet. You can still ask in Claude Code: <i>prep for a Junior DevOps interview at Acme</i>.</p>`}
    <p class="sub" style="margin-top:12px">General tips: <a href="https://github.com/DorEydan/job-hunt-agent/blob/main/docs/INTERVIEW_GUIDE.md" target="_blank" rel="noopener noreferrer">docs/INTERVIEW_GUIDE.md</a></p>
    <div id="prepView" style="margin-top:12px"></div></div>

  <div class="card"><h3>Learn a skill</h3>
    <p class="sub" style="margin-top:-6px">Find courses and tutorials, e.g. Docker, on the platforms you choose. The agent checks each link, says what's free, and never buys or signs up for anything.</p>
    <div class="row"><input type="text" id="skill" placeholder="e.g. Docker" style="max-width:260px"></div>
    <pre class="prompt" id="learnPrompt" style="margin-top:10px"></pre><button class="btn" data-copy="learnPrompt">Copy prompt for Claude Code</button>
    <h3 style="margin-top:16px">Settings</h3>
    <div class="grid"><div>${PLATFORM_LABELS.map(([k, l]) => `<label class="check"><input type="checkbox" data-platform="${k}" ${(lr.platforms || []).includes(k) ? "checked" : ""}> ${l}</label>`).join("")}</div>
      <div>${field("learning.free_only", "Free courses only", { type: "bool" })}${field("learning.suggest_in_runs", "Suggest courses in run reports when 3+ jobs ask for a skill I don't have", { type: "bool" })}
        ${field("learning.language", "Course language", { ph: "English" })}</div></div>
    <div id="learnView" style="margin-top:12px"></div></div>`;

  const prepPrompt = () => { const s = $("#prepApp"); if (s) $("#prepPrompt").textContent = `Open ${state.folder} and follow AGENT.md, section "Interview prep", for application ${s.value}.`; };
  const learnPrompt = () => { const sk = ($("#skill").value || "Docker").trim();
    $("#learnPrompt").textContent = `Open ${state.folder} and follow AGENT.md, section "Learning": find courses for ${sk}.`; };
  $("#prepApp")?.addEventListener("change", prepPrompt); $("#skill").addEventListener("input", learnPrompt);
  prepPrompt(); learnPrompt();
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
