'use strict';
const fs=require('fs');
const {layoutProcess}=require('./vendor/layout-engine.cjs');
(async()=>{const start=Date.now();const result=await layoutProcess(fs.readFileSync(process.argv[2],'utf8'));fs.writeFileSync(process.argv[3],result.xml);const report={elapsed_ms:Date.now()-start,warnings:result.warnings.map(w=>({code:w.code,message:w.message,elementId:w.element?.id}))};fs.writeFileSync(process.argv[4],JSON.stringify(report,null,2));})().catch(e=>{console.error(e.stack);process.exit(1)});