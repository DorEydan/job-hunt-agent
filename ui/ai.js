// AI tab (any provider, or none) and "Apply by hand" tab (works with no AI and no agent).
// Loaded after app.js. Other pages read state.ai.ready to show AI buttons only when an AI is set up.

state.ai = { ready: false, status: null, providers: [] };
async function loadAi() {
  try { const r = await api("/api/ai"); state.ai = { ready: r.status.ready, status: r.status, providers: r.providers }; } catch (e) {}
}
loadAi();
const aiBadge = () => state.ai.ready ? `<span class="pill sent">AI: ${esc(state.ai.status.label)}</span>` : `<span class="pill">No AI · offline</span>`;

pages.ai = async () => {
  await loadAi();
  const a = get("ai") || { provider: "none" }; const st = state.ai.status || {};
  const P = state.ai.providers; const cur = P.find(p => p.id === (a.provider || "none")) || P[0];
  $("#main").innerHTML = `<h2>AI</h2><p class="lead">Optional. Pick any AI for the panel's smart features, or none: everything that can work without AI does.</p>
  <div class="card"><h3>Which AI?</h3><div class="opts">${P.map(p => `<label class="opt ${p.id === cur.id ? "on" : ""}"><input type="radio" name="aiprov" value="${p.id}" ${p.id === cur.id ? "checked" : ""}>
      <span><b>${esc(p.label)}</b>${p.local ? ` <span class="pill">on this computer</span>` : ""}</span></label>`).join("")}</div></div>
  ${cur.id === "none" ? `<div class="card"><p class="sub" style="margin:0">Without AI you still get: the setup wizard, resume builder and its checks, keyword matching of a posting to your resume with a tailored PDF (<a href="#" data-go="manual">Apply by hand</a>), search links for every site, course links, interview guides, and the application log.</p></div>` : `
  <div class="card"><h3>${esc(cur.label)}</h3><div class="grid">
    ${field("ai.model", "Model", { ph: cur.model, hint: "Empty = " + cur.model })}
    ${cur.id === "custom" || a.base_url ? field("ai.base_url", "Server address", { ph: cur.base_url || "https://…/v1", hint: "https, or http://localhost for a model on this computer." }) : ""}
    ${cur.needs_key || cur.id === "custom" ? `<div><label for="aikey">API key</label><div class="row"><input type="password" id="aikey" autocomplete="off" placeholder="${st.key_set ? "saved · paste to replace" : "paste your key"}" style="flex:1">
      <button class="btn" id="saveKey">Save key</button></div>
      <div class="hint">Saved as <code>${esc(st.key_env || cur.key_env)}</code> in <code>.env</code> on this computer (git-ignored), never in config.json and never shown again. An environment variable with that name works too.</div></div>` : `<div class="hint" style="align-self:end">No key needed. Make sure ${esc(cur.label)} is running.</div>`}
    </div>
    <div class="row" style="margin-top:12px"><button class="btn primary" id="aiTest">Test connection</button><span id="aiMsg" class="msg"></span></div>
    <p class="sub" style="margin-top:10px">Save your settings first (bottom bar) if you changed the provider or model.</p></div>`}
  <div class="card"><h3>What uses it</h3><ul class="review">
    <li><b>Panel features</b> (this AI): rank a pasted posting against your resume, polish resume wording, interview prep from a posting, suggestions while setting up (local job sites, search terms in the local language, tips for your field).</li>
    <li><b>The automatic agent</b> (search sites, fill forms, research): runs in an agent tool that reads <code>AGENTS.md</code> in this folder: Claude Code, OpenAI Codex, Gemini CLI, Cursor, Aider and others. It needs a browser tool for sites you sign in to.</li>
    <li>Keys stay on this computer. Job postings are sent to the AI you pick; your contact details are not.</li></ul></div>`;
  $("#main").querySelectorAll('input[name="aiprov"]').forEach(r => r.addEventListener("change", () => {
    const p = P.find(x => x.id === r.value); set("ai", { provider: p.id, model: "", base_url: "", api_key_env: p.id === "custom" ? "CUSTOM_AI_API_KEY" : "" }); render();
  }));
  $("#saveKey")?.addEventListener("click", async () => {
    const v = $("#aikey").value.trim(); if (!v) return;
    try { await api("/api/ai/key", { name: st.provider === cur.id ? st.key_env : cur.key_env, value: v }); $("#aikey").value = ""; toast("Key saved on this computer"); await loadAi(); render(); }
    catch (err) { $("#aiMsg").className = "msg bad"; $("#aiMsg").textContent = err.message; }
  });
  $("#aiTest")?.addEventListener("click", async e => {
    if (dirty()) { $("#aiMsg").className = "msg warn"; $("#aiMsg").textContent = "Save your settings first."; return; }
    e.target.disabled = true; $("#aiMsg").className = "msg"; $("#aiMsg").textContent = "Asking…";
    try { const r = await api("/api/ai/test", {}); $("#aiMsg").className = "msg " + (r.ok ? "ok" : "bad"); $("#aiMsg").textContent = r.ok ? "Connected. The AI answered: " + r.answer : r.error; await loadAi(); }
    catch (err) { $("#aiMsg").className = "msg bad"; $("#aiMsg").textContent = err.message; } finally { e.target.disabled = false; }
  });
};

