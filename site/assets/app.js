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
    "international": [232, 52, "International"], "qualifying": [212, 62, "WC Qualifying"],
    "atp-slam": [22, 78, "ATP · Grand Slam"], "atp-1000": [38, 82, "ATP · 1000"],
    "atp-finals": [50, 85, "ATP · Finals"],
    "wta-slam": [345, 62, "WTA · Grand Slam"], "wta-1000": [322, 52, "WTA · 1000"], "wta-finals": [298, 45, "WTA · Finals"],
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
  function time(iso) {
    const d = parseIso(iso), opts = { hour: "2-digit", minute: "2-digit" };
    if (settings.times === "utc") opts.timeZone = "UTC";
    return isNaN(d) ? "" : d.toLocaleTimeString(undefined, opts) + (settings.times === "utc" ? " UTC" : "");
  }
  // calendar day in the viewer's chosen time zone, for grouping
  function dayKey(iso) {
    const d = parseIso(iso);
    return isNaN(d) ? "" : d.toLocaleDateString("en-CA", settings.times === "utc" ? { timeZone: "UTC" } : {});
  }

  let offline = false;
  async function json(path) {
    let r;
    try { r = await fetch(path, { cache: "no-cache" }); }
    catch (e) {
      // no connection: use the last copy this browser (or the Mac app) has, and say so
      r = await fetch(path, { cache: "force-cache" });
      offline = true;
    }
    if (!r.ok) throw new Error(path + " " + r.status);
    if (r.headers.get("X-SportsPred-Cache")) offline = true;  // answered by the offline cache (sw.js)
    return r.json();
  }

  // installable, and readable offline (not inside the Mac app, which has its own cache)
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost") && !/SportsPredMac/.test(navigator.userAgent)) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
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
    buildShortcuts();
    document.addEventListener("keydown", e => {
      if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); openSettings(); return; }
      const typing = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "") || document.querySelector("dialog[open]");
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "?") { e.preventDefault(); openShortcuts(); }
      // "/" searches: the home page has its own box; anywhere else, go there
      else if (e.key === "/" && !document.getElementById("find")) { e.preventDefault(); location.href = "index.html?find"; }
    });
  }

  /* ---------- keyboard shortcuts (press ?) ---------- */
  const inMacApp = /SportsPredMac/.test(navigator.userAgent);
  function buildShortcuts() {
    const mod = isMac ? "⌘" : "Ctrl+";
    const rows = [
      ["?", "Show these shortcuts"],
      ["/", "Find a team, player or competition"],
      ["↑ ↓ · Enter · Esc", "Move through search results, open one, clear the search"],
      [mod + ",", "Settings"],
    ].concat(inMacApp ? [
      ["⌘F", "Find a team or player"], ["⌘1 · ⌘2 · ⌘3", "Soccer · Tennis · How It Works"], ["⇧⌘H", "Home"],
      ["⌘[ · ⌘]", "Back · Forward"], ["⌘R", "Reload"], ["⌘+ · ⌘− · ⌘0", "Zoom in · out · actual size"],
      ["⇧⌘C", "Copy a link to this page"], ["⌥⌘O", "Open this page in your browser"],
    ] : []);
    const d = document.createElement("dialog");
    d.id = "shortcuts";
    d.innerHTML = `<div class="dlg-head"><h3>Keyboard shortcuts</h3><button class="icon-btn" data-close aria-label="Close">✕</button></div>
      <div class="dlg-body"><table class="keys"><tbody>${rows.map(([k, what]) => `<tr><td>${k.split(" · ").map(x => x.split(" ").map(y => `<kbd>${esc(y)}</kbd>`).join(" ")).join(" / ")}</td><td>${esc(what)}</td></tr>`).join("")}</tbody></table></div>`;
    document.body.appendChild(d);
    d.querySelector("[data-close]").onclick = () => d.close();
    d.addEventListener("click", e => { if (e.target === d) d.close(); });
  }
  function openShortcuts() { const d = document.getElementById("shortcuts"); if (d && !d.open) d.showModal(); }

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
        <p class="muted small" style="margin:0">Saved in this browser. Press ${isMac ? "⌘," : "Ctrl+,"} to open settings anywhere, or <button type="button" class="linkish" id="show-keys">?</button> for every keyboard shortcut.</p>
      </div>`;
    document.body.appendChild(d);
    d.querySelector("[data-close]").onclick = () => d.close();
    d.addEventListener("click", e => { if (e.target === d) d.close(); });
    d.querySelector("#show-keys").onclick = () => { d.close(); openShortcuts(); };
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

  function parseIso(iso) { return new Date(iso && iso.length === 17 ? iso.replace("Z", ":00Z") : iso); }
  function ago(iso) {
    const mins = Math.round((Date.now() - parseIso(iso)) / 60000);
    if (!(mins >= 0)) return "";
    if (mins < 2) return "just now";
    if (mins < 60) return `${mins} minutes ago`;
    const h = Math.round(mins / 60);
    return h < 48 ? `${h} hour${h > 1 ? "s" : ""} ago` : `${Math.round(h / 24)} days ago`;
  }
  const STALE_HOURS = 6;

  /* ---------- following teams and players (kept in this browser only) ---------- */
  const FOLLOW = "sportspred.follow";
  function following() {
    try { return new Set(JSON.parse(localStorage.getItem(FOLLOW) || "[]")); } catch (e) { return new Set(); }
  }
  function toggleFollow(name) {
    const f = following();
    f.has(name) ? f.delete(name) : f.add(name);
    try { localStorage.setItem(FOLLOW, JSON.stringify([...f])); } catch (e) { /* private mode */ }
    listeners.forEach(fn => fn(settings));
    tellMacApp();
    return f.has(name);
  }
  // the Mac app lists followed teams in its Your Teams menu: send it the names and their team pages
  async function tellMacApp() {
    const app = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.sportspred;
    if (!app) return;
    let files = {};
    try { files = await json("data/teams.json"); } catch (e) { /* offline: names only */ }
    const ids = Object.entries(files);
    app.postMessage([...following()].map(name => ({ name, id: (ids.find(([k]) => k.startsWith(name + "|")) || [])[1] || "" })));
  }
  if (/SportsPredMac/.test(navigator.userAgent)) tellMacApp();
  function starButton(name) {
    const on = following().has(name);
    return `<button class="star${on ? " on" : ""}" type="button" data-follow="${esc(name)}" aria-pressed="${on}"
      title="${on ? "Stop following" : "Follow"} ${esc(name)}" aria-label="${on ? "Stop following" : "Follow"} ${esc(name)}">${on ? "★" : "☆"}</button>`;
  }
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-follow]");
    if (!b) return;
    e.preventDefault();
    toggleFollow(b.dataset.follow);
  });

  /* ---------- where a match is now, judged from the clock (data can be a few hours old) ---------- */
  function matchState(iso, liveFlag, sport) {
    const mins = (Date.now() - parseIso(iso)) / 60000;
    const length = sport === "tennis" ? 240 : 150;  // generous match lengths, in minutes
    if (!(mins >= 0)) return "upcoming";
    if (mins < length || (liveFlag && mins < length * 1.5)) return "live";
    return "done";  // probably over; the result arrives with the next update
  }

  function footer(updated) {
    const f = document.getElementById("foot");
    if (!f) return;
    f.innerHTML = `<div class="wrap">Predictions refresh about every hour from public results${updated ? ` · updated <span title="${esc(when(updated))}">${esc(ago(updated))}</span>` : ""} ·
      <a href="how.html">How it works</a> · <a href="feed.xml" title="Upsets and big odds moves, for feed readers">Feed</a> · <a href="${REPO}">Source</a>. For fun and learning, not betting advice.</div>`;
    // the hourly update can be held up (GitHub delays scheduled runs); say so instead of looking current
    const hours = (Date.now() - parseIso(updated)) / 3600000;
    const main = document.querySelector("main");
    if (offline && main && !document.getElementById("offline")) {
      const note = document.createElement("div");
      note.id = "offline";
      note.className = "notice";
      note.innerHTML = `<b>You're offline.</b> Showing the predictions as they were ${esc(ago(updated) || "when you last loaded them")}.`;
      main.prepend(note);
      return;
    }
    if (updated && hours > STALE_HOURS && main && !document.getElementById("stale")) {
      const note = document.createElement("div");
      note.id = "stale";
      note.className = "notice";
      note.innerHTML = `<b>Last updated ${esc(ago(updated))}.</b> The hourly update is running late, so recent results may not be in yet.`;
      main.prepend(note);
    }
  }

  function flag(f) { return f ? `<span class="flag" aria-hidden="true">${esc(f)}</span>` : ""; }
  // court surface as a chip: clay, grass and hard each in their own colour
  function surface(s) {
    if (!s) return "";
    return `<span class="surface s-${esc(s)}"><i aria-hidden="true"></i>${esc(s[0].toUpperCase() + s.slice(1))}</span>`;
  }

  /* ---------- team and player pages ---------- */
  let teamFiles = {};
  async function loadTeams() {
    try { teamFiles = await json("data/teams.json"); } catch (e) { teamFiles = {}; }
    return teamFiles;
  }
  // a name as a link to its page when it has one, otherwise plain text
  function teamLink(name, sport) {
    const id = teamFiles[name + "|" + sport];
    return id ? `<a class="team-link" href="team.html?id=${encodeURIComponent(id)}">${esc(name)}</a>` : esc(name);
  }

  /* ---------- the maths behind a soccer match, for the detail panels and the compare tool ---------- */
  function poisson(lam, k) { let p = Math.exp(-lam); for (let i = 1; i <= k; i++) p *= lam / i; return p; }
  // Dixon-Coles: independent goals slightly miss how often games end 0-0, 1-0, 0-1 and 1-1 (as in the pipeline)
  function lowScore(lh, la, rho, h, a) {
    if (!rho || h > 1 || a > 1) return 1;
    return h === 0 && a === 0 ? 1 - lh * la * rho : h === 0 ? 1 + lh * rho : a === 0 ? 1 + la * rho : 1 - rho;
  }
  // chance of each score, over a 12 x 12 grid that sums to 1; `max` trims what's returned
  function scoreGrid(lh, la, max = 6, rho = 0) {
    const full = [];
    let sum = 0;
    for (let h = 0; h < 12; h++) { full.push([]); for (let a = 0; a < 12; a++) { const p = poisson(lh, h) * poisson(la, a) * lowScore(lh, la, rho, h, a); full[h].push(p); sum += p; } }
    return full.slice(0, max).map(row => row.slice(0, max).map(p => p / sum));
  }
  function outcomeProbs(lh, la, rho = 0) {
    const g = scoreGrid(lh, la, 12, rho);
    let h = 0, d = 0, a = 0;
    g.forEach((row, i) => row.forEach((p, j) => { if (i > j) h += p; else if (i === j) d += p; else a += p; }));
    return [h, d, a];
  }
  // a small heatmap of likely scores (one hue, light to dark), with the numbers written in each cell
  function scoreGridHtml(lh, la, home, away, rho = 0) {
    const g = scoreGrid(lh, la, 6, rho), top = Math.max(...g.flat());
    return `<table class="grid-scores" aria-label="Chance of each score"><caption class="small muted">Chance of each score (${esc(home)} down, ${esc(away)} across)</caption>
      <thead><tr><th><span class="sr">${esc(home)} goals down, ${esc(away)} goals across</span></th>${g[0].map((_, a) => `<th>${a}</th>`).join("")}</tr></thead><tbody>
      ${g.map((row, h) => `<tr><th>${h}</th>${row.map(p => { const t = p / top;
        return `<td style="--t:${t.toFixed(3)}" title="${h}–${row.indexOf(p)}">${p >= 0.005 ? Math.round(p * 100) + "%" : ""}</td>`; }).join("")}</tr>`).join("")}
      </tbody></table>`;
  }

  /* ---------- one place for how a result is judged (competition and team pages share it) ---------- */
  const UPSET = 0.25;  // a result we gave less than this is an upset
  // the chance we gave to what actually happened
  function happenedProb(m, sport) {
    if (sport === "tennis") return m.w === 0 ? m.p : 1 - m.p;
    const o = m.hg > m.ag ? 0 : m.hg === m.ag ? 1 : 2;
    return m.p[o];
  }
  function verdict(m, sport) {
    const p = happenedProb(m, sport);
    if (p < UPSET) return { kind: "upset", p, text: "Upset" };
    return m.called ? { kind: "yes", p, text: "Called it" } : { kind: "no", p, text: "Missed" };
  }
  function verdictBadge(m, sport) {
    const v = verdict(m, sport);
    return v.kind === "upset" ? `<span class="badge upset" title="We gave this ${prob(v.p)}">Upset · ${prob(v.p)}</span>`
      : `<span class="called ${v.kind}">${v.text}</span>`;
  }

  return { settings: () => settings, onChange, header, footer, tagFor, esc, prob, when, date, time, dayKey, json, REPO,
    happenedProb, verdict, verdictBadge,
    following, toggleFollow, starButton, matchState, flag, surface, ago, loadTeams, teamLink, scoreGrid, scoreGridHtml, outcomeProbs, lowScore };
})();
