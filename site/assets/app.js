/* SportsPred shared code: header, settings (⌘,), feedback tab, tags and number formatting. */
const SP = (() => {
  const REPO = "https://github.com/amalmehta/SportsPred";
  const DEFAULTS = { theme: "system", odds: "percent", times: "local", start: "all", finished: "show" };
  const KEY = "sportspred.settings";

  function load() {
    try { return Object.assign({}, DEFAULTS, JSON.parse(localStorage.getItem(KEY) || "{}")); }
    catch (e) { return Object.assign({}, DEFAULTS); }
  }
  let settings = load();
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch (e) { /* private mode: keep in memory */ }
  }
  function applyTheme() {
    const root = document.documentElement;
    if (settings.theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", settings.theme);
  }
  applyTheme();

  const listeners = [];
  function onChange(fn) { listeners.push(fn); }
  function set(k, v) {
    settings[k] = v; save(); applyTheme();
    listeners.forEach(fn => fn(settings));
  }

  /* ---------- tags: related categories share a hue family, each its own shade ---------- */
  const TAGS = {
    "eng.1": [145, 45, "Premier League"], "esp.1": [122, 42, "La Liga"], "ita.1": [100, 48, "Serie A"],
    "ger.1": [168, 48, "Bundesliga"], "fra.1": [82, 55, "Ligue 1"],
    "uefa.champions": [192, 62, "UEFA club"], "uefa.europa": [206, 55, "UEFA club"],
    "international": [232, 52, "International"],
    "atp-slam": [22, 78, "ATP · Grand Slam"], "atp-1000": [38, 82, "ATP · 1000"],
    "wta-slam": [345, 62, "WTA · Grand Slam"], "wta-1000": [322, 52, "WTA · 1000"],
  };
  function tagFor(c) {
    const t = TAGS[c.id] || TAGS[c.group] || [0, 0, c.group || ""];
    const label = c.sport === "soccer" && c.group === "domestic" ? (c.country || t[2]) : t[2];
    return `<span class="tag" style="--h:${t[0]};--s:${t[1]}%">${esc(label)}</span>`;
  }

  /* ---------- formatting ---------- */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }
  function prob(p) {
    if (p == null) return "–";
    if (settings.odds === "decimal") return p <= 0 ? "—" : (p >= 0.995 ? "1.00" : (1 / p).toFixed(p > 0.1 ? 2 : 1));
    if (p > 0 && p < 0.005) return "<1%";
    if (p < 1 && p > 0.995) return ">99%";
    return Math.round(p * 100) + "%";
  }
  function when(iso, withTime = true) {
    if (!iso) return "";
    const d = new Date(iso.length === 17 ? iso.replace("Z", ":00Z") : iso);
    if (isNaN(d)) return iso;
    const opts = { weekday: "short", day: "numeric", month: "short" };
    if (withTime) Object.assign(opts, { hour: "2-digit", minute: "2-digit" });
    if (settings.times === "utc") opts.timeZone = "UTC";
    return d.toLocaleString(undefined, opts) + (withTime && settings.times === "utc" ? " UTC" : "");
  }
  function date(iso) { return when(iso, false); }

  async function json(path) {
    const r = await fetch(path, { cache: "no-cache" });
    if (!r.ok) throw new Error(path + " " + r.status);
    return r.json();
  }

  /* ---------- header, settings, feedback ---------- */
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  const ICON = {
    gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
    logo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l5-5 4 4 8-9"/><path d="M14 7h6v6"/></svg>',
  };

  function header(active) {
    const el = document.getElementById("top");
    el.className = "top";
    el.innerHTML = `<div class="wrap">
      <a class="brand" href="index.html">${ICON.logo}<span class="brand-text">SportsPred</span></a>
      <nav class="nav">
        <a href="index.html?sport=soccer" class="${active === "soccer" ? "on" : ""}">Soccer</a>
        <a href="index.html?sport=tennis" class="${active === "tennis" ? "on" : ""}">Tennis</a>
        <a href="how.html" class="${active === "how" ? "on" : ""}">How it works</a>
      </nav>
      <div class="spacer"></div>
      <button class="icon-btn" id="open-settings" title="Settings (${isMac ? "⌘," : "Ctrl+,"})" aria-label="Settings">
        ${ICON.gear}<kbd class="kbd-hint">${isMac ? "⌘," : "Ctrl ,"}</kbd></button>
    </div>`;
    document.getElementById("open-settings").onclick = openSettings;
    buildSettings();
    buildFeedback();
    document.addEventListener("keydown", e => {
      if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); openSettings(); }
    });
  }

  const OPTIONS = [
    ["theme", "Appearance", [["system", "System"], ["light", "Light"], ["dark", "Dark"]]],
    ["odds", "Show chances as", [["percent", "Percent (54%)"], ["decimal", "Decimal odds (1.85)"]]],
    ["times", "Kick-off times", [["local", "My time zone"], ["utc", "UTC"]]],
    ["start", "Home page shows", [["all", "Everything"], ["soccer", "Soccer"], ["tennis", "Tennis"]]],
    ["finished", "Finished events", [["show", "Show"], ["hide", "Hide"]]],
  ];
  function buildSettings() {
    const d = document.createElement("dialog");
    d.id = "settings";
    d.innerHTML = `<div class="dlg-head"><h3>Settings</h3><button class="icon-btn" data-close aria-label="Close">✕</button></div>
      <div class="dlg-body">${OPTIONS.map(([k, label, opts]) => `
        <div class="field"><label>${label}</label><div class="seg" data-key="${k}">
          ${opts.map(([v, t]) => `<button type="button" data-v="${v}">${t}</button>`).join("")}</div></div>`).join("")}
        <p class="muted small" style="margin:0">Saved in this browser. Press ${isMac ? "⌘," : "Ctrl+,"} to open settings anywhere.</p>
      </div>`;
    document.body.appendChild(d);
    d.querySelector("[data-close]").onclick = () => d.close();
    d.addEventListener("click", e => { if (e.target === d) d.close(); });
    d.querySelectorAll(".seg").forEach(seg => seg.addEventListener("click", e => {
      const b = e.target.closest("button"); if (!b) return;
      set(seg.dataset.key, b.dataset.v); paintSettings();
    }));
  }
  function paintSettings() {
    document.querySelectorAll("#settings .seg").forEach(seg => seg.querySelectorAll("button").forEach(b =>
      b.classList.toggle("on", settings[seg.dataset.key] === b.dataset.v)));
  }
  function openSettings() { paintSettings(); const d = document.getElementById("settings"); if (!d.open) d.showModal(); }

  function buildFeedback() {
    const tab = document.createElement("button");
    tab.className = "fb-tab"; tab.textContent = "Feedback"; tab.type = "button";
    const d = document.createElement("dialog");
    d.className = "fb-panel";
    d.innerHTML = `<div class="dlg-head"><h3>Send feedback</h3><button class="icon-btn" data-close aria-label="Close">✕</button></div>
      <div class="dlg-body">
        <div class="field"><label for="fb-kind">What kind?</label>
          <select id="fb-kind"><option>Idea</option><option>Bug</option><option>Wrong or missing data</option><option>Other</option></select></div>
        <div class="field"><label for="fb-text">Message</label><textarea id="fb-text" placeholder="What would make SportsPred better?"></textarea></div>
        <div><button class="btn" id="fb-send" type="button">Continue on GitHub</button>
          <span class="muted small">&nbsp;Opens a pre-filled issue; nothing is sent until you submit it there.</span></div>
      </div>`;
    document.body.append(tab, d);
    tab.onclick = () => d.showModal();
    d.querySelector("[data-close]").onclick = () => d.close();
    d.addEventListener("click", e => { if (e.target === d) d.close(); });
    d.querySelector("#fb-send").onclick = () => {
      const kind = d.querySelector("#fb-kind").value, text = d.querySelector("#fb-text").value.trim();
      const title = `[${kind}] ${text.split("\n")[0].slice(0, 70) || "Feedback"}`;
      const body = `${text}\n\n---\nPage: ${location.pathname}${location.search}`;
      window.open(`${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`, "_blank", "noopener");
      d.close();
    };
  }

  function footer(updated) {
    const f = document.getElementById("foot");
    if (!f) return;
    f.innerHTML = `<div class="wrap">Predictions refresh daily from public results${updated ? " · last update " + esc(when(updated)) : ""} ·
      <a href="how.html">How it works</a> · <a href="${REPO}">Source</a>. For fun and learning, not betting advice.</div>`;
  }

  return { settings: () => settings, onChange, header, footer, tagFor, esc, prob, when, date, json, REPO };
})();
