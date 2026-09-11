# Third-party notices

This directory redistributes two local bundles. The original license and copyright notices must accompany copies of these bundles. No `node_modules` directory is distributed with the skill.

## Layout engine

`layout-engine.cjs` bundles the following components. This inventory was verified against the package paths in the generated bundle and the installed package versions used for the build.

| Component | Version | License text |
|---|---|---|
| bpmn-auto-layout | 2.0.0-alpha.2 | [MIT](licenses/bpmn-auto-layout-LICENSE.txt) |
| bpmn-moddle | 10.2.0 | [MIT](licenses/bpmn-moddle-LICENSE.txt) |
| min-dash | 5.1.0 | [MIT](licenses/min-dash-LICENSE.txt) |
| moddle | 8.2.1 | [MIT](licenses/moddle-LICENSE.txt) |
| moddle-xml | 12.2.0 | [MIT](licenses/moddle-xml-LICENSE.txt) |
| saxen | 11.1.1 | [MIT](licenses/saxen-LICENSE.txt) |

The layout engine contains a local sizing patch, applied by `../build_vendor.cjs`: task height 80 → 104, task width 100 → 220, external label width 90 → 150, and horizontal gap 100 → 120. These changes concern layout geometry. Upstream copyright notices are retained.

The `bpmn-auto-layout` npm package and the official [`v2.0.0-alpha.2` source tree](https://github.com/bpmn-io/bpmn-auto-layout/tree/v2.0.0-alpha.2) omit a `LICENSE` file; both its `package.json` and README declare MIT. The accompanying MIT text was obtained from the same project's [official LICENSE at commit `9eaa3b13532691b36f75d23806a84ccf53a91979`](https://github.com/bpmn-io/bpmn-auto-layout/blob/9eaa3b13532691b36f75d23806a84ccf53a91979/LICENSE), rather than reconstructing a copyright notice. The other five license files are verbatim copies from the exact installed package versions listed above.

## BPMN viewer

`bpmn-viewer.js` is the unmodified `bpmn-js` 18.6.3 production viewer distribution. Its complete license is provided in [BPMN-JS-LICENSE.txt](BPMN-JS-LICENSE.txt). It includes a condition requiring the bpmn.io watermark to remain fully visible in the application. The renderer preserves that watermark and reserves a separate footer in PNG previews so that the diagram does not cover it.

## Reproducible dependency resolution

`../vendor-src/package.json` pins `bpmn-auto-layout` 2.0.0-alpha.2, `bpmn-js` 18.6.3, and the build tool `esbuild` 0.25.12. `../vendor-src/package-lock.json` records exact transitive versions, npm download URLs, and integrity hashes. `esbuild` is used only to build the layout bundle; its executable is not included in the distributed skill. Bundle versions, sizing patches, and SHA-256 hashes are recorded in `versions.json`.
