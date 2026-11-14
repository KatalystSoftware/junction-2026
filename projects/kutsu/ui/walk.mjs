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
import { createHmac } from 'node:crypto'
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
// what the page sent that was not a plain GET, and how many times it opened a file chooser
const posts = []
let choosers = 0
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
    if (message.method === 'Network.requestWillBeSent' && message.params.request.method !== 'GET') posts.push(message.params.request.url)
    if (message.method === 'Page.fileChooserOpened') choosers++
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
  // a server with a demo key (KUTSU_KEY, as live) saves nothing without it: pass it to reset there too
  const keyed = (await fetch(`${base}/unlock`)).status === 403
  const keyHeader = process.env.KUTSU_KEY ? { 'x-kutsu-key': process.env.KUTSU_KEY } : {}
  await fetch(`${base}/review?id=${COMPANY}`, { method: 'POST', body: JSON.stringify(draft), headers: keyHeader })

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

  // a CV is a PDF read in the browser, or its text pasted. The files are made here: one with text, one with a drawing
  // and no text (what a scan is to a reader), one that is not a PDF, an empty one and one too large.
  const pdf = (lines) => {
    const stream = lines.length ? `BT /F1 11 Tf 50 780 Td 14 TL ${lines.map((l) => `(${l}) Tj T*`).join(' ')} ET` : '50 50 m 500 700 l S'
    const objects = [
      '<< /Type /Catalog /Pages 2 0 R >>',
      '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
      '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
      `<< /Length ${String(stream.length)} >>\nstream\n${stream}\nendstream`,
      '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    let out = '%PDF-1.4\n'
    const at = objects.map((o, i) => {
      const start = out.length
      out += `${String(i + 1)} 0 obj\n${o}\nendobj\n`
      return start
    })
    const size = String(objects.length + 1)
    return `${out}xref\n0 ${size}\n0000000000 65535 f \n${at.map((a) => `${String(a).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size ${size} /Root 1 0 R >>\nstartxref\n${String(out.length)}\n%%EOF\n`
  }
  const CV = ['Aino Example', 'Process engineer, thin films', 'Espoo, Finland', 'Experience', '2019-2026 Process engineer at a made-up fab: ran ALD and PECVD deposition on 200 mm tools,', 'wrote the recipes and the run cards, and cut particle counts by a third.', 'Education', 'M.Sc. (Tech.), materials science', 'Languages: Finnish, English']
  const files = mkdtempSync(join(tmpdir(), 'kutsu-cv-'))
  const file = (name, content) => {
    writeFileSync(join(files, name), content)
    return join(files, name)
  }
  const TEXT = 'textarea[aria-label="The text of your CV"]'
  const until = async (what, test) => {
    for (let i = 0; i < 40; i++) {
      if (await evaluate(test)) return
      await sleep(250)
    }
    errors.push(`${what}: never happened`)
  }
  const choose = async (path) => {
    const { result } = await send('Runtime.evaluate', { expression: `document.querySelector('input[type=file]')` })
    await send('DOM.setFileInputFiles', { files: [path], objectId: result.objectId })
  }
  const refused = async (what, path, says) => {
    await choose(path)
    await until(`${what} is refused`, `document.body.innerText.includes(${JSON.stringify(says)})`)
    await until(`${what} leaves the text field to paste into`, `!!document.querySelector('${TEXT}') && document.body.innerText.includes('Paste the text of your CV instead.')`)
    await holds(`the text field after ${what}`, TEXT, '')
  }
  await send('Network.enable')
  await send('Page.setInterceptFileChooserDialog', { enabled: true })
  await open('#/me')
  await enter()
  posts.length = 0
  await expect('the first card', 'Add your CV as a PDF')
  await expect('the first card', 'Paste CV text instead')
  // the chooser is reached and opened from the keyboard, and Enter on it does not start the reading
  await evaluate(`document.querySelector('input[type=file]').focus()`)
  await enter()
  if (choosers !== 1) errors.push(`Enter on the file chooser opened it ${String(choosers)} times, not once`)
  await expect('the first card after Enter on the chooser', 'Add your CV as a PDF')
  await shot('me-cv-empty')
  await refused('a text file', file('notes.txt', CV.join('\n')), 'Only a PDF can be read here.')
  await shot('me-cv-refused')
  await refused('an empty file', file('empty.pdf', ''), 'That file is empty.')
  await refused('a file that only has the name of a PDF', file('renamed.pdf', CV.join('\n')), 'That file is not a PDF')
  await refused('a file that is too large', file('large.pdf', Buffer.concat([Buffer.from('%PDF-1.4\n'), Buffer.alloc(10 * 1024 * 1024)])), 'larger than 10 MB')
  await refused('a PDF with no text in it', file('scan.pdf', pdf([])), 'No text could be read from that PDF.')
  // the way on after a file that could not be read: the text, typed or pasted
  await type(TEXT, 'Process engineer. ')
  await evaluate(`document.querySelector('${TEXT}').focus()`)
  await send('Input.insertText', { text: CV.join('\n') })
  await until('pasted text is offered for reading', `document.querySelector('button[aria-label="Read my CV"]').getAttribute('aria-checked') === 'true'`)
  await holds('the text field after typing and pasting', TEXT, `Process engineer. ${CV.join('\n')}`)
  if ((await text()).includes('could be read from that PDF')) errors.push('a refusal is still shown once the text is typed instead')
  await empty(TEXT)
  // a PDF with text: its name, its text in the field to check and change, and a way to take it out again
  await choose(file('aino-example-cv.pdf', pdf(CV)))
  await until('the text of a PDF arrives in the field', `(document.querySelector('${TEXT}')?.value ?? '').includes('Process engineer, thin films')`)
  await expect('a PDF that was read', 'aino-example-cv.pdf')
  await expect('a PDF that was read', 'this text, not the file, is what gets read')
  if ((await text()).includes('could be read from that PDF')) errors.push('the last refusal is still shown after a PDF was read')
  if ((await evaluate(`document.querySelector('button[aria-label="Read my CV"]').getAttribute('aria-checked')`)) !== 'true') errors.push('a PDF that was read is not offered for reading')
  await evaluate(`(() => { const f = document.querySelector('${TEXT}'); f.focus(); f.setSelectionRange(f.value.length, f.value.length) })()`)
  await type(TEXT, ' Also Swedish.')
  if (!(await field(TEXT)).endsWith('Finnish, English Also Swedish.')) errors.push('the text read from a PDF cannot be changed')
  await shot('me-cv-read')
  await evaluate(`[...document.querySelectorAll('button')].find((b) => b.textContent === 'Remove').click()`)
  await until('a removed CV is gone', `!document.querySelector('${TEXT}') && !document.body.innerText.includes('aino-example-cv.pdf')`)
  // dropped on the card, even off the box, a file is taken and not opened in the tab
  await evaluate(`(() => {
    const data = new DataTransfer()
    data.items.add(new File([${JSON.stringify(pdf(CV))}], 'dropped-cv.pdf', { type: 'application/pdf' }))
    document.querySelector('${LINK}').dispatchEvent(new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }))
  })()`)
  await until('a dropped PDF is read', `(document.querySelector('${TEXT}')?.value ?? '').includes('Process engineer, thin films') && document.body.innerText.includes('dropped-cv.pdf')`)
  // none of that left the browser: a file is not sent, and text is sent only when the person says read
  if (posts.length) errors.push(`handing over a CV sent something before anything was read: ${posts.join(', ')}`)
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await sleep(300)
  await evaluate(`document.querySelector('${TEXT}').scrollIntoView({ block: 'center' })`)
  if (await evaluate('document.documentElement.scrollWidth > innerWidth')) errors.push('the CV row is wider than a phone')
  await shot('me-cv-phone')
  await send('Page.setInterceptFileChooserDialog', { enabled: false })

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
  // on a server with a key, a sign-up from a link without the company's token is the visitor's alone: not saved
  if (keyed) {
    const saved = (await (await fetch(`${base}/reviews.json`)).json())[COMPANY]
    if (saved?.status === 'joined') errors.push('a sign-up from a link without its token was saved on a server with a key')
    // it is the visitor's own copy instead: still signed up after a reload and on Espoo's screen, said on the page, and cleared from the menu
    await open(`#/${COMPANY}`)
    await expect("a visitor's own copy after a reload", 'Your own copy')
    const mineNow = await evaluate(`JSON.parse(localStorage.getItem('kutsu-my-copy') || '{}')[${JSON.stringify(COMPANY)}]?.status`)
    if (mineNow !== 'joined') errors.push(`the visitor's own copy holds ${String(mineNow)} for the company, not joined`)
    await shot('my-copy')
    await evaluate(`document.querySelector('.demo .mine').click()`)
    await sleep(300)
    for (let i = 0; i < 2; i++) {
      await evaluate(`[...document.querySelectorAll('.demo .menu button')].find((b) => /clear your changes|Clear my changes/.test(b.textContent)).click()`)
      await sleep(400)
    }
    if (await evaluate(`localStorage.getItem('kutsu-my-copy')`)) errors.push("Clear my changes left the visitor's copy")
    if ((await text()).includes('Your own copy')) errors.push("the page still says it is the visitor's own copy after clearing it")
    for (const [method, path] of [['DELETE', '/reviews'], ['POST', `/review?id=${COMPANY}`]]) {
      const r = await fetch(base + path, { method, body: method === 'POST' ? JSON.stringify(draft) : undefined })
      if (r.status !== 403) errors.push(`${method} ${path} without the key answered ${String(r.status)}, not 403`)
    }
    await open('#/')
    await evaluate(`document.querySelector('.demo .toggle').click()`)
    await sleep(300)
    await expect('the Demo menu without the key', 'Unlock with the demo key')
    if ((await text()).includes('Clear every sign-up')) errors.push('the Demo menu offers to clear every sign-up without the key')
    // the company's own link, signed with the key as Espoo's screen signs it, is saved; then put back
    if (process.env.KUTSU_KEY) {
      const token = createHmac('sha256', process.env.KUTSU_KEY).update(`join:${COMPANY}`).digest('hex').slice(0, 24)
      await open(`#/join/${COMPANY}?t=${token}`)
      for (let i = 0; i < 14 && !(await text()).includes('Change my answers'); i++) await enter()
      const mine = (await (await fetch(`${base}/reviews.json`)).json())[COMPANY]
      if (mine?.status !== 'joined') errors.push("a sign-up from the company's own signed link was not saved")
      await fetch(`${base}/review?id=${COMPANY}`, { method: 'POST', body: JSON.stringify(draft), headers: keyHeader })
    }
  }
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
