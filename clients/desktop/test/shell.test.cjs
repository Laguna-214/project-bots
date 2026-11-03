const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
test('native shell denies certificate bypass, permissions, downloads and uses no remote bridge',()=>{
 const s=fs.readFileSync(path.join(__dirname,'../shell.cjs'),'utf8');
 for(const x of ['setCertificateVerifyProc','setPermissionRequestHandler','setPermissionCheckHandler','will-download','will-attach-webview','will-frame-navigate','setWindowOpenHandler','clearStorageData','cache: false']) assert.ok(s.includes(x),x);
 for(const x of ['ignore-certificate-errors','disable-web-security','no-sandbox','shell.openExternal']) assert.ok(!s.includes(x),x);
});
