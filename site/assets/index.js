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

  const ORDER = { live: 0, upcoming: 1, finished: 2 };
  const GROUP_ORDER = ["european", "domestic", "international", "atp-slam", "wta-slam", "atp-1000", "wta-1000"];

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
        <div class="meter" title="Chance to win"><i style="width:${Math.max(2, c.favourite.p * 100)}%"></i></div>`;
    } else {
      body = `<div class="muted small">Odds appear once the draw is out.</div>`;
    }
    const next = c.status !== "finished" && c.next_match ? `<div class="muted small">Next: ${SP.esc(SP.when(c.next_match))}</div>` : "";
    return `<a class="card" href="${href}">
      <div class="card-head">${SP.tagFor(c)}<span class="status ${c.status}">${c.status === "live" ? "Live" : c.status === "upcoming" ? "Upcoming" : "Finished"}</span></div>
      <div><h3>${SP.esc(c.name)}</h3><div class="muted small">${sub}</div></div>
      ${body}${next}</a>`;
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
    sections.innerHTML = blocks.join("");
  }
  filters.addEventListener("click", e => {
    const b = e.target.closest(".chip"); if (!b) return;
    sport = b.dataset.v;
    history.replaceState(null, "", sport === "all" ? "index.html" : `index.html?sport=${sport}`);
    render();
  });
  SP.onChange(render);
  render();
})();
