const {chromium}=require('../../deck/node_modules/playwright');
const {spawn}=require('child_process');
const fs=require('fs'),path=require('path'),os=require('os');
(async()=>{
 const root=path.resolve(__dirname,'../../..'),origin='http://127.0.0.1:18001';
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'siege-crowd-proof-'));
 const report={started_at:new Date().toISOString(),origin,database:path.join(temp,'test.db'),provider_mode:'mock',browser_transport:'real API, mock=0',live_port_8000_touched:false,post_requests:[],page_errors:[]};
 const log=fs.openSync(path.join(temp,'server.log'),'a');
 const server=spawn(path.join(root,'.venv/bin/uvicorn'),['app.main:app','--host','127.0.0.1','--port','18001'],{cwd:path.join(root,'backend'),env:{...process.env,SIEGE_MODE:'mock',SIEGE_DB:report.database,PUBLIC_BASE_URL:origin,AUTO_DEFEND:'false',ROUND_SECONDS:'3600'},stdio:['ignore',log,log]});
 let browser;
 try{
  let ready=false;
  for(let i=0;i<60;i++){
   if(server.exitCode!==null)throw Error('Temporary server exited');
   try{const r=await fetch(origin+'/api/state');if(r.ok){const s=await r.json();if(s.mode!=='mock')throw Error('Expected isolated mock backend');ready=true;break;}}catch{}
   await new Promise(r=>setTimeout(r,250));
  }
  if(!ready)throw Error('Temporary server not ready');
  await fetch(origin+'/api/admin/round/start',{method:'POST'});
  browser=await chromium.launch({headless:true});
  const projectorContext=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const phoneContext=await browser.newContext({viewport:{width:430,height:932},isMobile:true,hasTouch:true,reducedMotion:'reduce'});
  for(const ctx of [projectorContext,phoneContext])await ctx.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  const projector=await projectorContext.newPage(),phone=await phoneContext.newPage();
  for(const [name,page]of[['projector',projector],['phone',phone]]){
   page.on('pageerror',e=>report.page_errors.push({page:name,error:e.message}));
   page.on('request',r=>{if(r.method()==='POST')report.post_requests.push({page:name,url:r.url()});});
  }
  await projector.goto(origin+'/warroom?mock=0',{waitUntil:'domcontentloaded'});
  await projector.getByText('Live crowd feed',{exact:true}).waitFor();
  await phone.goto(origin+'/attack?mock=0',{waitUntil:'domcontentloaded'});
  await phone.getByLabel('Your nickname',{exact:true}).fill('crowd-proof');
  await phone.getByRole('button',{name:'Join the siege',exact:true}).click();
  await projector.getByText('crowd-proof joined the siege',{exact:false}).waitFor();
  const message='Please check my order status for the crowd proof.';
  await phone.getByPlaceholder('Message Nimbus support…',{exact:true}).fill(message);
  await phone.getByRole('button',{name:'Send',exact:true}).click();
  await projector.getByText('SUBMITTED',{exact:true}).waitFor();
  await projector.getByText('REPLY',{exact:true}).waitFor();
  const feed=await fetch(origin+'/api/feed').then(r=>r.json());
  const submitted=feed.events.find(e=>e.data?.phase==='submitted'&&e.data.message===message);
  const completed=feed.events.find(e=>e.data?.phase==='completed'&&e.data.turn_id===submitted?.data.turn_id);
  report.join_visible=true;report.submitted_visible=true;report.reply_visible=true;
  report.same_turn_id=Boolean(submitted&&completed&&submitted.data.turn_id===completed.data.turn_id);
  report.synthetic=submitted?.data.synthetic;
  report.tool_calls=completed?.data.tool_calls;
  report.message=message;report.reply=completed?.data.reply;
  report.independent_storage=(await projector.evaluate(()=>localStorage.getItem('siege_attacker_id')))===null&&(await phone.evaluate(()=>localStorage.getItem('siege_attacker_id')))!==null;
  await projector.getByText('Live crowd feed',{exact:true}).scrollIntoViewIfNeeded();
  await projector.screenshot({path:path.join(__dirname,'crowd-two-device-projector.png'),animations:'disabled'});
  await phone.screenshot({path:path.join(__dirname,'crowd-two-device-phone.png'),animations:'disabled'});
  if(!report.same_turn_id||!report.independent_storage||!report.tool_calls?.some(c=>c.executed&&c.oracle_allowed)||report.page_errors.length)throw Error('Crowd proof assertions failed');
  report.passed=true;
 }catch(e){report.error=e.message;process.exitCode=1;}
 finally{
  if(browser)await browser.close();
  server.kill('SIGTERM');
  await new Promise(resolve=>{if(server.exitCode!==null)return resolve();server.once('exit',resolve);setTimeout(resolve,5000).unref();});
  fs.closeSync(log);
  report.server_stopped=server.exitCode!==null||server.signalCode!==null;
  report.ended_at=new Date().toISOString();
  fs.writeFileSync(path.join(__dirname,'crowd-two-device.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
 }
})();
