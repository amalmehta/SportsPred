/* One team or player: chances in every competition, rating over the last year, next and recent games. */
(async () => {
  const id = new URLSearchParams(location.search).get("id") || "";
  const page = document.getElementById("page");
  let t;
  try { [t] = await Promise.all([SP.json(`data/teams/${encodeURIComponent(id)}.json`), SP.loadTeams()]); }
  catch (e) { SP.header(""); page.innerHTML = `<div class="empty">Couldn't find that team or player. <a href="index.html">Back to all predictions</a></div>`; return; }
  const tennis = t.sport === "tennis";
  SP.header(t.sport);
  document.title = `${t.name} · SportsPred`;
  SP.footer();
  let chart;
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  function compRow(e) {
    const extra = [e.p_top != null ? `top-four finish ${SP.prob(e.p_top)}` : "", e.p_drop ? `relegation ${SP.prob(e.p_drop)}` : ""].filter(Boolean).join(" · ");
    const odds = e.out ? `<span class="muted">Out</span>` : e.status === "finished" ? (e.p >= 0.999 ? "🏆 Champion" : `<span class="muted">Finished</span>`)
      : `<span class="pct">${SP.prob(e.p)}</span> <span class="muted small">to ${e.what}</span>`;
    return `<a class="mover" href="competition.html?sport=${e.sport}&id=${encodeURIComponent(e.id)}"><span>${SP.tagFor({ id: e.id, group: e.group, sport: e.sport })}</span>
      <span><b>${SP.esc(e.name)}</b>${extra ? `<span class="muted small"> · ${extra}</span>` : ""}</span><span class="num">${odds}</span></a>`;
  }

  // a match from this team's point of view: who they play and their own chances
  function matchRow(m, past) {
    const home = tennis ? m.a === t.name : m.home === t.name;
    const opp = tennis ? (home ? m.b : m.a) : (home ? m.away : m.home);
    let chances, result = "";
    if (tennis) {
      const p = home ? m.p : 1 - m.p;
      chances = `win ${SP.prob(p)}`;
      if (past) { const won = (m.w === 0) === home; result = `<b>${won ? "Won" : "Lost"}</b> · ${won ? (p < 0.25 ? "upset" : p >= 0.5 ? "called it" : "missed") : (1 - p < 0.25 ? "upset" : p < 0.5 ? "called it" : "missed")}`; }
    } else {
      const [w, d, l] = home ? m.p : [m.p[2], m.p[1], m.p[0]];
      chances = `win ${SP.prob(w)} · draw ${SP.prob(d)} · lose ${SP.prob(l)}`;
      if (past) {
        const gf = home ? m.hg : m.ag, ga = home ? m.ag : m.hg;
        result = `<b>${gf > ga ? "Won" : gf === ga ? "Drew" : "Lost"} ${gf}–${ga}</b>`;
      }
    }
    const comp = `<a href="competition.html?sport=${t.sport}&id=${encodeURIComponent(m.comp_id)}">${SP.esc(m.comp)}</a>`;
    return `<div class="match"><div class="when">${SP.esc(past ? SP.date(m.date) : SP.when(m.date))}${m.round ? "<br>" + SP.esc(m.round) : ""}</div>
      <div class="teams"><span>${tennis ? "v" : home ? "Home v" : "Away at"} ${SP.teamLink(opp, t.sport)}</span>${past ? `<span>${result}</span>` : ""}</div>
      <div class="meta"><span>${comp}</span><span>${past ? "We said: " : ""}${chances}</span></div></div>`;
  }

  function render() {
    const r = t.rating || [];
    const change = r.length > 1 ? r[r.length - 1][1] - r[0][1] : 0;
    page.innerHTML = `
      <p class="small"><a href="index.html?sport=${t.sport}">← All ${tennis ? "tennis" : "soccer"}</a></p>
      <div class="title-row"><h1>${SP.flag(t.flag)}${SP.esc(t.name)} ${SP.starButton(t.name)}</h1></div>
      <p class="sub">${tennis ? "Tennis player" : "Soccer team"}${r.length ? ` · rating <b>${r[r.length - 1][1]}</b>` : ""}</p>
      <h2>Chances</h2><div class="movers">${t.comps.map(compRow).join("")}</div>
      ${r.length > 2 ? `<h2>Rating over the last year</h2><div class="panel"><div class="chart-box" style="height:240px"><canvas id="rating" role="img" aria-label="Rating over time" aria-describedby="rating-sum"></canvas></div>
        <p class="small chart-sum" id="rating-sum">${SP.esc(SP.date(r[0][0] + "T12:00Z"))}: ${r[0][1]} → now: ${r[r.length - 1][1]} (${change >= 0 ? "+" : ""}${change}). Higher means stronger; the gap between two ratings sets each match's chances.</p></div>` : ""}
      <div class="two">
        <div><h2>Next up</h2><div class="matches">${t.upcoming.length ? t.upcoming.map(m => matchRow(m, false)).join("") : '<div class="empty">No scheduled matches.</div>'}</div></div>
        <div><h2>Recent results</h2><div class="matches">${t.recent.length ? t.recent.map(m => matchRow(m, true)).join("") : '<div class="empty">No recent results.</div>'}</div></div>
      </div>`;
    if (r.length > 2 && window.Chart) {
      if (chart) chart.destroy();
      const text2 = css("--text-2"), border = css("--border");
      chart = new Chart(document.getElementById("rating"), {
        type: "line",
        data: { labels: r.map(x => SP.date(x[0] + "T12:00Z")), datasets: [{ label: "Rating", data: r.map(x => x[1]), borderColor: css("--s1"),
          backgroundColor: css("--s1"), borderWidth: 2, pointRadius: ctx => (ctx.dataIndex === r.length - 1 ? 4 : 0), tension: 0.2 }] },
        options: { responsive: true, maintainAspectRatio: false, animation: false, interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false }, tooltip: { backgroundColor: css("--surface"), titleColor: css("--text"), bodyColor: css("--text-2"),
            borderColor: border, borderWidth: 1 } },
          scales: { x: { grid: { display: false }, ticks: { color: text2, maxRotation: 0, autoSkipPadding: 20 } },
                    y: { grid: { color: border }, ticks: { color: text2 } } } },
      });
    }
  }
  SP.onChange(render);
  render();
})();
