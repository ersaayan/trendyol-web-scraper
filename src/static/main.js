async function startJob(e) {
  e.preventDefault();
  const form = e.target;
  const btn = document.getElementById("job-submit");
  if (btn) {
    btn.disabled = true;
    btn.dataset.prev = btn.textContent;
    btn.textContent = "Başlatılıyor...";
  }
  const payload = {
    url: form.url.value,
    max_pages: Number(form.max_pages.value || 50),
    max_items: form.max_items.value ? Number(form.max_items.value) : null,
    out: form.out.value || "output-ui.ndjson",
    fmt: form.fmt.value,
    checkpoint: form.checkpoint.value || ".checkpoints/ui.json",
    resume: form.resume.value === "true",
    delay_ms: Number(form.delay_ms.value || 800),
    log_level: form.log_level.value || "INFO",
  };
  const res = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    toast("İş başlatılamadı", "danger");
    if (btn) {
      btn.disabled = false;
      btn.textContent = btn.dataset.prev || "Başlat";
    }
    return;
  }
  await refreshJobs();
  if (btn) {
    btn.disabled = false;
    btn.textContent = btn.dataset.prev || "Başlat";
  }
}

async function refreshJobs() {
  const res = await fetch("/api/jobs");
  const data = await res.json();
  updateJobStats(data);
  const tbody = document.getElementById("jobs-body");
  tbody.innerHTML = "";
  for (const j of data) {
    const tr = document.createElement("tr");
    const statusClass = statusToClass(j.status);
    tr.innerHTML = `
      <td>${j.job_id}</td>
      <td><span class="chip ${statusClass}">${j.status}</span></td>
      <td>${j.pid ?? ""}</td>
      <td>${new Date(j.started_at * 1000).toLocaleString()}</td>
      <td><button onclick="openLogs('${j.job_id}')">Görüntüle</button></td>
    `;
    tbody.appendChild(tr);
  }
}

async function openLogs(jobId) {
  const res = await fetch(`/api/jobs/${jobId}/logs`);
  if (!res.ok) {
    toast("Log bulunamadı", "danger");
    return;
  }
  const data = await res.json();
  document.getElementById("log-title").innerText = jobId;
  document.getElementById("log-stdout").innerText = data.stdout || "";
  document.getElementById("log-stderr").innerText = data.stderr || "";
  document.getElementById("log-modal").showModal();
}

function closeLogs() {
  document.getElementById("log-modal").close();
}

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("job-form").addEventListener("submit", startJob);
  refreshJobs();
  setInterval(refreshJobs, 3000);
  const af = document.getElementById("analyze-form");
  if (af) {
    af.addEventListener("submit", startAnalysis);
  }
  refreshRecentAnalysis();
  setInterval(refreshRecentAnalysis, 5000);

  // Theme init
  const saved = localStorage.getItem("theme") || "light";
  setTheme(saved);
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const next =
        document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      setTheme(next);
    });
  }

  // Sekmeler
  initTabs();

  // LLM mini tabs
  initMiniTabs();

  // Analiz girdi dosyaları
  try {
    fillInputSelect();
  } catch {}
  const manualToggle = document.getElementById("manual-toggle");
  const manualInput = document.getElementById("inp-manual");
  const inpSelect = document.getElementById("inp-select");
  if (manualToggle && manualInput && inpSelect) {
    manualToggle.addEventListener("change", () => {
      const on = manualToggle.checked;
      manualInput.disabled = !on;
      inpSelect.disabled = on;
    });
  }
  // PDP tab wiring (outside of manual toggle handler)
  const pdpForm = document.getElementById("pdp-form");
  if (pdpForm) pdpForm.addEventListener("submit", startPDPJob);
  fillPDPSelect();
  const pdpPrev = document.getElementById("pdp-preview");
  if (pdpPrev) pdpPrev.addEventListener("click", previewPDP);
  const pdpScoreBtn = document.getElementById("pdp-score");
  if (pdpScoreBtn) pdpScoreBtn.addEventListener("click", startPDPScore);
  const pdpPrevScored = document.getElementById("pdp-preview-scored");
  if (pdpPrevScored) pdpPrevScored.addEventListener("click", previewPDPScored);
  const pdpRefresh = document.getElementById("pdp-refresh");
  if (pdpRefresh) pdpRefresh.addEventListener("click", fillPDPSelect);
  const refreshBtn = document.getElementById("refresh-inputs");
  if (refreshBtn) refreshBtn.addEventListener("click", () => fillInputSelect());
});

