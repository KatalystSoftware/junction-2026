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
  await expect('events', 'Suggested next')
  await shot('events')
  await open('#/event/semiconductors-and-photonics')
  await expect('a suggested event', 'Employers to invite')
  await shot('event')
  await open('#/event/deep-tech-talent-forum', 390, 844)
  await expect('the upcoming event on a phone', 'People to invite')
  await shot('event-phone')
  await open(`#/${COMPANY}`)
  await expect('an employer', 'Looking for')

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
