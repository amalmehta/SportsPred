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
