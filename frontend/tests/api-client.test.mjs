import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { AlarmApiError, fetchAlarms } from '../src/api/client.ts'

const originalFetch = globalThis.fetch

afterEach(() => { globalThis.fetch = originalFetch })

test('requests the chosen page and preserves decimals, nulls and warnings', async () => {
  const signal = new AbortController().signal
  const body = { items: [{ value: '12.500001', message: null, warnings: ['VALUE_TRIGGER_MISMATCH'] }],
    pagination: { page: 2, page_size: 20, total: 21, total_pages: 2 } }
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/alarms?page=2&page_size=20')
    assert.equal(options.signal, signal)
    assert.equal(options.headers.Accept, 'application/json')
    return Response.json(body)
  }
  assert.deepEqual(await fetchAlarms(2, 20, signal), body)
})

test('returns an empty page without turning it into an error', async () => {
  const body = { items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } }
  globalThis.fetch = async () => Response.json(body)
  assert.deepEqual(await fetchAlarms(1, 20, new AbortController().signal), body)
})

test('reports service unavailability without exposing server internals', async () => {
  globalThis.fetch = async () => new Response('private database details', { status: 503 })
  await assert.rejects(fetchAlarms(1, 20, new AbortController().signal), (error) => {
    assert.ok(error instanceof AlarmApiError)
    assert.match(error.message, /temporarily unavailable/)
    assert.doesNotMatch(error.message, /private/)
    return true
  })
})

test('handles a non-JSON proxy failure as a friendly API error', async () => {
  globalThis.fetch = async () => new Response('<html>Bad Gateway</html>', { status: 502 })
  await assert.rejects(fetchAlarms(1, 20, new AbortController().signal), AlarmApiError)
})

test('preserves cancellation so the page can discard an obsolete request', async () => {
  const controller = new AbortController()
  controller.abort()
  globalThis.fetch = async (_url, options) => {
    options.signal.throwIfAborted()
    throw new Error('Unreachable')
  }
  await assert.rejects(fetchAlarms(1, 20, controller.signal), { name: 'AbortError' })
})
