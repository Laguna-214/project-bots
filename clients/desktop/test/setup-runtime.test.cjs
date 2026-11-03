const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const {EventEmitter}=require('node:events');
test('setup runtime fixture rejects remote/subframe IPC and changes endpoint without closing last window',async()=>{
 const windows=[],app=new EventEmitter();let handler,menu,protocolHandler;let quitGaps=0;
 Object.assign(app,{enableSandbox(){},setPath(){},commandLine:{appendSwitch(){}},whenReady:()=>Promise.resolve(),quit(){}});
 class Window {constructor(){this.destroyed=false;this.webContents={mainFrame:{url:'bots-setup://local/',origin:'bots-setup://local'},setWindowOpenHandler(){},on(){}};windows.push(this);}loadURL(){return Promise.resolve();}isDestroyed(){return this.destroyed;}close(){this.destroyed=true;if(!windows.some(w=>!w.destroyed))quitGaps++;}focus(){}}
 const fake={app,BrowserWindow:Window,protocol:{registerSchemesAsPrivileged(){}},session:{fromPartition:()=>({protocol:{handle:(_s,h)=>protocolHandler=h}})},ipcMain:{handle:(_n,h)=>handler=h},Menu:{buildFromTemplate:t=>t,setApplicationMenu:m=>menu=m}};
 const ctx={__dirname:require('node:path').resolve(__dirname,'..'),Response,require:name=>name==='electron'?fake:name==='node:fs'?{existsSync:()=>true,mkdtempSync:()=>'/fixture',chmodSync(){},rmSync(){},readFileSync:fs.readFileSync}:name==='./shell.cjs'?{createRemoteWindow:()=>new Window()}:name==='./policy.cjs'?require('../policy.cjs'):require(name)};
 vm.runInNewContext(fs.readFileSync(require.resolve('../main.cjs'),'utf8'),ctx);await new Promise(setImmediate);
 assert.equal(windows.length,1);assert.equal(typeof protocolHandler,'function');
 const setup=windows[0];const event={sender:setup.webContents,senderFrame:setup.webContents.mainFrame};
 assert.throws(()=>handler({...event,sender:{}},'https://bots.example'),/Denied/);
 assert.throws(()=>handler({...event,senderFrame:{url:'bots-setup://local/'}},'https://bots.example'),/Denied/);
 setup.webContents.mainFrame.origin='null';assert.throws(()=>handler(event,'https://bots.example'),/Denied/);setup.webContents.mainFrame.origin='bots-setup://local';
 assert.equal(handler(event,'http://192.168.1.4').ok,false);
 assert.equal(handler(event,'https://bots.example').ok,true);assert.equal(setup.destroyed,true);
 menu[0].submenu[0].click();assert.equal(windows.length,3);assert.equal(quitGaps,0,'must open setup before closing the remote window');
});
