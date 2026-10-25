// Real browser regression for the HA bridge, with HA APIs mocked at their boundary.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
function render(setup, start) {
  return execFileSync(process.env.PYTHON || 'python3', ['-X', 'utf8', '-c',
    `import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from prepare_aio import render_index; print(render_index(Path(sys.argv[1], 'index.html').read_text(encoding='utf-8'), '/api/hassio_ingress/test', sys.argv[3], 'repo_calibre-aio', sys.argv[2]=='true'))`,
    path.join(root, 'rootfs/opt/ha-cwa'), String(setup), start], {encoding:'utf8'});
}
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    for (const scenario of ['admin', 'reader', 'forbidden', 'restart-failed', 'missing-ha', 'normal-de', 'normal-en']) {
      const setup = !scenario.startsWith('normal');
      const language = scenario === 'normal-en' ? 'en' : 'de';
      const start = scenario === 'normal-en' ? 'shelfmark' : 'library';
      const context = await browser.newContext({locale:language, viewport:{width:360,height:780}});
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.route('https://ha.test/**', route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/') return route.fulfill({contentType:'text/html',body:`<style>body{margin:0}#aio{width:100%;height:100vh;border:0}</style><home-assistant></home-assistant><script>
          window.calls=[];
          document.querySelector('home-assistant').hass=${scenario === 'missing-ha' ? 'null' : `{
            locale:{language:'${language}'},user:{id:'current',is_admin:${scenario !== 'reader'}},
            callWS:async args=>{window.calls.push(args);${scenario === 'forbidden' ? "throw new Error('403');" : "return [{id:'other',username:'wrong',is_active:true},{id:'current',username:'login_name',is_active:true}];"}},
            callApi:async(method,url,body)=>{window.calls.push({method,url,body});
              if(method==='GET')return {result:'ok',data:{options:{start_page:'shelfmark',network_share_mode:true,shelfmark:{external_bypass_url:'http://example.test'},sso:{enabled:true,admin_username:'',admin_account:'custom',auto_create_users:false}}}};
              ${scenario === 'restart-failed' ? "if(url.endsWith('/restart'))throw new Error('restart');" : ''}
              return {result:'ok'};
            }} `};
          </script><iframe id="aio" src="/api/hassio_ingress/test/"></iframe>`});
        if (url.pathname === '/api/hassio_ingress/test/') return route.fulfill({contentType:'text/html',body:render(setup,start)});
        return route.fulfill({contentType:'text/html',body:'Native app fixture'});
      });
      await page.goto('https://ha.test/');
      const frame = page.frameLocator('#aio');
      await frame.locator('body').waitFor();
      if (setup) {
        assert.equal(await frame.locator('.setup').isVisible(),true,scenario);
        assert.equal(await frame.locator('iframe').getAttribute('src'),'about:blank');
        const button = frame.locator('#adopt');
        if (['reader','missing-ha'].includes(scenario)) {
          assert.equal(await button.isDisabled(),true);
          assert.deepEqual(await page.evaluate(()=>window.calls),[]);
        } else {
          await button.click();
          await page.waitForFunction(()=>window.calls.length >= 1);
          await frame.locator('#status').filter({hasText:scenario === 'forbidden' ? 'fehlgeschlagen' : scenario === 'restart-failed' ? 'nicht bestätigt' : 'startet neu'}).waitFor();
          const calls = await page.evaluate(()=>window.calls);
          if (scenario === 'forbidden') assert.equal(calls.length,1);
          else {
            assert.equal(calls[2].url,'hassio/addons/repo_calibre-aio/options');
            assert.deepEqual(calls[2].body.options,{start_page:'shelfmark',network_share_mode:true,shelfmark:{external_bypass_url:'http://example.test'},sso:{enabled:true,admin_username:'login_name',admin_account:'custom',auto_create_users:false}});
            assert.equal(calls[3].url,'hassio/addons/repo_calibre-aio/restart');
          }
        }
      } else {
        assert.equal(await frame.locator('html').getAttribute('lang'),language);
        assert.equal(await frame.locator('nav a').first().textContent(),language === 'de' ? 'Bibliothek' : 'Library');
        assert.equal(await frame.locator('iframe').getAttribute('src'),start+'/');
        const height=await frame.locator('header').evaluate(el=>el.getBoundingClientRect().height);
        assert.equal(height,40);
        assert.equal(await frame.locator('body').evaluate(el=>el.scrollWidth<=window.innerWidth),true);
      }
      assert.deepEqual(errors,[],scenario);
      await context.close();
      console.log('Passed:',scenario);
    }
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