async function startAnalysis(e) {
  e.preventDefault();
  const form = e.target;
  const btn = document.getElementById("analyze-submit");
  if (btn) {
    btn.disabled = true;
    btn.dataset.prev = btn.textContent;
    btn.textContent = "Çalışıyor...";
  }
  const useManual = document.getElementById("manual-toggle")?.checked;
  const inp = useManual
    ? document.getElementById("inp-manual").value
    : document.getElementById("inp-select").value;
  const payload = {
    inp,
    format: form.format.value,
    commission: Number(form.commission.value),
    default_cost: Number(form.default_cost.value),
    tiers: form.tiers.value,
    margins: form.margins.value,
    out_dir: form.out_dir.value || "analysis",
    use_llm: (form.use_llm.value || "false") === "true",
    llm_model: form.llm_model.value || null,
  };
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    toast("Analiz başlatılamadı", "danger");
    if (btn) {
      btn.disabled = false;
      btn.textContent = btn.dataset.prev || "Analizi Başlat";
    }
    return;
  }
  refreshRecentAnalysis();
  if (btn) {
    btn.disabled = false;
    btn.textContent = btn.dataset.prev || "Analizi Başlat";
  }
}

async function refreshRecentAnalysis() {
  const res = await fetch("/api/analysis/recent");
  if (!res.ok) return;
  const items = await res.json();
  const ul = document.getElementById("recent-analysis");
  if (!ul) return;
  ul.innerHTML = "";
  for (const f of items) {
    const li = document.createElement("li");
    if (f.type === "json") {
      const a = document.createElement("a");
      a.href = `/${f.path}`.replace(/^\/+/, "/");
      a.innerHTML = `${f.name} <span class="chip muted">${f.type}</span>`;
      a.addEventListener("click", async (ev) => {
        ev.preventDefault();
        try {
          const res = await fetch(a.href);
          if (!res.ok) throw new Error("Dosya okunamadı");
          const data = await res.json();
          const llm = data.llm;
          openLLMModal(llm);
        } catch (e) {
          toast(String(e), "danger");
        }
      });
      li.appendChild(a);
    } else if (f.type === "md") {
      const a = document.createElement("a");
      a.href = `/${f.path}`.replace(/^\/+/, "/");
      a.innerHTML = `${f.name} <span class=\"chip muted\">${f.type}</span>`;
      a.addEventListener("click", async (ev) => {
        ev.preventDefault();
        try {
          const res = await fetch(a.href);
          const text = await res.text();
          renderMarkdown(text);
          document.getElementById("md-modal").showModal();
        } catch (e) {
          toast(String(e), "danger");
        }
      });
      li.appendChild(a);
    } else {
      const a = document.createElement("a");
      a.href = `/${f.path}`.replace(/^\/+/, "/");
      a.innerHTML = `${f.name} <span class="chip muted">${f.type}</span>`;
      a.target = "_blank";
      li.appendChild(a);
    }
    ul.appendChild(li);
  }
}

function closeLLM() {
  document.getElementById("llm-modal").close();
}

