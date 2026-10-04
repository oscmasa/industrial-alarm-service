import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { fetchImports, fetchRejections, AlarmApiError } from '../src/api/client.ts'
import { normalizeIssueCode, auditTime } from '../src/components/qualityFormatting.ts'
const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('normalizes exact issue codes and rejects malformed filters', () => {
  assert.equal(normalizeIssueCode(' invalid_value '), 'INVALID_VALUE')
  assert.equal(normalizeIssueCode('   '), '')
  for (const value of ['BAD CODE', '1BAD', 'A'.repeat(65), "x';DROP TABLE alarms"]) assert.equal(normalizeIssueCode(value), null)
})
test('audit timestamps use plant time even across the UTC date boundary', () => {
  const text = auditTime('2026-10-01T02:00:00Z')
  assert.match(text, /30 Sept 2026/)
  assert.match(text, /21:00:00/)
})
test('paginates import history without combining counters between executions', async () => {
  const body = {items:[{id:'initial', accepted:9500, rejected:300, duplicates:200, accepted_with_warnings:167}, {id:'repeat', accepted:0, rejected:300, duplicates:9700, accepted_with_warnings:0}], pagination:{page:2, page_size:20, total:22, total_pages:2}}
  const signal = new AbortController().signal
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/imports?page=2&page_size=20')
    assert.equal(options.signal, signal)
    return Response.json(body)
  }
  assert.deepEqual(await fetchImports(2, signal), body)
})
test('rejection requests preserve original values and all issues', async () => {
  const body = {import_id:'test-id', items:[{original_data:{value:'  bad ', message:null}, errors:[{field:'value', code:'INVALID_VALUE'}, {field:'occurred_at', code:'INVALID_DATE'}]}], pagination:{page:2}}
  globalThis.fetch = async url => {
    const parsed = new URL(url, 'http://localhost')
    assert.equal(parsed.pathname, '/api/imports/test-id/rejections')
    assert.deepEqual(Object.fromEntries(parsed.searchParams), {page:'2', page_size:'20', error_code:'INVALID_VALUE'})
    return Response.json(body)
  }
  assert.deepEqual(await fetchRejections('test-id', 2, new AbortController().signal, 'INVALID_VALUE'), body)
})
test('an empty rejection result is valid and omits an unset error filter', async () => {
  globalThis.fetch = async url => {
    assert.equal(new URL(url, 'http://localhost').searchParams.has('error_code'), false)
    return Response.json({items:[], pagination:{total:0}})
  }
  assert.deepEqual((await fetchRejections('test-id', 1, new AbortController().signal)).items, [])
})
test('reports missing imports without exposing server text', async () => {
  globalThis.fetch = async () => new Response('private details', {status:404})
  await assert.rejects(fetchRejections('unknown', 1, new AbortController().signal), error => {
    assert.ok(error instanceof AlarmApiError)
    assert.doesNotMatch(error.message, /private/)
    return true
  })
})
test('cancels obsolete rejection requests', async () => {
  const controller = new AbortController(); controller.abort()
  globalThis.fetch = async (_url, options) => { options.signal.throwIfAborted() }
  await assert.rejects(fetchRejections('test-id', 1, controller.signal), {name:'AbortError'})
})
