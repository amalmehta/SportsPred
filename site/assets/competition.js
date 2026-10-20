/* One competition: favourite, odds over time, full odds table, upcoming matches, recent calls. */
(async () => {
  const params = new URLSearchParams(location.search);
  const sport = params.get("sport") === "tennis" ? "tennis" : "soccer";
  const id = params.get("id") || "";
  SP.header(sport);
  const page = document.getElementById("page");
  let c;
  try { [c] = await Promise.all([SP.json(`data/${sport}/${encodeURIComponent(id)}.json`), SP.loadTeams()]); }
  catch (e) { page.innerHTML = `<div class="empty">Couldn't find that competition. <a href="index.html">Back to all predictions</a></div>`; return; }
  document.title = `${c.name} · SportsPred`;
  SP.footer(c.updated);
  const tennis = sport === "tennis";
  let chart;

  const statusText = { live: "Live", upcoming: "Upcoming", finished: "Finished" }[c.status];
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function sinceYesterday(name) {
    const live = (c.live || []).filter(e => e.p);
    if (live.length < 2 || !name) return "";
    const a = live[live.length - 2].p[name] || 0, b = live[live.length - 1].p[name] || 0, d = b - a;
    if (Math.abs(d) < 0.005) return `<div class="delta">no change since yesterday</div>`;
    return `<div class="delta">${d > 0 ? "▲" : "▼"} ${Math.abs(Math.round(d * 100)) || "<1"} pts since yesterday</div>`;
  }

  function hero() {
    if (c.status === "finished" && (c.champion || c.favourite)) {
      return `<div class="hero"><div><div class="muted small">Champion</div><div class="big">🏆 ${SP.esc(c.champion || c.favourite.name)}</div></div></div>`;
    }
    const note = c.projected ? `<div class="panel" style="margin-bottom:16px"><b>Projected field.</b> <span class="muted">The groups aren't drawn yet, so these odds use the current top 8 in the rankings and simulate the draw (seeds 1 and 2 apart). The real field is the top 8 in the year-to-date Race and can differ by a name or two. Odds switch to the real groups as soon as they're published.</span></div>` : "";
    if (c.favourite && c.status !== "finished" && note) {
      return note + `<div class="hero"><div><div class="muted small">${qualifying ? "Likeliest to qualify" : "Favourite"}</div><div class="big">${SP.esc(c.favourite.name)}</div></div>
      <div class="lab"><div class="big">${SP.prob(c.favourite.p)}</div>chance to win the title${sinceYesterday(c.favourite.name)}</div></div>`;
    }
    if (!c.favourite) {
      return `<div class="panel"><b>The draw isn't out yet.</b> <span class="muted">Odds appear as soon as ESPN publishes the main draw${c.defending ? ` · defending champion: ${SP.esc(c.defending)}` : ""}.</span></div>`;
    }
    return `<div class="hero"><div><div class="muted small">${qualifying ? "Likeliest to qualify" : "Favourite"}</div><div class="big">${SP.esc(c.favourite.name)}</div></div>
      <div class="lab"><div class="big">${SP.prob(c.favourite.p)}</div>chance to ${qualifying ? "qualify" : "win"}${tennis ? " the title" : ""}${sinceYesterday(c.favourite.name)}</div></div>`;
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
        ${rows.map((r, i) => `<tr class="${r.alive ? "" : "out"}${SP.following().has(r.player) ? " mine" : ""}"><td class="muted">${i + 1}</td><td>${SP.starButton(r.player)} ${SP.flag(r.flag)}${SP.teamLink(r.player, c.sport)}${c.champion === r.player ? " 🏆" : ""}</td>
          ${groups ? `<td class="muted">${SP.esc((r.group || "").replace("Group ", ""))}</td>` : ""}<td class="num">${SP.esc(r.record || "")}</td>
          <td class="num opt">${r.rating}</td><td class="num">${SP.prob(r.p_sf)}</td>
          <td class="num">${SP.prob(r.p_win)}<span class="pbar"><i style="width:${r.p_win * 100}%"></i></span></td></tr>`).join("")}
      </tbody></table></div>`;
    }
    if (tennis) {
      const reach = rows.some(r => r.reach) && c.status !== "finished";
      const rc = [["qf", "Quarters"], ["sf", "Semis"], ["f", "Final"]];
      return `<div class="table-wrap"><table><thead><tr><th>#</th><th>Player</th><th class="num opt" title="Blend of overall and ${SP.esc(c.surface || "")}-court Elo">Rating</th><th>Status</th>
        ${reach ? rc.map(([, l]) => `<th class="num" title="Chance to reach the ${l.toLowerCase()}">${l}</th>`).join("") : ""}<th class="num">Win title</th></tr></thead><tbody>
        ${rows.map((r, i) => `<tr class="${r.alive ? "" : "out"}${SP.following().has(r.player) ? " mine" : ""}"><td class="muted">${i + 1}</td><td>${SP.starButton(r.player)} ${SP.flag(r.flag)}${SP.teamLink(r.player, c.sport)}</td>
          <td class="num opt">${r.rating}</td><td>${c.projected ? "Projected" : r.alive ? (c.champion === r.player ? "Champion" : "In") : "Out"}</td>
          ${reach ? rc.map(([k]) => `<td class="num">${SP.prob((r.reach || {})[k] || 0)}</td>`).join("") : ""}
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
          return head + `<tr><td class="muted">${pos}</td><td>${SP.starButton(r.team)} ${SP.flag(r.flag)}${SP.teamLink(r.team, c.sport)}</td>
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
      ${rows.map((r, i) => `<tr class="${SP.following().has(r.team) ? "mine" : ""}"><td class="muted">${i + 1}</td><td>${SP.starButton(r.team)} ${SP.flag(r.flag)}${SP.teamLink(r.team, c.sport)}</td>${groups ? `<td class="muted">${SP.esc((r.group || "").replace("Group ", ""))}</td>` : ""}
        <td class="num opt">${r.played}</td><td class="num">${r.pts}</td><td class="num opt">${r.gd > 0 ? "+" : ""}${r.gd}</td>
        <td class="num">${r.proj_pts == null ? "–" : r.proj_pts.toFixed(0)}</td><td class="num opt">${r.rating}</td>
        ${extra.map(([k]) => `<td class="num">${SP.prob(r[k])}</td>`).join("")}
        <td class="num">${SP.prob(r.p_win)}<span class="pbar"><i style="width:${r.p_win * 100}%"></i></span></td></tr>`).join("")}
    </tbody></table></div>`;
  }

  function seg(p, cls, label) {
    const w = Math.max(p * 100, 0);
    return `<div class="${cls}" style="flex:${w} 1 0" title="${SP.esc(label)}: ${SP.prob(p)}">${w >= 12 ? SP.prob(p) : ""}</div>`;
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
      const pA = m.p, names = `<div class="teams"><span>${SP.flag(m.af)}${SP.esc(m.a)}${past && m.w === 0 ? " ✓" : ""}</span><span>${past && m.w === 1 ? "✓ " : ""}${SP.esc(m.b)}${SP.flag(m.bf)}</span></div>`;
      const meta = past ? SP.verdictBadge(m, "tennis") : stateBadge(m);
      return `<div class="match"><div class="when">${SP.esc(past ? SP.when(m.date) : SP.time(m.date))}<br>${SP.esc(m.round)}</div>${names}
        <div class="split">${seg(pA, "h", m.a)}${seg(1 - pA, "a", m.b)}</div>
        <div class="meta"><span>${past ? "Pre-match chances" : "Win chances"}</span>${meta}</div>${past ? "" : tennisWhy(m)}</div>`;
    }
    const score = past ? ` <b>${m.hg}–${m.ag}</b> ` : "";
    const meta = past
      ? SP.verdictBadge(m, "soccer")
      : `<span>Likely score ${m.score[0]}–${m.score[1]}</span>${stateBadge(m)}`;
    return `<div class="match"><div class="when">${SP.esc(past ? SP.when(m.date) : SP.time(m.date))}</div>
      <div class="teams"><span>${SP.flag(m.hf)}${SP.esc(m.home)}</span>${score}<span>${SP.esc(m.away)}${SP.flag(m.af)}</span></div>
      <div class="split">${seg(m.p[0], "h", "Home win")}${seg(m.p[1], "d", "Draw")}${seg(m.p[2], "a", "Away win")}</div>
      <div class="meta">${past ? "<span>Pre-match: home · draw · away</span>" : ""}${meta}</div>${past ? "" : soccerWhy(m)}</div>`;
  }

  function h2hList(list, line) {
    if (!list || !list.length) return "<div>No meetings in our records since 2021.</div>";
    return `<div><b>Last meetings</b><ul>${list.map(x => `<li>${SP.esc(SP.date(x.date))}: ${line(x)}</li>`).join("")}</ul></div>`;
  }
  // "why": the ratings, home advantage and expected goals behind a soccer prediction
  function soccerWhy(m) {
    if (!m.r || !m.xg) return "";
    const gap = m.r[0] + (m.neutral ? 0 : (c.hfa || 0)) - m.r[1];
    return `<details><summary>Why these numbers?</summary><div class="why">
      <div>Ratings: ${SP.esc(m.home)} <b>${m.r[0]}</b>, ${SP.esc(m.away)} <b>${m.r[1]}</b>${m.neutral ? " (neutral ground)" : `, plus ${Math.round(c.hfa || 0)} for playing at home`}.
        A gap of ${Math.round(Math.abs(gap))} points in ${SP.esc(gap >= 0 ? m.home : m.away)}'s favour means about <b>${m.xg[0]}</b> goals to <b>${m.xg[1]}</b>.</div>
      ${SP.scoreGridHtml(m.xg[0], m.xg[1], m.home, m.away)}
      ${h2hList(m.h2h, x => `${SP.esc(x.home)} ${x.hg}–${x.ag} ${SP.esc(x.away)}`)}
      <div class="small muted"><a href="how.html">How the model works</a></div></div></details>`;
  }
  function tennisWhy(m) {
    if (!m.r) return "";
    return `<details><summary>Why these numbers?</summary><div class="why">
      <div>Ratings on ${SP.esc(c.surface || "this surface")} (a blend of overall and ${SP.esc(c.surface || "")}-court form): ${SP.esc(m.a)} <b>${m.r[0]}</b>, ${SP.esc(m.b)} <b>${m.r[1]}</b>.
        A ${Math.abs(m.r[0] - m.r[1])}-point gap${c.best_of === 5 ? ", over five sets" : ""} gives ${SP.esc(m.p >= 0.5 ? m.a : m.b)} ${SP.prob(Math.max(m.p, 1 - m.p))}.</div>
      ${h2hList(m.h2h, x => `${SP.esc(x.winner)} won${x.event ? " · " + SP.esc(x.event) : ""}${x.round ? " (" + SP.esc(x.round) + ")" : ""}`)}
      <div class="small muted"><a href="how.html">How the model works</a></div></div></details>`;
  }

  // chance of every finishing position, as a heatmap (one hue, light to dark)
  function positionsHtml() {
    const g = c.positions;
    if (!g) return "";
    const T = g.teams.length, top = Math.max(...g.p.flat());
    return `<details class="panel fold"><summary><h2>Every finishing position</h2><span class="muted small">How likely each team is to end up 1st, 2nd, 3rd…</span></summary>
      <div class="table-wrap"><table class="grid-scores positions"><thead><tr><th>Team</th>${g.p[0].map((_, k) => `<th>${k + 1}</th>`).join("")}</tr></thead><tbody>
      ${g.teams.map((t, i) => `<tr><th class="pos-team">${SP.esc(t)}</th>${g.p[i].map((p, k) =>
        `<td style="--t:${(p / top).toFixed(3)}" title="${SP.esc(t)}: ${k + 1}${["st", "nd", "rd"][k] || "th"} ${SP.prob(p)}">${p >= 0.01 ? Math.round(p * 100) : ""}</td>`).join("")}</tr>`).join("")}
      </tbody></table></div><p class="small muted">Numbers are percentages; blank means under 1%.</p></details>`;
  }

  // download the odds table as a spreadsheet-friendly CSV file
  function downloadCsv() {
    const cols = tennis ? [["player", "Player"], ["rating", "Rating"], ["p_win", "Win title"], ["p_sf", "Reach semis"]]
      : [["team", "Team"], ["group", "Group"], ["played", "Played"], ["pts", "Points"], ["gd", "Goal difference"], ["proj_pts", "Projected points"],
         ["rating", "Rating"], ["p_top", "Top places"], ["p_ko", "Knockouts"], ["p_drop", "Relegated"], ["p_qualify", "Qualify"], ["p_playoff", "Playoff"], ["p_win", "Win"]];
    const used = cols.filter(([k]) => c.table.some(r => r[k] != null));
    const cell = v => (v == null ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
    const reach = tennis && c.table.some(r => r.reach);
    const head = used.map(([, l]) => l).concat(reach ? ["Reach quarters", "Reach semis", "Reach final"] : []);
    const lines = [head.join(",")].concat(c.table.map(r => used.map(([k]) => cell(r[k]))
      .concat(reach ? ["qf", "sf", "f"].map(k => cell((r.reach || {})[k])) : []).join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
    a.download = `${c.name} odds ${(c.updated || "").slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // the chart in words: where the leading contenders started and where they are now
  function chartSummary() {
    const h = c.history;
    if (!h || h.dates.length < 2) return "";
    const first = SP.date(h.dates[0] + "T12:00Z");
    const lead = [...h.series].sort((a, b) => b.p[b.p.length - 1] - a.p[a.p.length - 1]).slice(0, 3);
    const bits = lead.map(s => {
      const a = s.p[0], b = s.p[s.p.length - 1];
      const how = Math.abs(b - a) < 0.02 ? "steady at" : b > a ? "up from " + SP.prob(a) + " to" : "down from " + SP.prob(a) + " to";
      return `${SP.esc(s.team)} ${how} ${SP.prob(b)}`;
    });
    return `Since ${SP.esc(first)}: ${bits.join("; ")}.`;
  }

  /* ---------- what if: pick results, replay the rest of the season in the browser ---------- */
  const picks = {};  // fixture index -> 0 home win, 1 draw, 2 away win
  let whatifResult = null;
  function whatifHtml() {
    const w = c.whatif;
    if (!w || !w.fixtures.length) return "";
    const next = w.fixtures.slice(0, 10);
    const opt = (k, v, label) => `<button type="button" data-pick="${k}" data-v="${v}" class="${(picks[k] ?? -1) === v ? "on" : ""}">${label}</button>`;
    return `<details class="panel whatif fold"${whatifResult || Object.keys(picks).length ? " open" : ""}><summary><h2>What if…?</h2><span class="muted small">Pick results and replay the season</span></summary>
      <p class="small muted" style="margin-top:0">Pick results for the next games and replay the rest of the season 2,000 times in your browser. Unpicked games are left to the model.</p>
      ${next.map((f, k) => `<div class="wi-row"><span class="wi-teams">${SP.esc(w.teams[f[0]])} v ${SP.esc(w.teams[f[1]])}</span>
        <span class="seg small">${opt(k, -1, "Model")}${opt(k, 0, "Home win")}${opt(k, 1, "Draw")}${opt(k, 2, "Away win")}</span></div>`).join("")}
      <p><button class="btn" id="wi-run" type="button">Play out the season</button> <button class="chip" id="wi-reset" type="button">Reset</button></p>
      <div id="wi-out" aria-live="polite">${whatifResult || ""}</div></details>`;
  }

  function runWhatif() {
    const w = c.whatif, T = w.teams.length, N = 2000;
    const gauss = () => Math.sqrt(-2 * Math.log(1 - Math.random())) * Math.cos(2 * Math.PI * Math.random());
    const poissonDraw = lam => { const L = Math.exp(-lam); let k = 0, p = 1; do { k++; p *= Math.random(); } while (p > L); return k - 1; };
    const win = new Array(T).fill(0), top = new Array(T).fill(0), drop = new Array(T).fill(0);
    for (let s = 0; s < N; s++) {
      const noise = Array.from({ length: T }, () => gauss() * w.noise);  // ratings are estimates, as in the main model
      const pts = w.base.map(b => b[0]), gd = w.base.map(b => b[1]), gf = w.base.map(b => b[2]);
      w.fixtures.forEach((f, k) => {
        const [i, j, lh, la] = f;
        let gh, ga;
        if (picks[k] != null && picks[k] >= 0) { [gh, ga] = [[1, 0], [0, 0], [0, 1]][picks[k]]; }
        else { const sh = Math.exp(noise[i] - noise[j]); gh = poissonDraw(lh * sh); ga = poissonDraw(la / sh); }
        pts[i] += gh > ga ? 3 : gh === ga ? 1 : 0; pts[j] += ga > gh ? 3 : gh === ga ? 1 : 0;
        gd[i] += gh - ga; gd[j] += ga - gh; gf[i] += gh; gf[j] += ga;
      });
      const order = [...Array(T).keys()].sort((a, b) => (pts[b] - pts[a]) || (gd[b] - gd[a]) || (gf[b] - gf[a]) || (Math.random() - 0.5));
      win[order[0]]++;
      order.slice(0, w.top || 0).forEach(i => top[i]++);
      if (w.drop) order.slice(T - w.drop).forEach(i => drop[i]++);
    }
    const now = Object.fromEntries(c.table.map(r => [r.team, r]));
    const rows = w.teams.map((t, i) => ({ t, win: win[i] / N, top: top[i] / N, drop: drop[i] / N, was: now[t] || {} }))
      .sort((a, b) => b.win - a.win || b.top - a.top);
    const show = rows.filter((r, k) => k < 6 || r.drop > 0.05 || (r.was.p_drop || 0) > 0.05);
    const cell = (v, was) => `${SP.prob(v)}${was != null && Math.abs(v - was) >= 0.01 ? ` <span class="muted small">(${v > was ? "▲" : "▼"} from ${SP.prob(was)})</span>` : ""}`;
    whatifResult = `<div class="table-wrap"><table><thead><tr><th>Team</th><th class="num">Win title</th>${w.top ? `<th class="num">Top ${w.top}</th>` : ""}${w.drop ? '<th class="num">Relegated</th>' : ""}</tr></thead><tbody>
      ${show.map(r => `<tr><td>${SP.esc(r.t)}</td><td class="num">${cell(r.win, r.was.p_win)}</td>${w.top ? `<td class="num">${cell(r.top, r.was.p_top)}</td>` : ""}${w.drop ? `<td class="num">${cell(r.drop, r.was.p_drop)}</td>` : ""}</tr>`).join("")}
      </tbody></table></div><p class="small muted">Picked results count as 1–0 or 0–0. Brackets show the site's current odds.</p>`;
    document.getElementById("wi-out").innerHTML = whatifResult;
  }

  document.addEventListener("click", e => {
    const b = e.target.closest("[data-pick]");
    if (b) {
      const k = +b.dataset.pick, v = +b.dataset.v;
      if (v < 0) delete picks[k]; else picks[k] = v;
      b.parentElement.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
      return;
    }
    if (e.target.id === "wi-run") {
      e.target.disabled = true; e.target.textContent = "Simulating…";
      setTimeout(() => { runWhatif(); e.target.disabled = false; e.target.textContent = "Play out the season"; }, 30);
    }
    if (e.target.id === "wi-reset") { Object.keys(picks).forEach(k => delete picks[k]); whatifResult = null; const y = scrollY; render(); scrollTo(0, y); }
  });

  // the games that swing the title race most, from the simulations split by each game's result
  function swingsHtml() {
    const list = (c.swings || []).filter(x => x.date).slice(0, 3);
    if (!list.length) return "";
    return `<h2>Matches that matter</h2><p class="small muted" style="margin:-6px 0 10px">Title chances after each possible result, from the same 10,000 simulated seasons.</p>
      <div class="matches">${list.map(x => {
      const lines = Object.entries(x.if).map(([team, v]) => {
        const words = team === x.home ? ["win", "draw", "lose"] : team === x.away ? ["lose", "draw", "win"]
          : [`${x.home} win`, "draw", `${x.away} win`];
        const parts = [0, 1, 2].filter(i => v[i] != null).map(i => `${SP.esc(words[i])} <b>${SP.prob(v[i])}</b>`);
        return `<div><b>${SP.esc(team)}</b>: ${parts.join(" · ")}</div>`;
      }).join("");
      return `<div class="match"><div class="when">${SP.esc(SP.when(x.date))}</div>
        <div class="teams"><span>${SP.esc(x.home)} v ${SP.esc(x.away)}</span><span class="muted small">moves the race up to ${Math.round(x.swing * 100)} pts</span></div>
        <div class="meta" style="display:block;color:var(--text-2)">${lines}</div></div>`;
    }).join("")}</div>`;
  }


  function render() {
    const fmt = c.format === "finals" ? "two groups of four, top two reach the semi-finals · " : "";
    const sub = tennis ? `${SP.esc(SP.date(c.start))} – ${SP.esc(SP.date(c.end))} · ${fmt}best of ${c.best_of} sets` : `${SP.esc(c.season)} season`;
    const h = c.history;
    const canChart = h && h.series.length && (h.dates.length > 1 || (c.live || []).length > 1);
    page.innerHTML = `
      <p class="small"><a href="index.html?sport=${sport}">← All ${tennis ? "tennis" : "soccer"}</a></p>
      <div class="card-head" style="justify-content:flex-start;margin-bottom:6px">${SP.tagFor(c)}<span class="status ${c.status}">${statusText}</span></div>
      <div class="title-row"><h1>${SP.esc(c.name)}</h1><button class="chip" id="share" type="button">Share</button></div>
      <p class="sub">${tennis ? SP.surface(c.surface) + " " : ""}${sub} <span class="updated" title="${SP.esc(SP.when(c.updated))}">· updated ${SP.esc(SP.ago(c.updated))}</span></p>
      ${c.stale ? `<div class="notice"><b>Not refreshed in the latest update.</b> ${SP.esc(c.stale_reason || "The data source didn't answer")}, so these are the last good predictions, from ${SP.esc(SP.when(c.updated))}.</div>` : ""}
      ${hero()}
      <h2>${tennis ? "Title odds over the tournament" : qualifying ? "Chance to qualify over the campaign: the races that moved most" : "Title odds over the season"}</h2>
      <div class="panel">${canChart ? `<div class="chart-box" ${asTable ? 'hidden' : ""}><canvas id="chart" role="img" aria-label="Chance to win over time" aria-describedby="chart-sum"></canvas></div>
        <p class="small chart-sum" id="chart-sum">${chartSummary()}</p>
        <div id="chart-table" ${asTable ? "" : "hidden"}>${chartTable()}</div>
        <div class="legend" id="legend"></div>
        <div style="margin-top:10px"><button class="chip" id="as-table">${asTable ? "Show as chart" : "Show as table"}</button></div>`
        : `<div class="muted">The chart fills in as results come in${c.projected ? ", starting when the groups are drawn" : ""}.</div>`}</div>
      <div class="title-row"><h2>${tennis ? "Every player's chances" : "Every team's chances"}</h2>${c.table.length ? '<button class="chip" id="csv" type="button" title="Download this table as a CSV file">Download CSV</button>' : ""}</div>
      <div class="panel" style="padding:4px 8px">${oddsTable() || '<div class="muted" style="padding:12px">No entrants yet.</div>'}${moreButton()}</div>
      ${swingsHtml()}
      ${whatifHtml()}
      ${positionsHtml()}
      <div class="two">
        <div><div class="title-row"><h2>Coming up</h2>${c.upcoming.length ? '<button class="chip" id="ics" type="button" title="Download these matches, with our chances, for your calendar">Add to calendar</button>' : ""}</div>${!tennis && c.upcoming.length ? `<p class="small muted" style="margin:-6px 0 10px"><i class="sw" style="background:var(--bar-home)"></i> home win &nbsp;<i class="sw" style="background:var(--bar-draw)"></i> draw &nbsp;<i class="sw" style="background:var(--bar-away)"></i> away win</p>` : ""}<div class="matches">${c.upcoming.length ? byDay(c.upcoming) : '<div class="empty">No scheduled matches.</div>'}</div></div>
        <div><h2>Recent results vs. our call</h2>${recordLine()}<div class="matches">${c.recent.length ? c.recent.map(m => matchRow(m, true)).join("") : '<div class="empty">No results yet.</div>'}</div></div>
      </div>`;
    if (canChart && !asTable) drawChart();
    if (canChart && asTable) legendOnly();
    document.getElementById("share").onclick = share;
    const csv = document.getElementById("csv");
    if (csv) csv.onclick = downloadCsv;
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
      borderWidth: 2, pointHoverRadius: 5, pointHoverBorderColor: surface, pointHoverBorderWidth: 2, tension: 0.25,
      pointRadius: ctx => (ctx.dataIndex === dates.length - 1 ? 4 : 0),  // mark today's value
      pointBorderColor: surface, pointBorderWidth: 2,
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
            backgroundColor: css("--surface"), titleColor: css("--text"), bodyColor: css("--text-2"),
            borderColor: css("--border"), borderWidth: 1, padding: 10, boxPadding: 4, usePointStyle: true,
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
