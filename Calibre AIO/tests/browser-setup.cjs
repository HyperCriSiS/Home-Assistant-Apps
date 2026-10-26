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
    for (const scenario of ['admin', 'auto-reload', 'reader', 'forbidden', 'save-forbidden', 'restart-failed', 'configured', 'no-login', 'missing-ha', 'normal-de', 'normal-en', 'normal-library-link']) {
      const setup = !scenario.startsWith('normal');
      const language = scenario === 'normal-en' ? 'en' : 'de';
      const start = ['normal-en','normal-library-link'].includes(scenario) ? 'shelfmark' : 'library';
      const context = await browser.newContext({locale:language, viewport:{width:360,height:780}});
      const page = await context.newPage();
      const errors = [];
      let polls = 0;
      let shellLoads = 0;
      let restartReady = false;
      let libraryChecks = 0;
      page.on('pageerror', e => errors.push(e.message));
      await page.route('https://ha.test/**', route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/') return route.fulfill({contentType:'text/html',body:`<style>body{margin:0}#aio{width:100%;height:100vh;border:0}</style><home-assistant></home-assistant><script>
          window.calls=[];
          document.querySelector('home-assistant').hass=${scenario === 'missing-ha' ? 'null' : `{
            locale:{language:'${language}'},user:{id:'current',is_admin:${scenario !== 'reader'}},
            callWS:async args=>{window.calls.push(args);
              if(args.type==='config/auth/list') {
                ${scenario === 'forbidden' ? "throw new Error('403');" : `return [{id:'other',username:'wrong',is_active:true},{id:'current',username:${scenario === 'no-login' ? 'null' : "'login_name'"},is_active:true}];`}
              }
              if(args.type!=='supervisor/api')throw new Error('Wrong transport');
              if(args.method==='get')return {options:{start_page:'shelfmark',network_share_mode:true,shelfmark:{external_bypass_url:'http://example.test'},sso:{enabled:true,admin_username:'${scenario === 'configured' ? 'existing_admin' : ''}',admin_account:'custom',auto_create_users:false}}};
              ${scenario === 'save-forbidden' ? "if(args.endpoint.endsWith('/options'))throw new Error('403');" : ''}
              ${scenario === 'restart-failed' ? "if(args.endpoint.endsWith('/restart'))throw new Error('restart');" : ''}
              return null;
            },
            callApi:async()=>{throw new Error('REST proxy does not support these endpoints');}
            } `};
          </script><iframe id="aio" src="/api/hassio_ingress/test/"></iframe>`});
        if (url.pathname === '/api/hassio_ingress/test/') {
          if (route.request().resourceType() === 'fetch') {
            polls++;
            if (scenario === 'auto-reload') {
              if (polls === 1) return route.fulfill({status:502,body:'Restarting'});
              restartReady = true;
              return route.fulfill({contentType:'text/html',body:render(false,start)});
            }
          } else shellLoads++;
          return route.fulfill({contentType:'text/html',body:render(setup && !restartReady,start)});
        }
        if (scenario === 'auto-reload' && url.pathname.endsWith('/library/') && route.request().resourceType() === 'fetch') {
          libraryChecks++;
          if (libraryChecks === 1) return route.fulfill({status:502,body:'Backend starting'});
        }
        if (url.pathname.endsWith('/shelfmark/')) return route.fulfill({contentType:'text/html',body:'<a id="library" href="/api/hassio_ingress/test/library/" target="_blank" rel="noopener noreferrer"><span>Go To Library</span></a><a id="external" href="https://outside.test/" target="_blank">External</a>'});
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
          await page.waitForFunction(()=>window.calls.length >= 1);
          if (scenario === 'auto-reload') {
            await frame.locator('body[data-setup-required="false"]').waitFor();
            assert.equal(shellLoads,2);
            assert.equal(polls,3);
            assert.equal(libraryChecks,2);
            assert.equal(await frame.locator('nav').isVisible(),true);
            assert.equal((await page.evaluate(()=>window.calls)).length,4);
            await context.close();
            console.log('Passed:',scenario);
            continue;
          }
          const expected = scenario === 'forbidden' ? 'HA-Anmeldenamen abfragen' : scenario === 'save-forbidden' ? 'Administrator speichern' : scenario === 'restart-failed' ? 'nicht bestätigt' : scenario === 'configured' ? 'bereits konfiguriert' : scenario === 'no-login' ? 'kein unterstützter' : 'startet neu';
          await frame.locator('#status').filter({hasText:expected}).waitFor();
          const calls = await page.evaluate(()=>window.calls);
          if (['forbidden','no-login'].includes(scenario)) assert.equal(calls.length,1);
          else if (scenario === 'configured') assert.equal(calls.length,2);
          else {
            assert.equal(calls[2].endpoint,'/addons/repo_calibre-aio/options');
            assert.deepEqual(calls[2].data.options,{start_page:'shelfmark',network_share_mode:true,shelfmark:{external_bypass_url:'http://example.test'},sso:{enabled:true,admin_username:'login_name',admin_account:'custom',auto_create_users:false}});
            if (scenario === 'save-forbidden') assert.equal(calls.length,3);
            else {
              assert.equal(calls[3].endpoint,'/addons/repo_calibre-aio/restart');
              assert.equal(calls[3].timeout,null);
            }
          }
          if (['forbidden','save-forbidden'].includes(scenario)) assert.equal(await button.isEnabled(),true);
        }
      } else {
        assert.equal(await frame.locator('html').getAttribute('lang'),language);
        assert.equal(await frame.locator('nav a').first().textContent(),language === 'de' ? 'Bibliothek' : 'Library');
        assert.equal(await frame.locator('iframe').getAttribute('src'),start+'/');
        const height=await frame.locator('header').evaluate(el=>el.getBoundingClientRect().height);
        assert.equal(height,40);
        assert.equal(await frame.locator('body').evaluate(el=>el.scrollWidth<=window.innerWidth),true);
        assert.deepEqual(await page.evaluate(()=>window.calls),[]);
        if (scenario === 'normal-library-link') {
          assert.equal(await frame.frameLocator('iframe').locator('#external').getAttribute('target'),'_blank');
          await frame.frameLocator('iframe').locator('#library span').click();
          await frame.locator('nav a[data-view="library"][aria-current="page"]').waitFor();
          assert.equal(await frame.locator('iframe').getAttribute('src'),'https://ha.test/api/hassio_ingress/test/library/');
          assert.equal(context.pages().length,1);
          assert.equal(await frame.locator('header').isVisible(),true);
          assert.equal(new URL(page.url()).pathname,'/');
        }
      }
      assert.deepEqual(errors,[],scenario);
      await context.close();
      console.log('Passed:',scenario);
    }
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
