const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=path.join(root,'.content-state',process.env.FOSSILIUM_MAP_QA_URL?'map-qa-live':'map-qa');
fs.mkdirSync(out,{recursive:true});
const server=http.createServer((req,res)=>{
  const u=new URL(req.url,'http://localhost'),file=path.resolve(root,'.'+(u.pathname==='/'?'/index.html':u.pathname));
  if(!file.startsWith(root+path.sep))return res.writeHead(403).end();
  fs.readFile(file,(err,body)=>{
    if(err)return res.writeHead(404).end();
    res.setHeader('Content-Type',file.endsWith('.svg')?'image/svg+xml':file.endsWith('.json')?'application/json; charset=utf-8':'text/html; charset=utf-8');res.end(body);
  });
});
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const results=[];
  try{
    for(const [width,height,name] of [[1440,1000,'desktop'],[390,844,'mobile']]){
      const page=await browser.newPage({viewport:{width,height}});
      const errors=[];page.on('pageerror',err=>errors.push(err.message));
      const base=process.env.FOSSILIUM_MAP_QA_URL || 'http://127.0.0.1:'+server.address().port+'/';
      await page.goto(base+'#weltkarte',{waitUntil:'networkidle'});
      await page.locator('#fundortKarte').waitFor();
      assert.equal(await page.locator('#markerEbene .marker').count(),6);
      assert.equal(await page.locator('.fundort-knopf').count(),6);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      const bbox=await page.locator('.map-land').evaluate(el=>{const b=el.getBBox();return {w:b.width,h:b.height}});
      assert.ok(bbox.w>900 && bbox.h>400,'real coastline must render');
      // Original coordinates remain geographically exact.
      const first=await page.locator('#markerEbene .marker').first().locator('.punkt').evaluate(c=>({x:+c.getAttribute('cx'),y:+c.getAttribute('cy')}));
      assert.ok(Math.abs(first.x-(73/360*1000))<.01);assert.ok(Math.abs(first.y-(43/180*500))<.01);
      // Every tightly grouped place is separately reachable through the list.
      for(let i=0;i<6;i++){
        const button=page.locator('.fundort-knopf').nth(i),dino=await button.getAttribute('data-dino');
        await button.click();
        assert.equal(await page.locator('#artikel').evaluate(el=>el.classList.contains('aktiv')),true);
        assert.ok((await page.locator('#artikel h1').textContent()).length>0);
        await page.getByRole('button',{name:'‹ Zurück zur Übersicht'}).click();
      }
      await page.locator('#markerEbene .marker').first().focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#artikel h1').textContent(),'Tyrannosaurus rex');
      await page.getByRole('button',{name:'‹ Zurück zur Übersicht'}).click();
      await page.locator('#markerEbene .marker').last().focus();await page.keyboard.press('Space');
      assert.equal(await page.locator('#artikel h1').textContent(),'Yutyrannus huali');
      await page.getByRole('button',{name:'‹ Zurück zur Übersicht'}).click();
      await page.locator('.karten-rahmen').scrollIntoViewIfNeeded();
      await page.locator('.karten-rahmen').screenshot({path:path.join(out,name+'.png')});
      await page.waitForFunction(()=>document.querySelectorAll('#newsRaster article').length===4);
      await page.getByRole('button',{name:'Alle Meldungen anzeigen'}).click();
      assert.equal(await page.locator('#newsArchivListe li').count(),49);
      assert.deepEqual(errors,[]);
      results.push({viewport:name,markers:6,placeButtons:6,newsCards:4,archive:49,coastlineRendered:true,keyboard:true});
      await page.close();
    }
    fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:true,results},null,2));
    console.log(JSON.stringify({passed:true,results}));
  }finally{await browser.close();server.close();}
})().catch(err=>{console.error(err);server.close();process.exitCode=1;});
