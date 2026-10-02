// Checks that the browser's per-atom resolution reproduces the build's area series at every change point.
// Needs a local server on :8765 serving preview.html (build/preview.sh, then python3 -m http.server 8765).
const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');
(async () => {
  const b = await chromium.launch({ channel: 'chromium' });
  const p = await b.newPage();
  const errs = []; p.on('pageerror', (e) => errs.push(e.message));
  await p.goto('http://localhost:8765/preview.html', { waitUntil: 'networkidle' });
  await p.waitForTimeout(600);
  const r = await p.evaluate(() => {
    const { stateAt, category, data } = window.__atlas, HELD = new Set(["direct", "focal_occupied", "autonomous"]);
    let worst = 0, at = null, n = 0;
    for (const row of data.series) {
      const s = stateAt(row.t + 1e-4); let claim = 0, held = 0, direct = 0;
      s.atomClaim.forEach((c, i) => { if (c) claim += data.atom_area[i]; });
      s.atomCtl.forEach((c, i) => { const k = category(c); if (HELD.has(k)) held += data.atom_area[i]; if (k === "direct" || k === "focal_occupied") direct += data.atom_area[i]; });
      const d = Math.max(Math.abs(claim - row.claim), Math.abs(held - row.held), Math.abs(direct - row.direct));
      n++; if (d > worst) { worst = d; at = row.t; }
    }
    return { checked: n, worst_km2: Math.round(worst), at };
  });
  console.log(JSON.stringify(r), errs.length ? errs : 'no page errors');
  await b.close();
})();