function openLLMModal(llm) {
  const mdEl = document.getElementById("llm-markdown");
  const jsonEl = document.getElementById("llm-json");
  if (!mdEl || !jsonEl) return;
  if (!llm) {
    mdEl.innerHTML = `<p class="muted">LLM verisi yok</p>`;
    jsonEl.textContent = "";
  } else {
    const output = llm.output;
    // Prefer human-readable markdown-ish text if provided
    const raw =
      typeof output === "string" ? output : (output && output.raw) || null;
    if (raw) {
      renderMarkdownTo("llm-markdown", raw);
    } else {
      // If no raw text, try to pretty print any object fields
      const fallbackMd = `\n## LLM Çıktısı (Özet)\n\n\n${escapeHtml(
        JSON.stringify(
          output ?? (llm.error ? { error: llm.error } : {}),
          null,
          2
        )
      )}`;
      renderMarkdownTo("llm-markdown", fallbackMd);
    }
    jsonEl.textContent = JSON.stringify(
      output ?? (llm.error ? { error: llm.error } : {}),
      null,
      2
    );
  }
  // default to markdown tab
  activateMiniTab("llm-markdown");
  document.getElementById("llm-modal").showModal();
}

function statusToClass(status) {
  switch ((status || "").toLowerCase()) {
    case "succeeded":
      return "success";
    case "failed":
      return "danger";
    case "running":
      return "running";
    default:
      return "muted";
  }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.textContent = theme === "dark" ? "☀️ Aydınlık" : "🌙 Karanlık";
  }
}

// Sekmeler kontrolü
function initTabs() {
  const links = document.querySelectorAll(".tabs a");
  const panes = document.querySelectorAll(".tab-pane");
  function activate(name) {
    panes.forEach((p) => {
      const isActive = p.id === `tab-${name}`;
      p.classList.toggle("active", isActive);
      p.toggleAttribute("hidden", !isActive);
      p.setAttribute("aria-hidden", String(!isActive));
    });
    links.forEach((a) => {
      const sel = a.dataset.tab === name;
      a.classList.toggle("active", sel);
      a.setAttribute("aria-selected", String(sel));
    });
  }
  function fromHash() {
    const name = location.hash.replace("#", "") || "scrape";
    activate(name);
  }
  links.forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const name = e.currentTarget.dataset.tab;
      if (name) {
        history.replaceState(null, "", `#${name}`);
        activate(name);
      }
    })
  );
  window.addEventListener("hashchange", fromHash);
  fromHash();
}

async function fillInputSelect() {
  const sel = document.getElementById("inp-select");
  if (!sel) return;
  sel.innerHTML = `<option value="">Yükleniyor...</option>`;
  try {
    const res = await fetch("/api/outputs/recent");
    if (!res.ok) throw new Error("Liste alınamadı");
    const items = await res.json();
    sel.innerHTML = "";
    if (!items.length) {
      sel.innerHTML = '<option value="">Bulunamadı</option>';
      return;
    }
    for (const f of items) {
      const label = `${f.name} • ${(f.size / 1024).toFixed(1)} KB`;
      const opt = document.createElement("option");
      opt.value = f.path;
      opt.textContent = label;
      sel.appendChild(opt);
    }
  } catch (e) {
    sel.innerHTML = '<option value="">Hata</option>';
    toast("Girdi dosyaları yüklenemedi", "danger");
  }
}

function closeMD() {
  document.getElementById("md-modal").close();
}

