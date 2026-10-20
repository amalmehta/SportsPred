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
  let chart, surfaces = null, ranks = null;
  // where this rating sits among everyone we rate (and, for players, on each court)
  const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");
  const rankOf = (mine, all) => 1 + all.filter(v => v > mine).length;
  try {
    const R = await SP.json("data/ratings.json");
    if (tennis) {  // overall and per-surface ratings, from the compare tool's ratings file
      const tour = ((R.atp || {}).players || {})[t.name] ? "atp" : ((R.wta || {}).players || {})[t.name] ? "wta" : null;
      if (tour) {
        const all = Object.values(R[tour].players);
        surfaces = R[tour].players[t.name];
        ranks = { tour: tour.toUpperCase(), of: all.length, at: surfaces.map((v, i) => rankOf(v, all.map(x => x[i]))) };
      }
    } else {
      const set = ((R[t.part === "international" ? "international" : "soccer"] || {}).teams) || {};
      if (set[t.name] != null) ranks = { of: Object.keys(set).length, at: [rankOf(set[t.name], Object.values(set))] };
    }
  } catch (e) { surfaces = ranks = null; }
  function rankText() {
    if (!ranks) return "";
    if (tennis) return ` · <b>${ordinal(ranks.at[0])}</b> in the ${ranks.tour} by our ratings`;
    const of = `of the ${ranks.of.toLocaleString()} ${t.part === "international" ? "national teams in current competitions" : "clubs we rate"}`;
    return ranks.at[0] === 1 ? ` · <b>top-rated</b> ${of}` : ` · <b>${ordinal(ranks.at[0])}</b> ${of}`;
  }
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  const ROUND = { r16: "last 16", qf: "quarter-finals", sf: "semi-finals", f: "final" };
  function compRow(e) {
    const s = e.sure || {}, gap = e.xpts != null && e.pts != null ? e.pts - e.xpts : null;
    const reach = e.reach && !e.out ? Object.entries(e.reach).filter(([k, v]) => ROUND[k] && v > 0 && v < 0.999).slice(-2)
      .map(([k, v]) => `${ROUND[k]} ${SP.prob(v)}`) : [];
    const extra = [
      s.title ? "title won" : "", s.down ? "relegated" : "",
      e.p_top != null && s.top == null ? `top-${e.top === 8 ? "8" : e.top === 3 ? "three" : "four"} finish ${SP.prob(e.p_top)}` : s.top ? `top ${e.top || 4} sure` : "",
      e.p_ko != null && s.ko == null && e.p_ko < 0.999 ? `knockouts ${SP.prob(e.p_ko)}` : "",
      e.p_adv != null && e.status !== "finished" ? `out of the group ${SP.prob(e.p_adv)}` : "",
      ...reach,
      e.p_drop && s.down == null ? `relegation ${SP.prob(e.p_drop)}` : "",
      gap != null && Math.abs(gap) >= 1 ? `${gap > 0 ? "+" : "−"}${Math.abs(gap).toFixed(1)} pts vs expected` : "",
      e.run_in ? `${e.run_in[0] === 1 ? "hardest" : e.run_in[0] === e.run_in[1] ? "easiest" : ordinal(e.run_in[0]) + "-hardest"} run-in of ${e.run_in[1]}` : "",
    ].filter(Boolean).join(" · ");
    const odds = e.out ? `<span class="muted">Out</span>` : e.status === "finished" ? (e.p >= 0.999 ? "🏆 Champion" : `<span class="muted">Finished</span>`)
      : s.title === false && e.what === "win" ? `<span class="muted">Can't win the title</span>`
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
      if (past) { const won = (m.w === 0) === home; result = `<b>${won ? "Won" : "Lost"}</b> · ${SP.verdict(m, "tennis").text.toLowerCase()}`; }
    } else {
      const [w, d, l] = home ? m.p : [m.p[2], m.p[1], m.p[0]];
      chances = `win ${SP.prob(w)} · draw ${SP.prob(d)} · lose ${SP.prob(l)}`;
      if (past) {
        const gf = home ? m.hg : m.ag, ga = home ? m.ag : m.hg;
        result = `<b>${gf > ga ? "Won" : gf === ga ? "Drew" : "Lost"} ${gf}–${ga}</b> · ${SP.verdict(m, "soccer").text.toLowerCase()}`;
      }
    }
    const comp = `<a href="competition.html?sport=${t.sport}&id=${encodeURIComponent(m.comp_id)}">${SP.esc(m.comp)}</a>`;
    return `<div class="match"><div class="when">${SP.esc(past ? SP.date(m.date) : SP.when(m.date))}${m.round ? "<br>" + SP.esc(m.round) : ""}</div>
      <div class="teams"><span>${tennis ? "v" : home ? "Home v" : "Away at"} ${SP.teamLink(opp, t.sport)}</span>${past ? `<span>${result}</span>` : ""}</div>
      <div class="meta"><span>${comp}</span><span>${past ? "We said: " : ""}${chances}</span></div></div>`;
  }

  // the team's last five results as W / D / L chips, newest first
  function form() {
    const last = t.recent.slice(0, 5);
    if (!last.length) return "";
    const chip = m => {
      let r;
      if (tennis) r = ((m.w === 0) === (m.a === t.name)) ? "W" : "L";
      else { const home = m.home === t.name, gf = home ? m.hg : m.ag, ga = home ? m.ag : m.hg; r = gf > ga ? "W" : gf === ga ? "D" : "L"; }
      const opp = tennis ? (m.a === t.name ? m.b : m.a) : (m.home === t.name ? m.away : m.home);
      return `<span class="form f-${r}" title="${SP.esc(SP.date(m.date))} v ${SP.esc(opp)}">${r}</span>`;
    };
    return `<div class="form-row"><span class="muted small">Form</span>${last.map(chip).join("")}</div>`;
  }

  // the next game, from this side's point of view
  function nextUp() {
    const m = t.upcoming[0];
    if (!m) return "";
    const home = tennis ? m.a === t.name : m.home === t.name;
    const opp = tennis ? (home ? m.b : m.a) : (home ? m.away : m.home);
    const [w, d, l] = tennis ? [home ? m.p : 1 - m.p, 0, home ? 1 - m.p : m.p] : (home ? m.p : [m.p[2], m.p[1], m.p[0]]);
    return `<div class="panel next-up"><div class="muted small">Next: ${SP.esc(SP.when(m.date))} · ${SP.esc(m.comp)}</div>
      <div class="next-teams"><b>${SP.esc(t.name)}</b> <span class="muted">${tennis ? "v" : home ? "v" : "at"}</span> <b>${SP.teamLink(opp, t.sport)}</b></div>
      <div class="split">${[[w, "h", "Win"], ...(tennis ? [] : [[d, "d", "Draw"]]), [l, "a", tennis ? "Lose" : "Lose"]].map(([v, cls, lab]) =>
        `<div class="${cls}" style="flex:${v * 100} 1 0" title="${lab}: ${SP.prob(v)}">${v >= 0.12 ? SP.prob(v) : ""}</div>`).join("")}</div>
      <div class="small muted">${tennis ? `win ${SP.prob(w)}` : `win ${SP.prob(w)} · draw ${SP.prob(d)} · lose ${SP.prob(l)}`}</div></div>`;
  }

  function surfaceTiles() {
    if (!surfaces) return "";
    const [o, h, c, g] = surfaces;
    const rank = i => ranks ? ` <span class="rank">${ordinal(ranks.at[i])}</span>` : "";
    const tile = (label, v, cls, i) => `<div class="stat"><b>${v}${rank(i)}</b><span>${cls ? SP.surface(cls) : label}</span></div>`;
    return `<h2>Ratings by court</h2><div class="stats">${tile("Overall", o, "", 0)}${tile("", h, "hard", 1)}${tile("", c, "clay", 2)}${tile("", g, "grass", 3)}</div>
      <p class="small muted">Each court has its own rating from matches on that surface only; predictions blend it with the overall rating.${ranks ? ` Ranks are among the top ${ranks.of} ${ranks.tour} players by our overall rating.` : ""}</p>`;
  }

  function render() {
    const r = t.rating || [];
    const change = r.length > 1 ? r[r.length - 1][1] - r[0][1] : 0;
    page.innerHTML = `
      <p class="small"><a href="index.html?sport=${t.sport}">← All ${tennis ? "tennis" : "soccer"}</a></p>
      <div class="title-row"><h1>${SP.flag(t.flag)}${SP.esc(t.name)} ${SP.starButton(t.name)}</h1></div>
      <p class="sub">${tennis ? "Tennis player" : "Soccer team"}${r.length ? ` · rating <b>${r[r.length - 1][1]}</b>` : ""}${rankText()}</p>
      ${form()}
      ${nextUp()}
      <h2>Chances</h2><div class="movers">${t.comps.map(compRow).join("")}</div>
      ${r.length > 2 ? `<h2>Rating over the last year</h2><div class="panel"><div class="chart-box" style="height:240px"><canvas id="rating" role="img" aria-label="Rating over time" aria-describedby="rating-sum"></canvas></div>
        <p class="small chart-sum" id="rating-sum">${SP.esc(SP.date(r[0][0] + "T12:00Z"))}: ${r[0][1]} → now: ${r[r.length - 1][1]} (${change >= 0 ? "+" : ""}${change}). Higher means stronger; the gap between two ratings sets each match's chances.</p></div>` : ""}
      ${surfaceTiles()}
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
