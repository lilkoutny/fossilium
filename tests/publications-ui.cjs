const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const root=path.resolve(__dirname,'..'),out=path.join(root,'.content-state/publication-expansion-2026-10-29');
fs.mkdirSync(out,{recursive:true});
const manifest=JSON.parse(fs.readFileSync(path.join(root,'publikationen/index.json'),'utf8'));
const server=http.createServer((req,res)=>{
  if(req.url==='/favicon.ico'){res.writeHead(204).end();return;}
  let pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);if(pathname.endsWith('/'))pathname+='index.html';
  const file=path.resolve(root,'.'+pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  fs.readFile(file,(err,body)=>{if(err){res.writeHead(404).end();return;}res.setHeader('Content-Type',({'.html':'text/html; charset=utf-8','.json':'application/json','.css':'text/css','.png':'image/png','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream');res.end(body);});
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>document.querySelectorAll('#newsRaster .news-publikation').length===4);
  assert.equal(await page.locator('#newsRaster article').count(),4);
  assert.equal(await page.locator('#newsRaster a[target="_blank"]').count(),4);
  const unsafe=await page.evaluate(()=>lesePublikationen({artikel:[{original_url:'https://example.org',pfad:'//evil.example/'},{original_url:'https://example.org/a',pfad:'/publikationen/../evil/'},{original_url:'https://example.org/b',pfad:'/publikationen/gut/'}]}).size);assert.equal(unsafe,1);
  await page.locator('#forschung').screenshot({path:path.join(out,'news-desktop.png')});
  const checks=[];
  for(const a of manifest.artikel){
   const response=await page.goto(base+a.pfad);assert.equal(response.status(),200);await page.reload();
   assert.equal(await page.locator('h1').innerText(),a.titel);
   assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'),'https://fossilium.org'+a.pfad);
   assert.ok(await page.locator('.quellen a').count()>=3);
   await page.locator('figure img').evaluateAll(imgs=>Promise.all(imgs.map(i=>i.decode())));
   if(a.pfad.includes('longipteryx')){
    assert.equal(await page.locator('figure img').count(),1);
    assert.equal(await page.locator('figure a[href="https://creativecommons.org/licenses/by/4.0/"]').count(),1);
    await page.screenshot({path:path.join(out,'article-desktop.png'),fullPage:true});
   }
   await page.setViewportSize({width:390,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   if(a.pfad.includes('longipteryx'))await page.screenshot({path:path.join(out,'article-mobile.png'),fullPage:true});
   checks.push(a.pfad);await page.setViewportSize({width:1440,height:1000});
  }
  // Static articles remain readable without JavaScript.
  const plain=await browser.newContext({javaScriptEnabled:false});const staticPage=await plain.newPage();
  await staticPage.goto(base+manifest.artikel[0].pfad);assert.equal(await staticPage.locator('h1').innerText(),manifest.artikel[0].titel);await plain.close();
  // A missing article index must not hide the news or invent internal links.
  await page.route('**/publikationen/index.json',r=>r.fulfill({status:503,body:'unavailable'}));
  await page.goto(base);await page.waitForFunction(()=>document.querySelectorAll('#newsRaster article').length===4);
  assert.equal(await page.locator('#newsRaster .news-publikation').count(),0);assert.equal(await page.locator('#newsRaster a[target="_blank"]').count(),4);
  assert.deepEqual(errors,[]);
  const report={passed:true,internalPages:checks,newsButtons:4,externalLinksPreserved:true,mobileOverflow:false,staticWithoutJavaScript:true,manifestFailureFallback:true,paidCalls:0};
  fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exit(1)});
