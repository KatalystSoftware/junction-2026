/** A Context.dev logo as serve.py's own copy, shrunk to fit `width` px and cached a year; any other address as it is. */
export const logoSrc = (url: string, width: 128 | 512): string =>
  /^https:\/\/(media\.brand\.dev|([\w-]+\.)*context\.dev)\//.test(url) ? `logo?u=${encodeURIComponent(url)}&w=${String(width)}` : url
