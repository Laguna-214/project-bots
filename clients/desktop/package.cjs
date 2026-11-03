'use strict';
const fs=require('node:fs');const path=require('node:path');const {execFileSync}=require('node:child_process');const {createHash}=require('node:crypto');
(async()=>{
 const root=path.resolve(__dirname,'../artifacts');fs.mkdirSync(root,{recursive:true});
 const out=path.join(root,'ProjectBots-linux-x64');fs.rmSync(out,{recursive:true,force:true});
 fs.cpSync(path.join(__dirname,'node_modules/electron/dist'),out,{recursive:true});
 fs.renameSync(path.join(out,'electron'),path.join(out,'project-bots'));
 const {flipFuses,FuseVersion,FuseV1Options}=await import('@electron/fuses');
 await flipFuses(path.join(out,'project-bots'),{version:FuseVersion.V1,[FuseV1Options.RunAsNode]:false,[FuseV1Options.EnableNodeOptionsEnvironmentVariable]:false,[FuseV1Options.EnableNodeCliInspectArguments]:false});
 const app=path.join(out,'resources/app');fs.mkdirSync(app,{recursive:true});
 for(const f of ['main.cjs','shell.cjs','policy.cjs','setup-preload.cjs','setup.html','setup.js'])fs.copyFileSync(path.join(__dirname,f),path.join(app,f));
 fs.writeFileSync(path.join(app,'package.json'),JSON.stringify({name:'project-bots-desktop',version:'0.1.0',main:'main.cjs'}));
 fs.writeFileSync(path.join(out,'AppRun'),'#!/bin/sh\nset -eu\nulimit -c 0\nHERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\nexec "$HERE/project-bots"\n',{mode:0o755});
 const archive=path.join(root,'ProjectBots-linux-x64.tar.gz');
 execFileSync('tar',['-czf',archive,'-C',root,'ProjectBots-linux-x64']);
 const hash=createHash('sha256').update(fs.readFileSync(archive)).digest('hex');fs.writeFileSync(archive+'.sha256',hash+'  '+path.basename(archive)+'\n');
 console.log(hash+'  '+archive);
})().catch(e=>{console.error(e);process.exitCode=1;});