// Minimal markdown dönüştürücü (güvenli alt küme)
function renderMarkdown(md) {
  const el = document.getElementById("md-content");
  if (!el) return;
  const esc = (s) =>
    s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  // code blocks first
  let tmp = [];
  md = md.replace(/```([\s\S]*?)```/g, (_, code) => {
    const token = `__CODE_${tmp.length}__`;
    tmp.push(`<pre><code>${esc(code)}</code></pre>`);
    return token;
  });
  let html = md
    .replace(/^### (.*)$/gim, "<h3>$1</h3>")
    .replace(/^## (.*)$/gim, "<h2>$1</h2>")
    .replace(/^# (.*)$/gim, "<h1>$1</h1>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/^\- (.*)$/gim, "<li>$1</li>")
    .replace(/^(?!<h\d|<li)(.+)$/gim, "<p>$1</p>");
  // wrap contiguous li into ul
  html = html.replace(/(<li>.*?<\/li>)/gms, "<ul>$1</ul>");
  // restore code blocks
  tmp.forEach((block, i) => {
    html = html.replace(`__CODE_${i}__`, block);
  });
  el.innerHTML = html;
}

function renderMarkdownTo(elementId, md) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const esc = (s) =>
    s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  let tmp = [];
  md = md.replace(/```([\s\S]*?)```/g, (_, code) => {
    const token = `__CODE_${tmp.length}__`;
    tmp.push(`<pre><code>${esc(code)}</code></pre>`);
    return token;
  });
  let html = md
    .replace(/^### (.*)$/gim, "<h3>$1</h3>")
    .replace(/^## (.*)$/gim, "<h2>$1</h2>")
    .replace(/^# (.*)$/gim, "<h1>$1</h1>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/^\- (.*)$/gim, "<li>$1</li>")
    .replace(/^(?!<h\d|<li)(.+)$/gim, "<p>$1</p>");
  html = html.replace(/(<li>.*?<\/li>)/gms, "<ul>$1</ul>");
  tmp.forEach((block, i) => {
    html = html.replace(`__CODE_${i}__`, block);
  });
  el.innerHTML = html;
}

function initMiniTabs() {
  const buttons = document.querySelectorAll("#llm-modal .mini-tab");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.target;
      activateMiniTab(target);
    });
  });
}

function activateMiniTab(targetId) {
  const buttons = document.querySelectorAll("#llm-modal .mini-tab");
  const panels = ["llm-markdown", "llm-json"];
  buttons.forEach((b) =>
    b.classList.toggle("active", b.dataset.target === targetId)
  );
  panels.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    const isActive = id === targetId;
    el.toggleAttribute("hidden", !isActive);
  });
}

function escapeHtml(s) {
  return String(s).replace(
    /[&<>]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])
  );
}

// Stats
function updateJobStats(jobs) {
  try {
    const total = jobs.length;
    const running = jobs.filter(
      (j) => (j.status || "").toLowerCase() === "running"
    ).length;
    const succeeded = jobs.filter(
      (j) => (j.status || "").toLowerCase() === "succeeded"
    ).length;
    const failed = jobs.filter(
      (j) => (j.status || "").toLowerCase() === "failed"
    ).length;
    setText("#stat-total", total);
    setText("#stat-running", running);
    setText("#stat-succeeded", succeeded);
    setText("#stat-failed", failed);
  } catch {}
}

function setText(sel, val) {
  const el = document.querySelector(sel);
  if (el) el.textContent = String(val);
}

// Toasts
function toast(message, kind = "info", timeout = 2500) {
  const c = document.getElementById("toast-container");
  if (!c) return alert(message);
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.setAttribute("role", "status");
  t.textContent = message;
  c.appendChild(t);
  requestAnimationFrame(() => t.classList.add("show"));
  setTimeout(() => {
    t.classList.remove("show");
    t.classList.add("hide");
    setTimeout(() => t.remove(), 300);
  }, timeout);
}

// LLM Copy
async function copyLLM() {
  const md = document.getElementById("llm-markdown");
  const json = document.getElementById("llm-json");
  // Copy active panel content
  const isJsonActive = json && !json.hasAttribute("hidden");
  const text = isJsonActive ? json.textContent || "" : md?.innerText || "";
  try {
    await navigator.clipboard.writeText(text);
    toast("LLM içeriği kopyalandı");
  } catch (e) {
    toast("Kopyalama başarısız", "danger");
  }
}

