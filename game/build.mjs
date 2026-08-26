// Build script - bundles everything into a single HTML file
import { build } from 'esbuild';
import { readFileSync, writeFileSync } from 'fs';

async function buildGame() {
  try {
    // Bundle JavaScript
    const result = await build({
      entryPoints: ['src/main.js'],
      bundle: true,
      minify: true,
      sourcemap: false,
      format: 'esm',
      target: ['es2020'],
      write: false
    });

    const bundledJS = result.outputFiles[0].text;

    // Read HTML template
    const htmlTemplate = readFileSync('index.html', 'utf8');
    const cssContent = readFileSync('styles.css', 'utf8');

    // Create single HTML file with embedded CSS and JS
    const outputHTML = htmlTemplate
      .replace('<link rel="stylesheet" href="styles.css">', `<style>${cssContent}</style>`)
      .replace('<script type="module" src="src/main.js"></script>', `<script type="module">${bundledJS}</script>`);

    // Write output
    writeFileSync('cheetosco.html', outputHTML);

    console.log('✓ Built cheetosco.html successfully');
    console.log('  Bundle size:', (outputHTML.length / 1024).toFixed(2), 'KB');
  } catch (error) {
    console.error('Build failed:', error);
    process.exit(1);
  }
}

buildGame();