// ---------- Apply by hand ----------
const M = { res: null, prepared: null, msg: "" };
pages.manual = async () => {
  const s = await api("/api/offline/searches");
  $("#main").innerHTML = `<h2>Apply by hand</h2><p class="lead">No agent running? Search the sites yourself with ready links, then paste a posting to get a resume tailored to it. ${aiBadge()}</p>
  <div class="card"><h3>1. Search</h3>${s.sites.length ? s.sites.map(x => `<div class="b-entry"><b>${esc(x.name)}</b>
      <div class="row" style="margin-top:6px">${x.links.map(l => `<a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.term)}</a>`).join("") || `<span class="sub">${esc(x.how)}</span>`}</div>
      ${x.apply ? `<div class="sub" style="margin-top:4px">Apply: ${esc(x.apply)}</div>` : ""}</div>`).join("") : `<p class="sub">Switch on sites in the Sites tab.</p>`}</div>
  <div class="card"><h3>2. Prepare a resume for a job</h3>
    <div class="grid"><div><label>Company</label><input type="text" id="mCompany"></div><div><label>Role</label><input type="text" id="mRole"></div>
      <div style="grid-column:1/-1"><label>Link (optional)</label><input type="text" id="mUrl" placeholder="https://…"></div>
      <div style="grid-column:1/-1"><label>The job posting (paste the text)</label><textarea id="mPosting" style="min-height:160px"></textarea></div></div>
    <div class="row" style="margin-top:10px"><button class="btn" id="mMatch">Check the match</button>
      ${state.ai.ready ? `<label class="check" style="margin:0"><input type="checkbox" id="mAi" checked> Use AI (${esc(state.ai.status.label)})</label>` : `<span class="sub">Keyword matching, no AI. <a href="#" data-go="ai">Add an AI</a> for a smarter ranking.</span>`}
      <button class="btn primary" id="mPrep">Make the PDF and log it</button></div>
    <div id="mOut" style="margin-top:12px"></div></div>`;
  const body = () => ({ company: $("#mCompany").value, role: $("#mRole").value, url: $("#mUrl").value.trim(), posting: $("#mPosting").value, use_ai: !!($("#mAi") && $("#mAi").checked) });
  const show = (html) => { $("#mOut").innerHTML = html; };
  const resHtml = r => `<div class="msg ${r.score >= 6 ? "ok" : "warn"}">Fit ${r.score}/10${r.ai_used ? " (AI)" : " (keywords)"}${r.reason ? ": " + esc(r.reason) : ""}</div>
    <p class="sub"><b>Your skills it asks for:</b> ${esc((r.matched || []).join(", ") || "none found")}</p>
    <p class="sub"><b>It asks for, not on your resume:</b> ${esc((r.gaps || []).join(", ") || "nothing obvious")}. Add them only if true; the Prepare tab finds courses.</p>`;
  $("#mMatch").addEventListener("click", async e => {
    e.target.disabled = true; show(`<p class="sub">Checking…</p>`);
    try { const r = await api("/api/match", body()); show(r.ok ? resHtml(r) + (r.first ? `<p class="sub">Skill order for this job: ${esc(r.line_order.map(l => l + ": " + (r.first[l] || []).join(", ")).join(" · "))}</p>` : "") : `<div class="msg bad">${esc(r.error)}</div>`); }
    catch (err) { show(`<div class="msg bad">${esc(err.message)}</div>`); } finally { e.target.disabled = false; }
  });
  $("#mPrep").addEventListener("click", async e => {
    e.target.disabled = true; show(`<p class="sub">Making the PDF… (10–30 seconds)</p>`);
    try {
      const r = await api("/api/match/prepare", body());
      if (!r.ok) return show(`<div class="msg bad">${esc(r.error)}</div>`);
      if (r.duplicate) return show(`<div class="msg warn">Already in your log: ${esc(r.duplicate)}</div>`);
      show(resHtml(r) + `<div class="msg ok">Ready: <code>${esc(r.folder)}/${esc(r.pdf)}</code> · logged as #${esc(r.id)} (manual). Apply on the site, then set it to <i>sent</i> in Applications.</div>`);
    } catch (err) { show(`<div class="msg bad">${esc(err.message)}</div>`); } finally { e.target.disabled = false; }
  });
};
