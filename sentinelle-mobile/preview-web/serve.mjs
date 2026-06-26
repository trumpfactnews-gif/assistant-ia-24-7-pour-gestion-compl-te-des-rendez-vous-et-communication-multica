// Serveur de développement : build + rechargement, puis sert l'app.
import * as esbuild from 'esbuild';

import { options } from './build-app.mjs';

const ctx = await esbuild.context(options);
await ctx.watch();
const { port } = await ctx.serve({ servedir: '.', port: 5173 });

console.log('\n====================================================');
console.log('  Sentinelle (démo navigateur) est prête.');
console.log(`  Ouvre cette adresse dans ton navigateur :`);
console.log(`\n      http://localhost:${port}/index-app.html\n`);
console.log('  (Ctrl+C pour arrêter)');
console.log('====================================================\n');
