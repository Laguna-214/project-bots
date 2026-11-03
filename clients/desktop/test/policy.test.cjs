const {test}=require('node:test');const assert=require('node:assert/strict');
const p=require('../policy.cjs');
test('endpoint validation requires HTTPS except exact loopback',()=>{
 for(const u of ['https://bots.example','https://192.168.1.4:8443','http://127.0.0.1:8765','http://localhost:8765','http://[::1]:8765']) assert.ok(p.endpoint(u));
 for(const u of ['http://192.168.1.4','http://127.1','http://2130706433','https://u:p@bots.example','https://bots.example/path','https://bots.example?key=secret','https://bots.example#x','file:///tmp/a','javascript:1','https://bots.example\\@evil.example',' https://bots.example','https://bots.example\n']) assert.throws(()=>p.endpoint(u),u);
});
