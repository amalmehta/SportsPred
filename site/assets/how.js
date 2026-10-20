/* How It Works page: accuracy, calibration chart, title-odds track record. */
(async () => {
  SP.header("how");
  const box = document.getElementById("stats");
  try {
    const m = await SP.json("data/model.json");
    SP.footer(m.updated);
    const items = [];
    const add = (label, b) => { if (b && b.n) items.push(`<div class="stat"><b>${Math.round(b.accuracy * 100)}%</b><span>${label} called · ${b.n.toLocaleString()} matches · Brier ${b.brier.toFixed(3)}</span></div>`); };
    add("Club soccer", m.soccer_clubs && m.soccer_clubs.backtest);
    add("International soccer", m.soccer_international && m.soccer_international.backtest);
    add("ATP tennis", m.tennis && m.tennis.atp && m.tennis.atp.backtest);
    add("WTA tennis", m.tennis && m.tennis.wta && m.tennis.wta.backtest);
    box.innerHTML = items.join("") || '<div class="muted">Run the build to see accuracy.</div>';
    byCompetition(m);
    calibrationChart(m);
    titleRecord(m);
    const t = m.tennis || {};
    if (t.atp && t.wta && t.atp.surface_weight != null) {
      const pc = w => Math.round(w * 100) + "%";
      const gain = x => x.backtest_overall_only ? ` (${(x.backtest_overall_only.accuracy * 100).toFixed(1)}% → ${(x.backtest.accuracy * 100).toFixed(1)}% called)` : "";
      document.getElementById("surface-mix").textContent =
        `(currently ${pc(t.atp.surface_weight)} surface for men${gain(t.atp)} and ${pc(t.wta.surface_weight)} for women${gain(t.wta)})`;
    }
  } catch (e) { box.innerHTML = '<div class="muted">Run the build to see accuracy.</div>'; SP.footer(); }
})();
// each competition against a no-skill baseline: soccer knows only how often home wins, draws and away
// wins happen there; tennis is a coin toss. Skill = how much lower our log loss is than the baseline's.
function byCompetition(m) {
  const t = m.tennis || {};
  const rows = [].concat((m.soccer_clubs || {}).by_competition || [], (m.soccer_international || {}).by_competition || [],
    (t.atp || {}).by_competition || [], (t.wta || {}).by_competition || []);
  const box = document.getElementById("by-comp");
  if (!rows.length) { box.hidden = true; return; }
  const pct = v => Math.round(v * 100) + "%", top = Math.max(...rows.map(r => r.skill));
  box.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Competition</th><th class="num opt">Matches</th>
    <th class="num" title="How often the result we rated likeliest happened">Called</th>
    <th class="num" title="Soccer: always picking the commonest result. Tennis: a coin toss.">Baseline</th>
    <th class="num" title="How much lower our log loss is than the baseline's">Skill</th>
    <th class="num opt" title="Lower is better">Log loss</th><th class="num opt">Baseline log loss</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${SP.esc(r.name)}</td><td class="num opt">${r.n.toLocaleString()}</td><td class="num">${pct(r.accuracy)}</td>
      <td class="num muted">${pct(r.base_accuracy)}</td>
      <td class="num">${(r.skill * 100).toFixed(1)}%<span class="pbar"><i style="width:${Math.max(0, r.skill / top) * 100}%"></i></span></td>
      <td class="num opt">${r.log_loss.toFixed(3)}</td><td class="num opt muted">${r.base_log_loss.toFixed(3)}</td></tr>`).join("")}
    </tbody></table></div>`;
}

function titleRecord(m) {
  const t = m.tennis || {};
  const groups = [["Club soccer seasons", m.soccer_clubs], ["ATP tournaments", t.atp], ["WTA tournaments", t.wta]]
    .map(([label, x]) => [label, x && x.title_backtest]).filter(([, b]) => b && b.summary && b.summary.n);
  const box = document.getElementById("titles");
  if (!groups.length) { box.closest("details") && (box.innerHTML = '<div class="muted">Run the build to see this.</div>'); return; }
  const pct = v => Math.round(v * 100) + "%";
  box.innerHTML = groups.map(([label, b]) => { const s = b.summary; return `<div class="stat"><b>${s.favourite_won} of ${s.n}</b>
    <span>${label}: won by the favourite · champion in our top 3 ${s.winner_in_top3} times · we gave the champion ${pct(s.avg_p_winner)} on average (${pct(s.avg_p_baseline)} if everyone were equal)</span></div>`; }).join("");
  const rows = groups.flatMap(([label, b]) => b.events.map(e => Object.assign({ group: label }, e)));
  document.getElementById("titles-table").innerHTML = `<div class="table-wrap"><table><thead><tr><th>Event</th><th>Champion</th>
    <th class="num">Our pre-event chance</th><th class="num">Our rank</th><th>Our favourite</th></tr></thead><tbody>
    ${rows.map(e => `<tr><td>${SP.esc(e.name)} <span class="muted">${SP.esc(e.season)}</span></td><td>${SP.esc(e.winner)}</td>
      <td class="num">${SP.prob(e.p_winner)}</td><td class="num">${e.rank === 1 ? "1st" : e.rank === 2 ? "2nd" : e.rank === 3 ? "3rd" : e.rank + "th"}</td>
      <td>${e.rank === 1 ? '<span class="muted">same</span>' : `${SP.esc(e.favourite)} <span class="muted">${SP.prob(e.p_favourite)}</span>`}</td></tr>`).join("")}
    </tbody></table></div>`;
}

