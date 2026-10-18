/* Home page: every covered competition as a card, filtered by sport. */
(async () => {
  const params = new URLSearchParams(location.search);
  let sport = params.get("sport") || SP.settings().start;
  SP.header(params.get("sport") || "");
  const filters = document.getElementById("filters");
  const sections = document.getElementById("sections");
  let index;
  try { index = await SP.json("data/index.json"); }
  catch (e) { sections.innerHTML = `<div class="empty">No predictions yet. Run <code>python3 -m pipeline.build</code> first.</div>`; return; }
  SP.footer(index.updated);
  let digest = { matches: [], movers: [] };
  try { digest = await SP.json("data/today.json"); } catch (e) { /* optional */ }
  let allMatches = false;

  const ORDER = { live: 0, upcoming: 1, finished: 2 };
  const GROUP_ORDER = ["european", "domestic", "international", "qualifying", "atp-slam", "wta-slam", "atp-finals", "wta-finals", "atp-1000", "wta-1000"];

  function card(c) {
    const href = `competition.html?sport=${c.sport}&id=${encodeURIComponent(c.id)}`;
    const sub = c.sport === "tennis"
      ? `${SP.date(c.start)} – ${SP.date(c.end)}${c.surface ? " · " + SP.esc(c.surface) : ""}`
      : `${SP.esc(c.season || "")}`;
    let body;
    if (c.status === "finished" && (c.champion || c.favourite)) {
      body = `<div class="fav"><span class="who">🏆 ${SP.esc(c.champion || c.favourite.name)}</span><span class="muted small">Champion</span></div>`;
    } else if (c.favourite) {
      body = `<div class="fav"><span class="who">${SP.esc(c.favourite.name)}</span><span class="pct">${SP.prob(c.favourite.p)}</span></div>
        ${c.format === "qualifying" ? `<div class="muted small" style="margin-top:-8px">Likeliest to qualify</div>` : ""}<div class="meter" title="Chance to win"><i style="width:${Math.max(2, c.favourite.p * 100)}%"></i></div>${c.projected ? `<div class="muted small">Projected field · draw not out yet</div>` : ""}`;
    } else {
      body = `<div class="muted small">Odds appear once the draw is out.</div>`;
    }
    const next = c.status !== "finished" && c.next_match ? `<div class="muted small">Next: ${SP.esc(SP.when(c.next_match))}</div>` : "";
    return `<a class="card" href="${href}">
      <div class="card-head">${SP.tagFor(c)}<span class="status ${c.status}">${c.status === "live" ? "Live" : c.status === "upcoming" ? "Upcoming" : "Finished"}</span></div>
      <div><h3>${SP.esc(c.name)}</h3><div class="muted small">${sub}</div></div>
      ${body}${next}</a>`;
  }

  function link(m) { return `competition.html?sport=${m.sport}&id=${encodeURIComponent(m.id)}`; }

  // today's matches everywhere, and whose odds moved most since the day before
  function digestHtml() {
    const pick = x => sport === "all" || x.sport === sport;
    const matches = (digest.matches || []).filter(pick), movers = (digest.movers || []).filter(pick);
    let html = "";
    if (matches.length) {
      const shown = allMatches ? matches : matches.slice(0, 8);
      html += `<h2>Coming up in the next day or so</h2><div class="matches">${shown.map(m => {
        const tag = SP.tagFor({ id: m.id, group: m.group, sport: m.sport, country: m.country });
        const home = m.home || m.a, away = m.away || m.b;
        const p = Array.isArray(m.p) ? m.p : [m.p, 0, 1 - m.p];
        const call = p[0] >= p[2] ? (p[0] >= p[1] ? home : "Draw") : (p[2] >= p[1] ? away : "Draw");
        const best = Math.max(...p);
        return `<a class="match today" href="${link(m)}"><div class="when">${SP.esc(SP.when(m.date))}${m.live ? ' <span class="status live">Live</span>' : ""}</div>
          <div class="teams"><span>${SP.esc(home)}</span><span class="muted small">v</span><span>${SP.esc(away)}</span></div>
          <div class="meta">${tag}<span>Pick: <b>${SP.esc(call)}</b> ${SP.prob(best)}</span></div></a>`;
      }).join("")}</div>${matches.length > 8 ? `<p><button class="chip" id="more-matches">${allMatches ? "Show fewer" : `Show all ${matches.length}`}</button></p>` : ""}`;
    }
    if (movers.length) {
      html += `<h2>Biggest moves since yesterday</h2><div class="movers">${movers.map(m => {
        const up = m.after > m.before;
        return `<a class="mover" href="${link(m)}"><span class="arrow" aria-hidden="true">${up ? "▲" : "▼"}</span>
          <span><b>${SP.esc(m.team)}</b><span class="muted small"> · ${SP.esc(m.comp)}</span></span>
          <span class="num">${SP.prob(m.before)} → <b>${SP.prob(m.after)}</b><span class="sr"> chance to ${m.what}, ${up ? "up" : "down"}</span></span></a>`;
      }).join("")}</div>`;
    }
    return html;
  }

  function render() {
    filters.innerHTML = [["all", "Everything"], ["soccer", "Soccer"], ["tennis", "Tennis"]]
      .map(([v, t]) => `<button class="chip ${sport === v ? "on" : ""}" data-v="${v}">${t}</button>`).join("");
    const hide = SP.settings().finished === "hide";
    const list = index.competitions
      .filter(c => sport === "all" || c.sport === sport)
      .filter(c => !(hide && c.status === "finished"))
      .sort((a, b) => (ORDER[a.status] - ORDER[b.status])
        || (GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group))
        || String(a.next_match || "").localeCompare(String(b.next_match || "")));
    const blocks = [["soccer", "Soccer"], ["tennis", "Tennis"]].filter(([s]) => sport === "all" || sport === s).map(([s, title]) => {
      const items = list.filter(c => c.sport === s);
      return `<h2>${title}</h2>` + (items.length ? `<div class="grid">${items.map(card).join("")}</div>`
        : `<div class="empty">Nothing ${s === "tennis" ? "on the ATP/WTA 1000 or Grand Slam calendar" : "in play"} right now.</div>`);
    });
    sections.innerHTML = digestHtml() + blocks.join("");
    const more = document.getElementById("more-matches");
    if (more) more.onclick = () => { allMatches = !allMatches; render(); };
  }
  filters.addEventListener("click", e => {
    const b = e.target.closest(".chip"); if (!b) return;
    sport = b.dataset.v;
    history.replaceState(null, "", sport === "all" ? "index.html" : `index.html?sport=${sport}`);
    render();
  });
  // find a team or player across every competition
  const find = document.getElementById("find"), found = document.getElementById("found");
  let people = null;
  const fold = t => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  async function search() {
    const q = fold(find.value.trim());
    if (q.length < 2) { found.hidden = true; return; }
    if (!people) {
      try { people = (await SP.json("data/search.json")).map(p => Object.assign(p, { key: fold(p.n) })); }
      catch (e) { people = []; }
    }
    const hits = people.filter(p => p.key.includes(q))
      .sort((a, b) => (a.key.startsWith(q) ? 0 : 1) - (b.key.startsWith(q) ? 0 : 1) || a.n.localeCompare(b.n)).slice(0, 12);
    found.innerHTML = hits.length ? hits.map(p => `<div class="hit"><b>${SP.esc(p.n)}</b>${p.in.map(e =>
      `<a href="competition.html?sport=${e.sport}&id=${encodeURIComponent(e.id)}">${SP.esc(e.name)} · ${e.out ? "out" : SP.prob(e.p) + " to " + e.what}</a>`).join("")}</div>`).join("")
      : `<div class="none">No team or player called “${SP.esc(find.value.trim())}” in the current competitions.</div>`;
    found.hidden = false;
  }
  find.addEventListener("input", search);
  find.addEventListener("keydown", e => { if (e.key === "Escape") { find.value = ""; found.hidden = true; } });
  document.addEventListener("click", e => { if (!e.target.closest(".search")) found.hidden = true; });

  SP.onChange(render);
  render();
})();
