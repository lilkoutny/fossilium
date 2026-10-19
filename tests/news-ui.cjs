const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const root = path.resolve(__dirname,'..');
const artifacts = path.join(root,'.content-state','news-ui-qa');
fs.mkdirSync(artifacts,{recursive:true});
const server = http.createServer((req,res)=>{
  const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  const file=path.resolve(root,'.'+(pathname==='/'?'/index.html':pathname));
  if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  fs.readFile(file,(err,body)=>{
    if(err){res.writeHead(404).end();return;}
    res.setHeader('Content-Type',file.endsWith('.json')?'application/json; charset=utf-8':'text/html; charset=utf-8');
    res.end(body);
  });
});
function item(n){return {titel:'Testmeldung '+n,zusammenfassung:'Sachliche Zusammenfassung für den UI-Test.',quelle:'Testquelle',url:'https://example.org/story/'+n,datum:'2026-10-'+String(n).padStart(2,'0')};}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',err=>errors.push(err.message));
    await page.route('**/news.json',r=>r.fulfill({json:{stand:'2026-10-19',meldungen:[item(9),item(8),{...item(7),url:'https://example.org/story/7/?utm_source=test'}]}}));
    await page.route('**/news-archiv.json',r=>r.fulfill({json:{stand:'2026-10-19',meldungen:Array.from({length:8},(_,i)=>item(i+1))}}));
    await page.goto(base+'/#forschung');
    await page.waitForFunction(()=>document.querySelectorAll('#newsRaster article').length===4);
    assert.equal(await page.locator('#newsArchiv').isVisible(),false);
    assert.deepEqual(await page.locator('#newsRaster h3').allTextContents(),['Testmeldung 9','Testmeldung 8','Testmeldung 7','Testmeldung 6']);
    await page.getByRole('button',{name:'Alle Meldungen anzeigen'}).click();
    assert.equal(await page.locator('#newsArchiv').isVisible(),true);
    assert.equal(await page.locator('#newsArchivListe li').count(),9);
    const dates=await page.locator('#newsArchivListe time').evaluateAll(nodes=>nodes.map(n=>n.dateTime));
    assert.deepEqual(dates,[...dates].sort().reverse());
    await page.getByRole('button',{name:'Liste wieder schließen'}).click();
    assert.equal(await page.locator('#newsArchiv').isVisible(),false);
    await page.setViewportSize({width:390,height:844});
    await page.getByRole('button',{name:'Alle Meldungen anzeigen'}).focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#newsArchiv').isVisible(),true);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    // Untrusted titles/URLs stay inert, and invalid dates do not produce Invalid Date.
    const sanitized=await page.evaluate(()=>sammleNews({meldungen:[
      {titel:'<img src=x onerror=alert(1)>',zusammenfassung:'Text',quelle:'Test',url:'https://example.org/safe',datum:'2026-99-55'},
      {titel:'Bad',zusammenfassung:'Text',url:'javascript:alert(1)',datum:'2026-10-01'}]},null));
    assert.equal(sanitized.length,1);assert.equal(sanitized[0].datum,'');
    await page.route('**/news-archiv.json',r=>r.fulfill({status:503,body:'temporarily unavailable'}));
    await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#newsRaster article').length===3);
    await page.getByRole('button',{name:'Alle Meldungen anzeigen'}).click();
    assert.match(await page.locator('#newsArchivHinweis').textContent(),/nicht erreichbar/);
    assert.deepEqual(errors,[]);
    await page.close();
    // The screenshots below show the real historical data, not the UI fixtures.
    const actual=await browser.newPage({viewport:{width:1440,height:1000}});
    await actual.goto(base+'/#forschung');
    await actual.waitForFunction(()=>document.querySelectorAll('#newsRaster article').length>0);
    await actual.locator('#forschung').screenshot({path:path.join(artifacts,'desktop.png')});
    await actual.getByRole('button',{name:'Alle Meldungen anzeigen'}).click();
    const realCount=await actual.locator('#newsArchivListe li').count();
    await actual.setViewportSize({width:390,height:844});
    assert.equal(await actual.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await actual.evaluate(()=>window.scrollTo(0,document.getElementById('newsArchiv').getBoundingClientRect().top+scrollY-20));
    await actual.screenshot({path:path.join(artifacts,'mobile.png')});
    fs.writeFileSync(path.join(artifacts,'result.json'),JSON.stringify({passed:true,fixturePreviewCount:4,fixtureArchiveCount:9,realArchiveCount:realCount,desktopAndMobile:true,paidCalls:0},null,2));
    console.log(JSON.stringify({passed:true,realArchiveCount:realCount,artifacts}));
  } finally {await browser.close();server.close();}
})().catch(err=>{console.error(err);server.close();process.exitCode=1;});
