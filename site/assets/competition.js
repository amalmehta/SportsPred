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
      return note + `<div class="hero"><div><div class="muted small">${qualifying ? "Likeliest to qualify" : "Favourite"}</div><div class="big">${SP.esc(c.favourite.name)}</div></div>
      <div class="lab"><div class="big">${SP.prob(c.favourite.p)}</div>chance to win the title</div></div>`;
    }
    if (!c.favourite) {
      return `<div class="panel"><b>The draw isn't out yet.</b> <span class="muted">Odds appear as soon as ESPN publishes the main draw${c.defending ? ` · defending champion: ${SP.esc(c.defending)}` : ""}.</span></div>`;
    }
    return `<div class="hero"><div><div class="muted small">${qualifying ? "Likeliest to qualify" : "Favourite"}</div><div class="big">${SP.esc(c.favourite.name)}</div></div>
      <div class="lab"><div class="big">${SP.prob(c.favourite.p)}</div>chance to ${qualifying ? "qualify" : "win"}${tennis ? " the title" : ""}</div></div>`;
  }

  let showAll = false;
  const LIMIT = 20;
  const qualifying = c.format === "qualifying";
  if (qualifying) showAll = true;  // groups read best in full
  function moreButton() {
    if (qualifying || c.table.length <= LIMIT) return "";
    return `<div style="padding:10px"><button class="chip" id="more">${showAll ? "Show fewer" : `Show all ${c.table.length}`}</button></div>`;
  }
  function oddsTable() {
    const rows = showAll ? c.table : c.table.slice(0, LIMIT);
    if (!rows.length) return "";
    if (c.format === "finals") {
      const groups = rows.some(r => r.group);
      return `<div class="table-wrap"><table><thead><tr><th>#</th><th>Player</th>${groups ? "<th>Group</th>" : ""}<th class="num">W–L</th>
        <th class="num opt" title="Blend of overall and ${SP.esc(c.surface || "")}-court Elo">Rating</th><th class="num">Reach semis</th><th class="num">Win title</th></tr></thead><tbody>
        ${rows.map((r, i) => `<tr class="${r.alive ? "" : "out"}"><td class="muted">${i + 1}</td><td>${SP.starButton(r.player)} ${SP.esc(r.player)}${c.champion === r.player ? " 🏆" : ""}</td>
          ${groups ? `<td class="muted">${SP.esc((r.group || "").replace("Group ", ""))}</td>` : ""}<td class="num">${SP.esc(r.record || "")}</td>
          <td class="num opt">${r.rating}</td><td class="num">${SP.prob(r.p_sf)}</td>
          <td class="num">${SP.prob(r.p_win)}<span class="pbar"><i style="width:${r.p_win * 100}%"></i></span></td></tr>`).join("")}
      </tbody></table></div>`;
    }
    if (tennis) {
      return `<div class="table-wrap"><table><thead><tr><th>#</th><th>Player</th><th class="num opt" title="Blend of overall and ${SP.esc(c.surface || "")}-court Elo">Rating</th><th>Status</th><th class="num">Win title</th></tr></thead><tbody>
        ${rows.map((r, i) => `<tr class="${r.alive ? "" : "out"}"><td class="muted">${i + 1}</td><td>${SP.starButton(r.player)} ${SP.esc(r.player)}</td>
          <td class="num opt">${r.rating}</td><td>${r.alive ? (c.champion === r.player ? "Champion" : "In") : "Out"}</td>
          <td class="num">${SP.prob(r.p_win)}<span class="pbar"><i style="width:${r.p_win * 100}%"></i></span></td></tr>`).join("")}
      </tbody></table></div>`;
    }
    const groups = rows.some(r => r.group);
    if (qualifying) {
      const s = c.slots, cols = 9;
      let last = null, pos = 0;
      return `<div class="table-wrap"><table><thead><tr><th>#</th><th>Team</th>
        <th class="num opt">Played</th><th class="num">Pts</th><th class="num opt">GD</th><th class="num opt" title="Average final points across simulations">Proj. pts</th>
        <th class="num opt" title="Elo rating">Rating</th>
        <th class="num" title="Top ${s.direct} in the group">${s.direct ? "Qualify" : ""}</th>
        <th class="num" title="Places ${s.direct + 1}${s.next > 1 ? "–" + (s.direct + s.next) : ""} in the group">${SP.esc(s.next_label)}</th>
        <th class="num opt">Top group</th></tr></thead><tbody>
        ${rows.map(r => {
          const head = r.group !== last ? `<tr><td colspan="${cols + 1}" style="font-weight:700;padding-top:16px">${SP.esc(r.group || "")}</td></tr>` : "";
          pos = r.group !== last ? 1 : pos + 1; last = r.group;
          return head + `<tr><td class="muted">${pos}</td><td>${SP.starButton(r.team)} ${SP.esc(r.team)}</td>
          <td class="num opt">${r.played}</td><td class="num">${r.pts}</td><td class="num opt">${r.gd > 0 ? "+" : ""}${r.gd}</td>
          <td class="num opt">${r.proj_pts == null ? "–" : r.proj_pts.toFixed(0)}</td><td class="num opt">${r.rating}</td>
          <td class="num">${s.direct ? SP.prob(r.p_qualify) + `<span class="pbar"><i style="width:${r.p_qualify * 100}%"></i></span>` : ""}</td>
          <td class="num">${SP.prob(r.p_playoff)}</td><td class="num opt">${SP.prob(r.p_win)}</td></tr>`;
        }).join("")}
      </tbody></table></div>`;
    }
    const pl = c.places || {};
    const extra = [
      pl.top && ["p_top", `Top ${pl.top}`, c.format === "league" ? `Finish in the top ${pl.top} (Champions League places)` : "Finish in the top 8: straight to the round of 16"],
      pl.ko && ["p_ko", "Knockouts", "Finish in the top 24: reach the knockout rounds"],
      pl.drop && ["p_drop", "Relegated", `Finish in the bottom ${pl.drop} (direct relegation; playoffs not counted)`],
    ].filter(Boolean);
    return `<div class="table-wrap"><table><thead><tr><th>#</th><th>Team</th>${groups ? "<th>Group</th>" : ""}
      <th class="num opt">Played</th><th class="num">Pts</th><th class="num opt">GD</th><th class="num" title="Average final points across simulations">Proj. pts</th>
      <th class="num opt" title="Elo rating">Rating</th>${extra.map(([, label, hint]) => `<th class="num" title="${hint}">${label}</th>`).join("")}<th class="num">Win title</th></tr></thead><tbody>
      ${rows.map((r, i) => `<tr><td class="muted">${i + 1}</td><td>${SP.starButton(r.team)} ${SP.esc(r.team)}</td>${groups ? `<td class="muted">${SP.esc((r.group || "").replace("Group ", ""))}</td>` : ""}
        <td class="num opt">${r.played}</td><td class="num">${r.pts}</td><td class="num opt">${r.gd > 0 ? "+" : ""}${r.gd}</td>
        <td class="num">${r.proj_pts == null ? "–" : r.proj_pts.toFixed(0)}</td><td class="num opt">${r.rating}</td>
        ${extra.map(([k]) => `<td class="num">${SP.prob(r[k])}</td>`).join("")}
        <td class="num">${SP.prob(r.p_win)}<span class="pbar"><i style="width:${r.p_win * 100}%"></i></span></td></tr>`).join("")}
    </tbody></table></div>`;
  }

  function seg(p, cls, label) {
    const w = Math.max(p * 100, 0);
    return `<div class="${cls}" style="flex:${w} 1 0" title="${label}: ${SP.prob(p)}">${w >= 12 ? SP.prob(p) : ""}</div>`;
  }

  // upcoming matches under one heading per day, so each card only needs the kick-off time
  function byDay(list) {
    let last = null;
    return list.map(m => {
      const key = SP.dayKey(m.date), head = key !== last ? `<div class="day">${SP.esc(SP.date(m.date))}</div>` : "";
      last = key;
      return head + matchRow(m, false);
    }).join("");
  }

  function stateBadge(m) {
    const st = SP.matchState(m.date, m.live, c.sport);
    if (st === "live") return `<span class="status live">Live</span>`;
    if (st === "done") return `<span class="status done" title="This page updates about hourly">Result due in the next update</span>`;
    return "";
  }

  // download the upcoming matches, with the model's chances, as a calendar file
  function calendar() {
    const pad = n => String(n).padStart(2, "0");
    const stamp = d => `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00Z`;
    const text = t => String(t).replace(/[\\;,]/g, x => "\\" + x).replace(/\n/g, "\\n");
    const now = stamp(new Date());
    const events = c.upcoming.map((m, i) => {
      const start = new Date(m.date.length === 17 ? m.date.replace("Z", ":00Z") : m.date);
      const end = new Date(start.getTime() + (tennis ? 150 : 115) * 60000);
      const title = tennis ? `${m.a} v ${m.b}` : `${m.home} v ${m.away}`;
      const odds = tennis ? `${m.a} ${SP.prob(m.p)} · ${m.b} ${SP.prob(1 - m.p)}`
        : `${m.home} ${SP.prob(m.p[0])} · Draw ${SP.prob(m.p[1])} · ${m.away} ${SP.prob(m.p[2])}`;
      return ["BEGIN:VEVENT", `UID:${c.id}-${i}-${stamp(start)}@sportspred`, `DTSTAMP:${now}`, `DTSTART:${stamp(start)}`, `DTEND:${stamp(end)}`,
        `SUMMARY:${text(title + " · " + c.name)}`, `DESCRIPTION:${text("SportsPred chances: " + odds + "\n" + location.href)}`, `URL:${location.href}`, "END:VEVENT"].join("\r\n");
    });
    const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SportsPred//EN", `X-WR-CALNAME:${text(c.name + " · SportsPred")}`, ...events, "END:VCALENDAR"].join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
    a.download = `${c.name} matches.ics`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function matchRow(m, past) {
    if (tennis) {
      const pA = m.p, names = `<div class="teams"><span>${SP.esc(m.a)}${past && m.w === 0 ? " ✓" : ""}</span><span>${past && m.w === 1 ? "✓ " : ""}${SP.esc(m.b)}</span></div>`;
      const meta = past ? `<span class="called ${m.called ? "yes" : "no"}">${m.called ? "Called it" : "Upset"}</span>` : stateBadge(m);
      return `<div class="match"><div class="when">${SP.esc(past ? SP.when(m.date) : SP.time(m.date))}<br>${SP.esc(m.round)}</div>${names}
        <div class="split">${seg(pA, "h", m.a)}${seg(1 - pA, "a", m.b)}</div>
        <div class="meta"><span>${past ? "Pre-match chances" : "Win chances"}</span>${meta}</div></div>`;
    }
    const score = past ? ` <b>${m.hg}–${m.ag}</b> ` : "";
    const meta = past
      ? `<span class="called ${m.called ? "yes" : "no"}">${m.called ? "Called it" : "Missed"}</span>`
      : `<span>Likely score ${m.score[0]}–${m.score[1]}</span>${stateBadge(m)}`;
    return `<div class="match"><div class="when">${SP.esc(past ? SP.when(m.date) : SP.time(m.date))}</div>
      <div class="teams"><span>${SP.esc(m.home)}</span>${score}<span>${SP.esc(m.away)}</span></div>
      <div class="split">${seg(m.p[0], "h", "Home win")}${seg(m.p[1], "d", "Draw")}${seg(m.p[2], "a", "Away win")}</div>
      <div class="meta">${past ? "<span>Pre-match: home · draw · away</span>" : ""}${meta}</div></div>`;
  }

  function render() {
    const court = c.surface ? `${c.surface[0].toUpperCase()}${c.surface.slice(1)} court · ` : "";
    const fmt = c.format === "finals" ? "two groups of four, top two reach the semi-finals · " : "";
    const sub = tennis ? `${SP.date(c.start)} – ${SP.date(c.end)} · ${fmt}${court}best of ${c.best_of} sets` : `${c.season} season`;
    const h = c.history;
    const canChart = h && h.series.length && (h.dates.length > 1 || (c.live || []).length > 1);
    page.innerHTML = `
      <p class="small"><a href="index.html?sport=${sport}">← All ${tennis ? "tennis" : "soccer"}</a></p>
      <div class="card-head" style="justify-content:flex-start;margin-bottom:6px">${SP.tagFor(c)}<span class="status ${c.status}">${statusText}</span></div>
      <div class="title-row"><h1>${SP.esc(c.name)}</h1><button class="chip" id="share" type="button">Share</button></div>
      <p class="sub">${SP.esc(sub)}</p>
      ${hero()}
      <h2>${tennis ? "Title odds over the tournament" : qualifying ? "Chance to qualify over the campaign: the races that moved most" : "Title odds over the season"}</h2>
      <div class="panel">${canChart ? `<div class="chart-box" ${asTable ? 'hidden' : ""}><canvas id="chart" aria-label="Chance to win over time"></canvas></div>
        <div id="chart-table" ${asTable ? "" : "hidden"}>${chartTable()}</div>
        <div class="legend" id="legend"></div>
        <div style="margin-top:10px"><button class="chip" id="as-table">${asTable ? "Show as chart" : "Show as table"}</button></div>`
        : `<div class="muted">The chart fills in as results come in${c.projected ? ", starting when the groups are drawn" : ""}.</div>`}</div>
      <h2>${tennis ? "Every player's chances" : "Every team's chances"}</h2>
      <div class="panel" style="padding:4px 8px">${oddsTable() || '<div class="muted" style="padding:12px">No entrants yet.</div>'}${moreButton()}</div>
      <div class="two">
        <div><div class="title-row"><h2>Coming up</h2>${c.upcoming.length ? '<button class="chip" id="ics" type="button" title="Download these matches, with our chances, for your calendar">Add to calendar</button>' : ""}</div>${!tennis && c.upcoming.length ? `<p class="small muted" style="margin:-6px 0 10px"><i class="sw" style="background:var(--bar-home)"></i> home win &nbsp;<i class="sw" style="background:var(--bar-draw)"></i> draw &nbsp;<i class="sw" style="background:var(--bar-away)"></i> away win</p>` : ""}<div class="matches">${c.upcoming.length ? byDay(c.upcoming) : '<div class="empty">No scheduled matches.</div>'}</div></div>
        <div><h2>Recent results vs. our call</h2>${recordLine()}<div class="matches">${c.recent.length ? c.recent.map(m => matchRow(m, true)).join("") : '<div class="empty">No results yet.</div>'}</div></div>
      </div>`;
    if (canChart && !asTable) drawChart();
    if (canChart && asTable) legendOnly();
    document.getElementById("share").onclick = share;
    const ics = document.getElementById("ics");
    if (ics) ics.onclick = calendar;
    const toggle = document.getElementById("as-table");
    if (toggle) toggle.onclick = () => { asTable = !asTable; const y = scrollY; render(); scrollTo(0, y); };
    const more = document.getElementById("more");
    if (more) more.onclick = () => { showAll = !showAll; const y = scrollY; render(); scrollTo(0, y); };
  }

  let asTable = false;
  const hidden = new Set();  // teams switched off in the chart legend
  document.addEventListener("click", e => {
    const b = e.target.closest("#legend [data-series]");
    if (!b || !chart) return;
    const team = c.history.series[+b.dataset.series].team;
    hidden.has(team) ? hidden.delete(team) : hidden.add(team);
    const n = c.history.series.length;
    chart.data.datasets.forEach((d, i) => { if (i % n === +b.dataset.series) d.hidden = hidden.has(team); });
    chart.update();
    b.setAttribute("aria-pressed", String(!hidden.has(team)));
  });

  // share sheet where there is one (phones, Safari), otherwise copy the link
  async function share() {
    const btn = document.getElementById("share");
    const fav = c.favourite ? ` ${c.favourite.name} ${SP.prob(c.favourite.p)}.` : "";
    try {
      if (navigator.share) { await navigator.share({ title: `${c.name} · SportsPred`, text: `${c.name}: who's going to win?${fav}`, url: location.href }); return; }
      await navigator.clipboard.writeText(location.href);
      btn.textContent = "Link copied";
    } catch (e) {
      if (e && e.name === "AbortError") return;  // closed the share sheet
      btn.textContent = "Copy failed";
    }
    setTimeout(() => { btn.textContent = "Share"; }, 2000);
  }

  function recordLine() {
    const r = c.record;
    if (!r || !r.n) return "";
    const pct = Math.round(100 * r.called / r.n);
    const span = tennis ? "This tournament" : "This season";
    const hint = tennis ? "how often the player we rated likelier won" : "how often the result we rated likeliest happened (home win, draw or away win)";
    return `<p class="small muted" style="margin:-6px 0 10px" title="${hint}. Brier score: 0 is perfect, lower is better.">
      ${span}: called <b>${r.called} of ${r.n}</b> (${pct}%) · Brier ${r.brier.toFixed(3)}</p>`;
  }

  // the chart's numbers as a table: one row per day, replay value with the published value beside it
  function chartTable() {
    const h = c.history, live = new Map((c.live || []).map(e => [e.date, e.p]));
    if (!h || !h.series.length) return "";
    const dates = [...new Set([...h.dates, ...live.keys()])].sort().reverse();
    const idx = new Map(h.dates.map((d, i) => [d, i]));
    return `<div class="table-wrap" style="max-height:420px;overflow-y:auto"><table><thead><tr><th>Day</th>
      ${h.series.map(s => `<th class="num">${SP.esc(s.team)}</th>`).join("")}</tr></thead><tbody>
      ${dates.map(d => `<tr><td>${SP.esc(SP.date(d + "T12:00Z"))}</td>${h.series.map(s => {
        const r = idx.has(d) ? SP.prob(s.p[idx.get(d)]) : "–";
        const pub = live.has(d) ? ` <span class="muted" title="published that day">(${SP.prob(live.get(d)[s.team] || 0)})</span>` : "";
        return `<td class="num">${r}${pub}</td>`;
      }).join("")}</tr>`).join("")}
      </tbody></table></div><p class="small muted">Replay value, with the value this site published that day in brackets.</p>`;
  }

  function legendOnly() {
    const colors = Array.from({ length: 8 }, (_, i) => css(`--s${i + 1}`));
    document.getElementById("legend").innerHTML = c.history.series.map((s, i) =>
      `<span><i style="background:${colors[i]}"></i>${SP.esc(s.team)} · ${SP.prob(s.p[s.p.length - 1])}</span>`).join("");
  }

  function drawChart() {
    const h = c.history;
    const live = (c.live || []).filter(e => e.p);
    const colors = Array.from({ length: 8 }, (_, i) => css(`--s${i + 1}`));
    const text2 = css("--text-2"), border = css("--border"), surface = css("--surface");
    const pct = SP.settings().odds === "percent";
    // one x-axis for both: replay days (lines) and days the site published odds (dots)
    const dates = [...new Set([...h.dates, ...live.map(e => e.date)])].sort();
    const at = (ds, vs) => { const m = new Map(ds.map((d, i) => [d, vs[i]])); return dates.map(d => m.has(d) ? m.get(d) * 100 : null); };
    const datasets = h.series.map((s, i) => ({
      label: s.team, data: at(h.dates, s.p), borderColor: colors[i], backgroundColor: colors[i], spanGaps: true,
      borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, pointHoverBorderColor: surface, pointHoverBorderWidth: 2, tension: 0.25,
    }));
    if (live.length) {
      h.series.forEach((s, i) => datasets.push({
        label: `${s.team} (published)`, data: at(live.map(e => e.date), live.map(e => e.p[s.team] || 0)),
        showLine: false, borderColor: colors[i], backgroundColor: surface, borderWidth: 2,
        pointRadius: 4, pointHoverRadius: 6, pointStyle: "circle",
      }));
    }
    const n = h.series.length;
    datasets.forEach((d, i) => { d.hidden = hidden.has(h.series[i % n].team); });
    if (chart) chart.destroy();
    chart = new Chart(document.getElementById("chart"), {
      type: "line",
      data: { labels: dates.map(d => SP.date(d + "T12:00Z")), datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            filter: item => item.parsed.y != null,
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
      `<button type="button" data-series="${i}" aria-pressed="${!hidden.has(s.team)}" title="Show or hide ${SP.esc(s.team)}"><i style="background:${colors[i]}"></i>${SP.esc(s.team)} · ${SP.prob(s.p[s.p.length - 1])}</button>`).join("") +
      `<span class="muted" style="flex-basis:100%">Lines: replay, using only what was known at the end of each day.${live.length
        ? ` Dots: the odds this site published that day (${live.length} day${live.length > 1 ? "s" : ""} so far, since ${SP.esc(SP.date(live[0].date + "T12:00Z"))}).` : ""}</span>`;
  }

  SP.onChange(render);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  render();
})();
