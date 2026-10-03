import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { plantDate, nextDay, monthRange, availableMonths } from '../src/components/overviewDates.ts'
import { fetchOverview, fetchAvailableDates, fetchCatalog } from '../src/api/client.ts'
const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })
test('assigns UTC events to the correct plant day at midnight boundaries', () => {
  assert.equal(plantDate('2026-10-01T02:57:28Z'), '2026-09-30')
  assert.equal(plantDate('2026-10-01T05:00:00Z'), '2026-10-01')
})
test('inclusive end dates advance correctly across months and leap years', () => {
  assert.equal(nextDay('2026-09-30'), '2026-10-01')
  assert.equal(nextDay('2024-02-28'), '2024-02-29')
  assert.deepEqual(monthRange('2024-02'), ['2024-02-01', '2024-02-29'])
  assert.deepEqual(monthRange('2026-12'), ['2026-12-01', '2026-12-31'])
})
test('month choices cover only the observed date interval in newest-first order', () => {
  assert.deepEqual(availableMonths('2026-09-01', '2026-09-30'), ['2026-09'])
  assert.deepEqual(availableMonths('2025-12-31', '2026-02-01'), ['2026-02', '2026-01', '2025-12'])
})
test('overview forwards every selected filter and preserves unavailable metrics', async () => {
  const filters = {start_time:'2026-09-01T00:00:00-05:00', end_time:'2026-10-01T00:00:00-05:00', tag:'PUMP_01_FLOW', alarm_code:'LOW_FLOW', severity:'HIGH'}
  const body = {total_events:0, daily:[{date:'2026-09-01', event_count:0, moving_average_7_days:null}], comparison:{event_count:null, change_percent:null}}
  const signal = new AbortController().signal
  globalThis.fetch = async (url, options) => {
    const parsed = new URL(url, 'http://localhost')
    assert.equal(parsed.pathname, '/api/metrics/overview')
    assert.deepEqual(Object.fromEntries(parsed.searchParams), filters)
    assert.equal(options.signal, signal)
    return Response.json(body)
  }
  assert.deepEqual(await fetchOverview(signal, filters), body)
})
test('loads real availability and catalog through separate endpoints', async () => {
  const seen = []
  globalThis.fetch = async url => { seen.push(url.split('?')[0]); return Response.json({items:[]}) }
  const signal = new AbortController().signal
  await fetchAvailableDates(signal); await fetchCatalog(signal)
  assert.deepEqual(seen, ['/api/metrics/available-dates', '/api/catalog/tags'])
})
