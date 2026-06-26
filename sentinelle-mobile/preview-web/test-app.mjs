import { chromium } from 'playwright-core';
import path from 'node:path';
const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN, args:['--no-sandbox'] });
const page = await browser.newPage({ viewport:{width:900,height:900}, deviceScaleFactor:2 });
const errors=[]; page.on('pageerror',e=>errors.push(e.message));
await page.goto('file://'+path.resolve('index-app.html'));
await page.waitForTimeout(1200);
// 1) Onboarding -> activer
await page.getByText('Activer la protection').first().click();
await page.waitForTimeout(600);
// 2) Accueil -> Analyser un message
await page.getByText('Analyser un message').first().click();
await page.waitForTimeout(400);
// 3) Saisir un faux SMS d'arnaque + analyser (aucun serveur -> hors ligne)
await page.locator('textarea').first().fill('Desjardins: votre compte est bloque. Verifiez votre NIP ici: http://desjardins-securite.xyz/login');
await page.getByText('Analyser le message').first().click();
await page.waitForTimeout(1500);
const body = await page.evaluate(()=>document.body.innerText);
await page.screenshot({ path:'demo-verdict.png' });
console.log('pageerrors:', errors.length ? errors : 'none');
console.log('contient "Fraude":', /Fraude/.test(body));
console.log('contient "hors ligne":', /hors ligne/.test(body));
console.log('contient "Que faire":', /Que faire/.test(body));
await browser.close();