function calibrationChart(m) {
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const t = m.tennis || {};
  const series = [
    ["Club soccer", m.soccer_clubs && m.soccer_clubs.calibration],
    ["International soccer", m.soccer_international && m.soccer_international.calibration],
    ["ATP tennis", t.atp && t.atp.calibration],
    ["WTA tennis", t.wta && t.wta.calibration],
  ].filter(([, rows]) => rows && rows.length);
  if (!series.length || !window.Chart) { document.getElementById("calib").closest(".panel").hidden = true; return; }
  const colors = [1, 2, 3, 4].map(i => css(`--s${i}`)), text2 = css("--text-2"), border = css("--border"), surface = css("--surface");
  const pct = v => Math.round(v * 100) + "%";
  new Chart(document.getElementById("calib"), {
    type: "line",
    data: { datasets: [
      { label: "Spot on", data: [{ x: 0, y: 0 }, { x: 100, y: 100 }], borderColor: css("--text-3"), borderDash: [5, 5],
        borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 0 },
      ...series.map(([label, rows], i) => ({
        label, data: rows.map(r => ({ x: r.p * 100, y: r.freq * 100, n: r.n })), borderColor: colors[i], backgroundColor: colors[i],
        borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, pointBorderColor: surface, pointBorderWidth: 2,
      })),
    ] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      parsing: false,
      plugins: { legend: { display: false },
        tooltip: { filter: it => it.datasetIndex > 0, callbacks: {
          label: ctx => ` ${ctx.dataset.label}: said ${pct(ctx.raw.x / 100)}, happened ${pct(ctx.raw.y / 100)} (${ctx.raw.n.toLocaleString()} predictions)` } } },
      scales: {
        x: { type: "linear", min: 0, max: 100, title: { display: true, text: "What the model said", color: text2 },
             grid: { color: border }, ticks: { color: text2, stepSize: 20, callback: v => v + "%" } },
        y: { min: 0, max: 100, title: { display: true, text: "How often it happened", color: text2 },
             grid: { color: border }, ticks: { color: text2, stepSize: 20, callback: v => v + "%" } },
      },
    },
  });
  document.getElementById("calib-legend").innerHTML = series.map(([label], i) =>
    `<span><i style="background:${colors[i]}"></i>${label}</span>`).join("") + `<span><i style="background:${css("--text-3")}"></i>Spot on</span>`;
  document.getElementById("calib-table").innerHTML = `<div class="table-wrap"><table><thead><tr><th>Band</th>${series.map(([l]) => `<th class="num">${l}</th>`).join("")}</tr></thead><tbody>
    ${Array.from({ length: 10 }, (_, b) => `<tr><td>${b * 10}–${b * 10 + 10}%</td>${series.map(([, rows]) => {
      const r = rows.find(r => Math.round(r.lo * 10) === b);
      return `<td class="num">${r ? `${pct(r.freq)} <span class="muted">of ${r.n.toLocaleString()}</span>` : "–"}</td>`;
    }).join("")}</tr>`).join("")}</tbody></table></div>`;
  const atp = t.atp && t.atp.calibration, top = atp && atp[atp.length - 1];
  if (top && top.lo >= 0.9) document.getElementById("calib-note").textContent =
    `Tennis runs a little hot at the extremes: ATP players given ${pct(top.p)} won ${pct(top.freq)} of the time. Softening those numbers was tested, but it didn't help on both tours when checked on unseen matches, so the model is left as it is and the gap is shown here instead.`;
}


