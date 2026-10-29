const {chromium}=require('playwright');
const assert=require('node:assert/strict'),http=require('node:http'),crypto=require('node:crypto'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'.content-state/dinodex-modern-2026-10-29');fs.mkdirSync(out,{recursive:true});
const server=http.createServer((req,res)=>{if(req.url==='/favicon.ico'){res.writeHead(204).end();return;}const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname),file=path.resolve(root,'.'+(pathname==='/'?'/index.html':pathname));if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}fs.readFile(file,(err,data)=>{if(err){res.writeHead(404).end();return;}res.setHeader('Content-Type',({'.html':'text/html; charset=utf-8','.svg':'image/svg+xml','.json':'application/json','.png':'image/png'})[path.extname(file)]||'application/octet-stream');res.end(data);});});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.goto('http://127.0.0.1:'+server.address().port,{waitUntil:'networkidle'});
  const dinos=await page.evaluate(()=>DINOS.map(d=>({id:d.id,name:d.name,bild:d.bild})));
  assert.equal(dinos.length,9);assert.equal(await page.locator('#markerEbene .marker').count(),9);assert.equal(await page.locator('#raster .karte-dino').count(),9);
  await page.locator('#raster img').evaluateAll(imgs=>Promise.all(imgs.map(i=>i.decode())));
  const portraitChecks=[];
  for(const d of dinos){
   const overview=page.locator('#raster .bild-oeffner[data-dino="'+d.id+'"]');
   assert.equal(await overview.getAttribute('aria-label'),'Artikel öffnen: '+d.name);
   await overview.click();
   assert.equal((await page.locator('#artikel h1').innerText()).replace(/\s+/g,' ').trim(),d.name);
   assert.equal(await page.locator('#lightbox').isVisible(),false);
   assert.equal(await page.locator('#artikel table').count(),0);
   assert.equal(await page.locator('#artikel .artikel-fakt').count(),4);
   const columns=await page.locator('#artikel .artikel-lesebereich').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length);assert.equal(columns,2);
   const zoom=page.locator('#artikel .bild-oeffner');await zoom.locator('img').evaluate(i=>i.decode());
   assert.equal(await zoom.locator('img').evaluate(i=>getComputedStyle(i).objectFit),'contain');
   assert.equal(await page.locator('#artikel h1').evaluate(e=>e===document.activeElement),true);
   await zoom.click();await page.locator('#lightboxBild').evaluate(i=>i.decode());
   assert.equal(await page.locator('#lightbox').isVisible(),true);assert.match(await page.locator('#lightboxBild').getAttribute('src'),new RegExp(d.id));
   await page.keyboard.press('Tab');assert.equal(await page.locator('#lightboxSchliessen').evaluate(e=>e===document.activeElement),true);
   await page.keyboard.press('Escape');assert.equal(await zoom.evaluate(e=>e===document.activeElement),true);
   if(d.id==='yutyrannus'){
    await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,'yutyrannus-desktop-hero.png')});await page.locator('#artikel').screenshot({path:path.join(out,'yutyrannus-desktop-full.png')});
   }
   portraitChecks.push(d.id);await page.getByRole('button',{name:'‹ Zurück zur Übersicht',exact:true}).click();
   assert.equal(await overview.evaluate(e=>e===document.activeElement),true);
  }
  // A keyboard activation on the overview also navigates, without opening the modal.
  const keyboardCard=page.locator('#raster .bild-oeffner[data-dino="deinocheirus"]');await keyboardCard.focus();await page.keyboard.press('Enter');
  assert.match(await page.locator('#artikel h1').innerText(),/Deinocheirus/);assert.equal(await page.locator('#lightbox').isVisible(),false);
  // Related portraits and the world-map link are real navigation controls.
  await page.locator('#artikel .artikel-weiter a').last().click();assert.match(await page.locator('#artikel h1').innerText(),/Therizinosaurus/);
  await page.getByRole('link',{name:'Auf der Weltkarte entdecken'}).click();assert.equal(await page.locator('#start').isVisible(),true);
  await page.locator('.fundort-knopf[data-dino="majungasaurus"]').click();assert.match(await page.locator('#artikel h1').innerText(),/Majungasaurus/);await page.getByRole('button',{name:'‹ Zurück zur Übersicht',exact:true}).click();
  await page.locator('#filterKost button[data-wert="Allesfresser"]').click();assert.equal(await page.locator('#raster .karte-dino').count(),1);assert.match(await page.locator('#raster').innerText(),/Deinocheirus/);await page.locator('#filterKost button[data-wert="alle"]').click();
  await page.locator('#raster .karte-text').first().click();assert.match(await page.locator('#artikel h1').innerText(),/Tyrannosaurus/);await page.getByRole('button',{name:'‹ Zurück zur Übersicht',exact:true}).click();
  const layouts=[];
  for(const width of [820,390,320]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   for(const id of ['yutyrannus','therizinosaurus','diplodocus']){
    await page.locator('#raster .bild-oeffner[data-dino="'+id+'"]').click();
    assert.equal(await page.locator('#lightbox').isVisible(),false);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.equal(await page.locator('#artikel .artikel-lesebereich').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length),1);
    await page.locator('#artikel .bild-oeffner img').evaluate(i=>i.decode());
    if(width===390){await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(out,id+'-mobile.png')});if(id==='yutyrannus')await page.locator('#artikel').screenshot({path:path.join(out,'yutyrannus-mobile-full.png')});}
    await page.locator('#artikel .bild-oeffner').click();await page.locator('#lightboxBild').evaluate(i=>i.decode());await page.getByRole('button',{name:'Großansicht schließen',exact:true}).click();
    assert.equal(await page.locator('#artikel').isVisible(),true);assert.equal(await page.locator('#artikel .bild-oeffner').evaluate(e=>e===document.activeElement),true);
    await page.getByRole('button',{name:'‹ Zurück zur Übersicht',exact:true}).click();
    layouts.push({width,id});
   }
  }
  assert.equal(await page.locator('button button, button a, a button').count(),0);assert.deepEqual(errors,[]);
  const hashes={};for(const id of ['majungasaurus','deinocheirus','therizinosaurus','triceratops'])hashes[id]=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'bilder',id+'.png'))).digest('hex');
  const result={passed:true,portraits:portraitChecks,overviewImageOpensArticle:true,onlyDetailImageOpensLightbox:true,keyboardNavigation:true,focusReturn:true,noInfoboxTables:true,responsiveLayouts:layouts,imagesUnchanged:hashes,errors};fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exit(1);});
