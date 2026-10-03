import assert from 'node:assert/strict'
import { test } from 'node:test'
import { EMPTY_FILTERS, validateFilters } from '../src/components/filterValidation.ts'

test('empty fields omit every optional filter', () => {
  assert.deepEqual(validateFilters(EMPTY_FILTERS), { valid: true, filters: {} })
})

test('converts the plant clock to UTC and normalizes the exact tag', () => {
  assert.deepEqual(validateFilters({ startTime: '2026-09-15T00:00', endTime: '2026-09-16T00:00:00',
    severity: 'HIGH', tag: ' pump_01_flow ' }), { valid: true, filters: {
    start_time: '2026-09-15T05:00:00.000Z', end_time: '2026-09-16T05:00:00.000Z',
    severity: 'HIGH', tag: 'PUMP_01_FLOW',
  } })
})

test('allows a one-sided range and rolls the UTC date forward', () => {
  assert.deepEqual(validateFilters({ ...EMPTY_FILTERS, startTime: '2026-09-30T23:59:59' }), {
    valid: true, filters: { start_time: '2026-10-01T04:59:59.000Z' },
  })
})

for (const endTime of ['2026-09-15T12:00', '2026-09-15T11:59']) {
  test(`rejects non-increasing range ending at ${endTime}`, () => {
    const result = validateFilters({ ...EMPTY_FILTERS, startTime: '2026-09-15T12:00', endTime })
    assert.equal(result.valid, false)
    assert.match(result.errors.endTime, /later than/)
  })
}

for (const startTime of ['2026-02-30T12:00', '2026-09-15T24:00', '2026-09-15', '2026-09-15T12:00Z', '0000-01-01T12:00', '9999-12-31T23:00']) {
  test(`rejects invalid or unsupported local date ${startTime}`, () => {
    const result = validateFilters({ ...EMPTY_FILTERS, startTime })
    assert.equal(result.valid, false)
    assert.ok(result.errors.startTime)
  })
}

for (const tag of ['PUMP FLOW', '1PUMP', 'A'.repeat(65), "x';DROP TABLE alarms;--"]) {
  test(`rejects malformed tag ${tag}`, () => {
    const result = validateFilters({ ...EMPTY_FILTERS, tag })
    assert.equal(result.valid, false)
    assert.ok(result.errors.tag)
  })
}

test('a whitespace-only tag means no tag filter', () => {
  assert.deepEqual(validateFilters({ ...EMPTY_FILTERS, tag: '   ' }), { valid: true, filters: {} })
})
