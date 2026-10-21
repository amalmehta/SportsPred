/* Home page: every covered competition as a card, filtered by sport. */
(async () => {
  const params = new URLSearchParams(location.search);
  let sport = params.get("sport") || SP.settings().start;
  SP.header(params.get("sport") || "");
  const filters = document.getElementById("filters");
  const sections = document.getElementById("sections");
  const summary = document.getElementById("summary");
  let index;
  try { index = await SP.json("data/index.json"); }
  catch (e) { sections.innerHTML = `<div class="empty">No predictions yet. Run <code>python3 -m pipeline.build</code> first.</div>`; return; }
  SP.footer(index.updated);
  let digest = { matches: [], movers: [] };
  try { digest = await SP.json("data/today.json"); } catch (e) { /* optional */ }
  const teamFiles = await SP.loadTeams();
  let allMatches = false;
  let people = null;
  const fold = t => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  async function loadPeople() {
    if (!people) {
      try { people = (await SP.json("data/search.json")).map(p => Object.assign(p, { key: fold(p.n) })); }
      catch (e) { people = []; }
    }
    return people;
  }

  const ORDER = { live: 0, upcoming: 1, finished: 2 };
  const GROUP_ORDER = ["european", "domestic", "international", "qualifying", "atp-slam", "wta-slam", "atp-finals", "wta-finals", "atp-1000", "wta-1000"];

  function card(c) {
    const href = `competition.html?sport=${c.sport}&id=${encodeURIComponent(c.id)}`;
    const sub = c.sport === "tennis"
      ? `${SP.esc(SP.date(c.start))} – ${SP.esc(SP.date(c.end))} ${SP.surface(c.surface)}`
      : `${SP.esc(c.season || "")}`;
    let body;
    if (c.status === "finished" && (c.champion || c.favourite)) {
      body = `<div class="fav"><span class="who">🏆 ${SP.esc(c.champion || c.favourite.name)}</span><span class="muted small">Champion</span></div>`;
    } else if (c.favourite) {
      body = `<div class="fav"><span class="who">${SP.esc(c.favourite.name)}</span><span class="pct">${SP.prob(c.favourite.p)}</span></div>
        ${c.format === "qualifying" ? `<div class="muted small" style="margin-top:-8px">Likeliest to qualify</div>` : ""}<div class="meter" title="Chance to win"><i style="width:${Math.max(2, c.favourite.p * 100)}%"></i></div>${c.second ? `<div class="second small"><span>${SP.esc(c.second.name)}</span><span>${SP.prob(c.second.p)}</span></div>` : ""}${c.projected ? `<div class="muted small">Projected field · draw not out yet</div>` : ""}`;
    } else {
      body = `<div class="muted small">Odds appear once the draw is out.</div>`;
    }
    const stale = c.stale ? `<div class="muted small">⚠︎ Not refreshed in the latest update</div>` : "";
    const next = c.status !== "finished" && c.next_match ? `<div class="muted small">Next: ${SP.esc(SP.when(c.next_match))}</div>` : "";
    return `<a class="card" href="${href}">
      <div class="card-head">${SP.tagFor(c)}<span class="status ${c.status}">${c.status === "live" ? "Live" : c.status === "upcoming" ? "Upcoming" : "Finished"}</span></div>
      <div><h3>${SP.esc(c.name)}</h3><div class="muted small">${sub}</div></div>
      ${body}${next}${stale}</a>`;
  }

  function link(m) { return `competition.html?sport=${m.sport}&id=${encodeURIComponent(m.id)}`; }

  // today's matches everywhere, and whose odds moved most since the day before
  // teams and players you follow (stars on competition pages), with their chances everywhere
  // each followed team's next game, from its team page file (fetched once, then cached here)
  const nextGame = {};
  function loadNext(mine) {
    const want = mine.filter(p => !(p.n in nextGame)).slice(0, 12);
    if (!want.length) return;
    want.forEach(p => { nextGame[p.n] = null; });
    Promise.all(want.map(p => {
      const fid = teamFiles[p.n + "|" + (p.in[0] || {}).sport];
      return fid ? SP.json(`data/teams/${encodeURIComponent(fid)}.json`).then(t => { nextGame[p.n] = (t.upcoming || [])[0] || null; }).catch(() => {}) : null;
    })).then(render);
  }
  function nextLine(name) {
    const m = nextGame[name];
    if (!m) return "";
    const tennis = m.a != null, first = tennis ? m.a === name : m.home === name;
    const opp = tennis ? (first ? m.b : m.a) : (first ? m.away : m.home);
    const win = tennis ? (first ? m.p : 1 - m.p) : (first ? m.p[0] : m.p[2]);
    return `<span class="small next-game">Next: ${tennis ? "v" : first ? "v" : "at"} ${SP.esc(opp)} · ${SP.esc(SP.when(m.date))} · <b>${SP.prob(win)}</b> to win</span>`;
  }
  function yourTeams() {
    const follow = SP.following();
    if (!follow.size) return "";
    if (!people) { loadPeople().then(render); return ""; }
    const mine = people.filter(p => follow.has(p.n));
    if (!mine.length) return "";
    loadNext(mine);
    return `<h2>Your teams</h2><div class="movers">${mine.map(p => `<div class="mover">${SP.starButton(p.n)}
      <span><b>${SP.teamLink(p.n, (p.in[0] || {}).sport)}</b>${nextLine(p.n)}</span><span class="small">${p.in.map(e =>
        `<a href="competition.html?sport=${e.sport}&id=${encodeURIComponent(e.id)}">${SP.esc(e.name)}: ${e.out ? "out" : SP.prob(e.p) + " to " + e.what}</a>`).join(" · ")}</span></div>`).join("")}</div>`;
  }

  // the closest races: competitions still being played where the favourite's lead over the runner-up is smallest
  function tightest() {
    const list = index.competitions.filter(c => c.status !== "finished" && c.favourite && c.second && c.format !== "qualifying" && !c.projected)
      .filter(c => sport === "all" || c.sport === sport)
      .sort((a, b) => (a.favourite.p - a.second.p) - (b.favourite.p - b.second.p)).slice(0, 4);
    if (list.length < 2) return "";
    return `<h2>Tightest title races</h2><div class="movers">${list.map(c => `<a class="mover" href="competition.html?sport=${c.sport}&id=${encodeURIComponent(c.id)}">
      <span class="arrow" aria-hidden="true">≈</span><span><b>${SP.esc(c.name)}</b>${c.sport === "tennis" && c.tour ? `<span class="muted small"> · ${SP.esc(c.tour)}</span>` : ""}</span>
      <span class="small">${SP.esc(c.favourite.name)} <b>${SP.prob(c.favourite.p)}</b> · ${SP.esc(c.second.name)} <b>${SP.prob(c.second.p)}</b></span></a>`).join("")}</div>`;
  }

  function digestHtml() {
    const pick = x => sport === "all" || x.sport === sport;
    // hide games that have probably finished since the last update; flag ones under way by the clock
    const matches = (digest.matches || []).filter(pick).filter(m => SP.matchState(m.date, m.live, m.sport) !== "done");
    const movers = (digest.movers || []).filter(pick);
    let html = "";
    if (matches.length) {
      const shown = allMatches ? matches : matches.slice(0, 5);
      html += `<h2>Coming up in the next day or so</h2><div class="matches">${shown.map(m => {
        const tag = SP.tagFor({ id: m.id, group: m.group, sport: m.sport, country: m.country });
        const home = m.home || m.a, away = m.away || m.b;
        const p = Array.isArray(m.p) ? m.p : [m.p, 0, 1 - m.p];
        const call = p[0] >= p[2] ? (p[0] >= p[1] ? home : "Draw") : (p[2] >= p[1] ? away : "Draw");
        const best = Math.max(...p);
        return `<a class="match today" href="${link(m)}"><div class="when">${SP.esc(SP.when(m.date))}${SP.matchState(m.date, m.live, m.sport) === "live" ? ' <span class="status live">Live</span>' : ""}</div>
          <div class="teams"><span>${SP.esc(home)}</span><span class="muted small">v</span><span>${SP.esc(away)}</span></div>
          <div class="meta">${tag}<span>Pick: <b>${SP.esc(call)}</b> ${SP.prob(best)}</span></div></a>`;
      }).join("")}</div>${matches.length > 5 ? `<p><button class="chip" id="more-matches">${allMatches ? "Show fewer" : `Show all ${matches.length}`}</button></p>` : ""}`;
    }
    const big = (digest.big || []).filter(pick);
    if (big.length) {
      html += `<h2>Big games this week</h2><div class="movers">${big.map(x => {
        const [team, v] = Object.entries(x.if)[0] || [];
        const words = team === x.home ? ["win", "draw", "lose"] : ["lose", "draw", "win"];
        const range = v ? [0, 1, 2].filter(i => v[i] != null).map(i => `${words[i]} ${SP.prob(v[i])}`).join(" · ") : "";
        return `<a class="mover" href="${link(x)}"><span class="arrow" aria-hidden="true">⚡</span>
          <span><b>${SP.esc(x.home)} v ${SP.esc(x.away)}</b><span class="muted small"> · ${SP.esc(x.comp)} · ${SP.esc(SP.when(x.date))}</span></span>
          <span class="small">${team ? `${SP.esc(team)}'s title chance: ${range}` : ""}</span></a>`;
      }).join("")}</div>`;
    }
    const upsets = (digest.upsets || []).filter(pick);
    if (upsets.length) {
      html += `<h2>Biggest upsets this week</h2><div class="movers">${upsets.map(u => `<a class="mover" href="${link(u)}">
        <span class="arrow" aria-hidden="true">!</span><span><b>${SP.esc(u.text)}</b><span class="muted small"> · ${SP.esc(u.comp)} · ${SP.esc(SP.date(u.date))}</span></span>
        <span class="small">we gave it <b>${SP.prob(u.p)}</b></span></a>`).join("")}</div>`;
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
    // your teams, then every competition, then what's on in the next day and who moved
    const live = index.competitions.filter(c => c.status === "live").length;
    const soon = (digest.matches || []).filter(m => SP.matchState(m.date, m.live, m.sport) !== "done").length;
    summary.innerHTML = `<b>${live}</b> competitions live · <b>${soon}</b> matches in the next day or so · updated ${SP.esc(SP.ago(index.updated))}`;
    sections.innerHTML = yourTeams() + blocks.join("") + tightest() + digestHtml();
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
  let active = -1;
  async function search() {
    const q = fold(find.value.trim());
    active = -1;
    if (q.length < 2) { found.hidden = true; return; }
    await loadPeople();
    const starts = k => (k.startsWith(q) || k.includes(" " + q) ? 0 : 1);
    const comps = index.competitions.map(c => Object.assign({ key: fold([c.name, c.country, c.tour].filter(Boolean).join(" ")) }, c))
      .filter(c => c.key.includes(q)).sort((a, b) => starts(a.key) - starts(b.key) || a.name.localeCompare(b.name)).slice(0, 4);
    const hits = people.filter(p => p.key.includes(q))
      .sort((a, b) => (a.key.startsWith(q) ? 0 : 1) - (b.key.startsWith(q) ? 0 : 1) || a.n.localeCompare(b.n)).slice(0, 12 - comps.length);
    const compHit = c => `<div class="hit"><b><a href="competition.html?sport=${c.sport}&id=${encodeURIComponent(c.id)}">${SP.esc(c.name)}${c.tour && !c.name.includes(c.tour) ? " · " + SP.esc(c.tour) : ""}</a></b>
      <span class="muted small">${c.status === "finished" ? `Finished${c.champion ? " · won by " + SP.esc(c.champion) : ""}` : c.favourite ? `Favourite: ${SP.esc(c.favourite.name)} ${SP.prob(c.favourite.p)}` : "Odds once the draw is out"}</span></div>`;
    found.innerHTML = comps.length || hits.length ? comps.map(compHit).join("") + hits.map(p => `<div class="hit"><b>${SP.teamLink(p.n, (p.in[0] || {}).sport)} ${SP.starButton(p.n)}</b>${p.in.map(e =>
      `<a href="competition.html?sport=${e.sport}&id=${encodeURIComponent(e.id)}">${SP.esc(e.name)} · ${e.out ? "out" : SP.prob(e.p) + " to " + e.what}</a>`).join("")}</div>`).join("")
      : `<div class="none">No team, player or competition called “${SP.esc(find.value.trim())}” right now.</div>`;
    found.hidden = false;
  }
  find.addEventListener("input", search);
  // keyboard: arrows move through the results' links, Enter opens one, Escape clears, "/" jumps to search
  find.addEventListener("keydown", e => {
    const links = [...found.querySelectorAll(".hit a")];
    if (e.key === "Escape") { find.value = ""; found.hidden = true; return; }
    if (found.hidden || !links.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
      links.forEach((a, i) => a.classList.toggle("active", i === active));
      links[active].scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      e.preventDefault();
      location.href = links[Math.max(active, 0)].href;
    }
  });
  document.addEventListener("keydown", e => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey) { e.preventDefault(); find.focus(); }
  });
  document.addEventListener("click", e => { if (!e.target.closest(".search")) found.hidden = true; });

  if (params.get("find") != null) find.focus();  // the Mac app's Find a Team (⌘F) lands here
  SP.onChange(() => { if (!found.hidden) search(); });  // keep stars in the results in step
  SP.onChange(render);
  render();
})();
