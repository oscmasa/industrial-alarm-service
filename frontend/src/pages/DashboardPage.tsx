import { useEffect, useState } from 'react'
import { AlarmApiError, fetchAlarms } from '../api/client'
import type { AlarmList, AlarmQueryFilters } from '../api/types'
import { AlarmFilters } from '../components/AlarmFilters'
import { AlarmPagination } from '../components/AlarmPagination'
import { AlarmTable } from '../components/AlarmTable'
import { DashboardHeader } from '../components/DashboardHeader'
import { TopTagsPanel } from '../components/TopTagsPanel'

const PAGE_SIZE = 20

type LoadState =
  | { status: 'loading' }
  | { status: 'success'; data: AlarmList }
  | { status: 'error'; message: string }

export function DashboardPage() {
  const [filters, setFilters] = useState<AlarmQueryFilters>({})
  const [page, setPage] = useState(1)
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchAlarms(page, PAGE_SIZE, controller.signal, filters)
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: 'success', data })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ status: 'error', message: error instanceof AlarmApiError
            ? error.message : 'Could not load alarms. Check the service connection and try again.' })
        }
      })
    return () => controller.abort()
  }, [page, retry, filters])

  function applyFilters(nextFilters: AlarmQueryFilters) {
    setState({ status: 'loading' })
    setPage(1)
    setFilters(nextFilters)
  }

  function changePage(nextPage: number) {
    setState({ status: 'loading' })
    setPage(nextPage)
  }

  function retryLoad() {
    setState({ status: 'loading' })
    setRetry((value) => value + 1)
  }

  // Reset metric state only when its own filters change, not on tag or page changes.
  const metricsKey = JSON.stringify([filters.start_time, filters.end_time, filters.severity])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to alarm history</a>
      <DashboardHeader />
      <main id="main-content" className="dashboard-main">
        <div className="page-heading">
          <p className="eyebrow">Production line overview</p>
          <h1>Alarm history</h1>
          <p className="page-description">Historical activations across the water treatment and bottling line.</p>
        </div>
        <AlarmFilters appliedFilters={filters} onApply={applyFilters} />
        <TopTagsPanel key={metricsKey} filters={filters} />
        <section className="alarm-panel" aria-labelledby="records-title" aria-busy={state.status === 'loading'}>
          <div className="panel-heading">
            <h2 id="records-title">Recorded alarms</h2>
            <span>Plant time · America/Bogota (UTC-05)</span>
          </div>
          <div role="status" className="visually-hidden">
            {state.status === 'success' ? `Page ${state.data.pagination.page} loaded, ${state.data.items.length} events shown.` : ''}
          </div>
          {state.status === 'loading' && <p className="panel-state" role="status">Loading alarm records…</p>}
          {state.status === 'error' && (
            <div className="panel-state error-state">
              <p role="alert">{state.message}</p>
              <button type="button" onClick={retryLoad}>Try again</button>
            </div>
          )}
          {state.status === 'success' && (
            <>
              {state.data.items.length > 0 ? <AlarmTable alarms={state.data.items} /> : (
                <div className="panel-state">
                  <p>{state.data.pagination.total === 0 ? (Object.keys(filters).length > 0 ? 'No alarms match the applied filters.' : 'No alarm records are available.') : 'No records on this page.'}</p>
                  {page > 1 && <button type="button" onClick={() => changePage(1)}>Return to first page</button>}
                </div>
              )}
              <AlarmPagination pagination={state.data.pagination} onPageChange={changePage} />
            </>
          )}
        </section>
        <footer className="dashboard-footer">AquaLine · Historical SCADA events · 20 events per page</footer>
      </main>
    </div>
  )
}
