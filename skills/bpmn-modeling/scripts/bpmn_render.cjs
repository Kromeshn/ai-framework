#!/usr/bin/env node
'use strict';
// Local bpmn-js preview. No external server, user profile, or browser download.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');

function options(argv) {
  const result = {};
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token === '--help' || token === '-h') return { help: true };
    if (['--out-dir', '--browser', '--playwright'].includes(token)) {
      if (!argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error(`Missing value for ${token}`);
      result[token.slice(2)] = argv[++i];
    } else if (!token.startsWith('-') && !result.input) result.input = token;
    else throw new Error(`Unexpected argument: ${token}`);
  }
  if (!result.input || !result['out-dir']) throw new Error('INPUT.bpmn and --out-dir DIR are required');
  return result;
}

function playwrightModule(explicit) {
  if (explicit || process.env.PLAYWRIGHT_MODULE) return require(path.resolve(explicit || process.env.PLAYWRIGHT_MODULE));
  try { return require('playwright'); } catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND') throw error;
  }
  const runtime = path.join(os.homedir(), '.cache', 'codex-runtimes');
  const candidates = [path.join(runtime, 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')];
  if (fs.existsSync(runtime)) {
    for (const entry of fs.readdirSync(runtime, { withFileTypes: true })) {
      if (entry.isDirectory()) candidates.push(path.join(runtime, entry.name, 'dependencies', 'node', 'node_modules', 'playwright'));
    }
  }
  for (const candidate of candidates) if (fs.existsSync(candidate)) return require(candidate);
  throw new Error('Playwright was not found. Use --playwright PATH or PLAYWRIGHT_MODULE; no packages are downloaded.');
}

function browserExecutable(explicit) {
  if (explicit) {
    const candidate = path.resolve(explicit);
    if (!fs.existsSync(candidate)) throw new Error(`Browser executable does not exist: ${candidate}`);
    return candidate;
  }
  const candidates = [];
  if (process.platform === 'win32') {
    for (const base of [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean)) {
      candidates.push(path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'));
      candidates.push(path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'));
    }
  } else if (process.platform === 'darwin') {
    candidates.push('/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
  } else candidates.push('/usr/bin/microsoft-edge', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser');
  const found = candidates.find(candidate => fs.existsSync(candidate));
  if (!found) throw new Error('A local Edge/Chrome executable was not found. Use --browser EXE; no browser is downloaded.');
  return found;
}

function fileStem(index, id) {
  return `${String(index + 1).padStart(2, '0')}-${String(id || 'diagram').replace(/[^a-zA-Z0-9_.-]/g, '_').slice(0, 100)}`;
}

async function main() {
  const args = options(process.argv.slice(2));
  if (args.help) {
    console.log('Usage: node bpmn_render.cjs INPUT.bpmn --out-dir DIR [--browser EXE] [--playwright PATH]');
    return;
  }
  const input = path.resolve(args.input), out = path.resolve(args['out-dir']);
  const source = fs.readFileSync(input);
  const xml = source.toString('utf8');
  const sha256 = crypto.createHash('sha256').update(source).digest('hex');
  const vendor = path.join(__dirname, 'vendor', 'bpmn-viewer.js');
  if (!fs.existsSync(vendor)) throw new Error(`Local bpmn-js bundle is missing: ${vendor}`);
  const playwright = playwrightModule(args.playwright);
  const executablePath = browserExecutable(args.browser);
  fs.mkdirSync(out, { recursive: true });
  const report = { status: 'running', input, sha256, generatedAt: new Date().toISOString(), renderer: 'bpmn-js', watermarkFooterHeight: 50, browser: executablePath, warnings: [], diagrams: [] };
  const geometry = { input, sha256, source: 'bpmn-js DOM text.getBBox()', diagrams: [] };
  const reportFile = path.join(out, 'report.json');
  let browser;
  try {
    browser = await playwright.chromium.launch({ executablePath, headless: true });
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1, serviceWorkers: 'block' });
    // This renderer never navigates to user content. The bundle is injected from disk.
    await context.route('**/*', route => route.abort('blockedbyclient'));
    const page = await context.newPage();
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.setContent('<!doctype html><html><head><meta charset="utf-8"><style>html,body,#canvas{margin:0;width:100%;height:100%;overflow:hidden;background:white} #canvas{height:calc(100% - 50px)} .djs-overlay-container,.bjs-breadcrumbs{display:none} .bjs-powered-by{position:fixed!important;right:12px!important;bottom:12px!important} svg{font-family:Arial,sans-serif}</style></head><body><div id="canvas"></div></body></html>');
    await page.addScriptTag({ path: vendor });
    const imported = await page.evaluate(async xmlText => {
      window.viewer = new window.BpmnJS({ container: '#canvas' });
      const imported = await window.viewer.importXML(xmlText);
      const diagrams = window.viewer.getDefinitions().diagrams || [];
      return { warnings: (imported.warnings || []).map(w => ({ message: w.message, elementId: w.element && w.element.id })), diagrams: diagrams.map(d => ({ id: d.id, planeId: d.plane && d.plane.id, bpmnElement: d.plane && d.plane.bpmnElement && d.plane.bpmnElement.id })) };
    }, xml);
    report.warnings.push(...imported.warnings);
    if (!imported.diagrams.length) throw new Error('No BPMNDiagram found in the input');
    for (const [index, diagram] of imported.diagrams.entries()) {
      const opened = await page.evaluate(async id => {
        const diagram = window.viewer.getDefinitions().diagrams.find(d => d.id === id);
        const result = await window.viewer.open(diagram);
        await document.fonts.ready;
        const canvas = window.viewer.get('canvas');
        canvas.zoom(1);
        const viewport = document.querySelector('.djs-container svg .viewport');
        if (!viewport) throw new Error('bpmn-js viewport is missing');
        const box = viewport.getBBox();
        const bounds = { x: Math.floor(box.x - 30), y: Math.floor(box.y - 30), width: Math.ceil(box.width + 60), height: Math.ceil(box.height + 60) };
        if (!Number.isFinite(bounds.width) || !Number.isFinite(bounds.height) || bounds.width <= 60 || bounds.height <= 60) throw new Error('Diagram is empty or has invalid rendered bounds');
        const labels = [], seen = new Set();
        const registry = window.viewer.get('elementRegistry');
        for (const element of registry.getAll()) {
          let elementRoot = element;
          while (elementRoot.parent) elementRoot = elementRoot.parent;
          if (elementRoot !== canvas.getRootElement()) continue;
          const gfx = registry.getGraphics(element);
          if (!gfx || element === canvas.getRootElement()) continue;
          for (const text of gfx.querySelectorAll('text.djs-label')) {
            if (seen.has(text) || !text.textContent.trim()) continue;
            // Only this element's visual, not text of nested children.
            if (text.closest('.djs-element') !== gfx) continue;
            seen.add(text);
            const b = text.getBBox();
            const transform = viewport.getCTM().inverse().multiply(text.getCTM());
            const points = [[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]].map(([x,y]) => new DOMPoint(x,y).matrixTransform(transform));
            const x = Math.min(...points.map(p => p.x)), y = Math.min(...points.map(p => p.y));
            const owner = element.labelTarget || element;
            labels.push({ id: element.id, ownerId: owner.businessObject ? owner.businessObject.id : owner.id, text: text.textContent, internal: !element.labelTarget, bounds: { x, y, width: Math.max(...points.map(p => p.x)) - x, height: Math.max(...points.map(p => p.y)) - y } });
          }
        }
        return { bounds, labels, warnings: (result.warnings || []).map(w => ({ message: w.message, elementId: w.element && w.element.id })) };
      }, diagram.id);
      const stem = fileStem(index, diagram.id);
      const entry = { ...diagram, dimensions: opened.bounds, warnings: opened.warnings, svg: path.join(out, `${stem}.svg`), overview: path.join(out, `${stem}.png`), tiles: [] };
      report.diagrams.push(entry);
      report.warnings.push(...opened.warnings.map(w => ({ ...w, diagramId: diagram.id })));
      const svg = await page.evaluate(async bounds => {
        const result = await window.viewer.saveSVG();
        // saveSVG has the same rendered content; enlarge its root viewport to include text.
        const parsed = new DOMParser().parseFromString(result.svg, 'image/svg+xml');
        const root = parsed.documentElement;
        root.setAttribute('viewBox', `${bounds.x} ${bounds.y} ${bounds.width} ${bounds.height}`);
        root.setAttribute('width', bounds.width); root.setAttribute('height', bounds.height);
        return new XMLSerializer().serializeToString(parsed);
      }, opened.bounds);
      fs.writeFileSync(entry.svg, svg);
      const bounds = opened.bounds;
      const scale = Math.min(1, 1600 / bounds.width, 1000 / bounds.height);
      const width = Math.max(1, Math.ceil(bounds.width * scale)), height = Math.max(1, Math.ceil(bounds.height * scale));
      await page.setViewportSize({ width, height: height + 50 });
      await page.evaluate(({ bounds, scale }) => window.viewer.get('canvas').viewbox({ x: bounds.x, y: bounds.y, width: window.innerWidth / scale, height: document.querySelector('#canvas').clientHeight / scale }), { bounds, scale });
      await page.screenshot({ path: entry.overview });
      entry.overviewScale = scale;
      if (scale < 1) {
        const tileWidth = Math.min(1400, bounds.width), tileHeight = Math.min(900, bounds.height), overlap = 100;
        const stepX = Math.max(1, tileWidth - overlap), stepY = Math.max(1, tileHeight - overlap);
        const columns = Math.max(1, Math.ceil((bounds.width - tileWidth) / stepX) + 1);
        const rows = Math.max(1, Math.ceil((bounds.height - tileHeight) / stepY) + 1);
        for (let row = 0; row < rows; row++) for (let column = 0; column < columns; column++) {
          const x = bounds.x + Math.min(column * stepX, bounds.width - tileWidth);
          const y = bounds.y + Math.min(row * stepY, bounds.height - tileHeight);
          await page.setViewportSize({ width: tileWidth, height: tileHeight + 50 });
          await page.evaluate(({ x, y, width, height }) => window.viewer.get('canvas').viewbox({ x, y, width, height }), { x, y, width: tileWidth, height: tileHeight });
          const filename = path.join(out, `${stem}-tile-${row + 1}-${column + 1}.png`);
          await page.screenshot({ path: filename });
          entry.tiles.push({ path: filename, x, y, width: tileWidth, height: tileHeight, imageHeight: tileHeight + 50, scale: 1 });
        }
      }
      geometry.diagrams.push({ ...diagram, bounds, labels: opened.labels });
    }
    if (pageErrors.length) throw new Error(`Browser rendering errors: ${pageErrors.join('; ')}`);
    report.geometry = path.join(out, 'geometry.json');
    fs.writeFileSync(report.geometry, JSON.stringify(geometry, null, 2));
    report.status = 'rendered';
    report.note = 'PNG images and DOM geometry come from this XML. Human inspection of overview and tiles is still required.';
  } catch (error) {
    report.status = 'failed';
    report.error = error.message;
    throw error;
  } finally {
    fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
    if (browser) await browser.close();
  }
  console.log(JSON.stringify({ status: report.status, diagrams: report.diagrams.length, report: reportFile, geometry: report.geometry }));
}
main().catch(error => { console.error(`bpmn_render: ${error.stack || error.message}`); process.exitCode = 1; });
