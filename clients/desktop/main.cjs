'use strict';
const {app,BrowserWindow,protocol,session,ipcMain,Menu}=require('electron');
const fs=require('node:fs');const path=require('node:path');const os=require('node:os');
const {createRemoteWindow}=require('./shell.cjs');const {webPreferences,endpoint}=require('./policy.cjs');
app.enableSandbox();
// Chromium transient state is held in private tmpfs, not a disk-backed profile.
if(!fs.existsSync('/dev/shm')) throw Error('Private memory-backed /dev/shm is required.');
const volatile=fs.mkdtempSync('/dev/shm/project-bots-');fs.chmodSync(volatile,0o700);
app.setPath('userData',volatile);app.setPath('sessionData',volatile);app.setPath('crashDumps',path.join(volatile,'crashes'));
app.commandLine.appendSwitch('disable-http-cache');
protocol.registerSchemesAsPrivileged([{scheme:'bots-setup',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
let setup,remote;
function showSetup(){
 const previous=remote;
 if(setup&&!setup.isDestroyed()){setup.focus();return;}
 setup=new BrowserWindow({title:'Connect Project Bots',width:620,height:380,resizable:false,webPreferences:{...webPreferences('setup'),preload:path.join(__dirname,'setup-preload.cjs')}});
 setup.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 setup.webContents.on('will-navigate',e=>e.preventDefault());
 setup.loadURL('bots-setup://local/');
 if(previous&&!previous.isDestroyed()) previous.close();
 remote=null;
}
app.whenReady().then(()=>{
 session.fromPartition('bots-setup', {cache: false}).protocol.handle('bots-setup',request=>{
  const u=new URL(request.url);const name=u.pathname==='/'?'setup.html':u.pathname.slice(1);
  if(u.host!=='local'||!['setup.html','setup.js'].includes(name)) return new Response('',{status:404});
  return new Response(fs.readFileSync(path.join(__dirname,name)),{headers:{'Content-Type':name.endsWith('.html')?'text/html':'text/javascript','Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; form-action 'none'; frame-ancestors 'none'",'Cache-Control':'no-store'}});
 });
 ipcMain.handle('connect',(event,value)=>{
  if(!setup||setup.isDestroyed()||event.sender!==setup.webContents||event.senderFrame!==setup.webContents.mainFrame||event.senderFrame.origin!=='bots-setup://local'||event.senderFrame.url!=='bots-setup://local/') throw Error('Denied');
  try {const origin=endpoint(value);remote=createRemoteWindow(origin);setup.close();return {ok:true};} catch {return {ok:false,error:'Use HTTPS origin only. HTTP is permitted only for exact localhost, 127.0.0.1 or [::1].'};}
 });
 Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'Project Bots',submenu:[{label:'Change endpoint / clear session',click:showSetup},{type:'separator'},{role:'quit'}]},{label:'View',submenu:[{role:'reload'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]}]));
 showSetup();
});
app.on('certificate-error',(event,_w,_url,_error,_certificate,callback)=>{event.preventDefault();callback(false);});
app.on('window-all-closed',()=>app.quit());
app.on('quit',()=>fs.rmSync(volatile,{recursive:true,force:true}));
