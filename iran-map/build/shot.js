// usage: node shot.js <out-prefix> [year] [w] [h] [dark] [actions-json]
const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');
(async () => {
  const [,, out, year = '1800', w = '1400', h = '860', dark = '0', actions = '[]'] = process.argv;
  const b = await chromium.launch({ channel: 'chromium' });
  const p = await b.newPage({ viewport: { width: +w, height: +h }, colorScheme: dark === '1' ? 'dark' : 'light' });
  const errs = [];
  p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ': ' + m.text()); });
  p.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  await p.goto(`http://localhost:8765/preview.html#${year}`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(900);
  for (const a of JSON.parse(actions)) {
    if (a.click) await p.click(a.click);
    if (a.eval) await p.evaluate(a.eval);
    if (a.key) { await p.focus(a.focus || 'body'); await p.keyboard.press(a.key); }
    await p.waitForTimeout(a.wait || 300);
  }
  await p.screenshot({ path: out + '.png', fullPage: w < 900 });
  const sw = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  console.log('horizontal overflow px:', sw);
  console.log(errs.join('\n') || 'no console errors');
  await b.close();
})();
