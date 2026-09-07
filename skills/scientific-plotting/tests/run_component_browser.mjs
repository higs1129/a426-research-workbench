// Small Chromium DevTools driver using Node's built-in WebSocket. Development only.
import {spawn} from 'node:child_process';
const [browser, profile, url] = process.argv.slice(2);
const child = spawn(browser, ['--headless=new','--disable-gpu','--no-first-run',
  '--disable-background-timer-throttling','--disable-renderer-backgrounding',
  '--disable-backgrounding-occluded-windows','--disable-background-networking',
  '--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'], {windowsHide:true});
let socket;
try {
  const endpoint = await new Promise((resolve,reject) => {
    let log=''; const timer=setTimeout(()=>reject(Error('DevTools startup timeout')),10000);
    child.stderr.on('data',chunk=>{log+=chunk;const match=log.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(match){clearTimeout(timer);resolve(match[1]);}});
    child.on('error',reject);
  });
  socket=new WebSocket(endpoint); await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let next=0; const pending=new Map();
  socket.onmessage=event=>{const msg=JSON.parse(event.data);const entry=pending.get(msg.id);if(entry){pending.delete(msg.id);msg.error?entry.reject(Error(JSON.stringify(msg.error))):entry.resolve(msg.result);}};
  const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params,sessionId}));});
  const {targetId}=await send('Target.createTarget',{url});
  const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
  await send('Emulation.setDeviceMetricsOverride',{width:1100,height:1600,deviceScaleFactor:1,mobile:false},sessionId);
  for(let i=0;i<200;i++){
    const state=await send('Runtime.evaluate',{expression:'document.querySelector("#regression-result")?.dataset.finished',returnByValue:true},sessionId);
    if(state.result.value==='true')break;
    await new Promise(r=>setTimeout(r,100));
  }
  const doc=await send('Runtime.evaluate',{expression:'document.documentElement.outerHTML',returnByValue:true},sessionId);
  process.stdout.write(doc.result.value);
  await send('Browser.close');
} finally {socket?.close(); child.kill();}
