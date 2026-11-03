'use strict';
function endpoint(value) {
 if(typeof value!=='string'||value!==value.trim()||/[\\\s\x00-\x1f]/.test(value)) throw Error('Enter an HTTPS origin without a path or credentials.');
 const u=new URL(value);
 if(u.username||u.password||u.search||u.hash||u.pathname!=='/') throw Error('Origin only: no credentials, path, query or fragment.');
 const authority=value.match(/^https?:\/\/(\[[^\]]+\]|[^/:?#]+)(?::\d+)?\/?$/i);
 if(!authority) throw Error('Invalid origin.');
 const loopback=['localhost','127.0.0.1','[::1]'].includes(authority[1]);
 if(u.protocol!=='https:'&&!(u.protocol==='http:'&&loopback)) throw Error('HTTPS required outside exact loopback.');
 return u.origin;
}
function webPreferences(id) {
 return {partition:'bots-'+id, sandbox:true, contextIsolation:true, nodeIntegration:false,
 nodeIntegrationInWorker:false, nodeIntegrationInSubFrames:false, webSecurity:true,
 allowRunningInsecureContent:false, webviewTag:false, devTools:false, navigateOnDragDrop:false,
 spellcheck:false, safeDialogs:true};
}
function allowed(origin, value, type) {
 try { const u=new URL(value); return type!=='subFrame' && ['https:','http:'].includes(u.protocol) && u.origin===origin && !u.username && !u.password; } catch { return false; }
}
module.exports={endpoint,webPreferences,allowed};
