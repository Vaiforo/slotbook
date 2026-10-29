// @vitest-environment jsdom
import { expect, it } from 'vitest'
import { captureManageToken, initializeManageToken, tokenForBooking } from './manage-token'

const id = '00000000-0000-4000-8000-000000000001'
const token = 'a'.repeat(43)
it('scrubs the fragment before mount and retains access across repeated reads', () => {
  history.replaceState({ marker: true }, '', `/manage/${id}#token=${token}`)
  initializeManageToken()
  expect(location.hash).toBe('')
  expect(history.state).toEqual({ marker: true })
  expect(tokenForBooking(id)).toBe(token)
  expect(tokenForBooking(id)).toBe(token)
  expect(tokenForBooking('other')).toBeUndefined()
  expect(localStorage.length).toBe(0)
  expect(sessionStorage.length).toBe(0)
  initializeManageToken()
  expect(tokenForBooking(id)).toBeUndefined()
})
it.each(['#token=invalid', '#other=secret', '#token='])(
  'scrubs malformed secrets without granting access: %s',
  (hash) => {
    history.replaceState(null, '', `/manage/${id}${hash}`)
    expect(captureManageToken(window)).toBeUndefined()
    expect(location.hash).toBe('')
  },
)

it('accepts a newly opened fragment on the same page and keeps ordinary anchors usable', () => {
  history.replaceState(null, '', `/manage/${id}`)
  initializeManageToken()
  history.replaceState(null, '', `/manage/${id}#token=${token}`)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
  expect(tokenForBooking(id)).toBe(token)
  expect(location.hash).toBe('')
  history.replaceState(null, '', `/manage/${id}#main`)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
  expect(tokenForBooking(id)).toBe(token)
})
