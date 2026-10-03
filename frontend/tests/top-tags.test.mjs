import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { AlarmApiError, fetchTopTags } from '../src/api/client.ts'
import { tagBars } from '../src/components/tagBars.ts'

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('requests five top tags and preserves API ranking and counts', async () => {
  const body = { items: [{ tag: 'PUMP_01_FLOW', event_count: 120 }, { tag: 'TANK_IN_01_LEVEL', event_count: 40 }], limit: 5 }
  const signal = new AbortController().signal
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/metrics/top-tags?limit=5')
    assert.equal(options.signal, signal)
    return Response.json(body)
  }
  assert.deepEqual(await fetchTopTags(signal), body)
})

test('uses time and severity, excluding tag and pagination even if supplied', async () => {
  const filters = { start_time: '2026-09-15T05:00:00.000Z', end_time: '2026-09-16T05:00:00.000Z',
    severity: 'HIGH', tag: 'PUMP_01_FLOW', page: 2 }
  globalThis.fetch = async (url) => {
    const parameters = new URL(url, 'http://localhost').searchParams
    assert.equal(parameters.get('limit'), '5')
    for (const key of ['start_time', 'end_time', 'severity']) assert.equal(parameters.get(key), filters[key])
    assert.equal(parameters.has('tag'), false)
    assert.equal(parameters.has('page'), false)
    return Response.json({ items: [], limit: 5 })
  }
  await fetchTopTags(new AbortController().signal, filters)
})

test('accepts empty metrics without fabricating bars', async () => {
  globalThis.fetch = async () => Response.json({ items: [], limit: 5 })
  assert.deepEqual(await fetchTopTags(new AbortController().signal), { items: [], limit: 5 })
  assert.deepEqual(tagBars([]), [])
})

test('scales bars against the largest count, keeping exact counts and tie order', () => {
  const items = [{ tag: 'A', event_count: 120 }, { tag: 'B', event_count: 60 }, { tag: 'C', event_count: 60 }]
  assert.deepEqual(tagBars(items), [
    { tag: 'A', event_count: 120, width: 100 },
    { tag: 'B', event_count: 60, width: 50 },
    { tag: 'C', event_count: 60, width: 50 },
  ])
  assert.deepEqual(items, [{ tag: 'A', event_count: 120 }, { tag: 'B', event_count: 60 }, { tag: 'C', event_count: 60 }])
})

test('zero counts do not produce invalid bar widths', () => {
  assert.deepEqual(tagBars([{ tag: 'A', event_count: 0 }]), [{ tag: 'A', event_count: 0, width: 0 }])
})

test('reports metrics failures safely', async () => {
  globalThis.fetch = async () => new Response('private query', { status: 502 })
  await assert.rejects(fetchTopTags(new AbortController().signal), (error) => {
    assert.ok(error instanceof AlarmApiError)
    assert.match(error.message, /top-tag metrics/)
    assert.doesNotMatch(error.message, /private/)
    return true
  })
})

test('keeps service-unavailable errors friendly', async () => {
  globalThis.fetch = async () => new Response('private query', { status: 503 })
  await assert.rejects(fetchTopTags(new AbortController().signal), /temporarily unavailable/)
})

test('preserves cancellation for obsolete metric requests', async () => {
  const controller = new AbortController()
  controller.abort()
  globalThis.fetch = async (_url, options) => {
    options.signal.throwIfAborted()
    throw new Error('Unreachable')
  }
  await assert.rejects(fetchTopTags(controller.signal), { name: 'AbortError' })
})
