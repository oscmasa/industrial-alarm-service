import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatMeasuredValue } from '../src/components/measuredValue.ts'

test('formats units and removes trailing zeros without rounding readings', () => {
  assert.equal(formatMeasuredValue('6.610000', 'L/min'), '6.61 L/min')
  assert.equal(formatMeasuredValue('0.510000', 'bar'), '0.51 bar')
  assert.equal(formatMeasuredValue('75.400000', 'degC'), '75.4 °C')
  assert.equal(formatMeasuredValue('12.000000', '%'), '12 %')
  assert.equal(formatMeasuredValue('999999999999.123456', 'bar'), '999999999999.123456 bar')
  assert.equal(formatMeasuredValue('0.000001', 'bar'), '0.000001 bar')
  assert.equal(formatMeasuredValue('120', 'L/min'), '120 L/min')
})

test('distinguishes missing readings from zero and interprets binary signals', () => {
  assert.equal(formatMeasuredValue(null, 'bar'), 'Not available')
  assert.equal(formatMeasuredValue('0.000000', 'bar'), '0 bar')
  assert.equal(formatMeasuredValue('0.000000', 'boolean'), '0 — Inactive')
  assert.equal(formatMeasuredValue('1.000000', 'boolean'), '1 — Active')
  assert.equal(formatMeasuredValue('2.000000', 'boolean'), '2 (binary signal)')
  assert.equal(formatMeasuredValue('6.610000', null), '6.61 (unit not specified)')
})
