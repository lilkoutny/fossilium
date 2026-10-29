const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const http = require('node:http');
const crypto = require('node:crypto');
const fs = require('fs');
const path = require('path');
const root=path.resolve(__dirname,'..');
const artifacts=path.join(root,'.content-state/dinodex-expansion-2026-10-29');
const server=http.createServer((req,res)=>{
  if(req.url==='/favicon.ico'){res.writeHead(204).end();return;}
  const file=path.resolve(root,'.'+(new URL(req.url,'http://localhost').pathname==='/'?'/index.html':new URL(req.url,'http://localhost').pathname));
  if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  fs.readFile(file,(err,data)=>{if(err){res.writeHead(404).end();return;}res.setHeader('Content-Type',({'.html':'text/html; charset=utf-8','.png':'image/png','.svg':'image/svg+xml','.json':'application/json'})[path.extname(file)]||'application/octet-stream');res.end(data);});
});
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const url='http://127.0.0.1:'+server.address().port;
  const hashes={};
  for(const [id,src] of Object.entries({majungasaurus:'0349ab8f-34d9-47f9-b9b6-2f30cd3e6bc6',deinocheirus:'d941e574-deba-45a8-b968-2b0e73c846a5',therizinosaurus:'c4961dce-d912-41c5-aed6-8736d0dae827',triceratops:'1b4685e6-d2a4-4cb4-abf1-6a6b85301f3a'})){
    const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
    hashes[id]=hash(path.join(root,'bilder',id+'.png'));assert.equal(hashes[id],hash('E:/Temp/codex-clipboard-'+src+'.png'));
  }
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}); const errors=[];
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())}); page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url); await page.waitForTimeout(300);
  const result=await page.evaluate(async()=>{
    const cards=[...document.querySelectorAll('.karte-dino')], markers=[...document.querySelectorAll('.marker')];
    const imgOK=await Promise.all([...document.querySelectorAll('.karte-dino img')].map(i=>new Promise(r=>{if(i.complete)r(i.naturalWidth>0);else{i.onload=()=>r(true);i.onerror=()=>r(false)}})));
    const nested=[...document.querySelectorAll('.karte-dino button button, .karte-dino a button, .karte-dino button a')].length;
    const filter=document.querySelector('#filterKost button[data-wert="Fleischfresser"]'); filter.click();
    const filterCount=document.querySelectorAll('.karte-dino').length;
    document.querySelector('#filterKost button[data-wert="alle"]').click();
    const opener=document.querySelector('.karte-dino .bild-oeffner'); opener.focus(); opener.click();
    const modalOpen=!document.querySelector('#lightbox').hidden, focused=document.activeElement.id==='lightboxSchliessen', overflow=getComputedStyle(document.body).overflow==='hidden';
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));
    return {cards:cards.length,markers:markers.length,imgOK:imgOK.every(Boolean),nested,filterCount,modalOpen,focused,overflow,focusReturned:document.activeElement===opener || document.activeElement.matches('.bild-oeffner')};
  });
  assert.equal(result.focusReturned,true);
  await page.getByRole('button',{name:'Großansicht öffnen: Therizinosaurus cheloniformis',exact:true}).click();
  await page.locator('#lightboxBild').evaluate(i=>i.decode());await page.keyboard.press('Tab');
  assert.equal(await page.locator('#lightboxSchliessen').evaluate(e=>e===document.activeElement),true);
  await page.screenshot({path:path.join(artifacts,'lightbox-desktop.png')});await page.keyboard.press('Escape');
  await page.locator('.fundort-knopf[data-dino="therizinosaurus"]').click();
  assert.match(await page.locator('#artikel h1').innerText(),/Therizinosaurus/);
  await page.locator('#artikel .bild-oeffner').click();await page.keyboard.press('Escape');
  assert.equal(await page.locator('#artikel .bild-oeffner').evaluate(e=>e===document.activeElement),true);
  await page.getByRole('button',{name:'Zurück zur Übersicht'}).click();
  await page.locator('#lexikon').screenshot({path:path.join(artifacts,'dinodex-desktop.png')});
  await page.locator('.karten-rahmen').screenshot({path:path.join(artifacts,'map-desktop.png')});
  await page.setViewportSize({width:390,height:844}); await page.reload(); await page.screenshot({path:'.content-state/dinodex-expansion-2026-10-29/dinodex-mobile.png',fullPage:true});
  const mobile=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth<=innerWidth, cards:document.querySelectorAll('.karte-dino').length}));
  await page.getByRole('button',{name:'Großansicht öffnen: Therizinosaurus cheloniformis',exact:true}).click();
  await page.locator('#lightboxBild').evaluate(i=>i.decode());await page.screenshot({path:path.join(artifacts,'lightbox-mobile.png')});
  await page.getByRole('button',{name:'Großansicht schließen'}).click();
  await browser.close();server.close();const report={result,mobile,errors,hashes};fs.writeFileSync(path.join(artifacts,'result.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(errors.length||result.cards!==9||result.markers!==9||!result.imgOK||result.nested||!result.modalOpen||!result.focused||!result.overflow||!result.focusReturned||!mobile.overflow)process.exitCode=1;
})().catch(e=>{console.error(e);server.close();process.exit(1)});
