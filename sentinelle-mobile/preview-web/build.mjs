import * as esbuild from 'esbuild';
import path from 'node:path';

const here = path.resolve('.');
const app = path.resolve(here, '..'); // = sentinelle-mobile

await esbuild.build({
  entryPoints: ['preview.tsx'],
  bundle: true,
  outfile: 'bundle.js',
  format: 'iife',
  jsx: 'automatic',
  // Config TS inline : évite qu'esbuild cherche le tsconfig de base RN (absent ici).
  tsconfigRaw: { compilerOptions: { jsx: 'react-jsx' } },
  loader: { '.js': 'jsx' },
  define: { __DEV__: 'true', 'process.env.NODE_ENV': '"production"' },
  resolveExtensions: ['.tsx', '.ts', '.jsx', '.js', '.json'],
  alias: {
    // Force UNE seule copie de React (les écrans du dépôt ont leur propre
    // node_modules → sinon deux React = dispatcher de hooks null).
    react: path.join(here, 'node_modules/react'),
    'react-dom': path.join(here, 'node_modules/react-dom'),
    'react-native': path.join(here, 'stubs/rn-shim.js'),
    '@react-native-async-storage/async-storage': path.join(here, 'stubs/async-storage.js'),
    'react-native-permissions': path.join(here, 'stubs/permissions.js'),
    'react-native-push-notification': path.join(here, 'stubs/push-notification.js'),
    '@app': app,
  },
  logLevel: 'info',
});
console.log('built bundle.js');
