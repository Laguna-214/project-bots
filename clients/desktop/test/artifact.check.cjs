'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
test('package includes an executable, launcher and native shell without development tests',()=>{
 const dir=path.join(__dirname,'../../artifacts/ProjectBots-linux-x64');
 for(const f of ['project-bots','AppRun','resources/app/main.cjs','resources/app/shell.cjs']) assert.ok(fs.statSync(path.join(dir,f)).isFile(),f);
 assert.equal(fs.existsSync(path.join(dir,'resources/app/test')),false);
 assert.ok((fs.statSync(path.join(dir,'AppRun')).mode&0o111)!==0);
});
test('packaged executable disables Node mode and Node debugger/environment entry points',async()=>{
 const {getCurrentFuseWire,FuseV1Options,FuseState}=await import('@electron/fuses');
 const wire=await getCurrentFuseWire(path.join(__dirname,'../../artifacts/ProjectBots-linux-x64/project-bots'));
 for(const key of [FuseV1Options.RunAsNode,FuseV1Options.EnableNodeOptionsEnvironmentVariable,FuseV1Options.EnableNodeCliInspectArguments])assert.equal(wire[key],FuseState.DISABLE);
});
