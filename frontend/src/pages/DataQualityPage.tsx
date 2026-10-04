import { useEffect, useRef, useState } from 'react'
import { fetchImports, fetchRejections } from '../api/client'
import type { ImportList, ImportSummary, RejectionList } from '../api/types'
import { RecordPagination } from '../components/RecordPagination'
import { RejectedRecordsTable } from '../components/RejectedRecordsTable'
import { createDebouncer } from '../components/automaticFilters'
import { auditTime, normalizeIssueCode } from '../components/qualityFormatting'

type ImportState = { key?: string; data?: ImportList; error?: string }
type RejectionState = { key?: string; data?: RejectionList; execution?: ImportSummary; code?: string; error?: string }
const message = (error: unknown) => error instanceof Error ? error.message : 'Could not load data quality. Please try again.'

export function DataQualityPage() {
  const [importsPage, setImportsPage] = useState(1)
  const [importsRetry, setImportsRetry] = useState(0)
  const [imports, setImports] = useState<ImportState>({})
  const [selected, setSelected] = useState<ImportSummary | null>(null)
  const [page, setPage] = useState(1)
  const [retry, setRetry] = useState(0)
  const [draftCode, setDraftCode] = useState('')
  const [code, setCode] = useState('')
  const [validation, setValidation] = useState('')
  const [rejections, setRejections] = useState<RejectionState>({})
  const importsKey = `${importsPage}:${importsRetry}`
  const importsBusy = imports.key !== importsKey
  const rejectionKey = JSON.stringify([selected?.id, page, code, retry])
  const busy = selected !== null && rejections.key !== rejectionKey

  useEffect(() => {
    const controller = new AbortController()
    fetchImports(importsPage, controller.signal).then(data => {
      if (controller.signal.aborted) return
      setImports({ key: importsKey, data })
      setSelected(current => current ?? data.items[0] ?? null)
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setImports(current => ({ ...current, key: importsKey, error: message(error) }))
    })
    return () => controller.abort()
  }, [importsPage, importsKey])

  useEffect(() => {
    if (!selected) return
    const controller = new AbortController()
    fetchRejections(selected.id, page, controller.signal, code).then(data => {
      if (!controller.signal.aborted) setRejections({ key: rejectionKey, data, execution: selected, code })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setRejections(current => ({ ...current, key: rejectionKey, error: message(error) }))
    })
    return () => controller.abort()
  }, [selected, page, code, rejectionKey])

  const debounce = useRef(createDebouncer())
  useEffect(() => () => debounce.current.cancel(), [])

  function updateCode(value: string) {
    debounce.current.cancel()
    setDraftCode(value)
    const normalized = normalizeIssueCode(value)
    if (normalized === null) { setValidation('Use a code shown in the rejection table, up to 64 letters, numbers or underscores, starting with a letter.'); return }
    setValidation('')
    const apply = () => { setPage(1); setCode(normalized) }
    if (normalized) debounce.current.schedule(apply)
    else apply()
  }

  function choose(id: string) {
    const execution = imports.data?.items.find(item => item.id === id)
    if (!execution) return
    debounce.current.cancel()
    setSelected(execution); setPage(1); setCode(''); setDraftCode(''); setValidation('')
  }
  const shown = rejections.execution
  const items = imports.data?.items ?? []
  const options = selected && !items.some(item => item.id === selected.id) ? [selected, ...items] : items
  return <>
    <div className="page-heading"><p className="eyebrow">Import traceability</p><h1>Data quality</h1><p className="page-description">Import outcomes and original rejected records - Bogota time (UTC-05:00)</p></div>
    <section className="quality-imports filter-panel" aria-label="Import selection" aria-busy={importsBusy}>
      <div className="quality-import-control filter-field"><label htmlFor="quality-import">Import execution</label>
        <select id="quality-import" value={selected?.id ?? ''} disabled={!options.length || importsBusy} onChange={e => choose(e.target.value)}>
          {!options.length && <option value="">{importsBusy ? 'Loading imports...' : 'No imports available'}</option>}
          {options.map(item => <option key={item.id} value={item.id}>{auditTime(item.started_at)} - {item.file_name} - {item.status} - {item.id.slice(0,8)}</option>)}
        </select>
      </div>
      {importsBusy && <span className="refresh-notice" role="status">{imports.data ? 'Updating import list...' : 'Loading import history...'}</span>}
      {imports.error && !importsBusy && <div className="quality-inline-error"><p role="alert">{imports.error}</p><button type="button" onClick={() => setImportsRetry(value => value + 1)}>Retry imports</button></div>}
      {imports.data && <RecordPagination pagination={imports.data.pagination} resource="imports" busy={importsBusy} onChange={setImportsPage} />}
    </section>
    {imports.data && !imports.data.pagination.total && <p className="panel-state">No import executions have been recorded yet.</p>}
    {selected && <>
      <div className="quality-filters filter-panel">
        <div className="filter-field"><label htmlFor="quality-code">Rejection reason code (optional)</label><input id="quality-code" value={draftCode} placeholder="e.g. INVALID_VALUE" aria-invalid={Boolean(validation)} aria-describedby="quality-code-help" onChange={e => updateCode(e.target.value)} /></div>
        <div className="filter-actions"><button type="button" onClick={() => {updateCode('')}}>Clear filter</button></div>
        <p id="quality-code-help" className={validation ? 'field-error' : 'quality-filter-help'}>{validation || 'Use a code shown in the rejection table. Results update automatically after typing; import totals remain unchanged.'}</p>
      </div>
      <div className="quality-update-status" role="status">{busy ? 'Updating results... Previous results remain visible until the selected execution loads.' : rejections.error ? 'Update failed. Previous results remain visible.' : shown ? `Showing execution ${shown.id.slice(0,8)} - ${rejections.code || 'All error codes'}` : ''}</div>
      {rejections.error && !busy && <div className="quality-inline-error error-state"><p role="alert">{rejections.error}</p><button type="button" onClick={() => setRetry(value => value + 1)}>Retry results</button></div>}
      {shown && <div aria-busy={busy}>
        <p className="quality-execution-meta">{shown.file_name} - {shown.source_system} - <strong>{shown.status}</strong> - Started {auditTime(shown.started_at)}{shown.finished_at ? ` - Finished ${auditTime(shown.finished_at)}` : ' - Not finished'}</p>
        <div className="quality-cards">
          <article className="quality-accepted"><span>Accepted</span><strong>{shown.accepted.toLocaleString('en-US')}</strong></article>
          <article className="quality-rejected"><span>Rejected</span><strong>{shown.rejected.toLocaleString('en-US')}</strong></article>
          <article className="quality-duplicates"><span>Duplicates</span><strong>{shown.duplicates.toLocaleString('en-US')}</strong></article>
          <article className="quality-warnings"><span>Accepted with warnings</span><strong>{shown.accepted_with_warnings.toLocaleString('en-US')}</strong></article>
        </div>
        <p className="quality-counter-note">{shown.records_read.toLocaleString('en-US')} records processed. Warnings are included in accepted records. Counts belong to this execution.{shown.status !== 'COMPLETED' && ' This execution is not completed; counters may be incomplete.'}</p>
        <section className="alarm-panel" aria-labelledby="rejections-title">
          <div className="panel-heading"><h2 id="rejections-title">Rejected records</h2><span>Source record order - Original values preserved</span></div>
          {rejections.data && (rejections.data.items.length ? <RejectedRecordsTable records={rejections.data.items} /> : <p className="panel-state">{rejections.data.pagination.total ? 'No records on this page.' : rejections.code ? 'No rejected records match this error code.' : 'This execution has no rejected records.'}</p>)}
          {rejections.data && <RecordPagination pagination={rejections.data.pagination} resource="rejected records" busy={busy} onChange={setPage} />}
        </section>
        <details className="quality-audit-details"><summary>Execution details</summary><dl><dt>Import ID</dt><dd>{shown.id}</dd><dt>SHA-256</dt><dd>{shown.file_sha256}</dd></dl></details>
      </div>}
    </>}
  </>
}
