/* Synthetic UI demo only. No real Auth, database or email calls are allowed. */
const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')
const root = path.resolve(__dirname, '..')
const { chromium } = require(require.resolve('playwright', {paths:[path.join(root,'frontend')]}))
const base = process.env.TEAM_TEST_URL || 'http://127.0.0.1:5174'
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base)) throw new Error('Loopback test server required')
const fixture = path.join(root, 'frontend/.local/team-browser.html')
fs.mkdirSync(path.dirname(fixture), { recursive: true })
fs.copyFileSync(path.join(__dirname, 'fixtures/team-browser.html'), fixture)
;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || (fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined), headless: process.env.TEAM_TEST_HEADED !== 'true', args: ['--no-sandbox'] })
  const results = []
  try {
    for (const width of [1280, 360]) {
      const context = await browser.newContext({viewport: {width, height: 900}})
      const page = await context.newPage()
      let mutations = 0, nativeDialogs = 0
      const errors = []
      page.on('pageerror', e => errors.push(e.message))
      page.on('dialog', async dialog => { nativeDialogs++; await dialog.dismiss() })
      await page.route('**/*', async route => {
        const url = new URL(route.request().url())
        if (url.origin !== base) return route.abort()
        if (!url.pathname.startsWith('/v1/')) return route.continue()
        if (route.request().method() !== 'GET') {mutations++; return route.fulfill({json:{state:'queued'}})}
        return route.fulfill({json: url.pathname.endsWith('/options') ? {
          branches:[{id:'branch-demo',name:'Centro ficticio'}], resources:[],
          permissions:{reception:'Agenda y recepción de sucursales asignadas; sin cierre clínico.',admin:'Gestiona equipo y toda la clínica; no administra el SaaS.'}
        } : {items:[{id:'staff-demo',kind:'member',email:'recepcion.ficticia@example.com',role:'reception',active:true,state:'active',version:1,branches:['branch-demo'],resources:[],delivery_state:null,expires_at:null},{id:'invitation-demo',kind:'invitation',email:'invitacion.ficticia@example.com',role:'reception',active:false,state:'pending',version:1,branches:['branch-demo'],resources:[],delivery_state:'queued',expires_at:'2030-10-25T12:00:00Z'}],has_more:false}})
      })
      await page.goto(base+'/.local/team-browser.html')
      await page.getByText('recepcion.ficticia@example.com',{exact:true}).waitFor()
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false,'Mobile overflow')
      await page.getByRole('button',{name:'Desactivar',exact:true}).click()
      const dialog = page.getByRole('alertdialog',{name:'Desactivar acceso'})
      await dialog.waitFor()
      assert.equal(await page.getByRole('button',{name:'Volver',exact:true}).evaluate(el=>el===document.activeElement),true)
      // Shift-Tab from initial cancel remains inside modal, as does repeated Tab.
      await page.keyboard.press('Shift+Tab')
      for(let n=0;n<7;n++){await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>Boolean(document.activeElement.closest('dialog'))),true)}
      await page.keyboard.press('Escape')
      assert.equal(mutations,0,'Cancel must not mutate')
      assert.equal(await page.getByRole('button',{name:'Desactivar',exact:true}).evaluate(el=>el===document.activeElement),true,'Focus restored')
      await page.screenshot({path:path.join(root,`docs/demos/team-${width}.png`),fullPage:true})
      await page.getByRole('button',{name:'Invitar personal'}).click()
      await page.getByLabel('Correo del destinatario').fill('nueva.persona@example.com')
      await page.getByLabel('Centro ficticio',{exact:true}).check()
      await page.getByRole('button',{name:'Revisar permisos y confirmar'}).click()
      await page.getByRole('alertdialog',{name:'Invitar al equipo'}).waitFor()
      assert.equal(await page.evaluate(()=>document.querySelector('dialog').getBoundingClientRect().width<=window.innerWidth),true)
      await page.screenshot({path:path.join(root,`docs/demos/team-confirm-${width}.png`),fullPage:true})
      await page.getByRole('button',{name:'Crear invitación',exact:true}).click()
      await page.getByRole('dialog',{name:'Equipo actualizado'}).waitFor()
      assert.equal(mutations,1)
      assert.equal(nativeDialogs,0)
      assert.deepEqual(errors,[])
      results.push({width,keyboard:'pasa',focus:'pasa',cancel:'pasa',modal:'pasa',overflow:'pasa',systemDialogs:0,api:'simulada; llamadas externas bloqueadas'})
      await context.close()
    }
    fs.writeFileSync(path.join(root,'docs/demos/browser-results.json'),JSON.stringify({results},null,2)+'\n')
    console.log(JSON.stringify(results))
  } finally { await browser.close(); fs.rmSync(fixture,{force:true}) }
})().catch(e=>{console.error(e.message);process.exitCode=1})
