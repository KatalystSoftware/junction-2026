// A CV handed over as a PDF is read here, in the browser. The file is never sent anywhere and nothing of it is
// written to a console: only the text it yields, which the person sees and can change first, takes the same road
// as a pasted CV. The reader (pdf.js) is fetched when the first file is chosen, not with the page.

/** A file larger than this is refused unread: no CV needs it, and a phone should not try. */
export const FILE_MOST = 10 * 1024 * 1024
/** A CV is read up to this many pages; the flow reads no more text than these hold anyway. */
const PAGES_MOST = 30
/** Less text than this is not a CV: the server refuses it too (person.py). A scan yields this little. */
const TEXT_LEAST = 200
const PASTE = 'Paste the text of your CV instead.'

/** A file that cannot be read here, with what to tell the person. */
export class Unread extends Error {}

type Pdfjs = typeof import('pdfjs-dist/legacy/build/pdf.mjs')
let reader: Promise<Pdfjs> | undefined
/** The reader and its worker, once per page. The older-browser build: a phone a few years old must manage it too. */
const pdfjs = () =>
  (reader ??= Promise.all([import('pdfjs-dist/legacy/build/pdf.mjs'), import('pdfjs-dist/legacy/build/pdf.worker.min.mjs?worker')]).then(([lib, worker]) => {
    lib.GlobalWorkerOptions.workerPort = new worker.default()
    return lib
  }))

const tidy = (text: string) =>
  text
    .split('\n')
    .map((line) => line.replace(/[ \t\u00a0]+/g, ' ').trim())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

/** The text of a PDF. Throws Unread, with a sentence for the person, when the file is not one this can read. */
export async function pdfText(file: File): Promise<string> {
  if (file.type !== 'application/pdf' && !/\.pdf$/i.test(file.name)) throw new Unread(`Only a PDF can be read here. ${PASTE}`)
  if (!file.size) throw new Unread(`That file is empty. ${PASTE}`)
  if (file.size > FILE_MOST) throw new Unread(`That file is larger than ${String(FILE_MOST / 1024 / 1024)} MB. ${PASTE}`)
  const data = new Uint8Array(await file.arrayBuffer())
  if (!new TextDecoder('latin1').decode(data.subarray(0, 1024)).includes('%PDF-')) throw new Unread(`That file is not a PDF, whatever its name says. ${PASTE}`)
  let lib: Pdfjs
  try {
    lib = await pdfjs()
  } catch {
    reader = undefined
    throw new Unread(`The PDF reader could not be loaded. ${PASTE}`)
  }
  // verbosity 0: the reader says nothing in the console about the file
  const task = lib.getDocument({ data, verbosity: 0, disableFontFace: true })
  try {
    const doc = await task.promise
    let text = ''
    for (let n = 1; n <= Math.min(doc.numPages, PAGES_MOST); n++) {
      const page = await doc.getPage(n)
      for (const item of (await page.getTextContent()).items) if ('str' in item) text += item.str + (item.hasEOL ? '\n' : '')
      text += '\n\n'
      page.cleanup()
    }
    text = tidy(text)
    if (text.length < TEXT_LEAST)
      throw new Unread(`${text ? 'Too little' : 'No'} text could be read from that PDF. It may be a scan: pictures of pages, not text. ${PASTE}`)
    return text
  } catch (error) {
    if (error instanceof Unread) throw error
    const name = error instanceof Error ? error.name : ''
    if (name === 'PasswordException') throw new Unread(`That PDF is locked with a password. ${PASTE}`)
    throw new Unread(`That file could not be opened as a PDF. ${PASTE}`)
  } finally {
    await task.destroy()
  }
}
