// Real pinned CWA templates and scripts, offline sample library and no provider requests.
const fs=require('fs'); const path=require('path'); const assert=require('assert/strict');
const {execFileSync}=require('child_process');
const playwright=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=path.resolve(__dirname,'..'), src=path.join(process.env.CWA_SOURCE,'cps/static');
const out=process.env.AIO_THEME_SCREENSHOTS; if(out) fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await playwright[process.env.AIO_THEME_BROWSER || 'chromium'].launch();try{
for(const width of [1440,1920,390]){
 const context=await browser.newContext({viewport:{width,height:900}}); const page=await context.newPage(); const errors=[], fontWarnings=new Set();page.on('pageerror',e=>errors.push(e.message));
 page.on('console',msg=>{
  // Firefox repairs bounding boxes in the unmodified upstream embedded fonts.
  // Record that specific warning separately; other warnings/errors still fail.
  if(msg.type()==='warning' && msg.text().includes('downloadable font: glyf: Glyph bbox was incorrect; adjusting')) {fontWarnings.add(msg.text().split('source:')[0]);return;}
  if(['error','warning'].includes(msg.type()))errors.push(msg.text().slice(0,500));
 });
 await page.route('https://calibre.test/**',async route=>{
  const u=new URL(route.request().url());
  if(u.pathname.startsWith('/static/')){const p=path.join(src,decodeURIComponent(u.pathname.slice(8)));if(fs.existsSync(p))return route.fulfill({path:p});return route.fulfill({status:404,body:''});}
  if(u.pathname.startsWith('/library/aio-theme/'))return route.fulfill({path:path.join(root,'rootfs/opt/ha-cwa/theme',path.basename(u.pathname))});
  if(u.pathname.startsWith('/cover/')){const i=Number(u.pathname.split('/').pop()); const colors=['#526d67','#4d6176','#a27a50','#5b4b66','#727b62','#435665'];return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300"><rect width="200" height="300" fill="${colors[i%6]}"/><rect x="12" y="12" width="176" height="276" fill="none" stroke="#ffffff55"/><path d="M12 210 Q100 80 188 210" fill="none" stroke="#ffffff33" stroke-width="30"/><text x="100" y="72" text-anchor="middle" font-family="serif" font-size="20" fill="#fff">LESEN</text><text x="100" y="125" text-anchor="middle" font-family="serif" font-size="30" fill="#fff">${String(i).padStart(2,'0')}</text></svg>`});}
  if(u.pathname==='/library/'||u.pathname==='/library') {const body=execFileSync(process.env.PYTHON || 'python3',['-X','utf8',path.join(__dirname,'theme_fixture.py'),u.searchParams.get('sort_param')||'abc',u.searchParams.get('scenario')||'books'],{encoding:'utf8'});return route.fulfill({contentType:'text/html',body});}
  return route.fulfill({contentType:'application/json',body:'{}'});
 });
 await page.goto('https://calibre.test/library/');await page.waitForTimeout(1400);
 assert.equal(await page.title(),'Calibre-Web | Bücher');
 assert(await page.locator('.discover.load-more .book').count()>0);
 const card=await page.locator('.discover.load-more .book').first().boundingBox();
 assert(card.width>=90 && card.width<180, 'Book cards must retain their compact, readable width');
 if(width>=768){
  const title=await page.locator('.discover.load-more > h2').boundingBox();
  const toolbar=await page.locator('.filterheader').boundingBox();
  assert(Math.abs(title.y+title.height/2-toolbar.y-toolbar.height/2)<2, 'Sorting must align with the page title');
  const content=await page.locator('.discover.load-more').boundingBox();
  assert(Math.abs(toolbar.x+toolbar.width/2-content.x-content.width/2)<2, 'Sorting must be centered in the content area');
 }
 if(out) await page.screenshot({path:path.join(out,`calibre-modern-${width}.png`)});
 console.log(JSON.stringify({width,title:await page.title(),sorts:await page.locator('.aio-sort').count(),errors,upstreamFontWarnings:fontWarnings.size,toolbar:await page.locator('.filterheader').boundingBox(),books:await page.locator('.discover.load-more .book').first().boundingBox()}));
 assert.equal(await page.locator('#asc').innerText(),'A–Z'); assert.equal(await page.locator('#desc').innerText(),'A–Z');
 assert.notEqual(await page.locator('#asc .aio-sort-arrow path').first().getAttribute('d'), await page.locator('#desc .aio-sort-arrow path').first().getAttribute('d'));
 await page.locator('#desc').click(); await page.waitForTimeout(300); assert.equal(await page.locator('#desc').getAttribute('aria-current'),'true');assert(page.url().includes('sort_param=zyx'));
 await page.locator('#auth_az').focus();assert.equal(await page.locator('#auth_az').getAttribute('data-sort-kind'),'author');
 assert.deepEqual(errors,[]);
 for(const button of await page.locator('.aio-sort').all()) { const box=await button.boundingBox(); assert(box.x>=0 && box.x+box.width<=width, 'Sort control is clipped'); assert(box.height>=32); assert(await button.getAttribute('aria-label')); }
 if(width<768){await page.locator('.navbar-toggle').click(); await page.waitForTimeout(400); assert(await page.locator('#nav_author').isVisible());}
 for(const scenario of ['authors','categories','languages','publishers','downloads','downloads-filled']) {
  await page.goto(`https://calibre.test/library/?scenario=${scenario}`); await page.waitForTimeout(500);
  assert((await page.title()).includes(scenario.startsWith('downloads') ? 'Downloads' : scenario==='authors' ? 'Authors' : scenario==='categories' ? 'Categories' : scenario==='languages' ? 'Languages' : 'Publishers'));
  assert(await page.locator('.aio-list-page > h1').isVisible());
  const main=await page.locator('.aio-list-page').boundingBox();
  const marker=await page.locator('.aio-list-page').evaluate(el=>{const s=getComputedStyle(el,'::before');return {size:parseFloat(s.fontSize),left:parseFloat(s.left),content:s.content};});
  if(!scenario.startsWith('downloads')) {assert(marker.size<=32, 'List group marker is oversized'); assert(marker.left>=0); assert(!['none','normal','""'].includes(marker.content), 'Keep the native list marker');}
  const heading=await page.locator('.aio-list-page > h1').boundingBox();assert(heading.y<100,'Reclaim the old duplicate header strip');
  if(width>=768) {const box=await page.locator('.filterheader').boundingBox();assert(Math.abs(box.x+box.width/2-main.x-main.width/2)<2);assert(Math.abs(box.y+box.height/2-heading.y-heading.height/2)<2);}
  if(scenario==='authors') {
   const letter=await page.locator('.character .char').first().boundingBox(),group=await page.locator('.character').boundingBox(),all=await page.locator('#all').boundingBox();
   assert(group.height>=letter.height && letter.y>=group.y && letter.y+letter.height<=group.y+group.height+1,'Letter group must contain its full-height buttons');
   // Linux fonts can wrap the whole character group onto the next line.
   if(Math.abs(group.y-all.y)<all.height/2) assert(Math.abs(letter.y-all.y)<2,'Letter buttons on the same line must align');
  }
  if(scenario==='downloads') {assert(await page.locator('.aio-empty').isVisible());assert((await page.locator('.aio-download-help').innerText()).includes('Shelfmark'));assert.equal(await page.locator('.container h1').count(),0);}
  else {
   assert(await page.locator('.list-container .row').count()>0);
   const original=await page.locator('.list-container .row').first().getAttribute('data-id');
   await page.locator('#desc').focus(); await page.keyboard.press('Enter');
   assert.equal(await page.locator('#desc').getAttribute('aria-pressed'),'true');
   assert.notEqual(await page.locator('.list-container .row').first().getAttribute('data-id'),original);
   await page.locator('.character .char').first().click();
   assert(await page.locator('.list-container .row:visible').count()>0);
   await page.locator('#all').click();
   assert.equal(await page.locator('.list-container .row:visible').count(),await page.locator('.list-container .row').count());
   if(scenario==='authors') {const before=await page.locator('#list_0').innerText();await page.locator('#sort_name').click();assert.notEqual(await page.locator('#list_0').innerText(),before);}
  }
  for(const control of await page.locator('.filterheader .btn').all()) {const box=await control.boundingBox();assert(box.x>=0 && box.x+box.width<=width,'List filter clipped');assert(box.height>=32);}
  // Native caliBlur animates reinserted list columns after sorting/filtering.
  await page.waitForFunction(()=>[...document.querySelectorAll('.list-container .row > div')].every(el=>Number(getComputedStyle(el).opacity)>=0.99));
  if(out) await page.screenshot({path:path.join(out,`calibre-${scenario}-${width}.png`)});
 }
 await page.locator('#query').click(); await page.locator('#query').fill('Garten');
 const input=await page.locator('#query').boundingBox(), submit=await page.locator('#query_submit').boundingBox();
 assert(input.x>=0 && submit.x+submit.width<=width); assert(submit.x>=input.x+input.width-1,'Search submit overlaps the input');
 assert(Math.abs(input.y+input.height/2-submit.y-submit.height/2)<2);
 assert.notEqual(await page.locator('#query').evaluate(el=>getComputedStyle(el).color),'rgb(85, 85, 85)');
 if(out) await page.screenshot({path:path.join(out,`calibre-search-${width}.png`)});
 await page.locator('#query_submit').click(); await page.waitForURL(/query=Garten/); assert(page.url().includes('query=Garten'));
 assert.deepEqual(errors,[]);
 await context.close();
}
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
