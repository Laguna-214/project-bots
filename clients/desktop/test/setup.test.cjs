const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');
test('first-run protocol is registered on the isolated setup session and IPC only trusts its main frame',()=>{
 const s=fs.readFileSync(require.resolve('../main.cjs'),'utf8');
 assert.ok(s.includes("session.fromPartition('bots-setup', {cache: false}).protocol.handle"));
 for(const x of ["event.sender!==setup.webContents","event.senderFrame!==setup.webContents.mainFrame","event.senderFrame.url!=='bots-setup://local/'","app.enableSandbox()","app.setPath('sessionData',volatile)"])assert.ok(s.includes(x),x);
});