/* Try it: the same formulas the pipeline uses, on any two teams or players. */
(async () => {
  const box = document.getElementById("compare");
  if (!box) return;
  let R;
  try { R = await SP.json("data/ratings.json"); } catch (e) { box.hidden = true; return; }
  let who = "soccer", venue = "home", court = "hard";
  const $ = id => document.getElementById(id);
  const names = () => Object.keys((R[who] || {}).teams || (R[who] || {}).players || {}).sort();
  const winProb = (ra, rb) => 1 / (1 + Math.pow(10, (rb - ra) / 400));
  const bestOfFive = p3 => {  // through the implied chance of winning each set, as in the pipeline
    let lo = 0, hi = 1;
    for (let i = 0; i < 50; i++) { const s = (lo + hi) / 2; if (s * s * (3 - 2 * s) < p3) lo = s; else hi = s; }
    const s = (lo + hi) / 2, q = 1 - s;
    return s ** 3 * (1 + 3 * q + 6 * q * q);
  };
  function fill() {
    $("cmp-list").innerHTML = names().map(n => `<option value="${SP.esc(n)}">`).join("");
    const list = names();
    const tops = list.slice().sort((a, b) => rating(b) - rating(a));
    $("cmp-a").value = tops[0] || ""; $("cmp-b").value = tops[1] || "";
    $("cmp-where").hidden = who === "atp" || who === "wta";
    $("cmp-court").hidden = !$("cmp-where").hidden;
    show();
  }
  function rating(name) {
    const x = R[who] || {};
    if (x.teams) return x.teams[name];
    const r = (x.players || {})[name];
    if (!r) return undefined;
    const w = x.weight || 0, surface = court === "bo5" ? "hard" : court;
    return (1 - w) * r[0] + w * r[{ hard: 1, clay: 2, grass: 3 }[surface]];
  }
  function show() {
    const a = $("cmp-a").value, b = $("cmp-b").value, ra = rating(a), rb = rating(b), out = $("cmp-out");
    if (ra == null || rb == null || a === b) { out.innerHTML = `<p class="muted small">Pick two different names from the list.</p>`; return; }
    if (who === "atp" || who === "wta") {
      let p = winProb(ra, rb); if (court === "bo5") p = bestOfFive(p);
      out.innerHTML = `<p>Ratings on this court: ${SP.esc(a)} <b>${Math.round(ra)}</b>, ${SP.esc(b)} <b>${Math.round(rb)}</b>.</p>
        <div class="split" style="height:26px">${[[p, "h", a], [1 - p, "a", b]].map(([v, cls, n]) => `<div class="${cls}" style="flex:${v * 100} 1 0" title="${SP.esc(n)}">${v >= 0.12 ? SP.prob(v) : ""}</div>`).join("")}</div>
        <p class="small muted">${SP.esc(a)} ${SP.prob(p)} · ${SP.esc(b)} ${SP.prob(1 - p)}. The chance is 1 / (1 + 10^(gap / 400)), using a blend of overall and court-specific ratings${court === "bo5" ? ", stretched to best of five sets" : ""}.</p>`;
      return;
    }
    const x = R[who], gap = ra + (venue === "home" ? x.hfa : 0) - rb;
    const lh = x.base * Math.exp(x.slope * gap / 400), la = x.base * Math.exp(-x.slope * gap / 400);
    const [h, d, aw] = SP.outcomeProbs(lh, la, x.rho || 0);
    out.innerHTML = `<p>Ratings: ${SP.esc(a)} <b>${ra}</b>, ${SP.esc(b)} <b>${rb}</b>${venue === "home" ? ` (+${Math.round(x.hfa)} for home)` : ""}. Expected goals: <b>${lh.toFixed(2)}</b> to <b>${la.toFixed(2)}</b>.</p>
      <div class="split" style="height:26px">${[[h, "h", a + " win"], [d, "d", "Draw"], [aw, "a", b + " win"]].map(([v, cls, n]) => `<div class="${cls}" style="flex:${v * 100} 1 0" title="${SP.esc(n)}">${v >= 0.12 ? SP.prob(v) : ""}</div>`).join("")}</div>
      <p class="small muted">${SP.esc(a)} win ${SP.prob(h)} · draw ${SP.prob(d)} · ${SP.esc(b)} win ${SP.prob(aw)}</p>
      ${SP.scoreGridHtml(lh, la, a, b, x.rho || 0)}`;
  }
  const seg = (id, set) => $(id).addEventListener("click", e => {
    const btn = e.target.closest("button"); if (!btn) return;
    $(id).querySelectorAll("button").forEach(x => x.classList.toggle("on", x === btn));
    set(btn.dataset.v);
  });
  seg("cmp-sport", v => { who = v; fill(); });
  seg("cmp-venue", v => { venue = v; show(); });
  seg("cmp-surface", v => { court = v; show(); });
  $("cmp-a").addEventListener("input", show); $("cmp-b").addEventListener("input", show);
  fill();
})();
