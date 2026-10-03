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

test('sends all combined filters together with pagination', async () => {
  const filters = { start_time: '2026-09-15T05:00:00.000Z', end_time: '2026-09-16T05:00:00.000Z',
    severity: 'HIGH', tag: 'PUMP_01_FLOW' }
  globalThis.fetch = async (url) => {
    const parameters = new URL(url, 'http://localhost').searchParams
    assert.equal(parameters.get('page'), '2')
    assert.equal(parameters.get('page_size'), '20')
    for (const [name, value] of Object.entries(filters)) assert.equal(parameters.get(name), value)
    return Response.json({ items: [], pagination: { page: 2, page_size: 20, total: 0, total_pages: 0 } })
  }
  await fetchAlarms(2, 20, new AbortController().signal, filters)
})

test('omits unset filters rather than sending empty parameters', async () => {
  globalThis.fetch = async (url) => {
    assert.equal(url, '/api/alarms?page=1&page_size=20')
    return Response.json({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } })
  }
  await fetchAlarms(1, 20, new AbortController().signal, { tag: '', severity: undefined })
})

test('handles server-side filter rejection with a safe message', async () => {
  globalThis.fetch = async () => new Response('private validation internals', { status: 422 })
  await assert.rejects(fetchAlarms(1, 20, new AbortController().signal), (error) => {
    assert.ok(error instanceof AlarmApiError)
    assert.match(error.message, /filters/)
    assert.doesNotMatch(error.message, /private/)
    return true
  })
})
