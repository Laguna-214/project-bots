'use strict';
// Opt-in real Electron GUI acceptance. Never packaged with the native client.
const {app}=require('electron');const http=require('node:http');const https=require('node:https');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');const {execFileSync}=require('node:child_process');const {once}=require('node:events');
app.enableSandbox();const tmp=fs.mkdtempSync('/dev/shm/project-bots-acceptance-');fs.chmodSync(tmp,0o700);app.setPath('userData',tmp);app.setPath('sessionData',tmp);app.setPath('crashDumps',tmp);
const {createRemoteWindow}=require('../shell.cjs');
const servers=[];
app.whenReady().then(async()=>{
 const serve=async(s)=>{servers.push(s);s.listen(0,'127.0.0.1');await once(s,'listening');return s.address().port;};
 let foreignRequests=0;const foreignPort=await serve(http.createServer((_q,r)=>{foreignRequests++;r.end('blocked');}));
 const port=await serve(http.createServer((_q,r)=>{r.writeHead(200,{'Content-Type':'text/html','Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; script-src 'self'; connect-src 'self'; frame-src 'none'"});r.end('<!doctype html><title>Native fixture only</title><p id="fixture">ready</p>');}));
 const win=createRemoteWindow('http://127.0.0.1:'+port);await once(win.webContents,'did-finish-load');
 const isolated=await win.webContents.executeJavaScript("({node:typeof require,process:typeof process,bridge:typeof connection,fixture:document.getElementById('fixture').textContent})");
 assert.deepEqual(isolated,{node:'undefined',process:'undefined',bridge:'undefined',fixture:'ready'});
 assert.equal(win.webContents.getLastWebPreferences().sandbox,true);assert.equal(win.webContents.getLastWebPreferences().contextIsolation,true);
 const renderer=win.webContents.getOSProcessId();const status=fs.readFileSync('/proc/'+renderer+'/status','utf8');
 assert.match(status,/NoNewPrivs:\s+1/);assert.match(status,/Seccomp:\s+2/);
 console.log('Renderer kernel sandbox proof: '+JSON.stringify({pid:renderer,noNewPrivileges:true,seccompFilter:true}));
 const blocked=await win.webContents.executeJavaScript(`Promise.all([fetch('http://127.0.0.1:${foreignPort}/').then(()=>false,()=>true),fetch('file:///etc/passwd').then(()=>false,()=>true)])`);assert.deepEqual(blocked,[true,true]);assert.equal(foreignRequests,0);
 const popup=await win.webContents.executeJavaScript("window.open('https://example.com')===null");assert.equal(popup,true);
 execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-keyout',path.join(tmp,'key.pem'),'-out',path.join(tmp,'cert.pem'),'-days','1','-subj','/CN=localhost'],{stdio:'ignore'});
 const tlsPort=await serve(https.createServer({key:fs.readFileSync(path.join(tmp,'key.pem')),cert:fs.readFileSync(path.join(tmp,'cert.pem'))},(_q,r)=>r.end('must not load')));
 const rejected=createRemoteWindow('https://127.0.0.1:'+tlsPort);
 const [,code]=await once(rejected.webContents,'did-fail-load');assert.ok(code<0);rejected.close();
 console.log('Real sandboxed Electron fixture acceptance passed: isolation, no remote bridge, cross-origin/file/popup denial, fatal certificate errors. This is not backend/device user acceptance.');
}).catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{for(const s of servers)s.close();app.quit();});
app.on('quit',()=>fs.rmSync(tmp,{recursive:true,force:true}));
setTimeout(()=>{console.error('Electron acceptance timed out');process.exitCode=1;app.quit();},30000).unref();
