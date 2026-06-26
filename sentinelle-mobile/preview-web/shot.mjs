import { chromium } from 'playwright-core';
import path from 'node:path';

const exe = process.env.CHROME_BIN;
const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--force-color-profile=srgb'] });
const page = await browser.newPage({ viewport: { width: 2020, height: 820 }, deviceScaleFactor: 2 });
await page.goto('file://' + path.resolve('index.html'));
// Laisse les effets async (chargement config/historique) se résoudre.
await page.waitForTimeout(2000);

// Plein écran (toutes les maquettes côte à côte).
await page.screenshot({ path: 'board.png', fullPage: true });

// Capture aussi chaque téléphone individuellement.
const frames = await page.$$('.frame');
for (let i = 0; i < frames.length; i++) {
  await frames[i].screenshot({ path: `screen-${i + 1}.png` });
}
console.log(`captured board.png + ${frames.length} écrans`);
await browser.close();
