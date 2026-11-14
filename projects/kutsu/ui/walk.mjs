// Walk the pages in a real browser and fail on any error the page reports.
//
//   node walk.mjs [base url] [directory for screenshots]
//
// Needs serve.py running (default http://127.0.0.1:8046) and a Chromium: $CHROME, or the newest one
// Playwright has downloaded under ~/.cache/ms-playwright. It opens Espoo's events, one suggested event
// and one employer, then signs a company up by pressing Enter until the finished page, the way a
// company that agrees with everything would. No dependencies: it speaks to the browser over its
// debugging socket.
import { spawn } from 'node:child_process'
import { mkdtempSync, readdirSync, writeFileSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { join } from 'node:path'

const base = process.argv[2] ?? 'http://127.0.0.1:8046'
const shots = process.argv[3]
const COMPANY = '2292619-7'

function chromium() {
  if (process.env.CHROME) return process.env.CHROME
  const cache = join(homedir(), '.cache/ms-playwright')
  const dir = readdirSync(cache).filter((d) => d.startsWith('chromium_headless_shell-')).sort().at(-1)
  if (!dir) throw new Error('no Chromium found: set CHROME')
  const inner = readdirSync(join(cache, dir)).find((d) => d.startsWith('chrome'))
  return join(cache, dir, inner, readdirSync(join(cache, dir, inner)).find((f) => /^(chrome-headless-shell|headless_shell|chrome)$/.test(f)))
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const browser = spawn(chromium(), ['--headless', '--no-sandbox', '--remote-debugging-port=0', `--user-data-dir=${mkdtempSync(join(tmpdir(), 'kutsu-walk-'))}`, 'about:blank'])
const errors = []
try {
  // the browser prints the address of its debugging socket on stderr
  const address = await new Promise((resolve, reject) => {
    let seen = ''
    browser.stderr.on('data', (chunk) => {
      seen += chunk
      const found = /ws:\/\/[^\s]+/.exec(seen)
      if (found) resolve(found[0])
    })
    setTimeout(() => reject(new Error('the browser did not start')), 15000)
  })
  const port = new URL(address).port
  const target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === 'page')
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((r) => (socket.onopen = r))
  let id = 0
  const waiting = new Map()
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data)
    if (message.id) return waiting.get(message.id)?.(message.result ?? message.error)
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text)
    if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error')
      errors.push(message.params.args.map((a) => a.value ?? a.description).join(' '))
  }
  const send = (method, params = {}) =>
    new Promise((resolve) => {
      waiting.set(++id, resolve)
      socket.send(JSON.stringify({ id, method, params }))
    })
  const evaluate = async (expression) => (await send('Runtime.evaluate', { expression, returnByValue: true })).result?.value
  const open = async (hash, width = 1440, height = 900) => {
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 })
    await send('Page.navigate', { url: `${base}/${hash}` })
    await evaluate('location.reload()')
    await sleep(1500)
  }
  const shot = async (name) => {
    if (!shots) return
    const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
    writeFileSync(join(shots, `${name}.png`), Buffer.from(data, 'base64'))
  }
  const text = () => evaluate('document.body.innerText')
  const expect = async (what, wanted) => {
    if (!(await text()).includes(wanted)) errors.push(`${what}: the page does not say "${wanted}"`)
  }
  const enter = async () => {
    for (const type of ['keyDown', 'keyUp']) await send('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: type === 'keyDown' ? '\r' : undefined })
    await sleep(900)
  }

  await send('Runtime.enable')
  await send('Page.enable')

  // a walk must not start from an earlier one's answers: put the company back to the draft it starts from
  const brief = (await (await fetch(`${base}/signals.json`)).json()).find((b) => b.id === COMPANY)
  const draft = { status: 'draft', needs: brief.card.needs.map((n, i) => ({ ...n, id: `n${String(i)}` })) }
  await fetch(`${base}/review?id=${COMPANY}`, { method: 'POST', body: JSON.stringify(draft) })

  await open('#/')
  await expect('home', 'Their profiles')
  await shot('home')
  await open('#/events')
  await expect('events', 'Proposed events')
  await shot('events')
  await open('#/companies')
  await expect('companies', 'Hiring in Espoo')
  await open('#/pool')
  await expect('the talent pool', 'By field of work')
  // an application is decided in three steps from the keyboard: approve, the reason offered, record; then undone
  const press = async (key, code) => {
    for (const type of ['keyDown', 'keyUp']) await send('Input.dispatchKeyEvent', { type, key, code, text: type === 'keyDown' ? key : undefined })
    await sleep(500)
  }
  await open('#/applications')
  await expect('applications', 'Waiting')
  await shot('applications')
  await press('a', 'KeyA')
  await expect('the reason step', 'Record approval')
  await shot('applications-reason')
  await enter()
  await expect('a recorded decision', 'approved')
  await shot('applications-recorded')
  await press('z', 'KeyZ')
  await open('#/applications/A-003', 390, 844)
  await expect('one application on a phone', 'All applications')
  await shot('applications-phone')
  await open('#/event/semiconductors-and-photonics')
  await expect('a suggested event', 'Employers to invite')
  await shot('event')
  await open('#/event/deep-tech-talent-forum', 390, 844)
  await expect('the upcoming event on a phone', 'People to invite')
  await shot('event-phone')
  await open(`#/${COMPANY}`)
  await expect('an employer', 'Looking for')

  // a person's links are typed one key at a time, the way a keyboard does it: what is typed stays as typed,
  // slashes included, and is tidied only when the field is left; a pasted address is tidied at once
  const LINK = 'input[aria-label="A link of yours"]'
  const LINKEDIN = 'input[aria-label="Your LinkedIn username"]'
  const key = async (key, code = '', text = key.length === 1 ? key : undefined) => {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: { Backspace: 8, Home: 36 }[key], text })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code })
  }
  const type = async (selector, typed) => {
    await evaluate(`document.querySelector('${selector}').focus()`)
    for (const c of typed) await key(c)
  }
  const field = (selector) => evaluate(`document.querySelector('${selector}').value`)
  const holds = async (what, selector, wanted) => {
    const value = await field(selector)
    if (value !== wanted) errors.push(`${what}: the field holds "${String(value)}", not "${wanted}"`)
  }
  const empty = (selector) => evaluate(`(() => { const f = document.querySelector('${selector}'); f.focus(); f.select() })()`).then(() => key('Backspace', 'Backspace'))
  const leave = () => evaluate('document.activeElement.blur()')
  const paste = (selector, pasted) =>
    evaluate(`(() => {
      const f = document.querySelector('${selector}')
      f.focus()
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(f, ${JSON.stringify(pasted)})
      f.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste', data: ${JSON.stringify(pasted)} }))
    })()`)
  await open('#/me')
  await enter()
  await type(LINK, 'https://github.com/octocat/hello-world/')
  await holds('a GitHub address typed key by key', LINK, 'https://github.com/octocat/hello-world/')
  if ((await evaluate(`document.querySelector('button[aria-label="Read this page"]').getAttribute('aria-checked')`)) !== 'true') errors.push('a GitHub address typed key by key is not offered for reading')
  await shot('me-link-typed')
  await leave()
  await holds('a typed address once the field is left', LINK, 'github.com/octocat/hello-world')
  await empty(LINK)
  await type(LINK, 'example.com/work/2026')
  await key('Backspace', 'Backspace')
  await key('Backspace', 'Backspace')
  await key('Backspace', 'Backspace')
  await key('Backspace', 'Backspace')
  await holds('a path after four presses of Backspace', LINK, 'example.com/work/')
  await type(LINK, 'cv')
  await key('Home', 'Home')
  await type(LINK, 'my.')
  await holds('an address edited at its start', LINK, 'my.example.com/work/cv')
  await paste(LINK, 'https://www.example.com/portfolio/')
  await holds('a pasted address', LINK, 'example.com/portfolio')
  await type(LINKEDIN, 'https://www.linkedin.com/in/jane-doe')
  await holds('a LinkedIn address typed key by key', LINKEDIN, 'jane-doe')
  await paste(LINKEDIN, 'https://fi.linkedin.com/in/jane-doe/?trk=profile')
  await holds('a pasted LinkedIn address', LINKEDIN, 'jane-doe')
  await paste(LINK, 'https://www.linkedin.com/in/someone-else/')
  await holds('a LinkedIn address pasted among the links', LINK, '')
  await holds('the LinkedIn field after that paste', LINKEDIN, 'someone-else')

  // an invitation from a suggested event names that event, not the upcoming one
  await open('#/join/nitor.com/security')
  await expect('an invitation to a suggested event', 'Security talent event')
  await shot('join-suggested-cover')
  await open(`#/join/${COMPANY}`)
  await shot('join-1-cover')
  let presses = 0
  while (presses < 14 && !(await text()).includes('Change my answers')) {
    await enter()
    presses++
    await shot(`join-${String(presses + 1)}`)
  }
  await expect(`the sign-up after ${String(presses)} presses of Enter`, 'Change my answers')
  console.log(`signed up in ${String(presses)} presses of Enter`)
  socket.close()
} catch (e) {
  errors.push(String(e))
} finally {
  browser.kill()
}
if (errors.length) {
  console.error(errors.join('\n'))
  process.exit(1)
}
console.log('walked every page with no errors')
