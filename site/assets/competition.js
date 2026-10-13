/* One competition: favourite, odds over time, full odds table, upcoming matches, recent calls. */
(async () => {
  const params = new URLSearchParams(location.search);
  const sport = params.get("sport") === "tennis" ? "tennis" : "soccer";
  const id = params.get("id") || "";
  SP.header(sport);
  const page = document.getElementById("page");
  let c;
  try { c = await SP.json(`data/${sport}/${encodeURIComponent(id)}.json`); }
  catch (e) { page.innerHTML = `<div class="empty">Couldn't find that competition. <a href="index.html">Back to all predictions</a></div>`; return; }
  document.title = `${c.name} · SportsPred`;
  SP.footer(c.updated);
  const tennis = sport === "tennis";
  let chart;

  const statusText = { live: "Live", upcoming: "Upcoming", finished: "Finished" }[c.status];
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function hero() {
    if (c.status === "finished" && (c.champion || c.favourite)) {
      return `<div class="hero"><div><div class="muted small">Champion</div><div class="big">🏆 ${SP.esc(c.champion || c.favourite.name)}</div></div></div>`;
    }
    const note = c.projected ? `<div class="panel" style="margin-bottom:16px"><b>Projected field.</b> <span class="muted">The groups aren't drawn yet, so these odds use the current top 8 in the rankings and simulate the draw (seeds 1 and 2 apart). The real field is the top 8 in the year-to-date Race and can differ by a name or two. Odds switch to the real groups as soon as they're published.</span></div>` : "";
    if (c.favourite && c.status !== "finished" && note) {
      return note + `<div class="hero"><div><div class="muted small">Favourite</div><div class="big">${SP.esc(c.favourite.name)}</div></div>
      <div class="lab"><div class="big">${SP.prob(c.favourite.p)}</div>chance to win the title</div></div>`;
    }
    if (!c.favourite) {
      return `<div class="panel"><b>The draw isn't out yet.</b> <span class="muted">Odds appear as soon as ESPN publishes the main draw${c.defending ? ` · defending champion: ${SP.esc(c.defending)}` : ""}.</span></div>`;
    }
    return `<div class="hero"><div><div class="muted small">Favourite</div><div class="big">${SP.esc(c.favourite.name)}</div></div>
      <div class="lab"><div class="big">${SP.prob(c.favourite.p)}</div>chance to win${tennis ? " the title" : ""}</div></div>`;
  }

  let showAll = false;
  const LIMIT = 20;
  function moreButton() {
    if (c.table.length <= LIMIT) return "";
    return `<div style="padding:10px"><button class="chip" id="more">${showAll ? "Show fewer" : `Show all ${c.table.length}`}</button></div>`;
  }
  function oddsTable() {
    const rows = showAll ? c.table : c.table.slice(0, LIMIT);
    if (!rows.length) return "";
    if (c.format === "finals") {
      const groups = rows.some(r => r.group);
      return `<div class="table-wrap"><table><thead><tr><th>#</th><th>Player</th>${groups ? "<th>Group</th>" : ""}<th class="num">W–L</th>
        <th class="num opt" title="Blend of overall and ${SP.esc(c.surface || "")}-court Elo">Rating</th><th class="num">Reach semis</th><th class="num">Win title</th></tr></thead><tbody>
        ${rows.map((r, i) => `<tr class="${r.alive ? "" : "out"}"><td class="muted">${i + 1}</td><td>${SP.esc(r.player)}${c.champion === r.player ? " 🏆" : ""}</td>
          ${groups ? `<td class="muted">${SP.esc((r.group || "").replace("Group ", ""))}</td>` : ""}<td class="num">${SP.esc(r.record || "")}</td>
          <td class="num opt">${r.rating}</td><td class="num">${SP.prob(r.p_sf)}</td>
          <td class="num">${SP.prob(r.p_win)}<span class="pbar"><i style="width:${r.p_win * 100}%"></i></span></td></tr>`).join("")}
      </tbody></table></div>`;
    }
    if (tennis) {
      return `<div class="table-wrap"><table><thead><tr><th>#</th><th>Player</th><th class="num opt" title="Blend of overall and ${SP.esc(c.surface || "")}-court Elo">Rating</th><th>Status</th><th class="num">Win title</th></tr></thead><tbody>
        ${rows.map((r, i) => `<tr class="${r.alive ? "" : "out"}"><td class="muted">${i + 1}</td><td>${SP.esc(r.player)}</td>
          <td class="num opt">${r.rating}</td><td>${r.alive ? (c.champion === r.player ? "Champion" : "In") : "Out"}</td>
          <td class="num">${SP.prob(r.p_win)}<span class="pbar"><i style="width:${r.p_win * 100}%"></i></span></td></tr>`).join("")}
      </tbody></table></div>`;
    }
    const groups = rows.some(r => r.group);
    return `<div class="table-wrap"><table><thead><tr><th>#</th><th>Team</th>${groups ? "<th>Group</th>" : ""}
      <th class="num opt">Played</th><th class="num">Pts</th><th class="num opt">GD</th><th class="num" title="Average final points across simulations">Proj. pts</th>
      <th class="num opt" title="Elo rating">Rating</th><th class="num">Win title</th></tr></thead><tbody>
      ${rows.map((r, i) => `<tr><td class="muted">${i + 1}</td><td>${SP.esc(r.team)}</td>${groups ? `<td class="muted">${SP.esc((r.group || "").replace("Group ", ""))}</td>` : ""}
        <td class="num opt">${r.played}</td><td class="num">${r.pts}</td><td class="num opt">${r.gd > 0 ? "+" : ""}${r.gd}</td>
        <td class="num">${r.proj_pts == null ? "–" : r.proj_pts.toFixed(0)}</td><td class="num opt">${r.rating}</td>
        <td class="num">${SP.prob(r.p_win)}<span class="pbar"><i style="width:${r.p_win * 100}%"></i></span></td></tr>`).join("")}
    </tbody></table></div>`;
  }

  function seg(p, cls, label) {
    const w = Math.max(p * 100, 0);
    return `<div class="${cls}" style="flex:${w} 1 0" title="${label}: ${SP.prob(p)}">${w >= 12 ? SP.prob(p) : ""}</div>`;
  }

  function matchRow(m, past) {
    if (tennis) {
      const pA = m.p, names = `<div class="teams"><span>${SP.esc(m.a)}${past && m.w === 0 ? " ✓" : ""}</span><span>${past && m.w === 1 ? "✓ " : ""}${SP.esc(m.b)}</span></div>`;
      const meta = past ? `<span class="called ${m.called ? "yes" : "no"}">${m.called ? "Called it" : "Upset"}</span>` : (m.live ? `<span class="status live">Live</span>` : "");
      return `<div class="match"><div class="when">${SP.esc(SP.when(m.date))}<br>${SP.esc(m.round)}</div>${names}
        <div class="split">${seg(pA, "h", m.a)}${seg(1 - pA, "a", m.b)}</div>
        <div class="meta"><span>${past ? "Pre-match chances" : "Win chances"}</span>${meta}</div></div>`;
    }
    const score = past ? ` <b>${m.hg}–${m.ag}</b> ` : "";
    const meta = past
      ? `<span class="called ${m.called ? "yes" : "no"}">${m.called ? "Called it" : "Missed"}</span>`
      : `<span>Likely score ${m.score[0]}–${m.score[1]}</span>${m.live ? `<span class="status live">Live</span>` : ""}`;
    return `<div class="match"><div class="when">${SP.esc(SP.when(m.date))}</div>
      <div class="teams"><span>${SP.esc(m.home)}</span>${score}<span>${SP.esc(m.away)}</span></div>
      <div class="split">${seg(m.p[0], "h", "Home win")}${seg(m.p[1], "d", "Draw")}${seg(m.p[2], "a", "Away win")}</div>
      <div class="meta">${past ? "<span>Pre-match: home · draw · away</span>" : ""}${meta}</div></div>`;
  }

  function render() {
    const court = c.surface ? `${c.surface[0].toUpperCase()}${c.surface.slice(1)} court · ` : "";
    const fmt = c.format === "finals" ? "two groups of four, top two reach the semi-finals · " : "";
    const sub = tennis ? `${SP.date(c.start)} – ${SP.date(c.end)} · ${fmt}${court}best of ${c.best_of} sets` : `${c.season} season`;
    const h = c.history;
    const canChart = h && h.dates.length > 1 && h.series.length;
    page.innerHTML = `
      <p class="small"><a href="index.html?sport=${sport}">← All ${tennis ? "tennis" : "soccer"}</a></p>
      <div class="card-head" style="justify-content:flex-start;margin-bottom:6px">${SP.tagFor(c)}<span class="status ${c.status}">${statusText}</span></div>
      <h1>${SP.esc(c.name)}</h1><p class="sub">${SP.esc(sub)}</p>
      ${hero()}
      <h2>${tennis ? "Title odds over the tournament" : "Title odds over the season"}</h2>
      <div class="panel">${canChart ? `<div class="chart-box"><canvas id="chart" aria-label="Chance to win over time"></canvas></div><div class="legend" id="legend"></div>`
        : `<div class="muted">The chart fills in as results come in${c.projected ? ", starting when the groups are drawn" : ""}.</div>`}</div>
      <h2>${tennis ? "Every player's chances" : "Every team's chances"}</h2>
      <div class="panel" style="padding:4px 8px">${oddsTable() || '<div class="muted" style="padding:12px">No entrants yet.</div>'}${moreButton()}</div>
      <div class="two">
        <div><h2>Coming up</h2>${!tennis && c.upcoming.length ? `<p class="small muted" style="margin:-6px 0 10px"><i class="sw" style="background:var(--bar-home)"></i> home win &nbsp;<i class="sw" style="background:var(--bar-draw)"></i> draw &nbsp;<i class="sw" style="background:var(--bar-away)"></i> away win</p>` : ""}<div class="matches">${c.upcoming.length ? c.upcoming.map(m => matchRow(m, false)).join("") : '<div class="empty">No scheduled matches.</div>'}</div></div>
        <div><h2>Recent results vs. our call</h2><div class="matches">${c.recent.length ? c.recent.map(m => matchRow(m, true)).join("") : '<div class="empty">No results yet.</div>'}</div></div>
      </div>`;
    if (canChart) drawChart();
    const more = document.getElementById("more");
    if (more) more.onclick = () => { showAll = !showAll; const y = scrollY; render(); scrollTo(0, y); };
  }

  function drawChart() {
    const h = c.history;
    const colors = Array.from({ length: 8 }, (_, i) => css(`--s${i + 1}`));
    const text2 = css("--text-2"), border = css("--border"), surface = css("--surface");
    const pct = SP.settings().odds === "percent";
    if (chart) chart.destroy();
    chart = new Chart(document.getElementById("chart"), {
      type: "line",
      data: {
        labels: h.dates.map(d => SP.date(d + "T12:00Z")),
        datasets: h.series.map((s, i) => ({
          label: s.team, data: s.p.map(v => v * 100), borderColor: colors[i], backgroundColor: colors[i],
          borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, pointHoverBorderColor: surface, pointHoverBorderWidth: 2, tension: 0.25,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            itemSort: (a, b) => b.parsed.y - a.parsed.y,
            callbacks: { label: ctx => ` ${ctx.dataset.label}: ${SP.prob(ctx.parsed.y / 100)}` },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: text2, maxRotation: 0, autoSkipPadding: 16 }, border: { color: border } },
          y: { min: 0, max: 100, grid: { color: border }, border: { display: false },
               ticks: { color: text2, stepSize: 25, callback: v => pct ? v + "%" : (v ? (100 / v).toFixed(1) : "") } },
        },
      },
    });
    document.getElementById("legend").innerHTML = h.series.map((s, i) =>
      `<span><i style="background:${colors[i]}"></i>${SP.esc(s.team)} · ${SP.prob(s.p[s.p.length - 1])}</span>`).join("");
  }

  SP.onChange(render);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  render();
})();
