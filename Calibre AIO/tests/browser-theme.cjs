// Real pinned CWA templates and scripts, offline sample library and no provider requests.
const fs=require('fs'); const path=require('path'); const assert=require('assert/strict');
const {execFileSync}=require('child_process');
const playwright=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=path.resolve(__dirname,'..'), src=path.join(process.env.CWA_SOURCE,'cps/static');
const out=process.env.AIO_THEME_SCREENSHOTS; if(out) fs.mkdirSync(out,{recursive:true});
// Headless Chromium hides scrollbars by default; real browsers may give them layout width.
(async()=>{const browser=await playwright[process.env.AIO_THEME_BROWSER || 'chromium'].launch({ignoreDefaultArgs:['--hide-scrollbars']});try{
for(const width of (process.env.AIO_THEME_WIDTHS || '1440,1920,390,320').split(',').map(Number)){
 const context=await browser.newContext({viewport:{width,height:900}}); const page=await context.newPage(); const errors=[], fontWarnings=new Set();page.on('pageerror',e=>errors.push(e.message));
 page.on('console',msg=>{
  // Firefox repairs bounding boxes in the unmodified upstream embedded fonts.
  // Record that specific warning separately; other warnings/errors still fail.
  if(msg.type()==='warning' && msg.text().includes('downloadable font: glyf: Glyph bbox was incorrect; adjusting')) {fontWarnings.add(msg.text().split('source:')[0]);return;}
  if(['error','warning'].includes(msg.type()))errors.push(msg.text().slice(0,500));
 });
 const uploads=[];
 let themeGate=null;
 await page.route('https://calibre.test/**',async route=>{
  const u=new URL(route.request().url());
  if(u.pathname==='/shell')return route.fulfill({contentType:'text/html; charset=utf-8',body:'<!doctype html><title>AIO fixture</title><body style="margin:0"><iframe title="Library" style="width:100vw;height:100vh;border:0" src="/library/?scenario=authors"></iframe></body>'});
  if(u.pathname==='/ajax/listbooks'){const rows=Array.from({length:10},(_,i)=>({id:i+1,title:`Buch ${i+1}`,sort:`Buch ${i+1}`,authors:'Mara Winter',author_sort:'Winter, Mara',tags:'',series:'',series_index:'',languages:'Deutsch',publishers:'',pubdate:'',comments:'',read_status:false,is_archived:false}));return route.fulfill({contentType:'application/json',body:JSON.stringify({total:115,rows})});}
  if(u.pathname==='/upload'){uploads.push(route.request().postDataBuffer().toString());return route.fulfill({contentType:'application/json',body:JSON.stringify({location:'/library/?uploaded=1'})});}
  if(u.pathname.startsWith('/static/')){if(u.pathname.endsWith('/filter_grid.js')&&themeGate)await themeGate;const p=path.join(src,decodeURIComponent(u.pathname.slice(8)));if(fs.existsSync(p))return route.fulfill({path:p});return route.fulfill({status:404,body:''});}
  if(u.pathname.startsWith('/library/aio-theme/')){if(path.basename(u.pathname)==='modern.js'&&themeGate)await themeGate;return route.fulfill({path:path.join(root,'rootfs/opt/ha-cwa/theme',path.basename(u.pathname))});}
  if(u.pathname.startsWith('/cover/')){const i=Number(u.pathname.split('/').pop()); const colors=['#526d67','#4d6176','#a27a50','#5b4b66','#727b62','#435665'];return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300"><rect width="200" height="300" fill="${colors[i%6]}"/><rect x="12" y="12" width="176" height="276" fill="none" stroke="#ffffff55"/><path d="M12 210 Q100 80 188 210" fill="none" stroke="#ffffff33" stroke-width="30"/><text x="100" y="72" text-anchor="middle" font-family="serif" font-size="20" fill="#fff">LESEN</text><text x="100" y="125" text-anchor="middle" font-family="serif" font-size="30" fill="#fff">${String(i).padStart(2,'0')}</text></svg>`});}
  if(u.pathname==='/library/'||u.pathname==='/library') {const body=execFileSync(process.env.PYTHON || 'python3',['-X','utf8',path.join(__dirname,'theme_fixture.py'),u.searchParams.get('sort_param')||'abc',u.searchParams.get('scenario')||'books'],{encoding:'utf8'});return route.fulfill({contentType:'text/html; charset=utf-8',headers:{'Referrer-Policy':'no-referrer'},body});}
  return route.fulfill({contentType:'application/json',body:'{}'});
 });
 for(const scenario of ['authors','publishers','books','books-paged','books-many','books-read','books-random','magic','series-grid','series-grid-many','duplicates','no-sidebar']) {
  let release;themeGate=new Promise(resolve=>{release=resolve;});
  await page.goto(`https://calibre.test/library/?scenario=${scenario}`,{waitUntil:'commit'});
  await page.locator('.aio-page-header').waitFor({state:'visible'});
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('.aio-page-header')).position==='sticky');
  // Firefox's FontFaceSet.ready may wait for document load, which this test
  // intentionally holds back. Wait for the fonts already used by layout.
  await page.evaluate(()=>Promise.all([...document.fonts].filter(font=>font.status==='loading').map(font=>font.loaded)));
  // The native mobile script relocates the closed, offscreen navigation drawer.
  // Compare its visible desktop links; mobile opening is covered below.
  const snapshot=()=>page.evaluate(()=>Object.fromEntries(['.aio-page-header','.aio-page-tools','.aio-page-tools #asc','.pagination','.duplicate-group','#query','#query_submit',...(innerWidth>=768?['#nav_author']:[])].map(selector=>{const el=document.querySelector(selector);if(!el)return [selector,null];const r=el.getBoundingClientRect();return [selector,{x:r.x,y:r.y,width:r.width,height:r.height}];})));
  const before=await snapshot();
  const seriesPositions=()=>page.locator('#list .book').evaluateAll(nodes=>nodes.map(node=>{const r=node.getBoundingClientRect();return {x:r.x,y:r.y};}));
  const initialCards=await seriesPositions();
  assert.equal(await page.locator('.aio-page-tools .glyphicon').count(),scenario==='magic'?2:0,'Sort symbols must already be modern before the script');
  const symbols=()=>page.locator('.aio-page-tools .aio-sort').evaluateAll(nodes=>nodes.map(node=>node.innerHTML));
  const initialSymbols=await symbols();
  for(const icon of await page.locator('.aio-search-icon, #query_submit svg').all()) {
   assert.equal(await icon.getAttribute('width'),'16');assert.equal(await icon.getAttribute('height'),'16');
  }
  if(out&&scenario==='publishers')await page.screenshot({path:path.join(out,`first-paint-${width}-before.png`)});
  themeGate=null;release();await page.waitForLoadState('load');await page.waitForTimeout(600);
  const after=await snapshot();
  assert.deepEqual(await page.evaluate(()=>[...document.querySelectorAll('.discover .row, #list')].filter(node=>window.jQuery(node).data('isotope')).map(node=>window.jQuery(node).data('isotope').options.transitionDuration)),await page.evaluate(()=>[...document.querySelectorAll('.discover .row, #list')].filter(node=>window.jQuery(node).data('isotope')).map(()=>0)),`${scenario} ${width}: Isotope grids must relayout without a slide animation`);
  if(/books|magic|series/.test(scenario))assert(await page.evaluate(()=>[...document.querySelectorAll('.discover .row, #list')].some(node=>window.jQuery(node).data('isotope'))),`${scenario} ${width}: expected an Isotope grid`);
  const finalCards=await seriesPositions();
  initialCards.forEach((box,i)=>{for(const axis of ['x','y'])assert(Math.abs(box[axis]-finalCards[i][axis])<2,`Series ${width}: card ${i} ${axis} jumped ${box[axis]} -> ${finalCards[i][axis]}`);});
  if(width>=768&&scenario==='books-paged') {
   const header=await page.locator('.aio-page-header').boundingBox();
   for(const control of await page.locator('.pagination > .page-item > a').all()) {const box=await control.boundingBox();assert(Math.abs(box.y+box.height/2-header.y-header.height/2)<2,'Page controls must be vertically centered');}
  }
  if(scenario==='books-paged')assert(await page.evaluate(()=>!!(document.querySelector('.pagination').compareDocumentPosition(document.querySelector('.aio-page-header'))&Node.DOCUMENT_POSITION_FOLLOWING)),'Pagination must be rendered before the list so it exists at first paint');
  if(width<768&&scenario==='books-paged') {
   const pagination=await page.locator('.pagination').boundingBox(),tools=await page.locator('.aio-page-tools').boundingBox();
   assert(pagination.y+pagination.height<=tools.y,'Mobile page navigation must have its own row above sorting');
   for(const control of await page.locator('.pagination > .page-item > a').all()) {const box=await control.boundingBox();assert(box.y>=pagination.y&&box.y+box.height<=pagination.y+pagination.height,'Mobile pagination controls must fit their row');}
   const band=await page.locator('.aio-page-header').boundingBox(),firstCard=await page.locator('.discover.load-more .book').first().boundingBox();
   assert(firstCard.y>=band.y+band.height-1,`First card must start below the band with pagination: ${firstCard.y} vs ${band.y+band.height}`);
   await page.evaluate(()=>window.scrollTo(0,100));
   const scrolledTools=await page.locator('.aio-page-tools').boundingBox();
   assert(scrolledTools.y>=pagination.y+pagination.height,'Mobile sorting must stay below pagination while scrolling');
   await page.evaluate(()=>window.scrollTo(0,0));
   const jump=page.locator('.pagination .page-jump').first();await jump.locator(':scope > a').click();
   const menu=jump.locator('.page-jump-menu');assert(await menu.isVisible());
   assert(await menu.locator('a').first().evaluate(el=>{const r=el.getBoundingClientRect();return !!document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest('.page-jump-menu');}),'Mobile page-jump menu must not be clipped');
   await jump.locator(':scope > a').click();
  }
  assert.deepEqual(await symbols(),initialSymbols,'Sort symbols must not switch after first paint');
  assert.equal(await page.locator('link[href*="caliBlur"]').count(),0,'caliBlur must not load');
  if(scenario==='books-read') {
   // Every second book is read: the marker is a small disc inside the lower left of its cover.
   const badges=page.locator('.discover.load-more .book .cover .badge.read');assert.equal(await badges.count(),9);
   const cover=await page.locator('.discover.load-more .book .cover img').first().boundingBox(),badge=await badges.first().boundingBox();
   assert(badge.width<=22&&badge.height<=22,'Read marker must stay small');
   assert(badge.x>=cover.x&&badge.y+badge.height<=cover.y+cover.height+1&&badge.y>cover.y+cover.height/2,'Read marker sits inside the lower left of the cover');
   assert.equal(await badges.first().evaluate(el=>getComputedStyle(el).borderRadius),'50%');
  }
  if(scenario==='books-random') {
   // Four random picks sit above the library as a labeled section, so their
   // partial last row does not read as a hole in the library grid.
   const label=page.locator('.discover.random-books > h2');assert(await label.isVisible());
   assert(Number(await label.evaluate(el=>parseFloat(getComputedStyle(el).fontSize)))<=14,'Random section label must stay compact');
   assert.equal(await page.locator('.discover.random-books .book').count(),12);
   const libraryRow=await page.locator('.discover.load-more .book').evaluateAll(cards=>cards.filter(card=>card.getBoundingClientRect().y===cards[0].getBoundingClientRect().y).length);
   assert.equal(await page.locator('.discover.random-books .book:visible').count(),libraryRow,`Random picks fill exactly one row of ${libraryRow} at ${width}`);
   assert.equal(await page.locator('.discover.random-books .book:visible').evaluateAll(cards=>new Set(cards.map(card=>Math.round(card.getBoundingClientRect().y))).size),1,'Visible random picks sit in one row');
   const section=await page.locator('.discover.random-books').boundingBox(),first=await page.locator('.discover.load-more .book').first().boundingBox();
   assert(first.y>=section.y+section.height,'Library grid starts below the random section');
   assert.equal(await page.locator('.discover.random-books').evaluate(el=>getComputedStyle(el).borderBottomStyle),'solid');
  }
  if(scenario==='no-sidebar') {
   // Pages without the sidebar (login, errors) keep the content at the left edge and the title in the bar.
   assert.equal(await page.locator('.row-fluid > .col-sm-2').count(),0);
   const main=await page.locator('.aio-main').boundingBox(),brand=await page.locator('.navbar-brand').boundingBox();
   assert(main.x<1,`Content must start at the edge without a sidebar: ${main.x}`);
   assert(brand.y+brand.height<=(width>=768?60:48)+1,'Brand stays inside the bar without a sidebar');
  }
  assert(!(await page.evaluate(()=>document.body.classList.contains('blur'))),'Standalone theme must not run in blur mode');
  if(scenario==='books-many'&&width>=768) {
   await page.evaluate(()=>window.scrollTo(0,300));
   assert(await page.evaluate(()=>window.scrollY>200),'The viewport must be the scroll container');
   const stuck=await page.locator('.aio-page-header').boundingBox();assert(Math.abs(stuck.y-60)<1,'Band must stick under the navbar: '+stuck.y);
   await page.evaluate(()=>window.scrollTo(0,0));
  }
  if(/books|magic/.test(scenario)) {
   // Isotope must measure the same grid width the stylesheet laid out, scrollbar gutter included.
   const row=await page.locator('.discover.load-more .row').boundingBox(),cards=await page.locator('.discover.load-more .book').evaluateAll(nodes=>nodes.slice(0,3).map(node=>{const r=node.getBoundingClientRect();return {x:r.x,right:r.right,width:r.width};}));
   assert(Math.abs(cards[1].x-cards[0].x-cards[0].width)<1,`${scenario} ${width}: card pitch ${cards[1].x-cards[0].x} must equal card width ${cards[0].width}`);
   assert(cards[cards.length-1].right<=row.x+row.width+1,`${scenario} ${width}: cards must stay inside the grid row`);
  }
  for(const [selector,box] of Object.entries(before))if(box)for(const key of ['x','y','width','height'])assert(Math.abs(box[key]-after[selector][key])<2,`${scenario} ${width}: ${selector} ${key} moved from ${box[key]} to ${after[selector][key]}`);
  if(out&&scenario==='publishers')await page.screenshot({path:path.join(out,`first-paint-${width}-after.png`)});
  if(out&&scenario==='books-paged')await page.screenshot({path:path.join(out,`pagination-${width}.png`)});
 }
 await page.goto('https://calibre.test/library/');await page.waitForTimeout(1400);
 assert.equal(await page.title(),'Calibre-Web | Bücher');
 assert(await page.locator('.discover.load-more .book').count()>0);
 const card=await page.locator('.discover.load-more .book').first().boundingBox();
 assert(card.width>=90 && card.width<180, 'Book cards must retain their compact, readable width');
 assert.equal(await page.locator('.book a[data-toggle="modal"]').count(),0,'Covers open the book page, not the detail modal');
 await page.locator('.discover.load-more .book .cover a').first().click();await page.waitForURL(/book_id=/);
 await page.goto('https://calibre.test/library/');await page.waitForTimeout(1400);
 if(width>=768){
  assert(!(await page.locator('.aio-page-header > h2').isVisible()),'Desktop must not repeat the page title in the content band');
  const band=await page.locator('.aio-page-header').boundingBox();
  const toolbar=await page.locator('.filterheader').boundingBox();
  assert(Math.abs(band.y+band.height/2-toolbar.y-toolbar.height/2)<2, 'Sorting must be centered in the title band');
  // Center within the scrollable content box; a classic scrollbar sits outside it.
  const content=await page.locator('.aio-main').evaluate(el=>{const r=el.getBoundingClientRect();return {x:r.x+el.clientLeft,width:el.clientWidth};});
  assert(Math.abs(toolbar.x+toolbar.width/2-content.x-content.width/2)<2, 'Sorting must be centered in the content area');
 }
 if(out) await page.screenshot({path:path.join(out,`calibre-modern-${width}.png`)});
 console.log(JSON.stringify({width,title:await page.title(),sorts:await page.locator('.aio-sort').count(),errors,upstreamFontWarnings:fontWarnings.size,toolbar:await page.locator('.filterheader').boundingBox(),books:await page.locator('.discover.load-more .book').first().boundingBox()}));
 assert.equal(await page.locator('#asc').innerText(),'A–Z'); assert.equal(await page.locator('#desc').innerText(),'A–Z');
 assert.notEqual(await page.locator('#asc .aio-sort-arrow path').first().getAttribute('d'), await page.locator('#desc .aio-sort-arrow path').first().getAttribute('d'));
 await page.locator('#desc').click(); await page.waitForTimeout(300); assert.equal(await page.locator('#desc').getAttribute('aria-current'),'true');assert(page.url().includes('sort_param=zyx'));
 await page.locator('#auth_az').focus();assert.equal(await page.locator('#auth_az').getAttribute('data-sort-kind'),'author');
 assert.deepEqual(errors,[]);
 for(const button of await page.locator('.aio-sort').all()) { const box=await button.boundingBox(); if(width>=768)assert(box.x>=0 && box.x+box.width<=width, 'Sort control is clipped'); assert(box.height>=32); assert(await button.getAttribute('aria-label')); }
 if(width<768){await page.locator('.navbar-toggle').click(); await page.waitForTimeout(400); assert(await page.locator('#nav_author').isVisible());
  assert(await page.evaluate(()=>document.querySelector('.navbar-collapse').contains(document.querySelector('#scnd-nav'))&&!document.querySelector('.col-sm-2').offsetParent),'Drawer must hold the browse navigation while the sidebar is hidden');
  const drawer=await page.locator('.navbar-collapse').boundingBox();assert(drawer.x>=0&&drawer.x+drawer.width<=width,`Drawer must fill the viewport, not hang over its left edge: ${drawer.x}`);
  assert(Number((await page.locator('#nav_books a').evaluate(el=>getComputedStyle(el).paddingLeft)).replace('px',''))>=16,'Drawer rows keep a readable left inset');}
 assert(!(await page.locator('#logout').isVisible()),'Ingress signs in; logout stays hidden');
 assert.equal(await page.locator('#nav_createshelf,#nav_createmagicshelf').count(),0);
 assert.equal(await page.locator('#scnd-nav .aio-section-create').count(),2);
 assert(!(await page.locator('#scnd-nav').innerText()).includes('✨'),'Magic Shelves uses only the separate plus action');
 for(const heading of await page.locator('#scnd-nav .aio-nav-section > button').all()) {
  assert(!(await heading.evaluate(el=>getComputedStyle(el).fontFamily)).includes('Open Sans Bold'),'Section headings must not inherit the pre-bolded upstream font');
 }
 if(width>=768) {
  const brand=page.locator('.navbar-brand'),header=page.locator('.aio-page-header');
  assert(await brand.isVisible(),'Desktop keeps the page title in the sidebar');
  assert.equal((await brand.textContent()).trim(),(await page.locator('.aio-page-header > h2').textContent()).trim(),'Sidebar title must be the page title');
  const bandStyle=locator=>locator.evaluate(el=>{const s=getComputedStyle(el);return [s.backgroundColor,s.borderBottomWidth,s.borderBottomStyle,s.borderBottomColor];});
  assert.deepEqual(await bandStyle(brand),await bandStyle(header),'Sidebar title and page band must share one surface and divider');
  const left=await brand.boundingBox(),right=await header.boundingBox();
  assert(Math.abs(left.y+left.height-right.y-right.height)<1,'Title dividers must align vertically');
  assert(left.x+left.width>=right.x,'Title divider must have no gap at the sidebar edge');
 } else assert(await page.locator('.navbar-brand').isVisible(),'Mobile keeps the page title in the navbar');
 if(width>=768)assert(!(await page.locator('#main-nav > .aio-functions-head').isVisible()),'Mobile functions heading must stay hidden on desktop');
 for(const action of await page.locator('#scnd-nav .aio-section-create').all()) {
  assert.equal((await action.innerText()).trim(),'+');assert(await action.getAttribute('aria-label'));
  const heading=action.locator('..').locator(':scope > button');
  assert(Number(await heading.evaluate(el=>parseFloat(getComputedStyle(el).fontSize)))>Number(await page.locator('#nav_author a').evaluate(el=>parseFloat(getComputedStyle(el).fontSize))),'Section headings must be larger than items');
  const before=await heading.getAttribute('aria-expanded'),href=await action.getAttribute('href');assert(href.includes('shelf'));
  const titleBox=await heading.boundingBox(),actionBox=await action.boundingBox();
  const navBox=await page.locator('#scnd-nav').boundingBox();
  assert(titleBox.x>=navBox.x-1&&actionBox.x+actionBox.width<=navBox.x+navBox.width+1,'Heading and plus must fit inside the visible menu');
  assert(actionBox.width<=44&&titleBox.width>80,'Plus must not take the heading space');
  assert(actionBox.x>=titleBox.x+titleBox.width-1&&actionBox.x+actionBox.width<=width,'Plus must sit to the right of its section heading');
  if(width<768)assert(actionBox.x-titleBox.x-titleBox.width<4,'In the drawer the plus follows its heading instead of the far edge');
  assert.equal(await heading.locator('..').evaluate(el=>getComputedStyle(el).marginTop),'0px','Section headings keep the menu rhythm');
  assert(Math.abs(actionBox.y+actionBox.height/2-titleBox.y-titleBox.height/2)<2,'Plus must be vertically centered');
  await heading.click();assert(await action.isVisible(),'Plus must remain available when the section is collapsed');await heading.click();
  await action.evaluate(el=>el.addEventListener('click',event=>event.preventDefault(),{once:true}));
  await action.click();
  assert.equal(await heading.getAttribute('aria-expanded'),before,'Creation must not collapse the section');
 }
 const navSpacing=await page.evaluate(()=>{const head=document.querySelector('#scnd-nav .aio-nav-section > button'),first=document.querySelector('#nav_books a'),second=document.querySelector('#nav_author a');return [head,first,second].map(el=>{const r=el.getBoundingClientRect();return r.y+r.height/2;});});
 assert(Math.abs((navSpacing[1]-navSpacing[0])-(navSpacing[2]-navSpacing[1]))<2,'Section and menu rows must have equal spacing: '+navSpacing);
 const sectionGaps=await page.locator('#scnd-nav .aio-nav-section').evaluateAll(heads=>heads.flatMap(head=>{const button=head.querySelector('button'),next=head.nextElementSibling;if(!button||!next||next.classList.contains('nav-head'))return [];const link=next.querySelector('a');if(!link)return [];const a=button.getBoundingClientRect(),b=link.getBoundingClientRect();return [b.y+b.height/2-a.y-a.height/2];}));
 assert(sectionGaps.every(gap=>Math.abs(gap-(navSpacing[2]-navSpacing[1]))<2),'All section headings must match menu spacing: '+sectionGaps);
 for(const scenario of ['authors','categories','languages','publishers','downloads','downloads-filled']) {
  await page.goto(`https://calibre.test/library/?scenario=${scenario}`); await page.waitForTimeout(500);
  assert((await page.title()).includes(scenario.startsWith('downloads') ? 'Downloads' : scenario==='authors' ? 'Authors' : scenario==='categories' ? 'Categories' : scenario==='languages' ? 'Languages' : 'Publishers'));
  assert(!(await page.locator('.aio-page-header > h1').isVisible()),'The content band must not repeat the sidebar title');
  const main=await page.locator('.aio-list-page').evaluate(el=>{const r=el.getBoundingClientRect();return {x:r.x+el.clientLeft,y:r.y,width:el.clientWidth,height:r.height};});
  const band=await page.locator('.aio-page-header').boundingBox();if(width>=768)assert(band.y<100,'Reclaim the old duplicate header strip');
  if(width>=768) {const box=await page.locator('.filterheader').boundingBox();assert(Math.abs(box.x+box.width/2-main.x-main.width/2)<2);assert(Math.abs(box.y+box.height/2-band.y-band.height/2)<2);}
  if(scenario==='authors') {
   const letter=await page.locator('.character .char').first().boundingBox(),group=await page.locator('.character').boundingBox(),all=await page.locator('#all').boundingBox();
   assert(group.height>=letter.height && letter.y>=group.y && letter.y+letter.height<=group.y+group.height+1,'Letter group must contain its full-height buttons');
   // Linux fonts can wrap the whole character group onto the next line.
   if(Math.abs(group.y-all.y)<all.height/2) assert(Math.abs(letter.y-all.y)<2,'Letter buttons on the same line must align');
  }
  if(scenario==='downloads') {assert(await page.locator('.aio-empty').isVisible());assert.equal(await page.locator('.aio-download-help').count(),0);assert.equal(await page.locator('.container h1').count(),0);}
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
  for(const control of await page.locator('.filterheader .btn').all()) {const box=await control.boundingBox();if(width>=768)assert(box.x>=0 && box.x+box.width<=width,'List filter clipped');assert(box.height>=32);}
  if(out) await page.screenshot({path:path.join(out,`calibre-${scenario}-${width}.png`)});
 }
 for(const scenario of ['series','series-grid','duplicates','magic','table']) {
  await page.goto(`https://calibre.test/library/?scenario=${scenario}`);await page.waitForTimeout(800);
  if(scenario==='table') {
   // bootstrap-table paginates with the same class as the band; its items stay in one line.
   const items=page.locator('.fixed-table-pagination ul.pagination > li');await items.first().waitFor();
   const boxes=await items.evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect();return [Math.round(r.y),r.x];}));
   assert(boxes.length>=5,'Table pagination renders its pages');
   assert.equal(new Set(boxes.map(([y])=>y)).size,1,`Table pagination items sit in one row: ${JSON.stringify(boxes)}`);
   for(let i=1;i<boxes.length;i++)assert(boxes[i][1]>boxes[i-1][1],'Table pagination items run left to right');
   assert.equal(await page.locator('.fixed-table-pagination .pagination-detail').count(),1);
  }
  assert.equal(await page.locator('.aio-page-header').count(),1);
  if(scenario==='series-grid') {
   const cards=page.locator('#list .book');assert.equal(await cards.count(),6);const row=await cards.all();const positions=await Promise.all(row.slice(0,3).map(el=>el.boundingBox()));assert(positions.every(b=>Math.abs(b.y-positions[0].y)<2),'Series cards must fill the first row: '+JSON.stringify(await cards.evaluateAll(els=>els.map(el=>({box:el.getBoundingClientRect().toJSON(),style:el.getAttribute('style'),position:getComputedStyle(el).position,transform:getComputedStyle(el).transform,width:getComputedStyle(el).width,margin:getComputedStyle(el).margin})))));
   const box=await cards.first().boundingBox();assert(box.width>=75 && box.width<220);
   for(const card of await cards.all()){const b=await card.boundingBox();assert(b.x>=0&&b.x+b.width<=width+1);}
   await page.locator('#desc').click();assert.equal(await page.locator('#desc').getAttribute('aria-pressed'),'true');
  }
  if(scenario==='duplicates') {
   const options=await page.locator('.aio-duplicate-options').boundingBox(),group=await page.locator('.duplicate-group').first().boundingBox();assert(Math.abs(options.x-group.x)<2&&Math.abs(options.width-group.width)<2,'Duplicate panels must share the same content width');
   const cover=await page.locator('.book-cover img').first().boundingBox();assert(cover.width<=50&&cover.height<=75);
   await page.locator('.book-checkbox').first().check();assert(await page.locator('.book-checkbox').first().isChecked());
   assert(await page.locator('#delete_selected').isEnabled());
  }
  if(scenario==='magic') {assert.equal(await page.locator('.aio-page-header > h2').count(),0);assert.equal(await page.locator('.magic-shelf-buttons a').count(),2);}
  if(width<768&&scenario==='magic') {
   const rail=page.locator('.aio-page-tools');assert(await rail.evaluate(el=>el.scrollWidth>el.clientWidth));
   await rail.evaluate(el=>el.scrollLeft=el.scrollWidth);assert(await rail.evaluate(el=>el.scrollLeft>0));
   assert.equal(await page.locator('.aio-sort').first().evaluate(el=>getComputedStyle(el).borderTopWidth),'0px');
  }
  if(out)await page.screenshot({path:path.join(out,`calibre-${scenario}-${width}.png`)});
 }
 // Two consecutive back operations must unwind history instead of B→C→B loops.
 await page.goto('https://calibre.test/library/?scenario=authors');
 await page.evaluate(()=>location.assign('/library/?scenario=publishers'));await page.waitForURL(/scenario=publishers/);
 await page.evaluate(()=>location.assign('/library/?scenario=categories'));await page.waitForURL(/scenario=categories/);
 if(width>=768)await page.locator('.aio-back').click();else await page.locator('.aio-back').evaluate(el=>el.click());await page.waitForURL(/scenario=publishers/);
 if(width>=768)await page.locator('.aio-back').click();else await page.locator('.aio-back').evaluate(el=>el.click());await page.waitForURL(/scenario=authors/);
 if(width<768){await page.locator('.navbar-toggle').click();await page.waitForFunction(()=>document.querySelector('.navbar-collapse').classList.contains('in'));}
 const section=page.locator('#scnd-nav .aio-nav-section button').first();await section.click();assert.equal(await section.getAttribute('aria-expanded'),'false');assert(!(await page.locator('#nav_author').isVisible()));
 await section.click();assert.equal(await section.getAttribute('aria-expanded'),'true');assert(await page.locator('#nav_author').isVisible());
 if(width<768) {
  assert.equal(await page.locator('#nav_author a').evaluate(el=>getComputedStyle(el).fontSize),'15px');
  const functions=page.locator('.aio-functions-head button');await functions.click();assert(!(await page.locator('#refresh-library').isVisible()));await functions.click();assert(await page.locator('#refresh-library').isVisible());
 }
 if(out)await page.screenshot({path:path.join(out,`nav-open-${width}.png`)});
 if(width<768){await page.locator('.navbar-toggle').click();await page.waitForFunction(()=>!document.querySelector('.navbar-collapse').classList.contains('in'));}
 await page.locator('.aio-upload-menu summary').click();assert(await page.locator('.aio-folder-trigger').isVisible());
 assert.deepEqual(await page.locator('.aio-upload-menu').evaluate(el=>[el.querySelector('summary'),...el.querySelectorAll('.aio-upload-options *')].flatMap(node=>['::before','::after'].map(pseudo=>getComputedStyle(node,pseudo).content)).filter(content=>!['none','normal'].includes(content))),[],'Upload menu must not show stray glyphs');
 assert.deepEqual((await page.locator('.aio-upload-options').innerText()).split('\n').map(line=>line.trim()).filter(Boolean),['Upload','Ordner hinzufügen …'],'Upload menu shows exactly its two actions');
 const folder=fs.mkdtempSync(path.join(require('os').tmpdir(),'cwa-folder-'));
 try {
  fs.mkdirSync(path.join(folder,'nested'));fs.writeFileSync(path.join(folder,'one.epub'),'fixture epub');fs.writeFileSync(path.join(folder,'nested','two.pdf'),'fixture pdf');fs.writeFileSync(path.join(folder,'nested','ignore.jpg'),'not a book');
  const chooserPromise=page.waitForEvent('filechooser');await page.locator('.aio-folder-trigger').click();const chooser=await chooserPromise;await chooser.setFiles(folder);
  await page.waitForURL(/uploaded=1/);assert.equal(uploads.length,1);assert(uploads[0].includes('one.epub')&&uploads[0].includes('two.pdf'));assert(!uploads[0].includes('ignore.jpg'));assert(uploads[0].includes('csrf_token'));
 } finally {fs.rmSync(folder,{recursive:true,force:true});}
 await page.locator('#query').click(); await page.locator('#query').fill('Garten');
 const input=await page.locator('#query').boundingBox(), submit=await page.locator('#query_submit').boundingBox();
 assert(input.x>=0 && submit.x+submit.width<=width); assert(submit.x>=input.x+input.width-1,'Search submit overlaps the input');
 assert(Math.abs(input.y+input.height/2-submit.y-submit.height/2)<2);
 assert.notEqual(await page.locator('#query').evaluate(el=>getComputedStyle(el).color),'rgb(85, 85, 85)');
 if(out) await page.screenshot({path:path.join(out,`calibre-search-${width}.png`)});
 await page.locator('#query_submit').click(); await page.waitForURL(/query=Garten/); assert(page.url().includes('query=Garten'));
 await page.evaluate(()=>sessionStorage.clear());
 await page.goto('https://calibre.test/shell');
 const frame=await (await page.$('iframe')).contentFrame();await frame.waitForSelector('.aio-page-header');
 assert.equal(await frame.locator('.aio-back').getAttribute('aria-disabled'),'true');
 await frame.evaluate(()=>location.assign('/library/?scenario=publishers'));await frame.waitForURL(/scenario=publishers/);
 await frame.evaluate(()=>location.assign('/library/?scenario=categories'));await frame.waitForURL(/scenario=categories/);
 assert.equal(await frame.evaluate(()=>document.referrer),'','Back must work with the referrer suppressed');
 await Promise.all([frame.waitForNavigation({waitUntil:'load'}),frame.evaluate(()=>location.reload())]);
 await frame.locator('.aio-back').evaluate(el=>el.click());await frame.waitForURL(/scenario=publishers/);
 await frame.locator('.aio-back').evaluate(el=>el.click());await frame.waitForURL(/scenario=authors/);
 assert.equal(page.url(),'https://calibre.test/shell');
 // The standalone error page bypasses layout.html and still gets the dark look.
 await page.goto('https://calibre.test/library/?scenario=error');
 assert.equal(await page.locator('link[href*="modern.css"]').count(),1);assert.equal(await page.locator('link[href*="caliBlur"]').count(),0);
 assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(15, 18, 23)','Error page must use the theme background');
 assert.equal(await page.evaluate(()=>parseFloat(getComputedStyle(document.body).paddingTop)),0,'Error page has no navbar to make room for');
 assert.deepEqual(errors,[]);
 await context.close();
}
// Before JavaScript runs, list markers already have the compact server class.
const initial=await browser.newContext({javaScriptEnabled:false});const first=await initial.newPage();
const fixture=execFileSync(process.env.PYTHON||'python3',['-X','utf8',path.join(__dirname,'theme_fixture.py'),'abc','authors'],{encoding:'utf8'});
await first.route('https://calibre.test/**',route=>{const u=new URL(route.request().url());if(u.pathname.startsWith('/library/aio-theme/'))return route.fulfill({path:path.join(root,'rootfs/opt/ha-cwa/theme',path.basename(u.pathname))});if(u.pathname.startsWith('/static/')){const p=path.join(src,decodeURIComponent(u.pathname.slice(8)));if(fs.existsSync(p))return route.fulfill({path:p});}return route.fulfill({contentType:'text/html; charset=utf-8',body:fixture});});
await first.goto('https://calibre.test/library/');assert.equal(await first.locator('.aio-list-page').count(),1);assert.equal(await first.locator('link[href*="caliBlur"]').count(),0);
await first.evaluate(()=>document.querySelectorAll('style,link[rel="stylesheet"]').forEach(node=>node.remove()));
for(const icon of await first.locator('.aio-search-icon, #query_submit svg').all()) {const box=await icon.boundingBox();assert(box.width===16&&box.height===16,'Search symbols must stay small without theme CSS or JavaScript');}
await initial.close();
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
