'use strict';
const {BrowserWindow,session}=require('electron');
const {randomUUID}=require('node:crypto');
const {endpoint,allowed,webPreferences}=require('./policy.cjs');
function createRemoteWindow(value) {
 const origin=endpoint(value), id=randomUUID();
 const ses=session.fromPartition('bots-'+id,{cache: false});
 ses.setPermissionRequestHandler((_w,_p,cb)=>cb(false));
 ses.setPermissionCheckHandler(()=>false);
 ses.setDevicePermissionHandler(()=>false);
 ses.setCertificateVerifyProc((request,cb)=>cb(request.errorCode===0?0:-2));
 ses.webRequest.onBeforeRequest((details,cb)=>cb({cancel:!allowed(origin,details.url,details.resourceType)}));
 ses.on('will-download',(event)=>event.preventDefault());
 const win=new BrowserWindow({title:'Project Bots',width:1220,height:850,backgroundColor:'#111827',webPreferences:webPreferences(id)});
 win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 win.webContents.on('will-attach-webview',event=>event.preventDefault());
 win.webContents.on('will-navigate',(event)=>{if(!allowed(origin,event.url,'mainFrame')) event.preventDefault();});
 win.webContents.on('will-frame-navigate',(event)=>{if(!event.isMainFrame||!allowed(origin,event.url,'mainFrame')) event.preventDefault();});
 win.webContents.on('will-redirect',(event)=>{if(!allowed(origin,event.url,'mainFrame')) event.preventDefault();});
 win.webContents.on('login',(event)=>event.preventDefault());
 win.on('closed',()=>{void ses.clearStorageData();void ses.clearCache();});
 win.loadURL(origin+'/').catch(()=>{if(!win.isDestroyed()) win.setTitle('Project Bots — connection failed (check endpoint and certificate)');});
 return win;
}
module.exports={createRemoteWindow};
