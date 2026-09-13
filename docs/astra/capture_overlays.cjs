// Original motion-film typography, rendered as transparent video layers.
// No application routes, live data or generated key art are modified.
const { chromium } = require('../deck/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');

const scenes = [
  {kicker:'01 / THE CHALLENGE', title:'Every agent has a<br><em>breaking point.</em>', sub:'Give it real tools.<br>Let the room find the cracks.', tags:['REFUNDS','ORDER DATA','STORE CREDIT']},
  {kicker:'02 / THE SIGNAL', title:'A breach becomes<br><em>evidence.</em>', sub:'A forbidden tool call executes.<br>The trace preserves what happened.', tags:['GATE ALLOWED','ORACLE FORBIDDEN','TOOL EXECUTED'], tone:'red'},
  {kicker:'03 / THE RESPONSE', title:'The gate<br><em>learns from it.</em>', sub:'A defender rewrites its policy.<br>Attack variants test the new defense.', tags:['COLLECT','AMPLIFY','PATCH','EVALUATE'], tone:'violet'},
  {kicker:'04 / THE STANDARD', title:'A fix earns<br><em>its way in.</em>', sub:'Catch more attacks.<br>Keep legitimate customers moving.', tags:['CATCH RATE MUST RISE','BENIGN ALLOW ≥ 90%'], tone:'green'},
  {kicker:'SIEGE / AN AGENT LOOP THAT LEARNS', title:'Break it.<br><em>Watch it learn.</em>', sub:'A live red-team arena.<br>An evaluated defense loop.', tags:['WEAVE','TYPESAFE','COREWEAVE'], end:true},
];

function html(scene, portrait) {
 const accent=scene.tone==='red'?'#ff6078':scene.tone==='violet'?'#bba3ff':'#66eea4';
 return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
 *{box-sizing:border-box}html,body{width:100%;height:100%;margin:0;background:transparent;color:#eef0eb;font-family:'Avenir Next','Arial',sans-serif}
 body{position:relative;overflow:hidden}body:before{content:'';position:absolute;inset:0;background:${portrait?'linear-gradient(180deg,#07080c 0%,#07080c 32%,transparent 47%,transparent 65%,#07080c 79%)':'linear-gradient(90deg,rgba(7,8,12,.99),rgba(7,8,12,.92) 26%,rgba(7,8,12,.48) 49%,transparent 75%)'}}
 .brand{position:absolute;top:64px;left:80px;font-weight:800;font-size:30px;letter-spacing:10px;display:flex;align-items:center;gap:20px}.mark{width:23px;height:29px;border:2px solid #66eea4;transform:skewY(-12deg);box-shadow:7px 0 0 -3px #07080c,9px 0 #66eea4}
 .edition{position:absolute;top:74px;right:80px;font:13px 'Menlo',monospace;letter-spacing:2px;color:#b0b7bb}
 main{position:absolute;top:245px;left:80px;width:1000px}.kicker{font:14px 'Menlo',monospace;letter-spacing:3px;color:${accent};margin-bottom:35px}h1{font-size:91px;font-weight:650;letter-spacing:-5px;line-height:1.06;margin:0 0 34px}h1 em{font-style:normal;color:${accent}}.sub{font-size:28px;line-height:1.5;color:#bfc5c6;font-weight:400;margin-bottom:45px}.tags{display:flex;gap:12px;flex-wrap:wrap;max-width:830px}.tag{font:12px 'Menlo',monospace;letter-spacing:1px;padding:12px 16px;border:1px solid #52605a;border-radius:3px;background:rgba(7,8,12,.6);color:#d0d5d2}
 footer{position:absolute;left:80px;right:80px;bottom:58px;display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(168,190,181,.24);padding-top:24px;font:12px 'Menlo',monospace;letter-spacing:1.5px;color:#aeb8b2}.pill{display:flex;align-items:center;gap:9px}.dot{height:6px;width:6px;border-radius:100%;background:#66eea4}.progress{position:absolute;bottom:0;left:0;height:3px;background:${accent};width:${(scenes.indexOf(scene)+1)*20}%;}
 ${portrait?`.brand{left:66px;top:100px;font-size:35px}.edition{right:66px;top:111px;font-size:11px}main{left:66px;top:255px;width:948px}.kicker{font-size:16px;margin-bottom:35px}h1{font-size:98px;line-height:1.08;letter-spacing:-4px;margin-bottom:34px}.sub{font-size:33px;line-height:1.45}.tags{position:absolute;top:1210px;max-width:890px;gap:16px}.tag{font-size:15px;padding:18px 22px}footer{left:66px;right:66px;bottom:115px;font-size:13px;line-height:1.8;gap:30px}.sub{max-width:930px}`:''}
 </style></head><body><div class="brand"><i class="mark"></i>SIEGE</div><div class="edition">COREWEAVE HACKS / 2026</div><main><div class="kicker">${scene.kicker}</div><h1>${scene.title}</h1><div class="sub">${scene.sub}</div><div class="tags">${scene.tags.map(t=>`<span class="tag">${t}</span>`).join('')}</div></main><footer><span class="pill"><i class="dot"></i>REASON → ACT → CATCH → ITERATE</span><span>ILLUSTRATIVE FILM</span></footer><div class="progress"></div></body></html>`;
}

(async()=>{
 const out=path.join(__dirname,'render');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true});
 for(const [name,width,height] of [['landscape',1920,1080],['portrait',1080,1920]]){
   const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
   for(let i=0;i<scenes.length;i++){
     const source=html(scenes[i],name==='portrait');
     fs.writeFileSync(path.join(out,`${name}-${i}.html`),source);
     await page.setContent(source);await page.evaluate(()=>document.fonts.ready);
     await page.screenshot({path:path.join(out,`${name}-${i}.png`),omitBackground:true});
   }
   await page.close();
 }
 await browser.close();console.log('Rendered 10 transparent title layers.');
})().catch(err=>{console.error(err);process.exit(1)});