// ---------------- PDP helpers ----------------
async function startPDPJob(e) {
  e.preventDefault();
  const form = e.target;
  const btn = document.getElementById("pdp-submit");
  if (btn) {
    btn.disabled = true;
    btn.dataset.prev = btn.textContent;
    btn.textContent = "Başlatılıyor...";
  }
  const urls = (form.urls.value || "")
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const payload = {
    urls,
    out: form.out.value || "pdp.ndjson",
    delay_ms: Number(form.delay_ms.value || 800),
    log_level: form.log_level.value || "INFO",
  };
  const res = await fetch("/api/pdp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    toast("PDP işi başlatılamadı", "danger");
  } else {
    toast("PDP işi başlatıldı", "success");
    // refresh lists so the new file appears soon
    setTimeout(fillPDPSelect, 800);
    setTimeout(fillInputSelect, 800);
  }
  if (btn) {
    btn.disabled = false;
    btn.textContent = btn.dataset.prev || "PDP İşini Başlat";
  }
}

async function fillPDPSelect() {
  const sel = document.getElementById("pdp-select");
  if (!sel) return;
  sel.innerHTML = `<option value="">Yükleniyor...</option>`;
  try {
    const res = await fetch("/api/outputs/recent");
    if (!res.ok) throw new Error("Liste alınamadı");
    const items = (await res.json()).filter((x) => x.type === "ndjson");
    sel.innerHTML = "";
    if (!items.length) {
      sel.innerHTML = '<option value="">Bulunamadı</option>';
      return;
    }
    for (const f of items) {
      const opt = document.createElement("option");
      opt.value = f.path;
      opt.textContent = `${f.name} • ${(f.size / 1024).toFixed(1)} KB`;
      sel.appendChild(opt);
    }
  } catch (e) {
    sel.innerHTML = '<option value="">Hata</option>';
  }
}

async function previewPDP() {
  const sel = document.getElementById("pdp-select");
  const out = document.getElementById("pdp-preview-content");
  const tableWrap = document.getElementById("pdp-preview-table-wrap");
  const tbody = document.getElementById("pdp-table-body");
  if (!sel || (!out && !tbody)) return;
  const path = sel.value;
  if (!path) return;
  if (out) out.textContent = "Yükleniyor...";
  try {
    const res = await fetch(
      `/api/ndjson?path=${encodeURIComponent(path)}&limit=50`
    );
    if (!res.ok) throw new Error("Önizleme alınamadı");
    const data = await res.json();
    // Render structured table if container exists
    if (tbody) {
      renderPDPTable(tbody, data.items || []);
      if (tableWrap) tableWrap.removeAttribute("hidden");
      if (out) out.textContent = "";
    } else if (out) {
      out.textContent = JSON.stringify(data, null, 2);
    }
  } catch (e) {
    if (out) out.textContent = String(e);
  }
}

