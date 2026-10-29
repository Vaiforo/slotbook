// Capture before React/router initialization; reads never consume the credential.
export function captureManageToken(browser: Pick<Window, 'location' | 'history'>) {
  const { pathname, search, hash } = browser.location
  const match = /^\/manage\/([0-9a-f-]{36})\/?$/i.exec(pathname)
  if (!match) return undefined
  const token = new URLSearchParams(hash.slice(1)).get('token')
  if (hash) browser.history.replaceState(browser.history.state, '', pathname + search)
  if (!token || !/^[A-Za-z0-9_-]{43}$/.test(token)) return undefined
  return { id: match[1], token }
}

let revision = 0
let credential:
  (NonNullable<ReturnType<typeof captureManageToken>> & { revision: number }) | undefined
const listeners = new Set<() => void>()
function capture() {
  const next = captureManageToken(window)
  credential = next ? { ...next, revision: ++revision } : undefined
  listeners.forEach((notify) => notify())
}
function onHashChange() {
  // Opening a saved link on the same page may only change the fragment.
  if (new URLSearchParams(window.location.hash.slice(1)).has('token')) capture()
}
export function initializeManageToken() {
  capture()
  window.addEventListener('hashchange', onHashChange)
}
export function subscribeManageToken(notify: () => void) {
  listeners.add(notify)
  return () => {
    listeners.delete(notify)
  }
}
export function getManageCredential() {
  return credential
}
export function tokenForBooking(id: string) {
  return credential?.id === id ? credential.token : undefined
}
export function manageLink(id: string, token: string) {
  return `${window.location.origin}/manage/${encodeURIComponent(id)}#token=${encodeURIComponent(token)}`
}
