// Real pinned CWA templates and scripts, offline sample library and no provider requests.
const fs=require('fs'); const path=require('path'); const assert=require('assert/strict');
const {execFileSync}=require('child_process');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=path.resolve(__dirname,'..'), src=path.join(process.env.CWA_SOURCE,'cps/static');
const out=process.env.AIO_THEME_SCREENSHOTS; if(out) fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch();try{
for(const width of [1440,1920,390]){
 const context=await browser.newContext({viewport:{width,height:900}}); const page=await context.newPage(); const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://calibre.test/**',async route=>{
  const u=new URL(route.request().url());
  if(u.pathname.startsWith('/static/')){const p=path.join(src,decodeURIComponent(u.pathname.slice(8)));if(fs.existsSync(p))return route.fulfill({path:p});return route.fulfill({status:404,body:''});}
  if(u.pathname.startsWith('/library/aio-theme/'))return route.fulfill({path:path.join(root,'rootfs/opt/ha-cwa/theme',path.basename(u.pathname))});
  if(u.pathname.startsWith('/cover/')){const i=Number(u.pathname.split('/').pop()); const colors=['#526d67','#4d6176','#a27a50','#5b4b66','#727b62','#435665'];return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300"><rect width="200" height="300" fill="${colors[i%6]}"/><rect x="12" y="12" width="176" height="276" fill="none" stroke="#ffffff55"/><path d="M12 210 Q100 80 188 210" fill="none" stroke="#ffffff33" stroke-width="30"/><text x="100" y="72" text-anchor="middle" font-family="serif" font-size="20" fill="#fff">LESEN</text><text x="100" y="125" text-anchor="middle" font-family="serif" font-size="30" fill="#fff">${String(i).padStart(2,'0')}</text></svg>`});}
  if(u.pathname==='/library/'||u.pathname==='/library') {const body=execFileSync(process.env.PYTHON || 'python3',['-X','utf8',path.join(__dirname,'theme_fixture.py'),u.searchParams.get('sort_param')||'abc'],{encoding:'utf8'});return route.fulfill({contentType:'text/html',body});}
  return route.fulfill({contentType:'application/json',body:'{}'});
 });
 await page.goto('https://calibre.test/library/');await page.waitForTimeout(1400);
 assert.equal(await page.title(),'Calibre-Web | Bücher');
 assert(await page.locator('.discover.load-more .book').count()>0);
 assert((await page.locator('.discover.load-more .book').first().boundingBox()).width<180);
 if(out) await page.screenshot({path:path.join(out,`calibre-modern-${width}.png`)});
 console.log(JSON.stringify({width,title:await page.title(),sorts:await page.locator('.aio-sort').count(),errors,toolbar:await page.locator('.filterheader').boundingBox(),books:await page.locator('.discover.load-more .book').first().boundingBox()}));
 assert.equal(await page.locator('#asc').innerText(),'A–Z'); assert.equal(await page.locator('#desc').innerText(),'A–Z');
 assert.notEqual(await page.locator('#asc .aio-sort-arrow path').first().getAttribute('d'), await page.locator('#desc .aio-sort-arrow path').first().getAttribute('d'));
 await page.locator('#desc').click(); await page.waitForTimeout(300); assert.equal(await page.locator('#desc').getAttribute('aria-current'),'true');assert(page.url().includes('sort_param=zyx'));
 await page.locator('#auth_az').focus();assert.equal(await page.locator('#auth_az').getAttribute('data-sort-kind'),'author');
 assert.deepEqual(errors,[]);
 for(const button of await page.locator('.aio-sort').all()) { const box=await button.boundingBox(); assert(box.x>=0 && box.x+box.width<=width, 'Sort control is clipped'); assert(box.height>=32); assert(await button.getAttribute('aria-label')); }
 if(width<768){await page.locator('.navbar-toggle').click(); await page.waitForTimeout(400); assert(await page.locator('#nav_author').isVisible());}
 await context.close();
}
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
