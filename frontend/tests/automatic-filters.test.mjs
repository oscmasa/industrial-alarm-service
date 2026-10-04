import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createDebouncer, overviewFilters } from '../src/components/automaticFilters.ts'

test('rapid text edits run only the latest scheduled query', async () => {
  const debounce = createDebouncer(10)
  const calls = []
  debounce.schedule(() => calls.push('old'))
  debounce.schedule(() => calls.push('latest'))
  await new Promise(resolve => setTimeout(resolve, 30))
  assert.deepEqual(calls, ['latest'])
})
test('clearing fields or unmounting cancels a pending text query', async () => {
  const debounce = createDebouncer(10)
  let calls = 0
  debounce.schedule(() => calls++)
  debounce.cancel()
  await new Promise(resolve => setTimeout(resolve, 30))
  assert.equal(calls, 0)
})
test('overview builds a complete combined query with inclusive plant-day bounds', () => {
  assert.deepEqual(overviewFilters('2026-09-01','2026-09-30','PUMP_01_FLOW','LOW_FLOW','HIGH'), {
    start_time:'2026-09-01T00:00:00-05:00', end_time:'2026-10-01T00:00:00-05:00',
    tag:'PUMP_01_FLOW', alarm_code:'LOW_FLOW', severity:'HIGH',
  })
})
test('incomplete, reversed, invalid and oversized periods never produce a query', () => {
  for (const [start,end] of [['','2026-09-30'], ['2026-09-01',''], ['2026-09-30','2026-09-01'], ['2026-02-30','2026-03-01'], ['2025-01-01','2026-02-01'], ['0000-01-01','0000-01-02']]) {
    assert.equal(overviewFilters(start,end,'','',''), null)
  }
})
test('cleared optional selectors omit their filters and leap days remain valid', () => {
  const query = overviewFilters('2024-02-29','2024-02-29','','','')
  assert.equal(query.end_time, '2024-03-01T00:00:00-05:00')
  assert.equal(query.tag, undefined)
  assert.equal(query.alarm_code, undefined)
  assert.equal(query.severity, undefined)
})