async function startPDPScore() {
  const sel = document.getElementById("pdp-select");
  if (!sel || !sel.value) return toast("PDP dosyası seçin", "danger");
  const base = sel.value;
  const out = base.endsWith("-scored.ndjson")
    ? base
    : base.replace(/\.ndjson$/i, "-scored.ndjson");
  const body = { inp: base, out };
  const res = await fetch("/api/pdp/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) return toast("Skorlama başlatılamadı", "danger");
  toast("Skorlama başlatıldı", "success");
}

function renderPDPTable(tbody, items) {
  tbody.innerHTML = "";
  for (const it of items) {
    const tr = document.createElement("tr");
    const price =
      it.price != null
        ? Number(it.price).toLocaleString("tr-TR", {
            style: "currency",
            currency: "TRY",
          })
        : "-";
    const rating =
      it.rating != null ? `${it.rating} (${it.ratingCount || 0})` : "-";
    const badges = Array.isArray(it.badges)
      ? it.badges.slice(0, 3).join(", ")
      : "";
    const seller = it.seller || "";
    const brand = it.brand || "";
    const name = it.name || "";
    tr.innerHTML = `
      <td>${it.productId ?? ""}</td>
      <td>${escapeHtml(brand)}</td>
      <td>${escapeHtml(name)}</td>
      <td>${price}</td>
      <td>${rating}</td>
      <td>${escapeHtml(seller)}</td>
      <td>${escapeHtml(badges)}</td>
      <td><button class="secondary" data-action="view-json">Detay</button></td>
    `;
    tr.querySelector('[data-action="view-json"]').addEventListener(
      "click",
      () => openJSONModal(it)
    );
    tbody.appendChild(tr);
  }
}

function openJSONModal(obj) {
  const pre = document.getElementById("json-detail");
  const dlg = document.getElementById("json-modal");
  if (!pre || !dlg) return;
  pre.textContent = JSON.stringify(obj, null, 2);
  dlg.showModal();
}

function closeJSON() {
  const dlg = document.getElementById("json-modal");
  if (dlg) dlg.close();
}

// ---------- PDP scored preview ----------
async function previewPDPScored() {
  const sel = document.getElementById("pdp-select");
  const out = document.getElementById("pdp-scored-preview-content");
  const tableWrap = document.getElementById("pdp-scored-table-wrap");
  const tbody = document.getElementById("pdp-scored-table-body");
  if (!sel || (!out && !tbody)) return;
  const base = sel.value;
  if (!base) return toast("Önce bir PDP dosyası seçin", "danger");
  const scored = base.endsWith("-scored.ndjson")
    ? base
    : base.replace(/\.ndjson$/i, "-scored.ndjson");
  if (out) out.textContent = "Yükleniyor...";
  try {
    const res = await fetch(
      `/api/ndjson?path=${encodeURIComponent(scored)}&limit=50`
    );
    if (!res.ok) throw new Error("Skor önizleme alınamadı");
    const data = await res.json();
    const items = data.items || [];
    if (tbody) {
      renderPDPScoredTable(tbody, items);
      if (tableWrap) tableWrap.removeAttribute("hidden");
      if (out) out.textContent = "";
    } else if (out) {
      out.textContent = JSON.stringify(data, null, 2);
    }
  } catch (e) {
    if (out) out.textContent = String(e);
  }
}

function renderPDPScoredTable(tbody, items) {
  tbody.innerHTML = "";
  for (const it of items) {
    const tr = document.createElement("tr");
    const base = it || {};
    const llm = base.llm || base.LLM || base.score || {};
    // Flexible extraction of nested outputs
    const output = llm.output || llm; // sometimes we store {llm: {output: {...}}}
    const scores = output.scores || output || {};
    const checks = output.checks || output || {};
    const product_score = pickNumber(scores, [
      "product_score",
      "productScore",
      "score",
    ]);
    const title_score = pickNumber(scores, ["title_score", "titleScore"]);
    const category_fit = pickString(checks, [
      "category_fit",
      "categoryFit",
      "fit",
    ]);
    const compliance = pickString(checks, [
      "compliance",
      "policy",
      "is_compliant",
    ]);
    tr.innerHTML = `
      <td>${base.productId ?? ""}</td>
      <td>${escapeHtml(base.brand || "")}</td>
      <td>${escapeHtml(base.name || "")}</td>
      <td>${fmtMaybe(product_score)}</td>
      <td>${fmtMaybe(title_score)}</td>
      <td>${escapeHtml(String(category_fit ?? ""))}</td>
      <td>${escapeHtml(String(compliance ?? ""))}</td>
      <td><button class="secondary" data-action="view-json">Detay</button></td>
    `;
    tr.querySelector('[data-action="view-json"]').addEventListener(
      "click",
      () => openJSONModal(it)
    );
    tbody.appendChild(tr);
  }
}

function pickNumber(obj, keys) {
  if (!obj || typeof obj !== "object") return null;
  for (const k of keys) {
    if (k in obj) {
      const v = Number(obj[k]);
      if (!Number.isNaN(v)) return v;
    }
  }
  return null;
}

function pickString(obj, keys) {
  if (!obj || typeof obj !== "object") return null;
  for (const k of keys) {
    if (k in obj) {
      const v = obj[k];
      if (v == null) continue;
      return String(v);
    }
  }
  return null;
}

function fmtMaybe(v) {
  if (v == null || Number.isNaN(v)) return "-";
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(2) : String(v);
}
