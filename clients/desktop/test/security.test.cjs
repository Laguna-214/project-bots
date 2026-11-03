const {test}=require('node:test');const assert=require('node:assert/strict');const p=require('../policy.cjs');
test('remote renderer cannot access Node, preload, frames, unsafe content or disk sessions',()=>{
 const w=p.webPreferences('test');
 assert.equal(w.nodeIntegration,false);assert.equal(w.contextIsolation,true);assert.equal(w.sandbox,true);
 assert.equal(w.webSecurity,true);assert.equal(w.allowRunningInsecureContent,false);assert.equal(w.webviewTag,false);
 assert.equal(w.preload,undefined);assert.ok(!w.partition.startsWith('persist:'));
});
test('all requests bind exact configured origin and reject frame injection',()=>{
 for(const u of ['https://bots.example/','https://bots.example/api/session']) assert.equal(p.allowed('https://bots.example',u,'xhr'),true);
 for(const u of ['https://evil.example','https://bots.example.evil/','file:///etc/passwd','data:text/html,hi','javascript:1','http://bots.example','wss://bots.example/']) assert.equal(p.allowed('https://bots.example',u,'xhr'),false);
 assert.equal(p.allowed('https://bots.example','https://bots.example/','subFrame'),false);
});
