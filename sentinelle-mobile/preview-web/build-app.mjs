import * as esbuild from 'esbuild';
import path from 'node:path';

const here = path.resolve('.');
const app = path.resolve(here, '..'); // = sentinelle-mobile

export const options = {
  entryPoints: ['app.tsx'],
  bundle: true,
  outfile: 'bundle-app.js',
  format: 'iife',
  jsx: 'automatic',
  loader: { '.js': 'jsx' },
  define: { __DEV__: 'false', 'process.env.NODE_ENV': '"production"' },
  resolveExtensions: ['.tsx', '.ts', '.jsx', '.js', '.json'],
  alias: {
    react: path.join(here, 'node_modules/react'),
    'react-dom': path.join(here, 'node_modules/react-dom'),
    'react-native': path.join(here, 'stubs/rn-shim.js'),
    // Version web (localStorage) pour une vraie persistance interactive.
    '@react-native-async-storage/async-storage': path.join(here, 'stubs/async-storage-web.js'),
    'react-native-permissions': path.join(here, 'stubs/permissions.js'),
    'react-native-push-notification': path.join(here, 'stubs/push-notification.js'),
    '@app': app,
  },
  logLevel: 'info',
};

// Build direct uniquement si exécuté en script (pas à l'import depuis serve.mjs).
if (import.meta.url === `file://${process.argv[1]}`) {
  await esbuild.build(options);
  console.log('built bundle-app.js');
}
