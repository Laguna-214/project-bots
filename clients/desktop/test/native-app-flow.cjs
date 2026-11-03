'use strict';
// Real native setup/IPC/window flow against a labeled local HTTP fixture.
const {app,BrowserWindow}=require('electron');
const http=require('node:http');
const assert=require('node:assert/strict');
const {once}=require('node:events');
let requests=0;
const server=http.createServer((_req,res)=>{requests++;res.writeHead(200,{'Content-Type':'text/html','Cache-Control':'no-store'});res.end('<!doctype html><title>Native flow fixture</title><p id="native-flow">Connected through real native setup</p>');});
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function waitFor(select){const until=Date.now()+20000;while(Date.now()<until){const value=select();if(value)return value;await delay(40);}throw Error('Native window readiness timed out');}
require('../main.cjs');
app.whenReady().then(async()=>{
 server.listen(0,'127.0.0.1');await once(server,'listening');const origin='http://127.0.0.1:'+server.address().port;
 const setup=await waitFor(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL()==='bots-setup://local/'&&!w.webContents.isLoading()));
 const setupState=await setup.webContents.executeJavaScript("({node:typeof require,process:typeof process,connect:typeof connection.connect})");
 assert.deepEqual(setupState,{node:'undefined',process:'undefined',connect:'function'});
 await setup.webContents.executeJavaScript('document.getElementById("endpoint").value='+JSON.stringify(origin)+';document.getElementById("connect").requestSubmit();true');
 const remote=await waitFor(()=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL()===origin+'/'&&!w.webContents.isLoading()));
 assert.equal(await remote.webContents.executeJavaScript('document.getElementById("native-flow").textContent'),'Connected through real native setup');
 assert.equal(await remote.webContents.executeJavaScript('typeof connection'),'undefined');
 assert(requests>0);
 console.log('Real native setup, restricted connect IPC and remote-window flow passed; fixture only, not production login/device acceptance.');
}).catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{server.close();app.quit();});
setTimeout(()=>{console.error('Native setup flow timed out');process.exitCode=1;app.quit();},30000).unref();
