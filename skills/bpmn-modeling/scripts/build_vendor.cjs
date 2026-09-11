/* Rebuild the pinned local bundles. npm ci --ignore-scripts in vendor-src first. */
const fs=require('fs'), path=require('path');
const runtime=path.resolve(process.argv[2] || path.join(__dirname,'vendor-src'));
const out=path.join(__dirname,'vendor');
const packages=path.join(runtime,'node_modules');
const pkg=JSON.parse(fs.readFileSync(path.join(packages,'bpmn-auto-layout/package.json'),'utf8'));
if(pkg.version!=='2.0.0-alpha.2')throw Error('Unexpected layout version');
let source=fs.readFileSync(path.join(packages,'bpmn-auto-layout/dist/index.cjs'),'utf8');
const patches={
 'const DEFAULT_TASK_HEIGHT = 80;':'const DEFAULT_TASK_HEIGHT = 104;',
 'const DEFAULT_TASK_WIDTH = 100;':'const DEFAULT_TASK_WIDTH = 220;',
 'const EXTERNAL_LABEL_WIDTH = 90;':'const EXTERNAL_LABEL_WIDTH = 150;',
 'const HORIZONTAL_GAP = 100;':'const HORIZONTAL_GAP = 120;'
};
for(const [before,after] of Object.entries(patches)) {
 if(source.split(before).length!==2)throw Error('Patch does not match exactly once: '+before);
 source=source.replace(before,after);
}
fs.mkdirSync(out,{recursive:true});
const esbuild=require(path.join(packages,'esbuild'));
esbuild.buildSync({absWorkingDir:__dirname,stdin:{contents:source,resolveDir:path.join(packages,'bpmn-auto-layout/dist'),sourcefile:'patched-bpmn-auto-layout.cjs'},outfile:path.join(out,'layout-engine.cjs'),bundle:true,platform:'node',target:'node18',format:'cjs',minify:false,legalComments:'eof',banner:{js:'/* bpmn-auto-layout 2.0.0-alpha.2; local sizing patch. See THIRD-PARTY-NOTICES.md. */'}});
fs.copyFileSync(path.join(packages,'bpmn-js/dist/bpmn-viewer.production.min.js'),path.join(out,'bpmn-viewer.js'));
fs.copyFileSync(path.join(packages,'bpmn-js/LICENSE'),path.join(out,'BPMN-JS-LICENSE.txt'));
const crypto=require('crypto');
const hashes=Object.fromEntries(['layout-engine.cjs','bpmn-viewer.js'].map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(out,f))).digest('hex')]));
fs.writeFileSync(path.join(out,'versions.json'),JSON.stringify({layout:'2.0.0-alpha.2',viewer:'18.6.3',esbuild:'0.25.12',patches,sha256:hashes},null,2)+'\n');
console.log(JSON.stringify(hashes));
