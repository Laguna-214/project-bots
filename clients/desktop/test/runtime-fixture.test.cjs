const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const {EventEmitter}=require('node:events');
function fixture(){
 let ses,win,options,sessionOptions;class Window extends EventEmitter{constructor(o){super();options=o;win=this;this.webContents=new EventEmitter();this.webContents.setWindowOpenHandler=f=>this.popup=f;} loadURL(u){this.loaded=u;return Promise.resolve();} isDestroyed(){return false;}}
 const fake={BrowserWindow:Window,session:{fromPartition:(id,o)=>{sessionOptions={id,...o};ses=new EventEmitter();ses.webRequest={onBeforeRequest:f=>ses.request=f};for(const m of ['setPermissionRequestHandler','setPermissionCheckHandler','setDevicePermissionHandler','setCertificateVerifyProc'])ses[m]=f=>ses[m+'Callback']=f;ses.clearStorageData=async()=>{ses.cleared=true};ses.clearCache=async()=>{ses.cacheCleared=true};return ses;}}};
 const ctx={module:{exports:{}},require:name=>name==='electron'?fake:name==='./policy.cjs'?require('../policy.cjs'):require(name)};
 vm.runInNewContext(fs.readFileSync(require.resolve('../shell.cjs'),'utf8'),ctx);
 ctx.module.exports.createRemoteWindow('https://bots.example');return {ses,win,options,sessionOptions};
}
test('shell runtime fixture enforces certificate verification without override',()=>{
 const {ses}=fixture();let result;
 for(const errorCode of [-202,-200,-2]){ses.setCertificateVerifyProcCallback({errorCode},v=>result=v);assert.equal(result,-2);}
 ses.setCertificateVerifyProcCallback({errorCode:0},v=>result=v);assert.equal(result,0);
});
test('shell runtime fixture permits same-origin main navigation using current Electron event contract',()=>{
 const {win}=fixture();let prevented=0;
 const good={url:'https://bots.example/chat',isMainFrame:true,preventDefault(){prevented++;}};
 win.webContents.emit('will-navigate',good);win.webContents.emit('will-redirect',good);assert.equal(prevented,0);
 const bad={...good,url:'https://evil.example/'};win.webContents.emit('will-navigate',bad);win.webContents.emit('will-redirect',bad);assert.equal(prevented,2);
});
test('shell runtime fixture blocks all device permissions, downloads, popups and subframes',()=>{
 const {ses,win,options,sessionOptions}=fixture();let result;
 ses.setPermissionRequestHandlerCallback(null,'clipboard-read',v=>result=v);assert.equal(result,false);
 assert.equal(ses.setPermissionCheckHandlerCallback(),false);assert.equal(ses.setDevicePermissionHandlerCallback(),false);
 assert.equal(win.popup().action,'deny');assert.equal(options.webPreferences.preload,undefined);assert.equal(sessionOptions.cache,false);assert.ok(!sessionOptions.id.startsWith('persist:'));
 let prevented=0;const event={preventDefault(){prevented++;}};ses.emit('will-download',event);win.webContents.emit('will-attach-webview',event);win.webContents.emit('will-frame-navigate',{...event,isMainFrame:false,url:'https://bots.example/'});assert.equal(prevented,3);
 for(const [url,type,cancel] of [['https://bots.example/api/session','xhr',false],['https://evil.example/','xhr',true],['https://bots.example/','subFrame',true],['file:///etc/passwd','image',true]]){ses.request({url,resourceType:type},v=>result=v.cancel);assert.equal(result,cancel);}
 win.emit('closed');assert.equal(ses.cleared,true);assert.equal(ses.cacheCleared,true);
});
