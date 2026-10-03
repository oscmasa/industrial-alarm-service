import { useEffect, useState } from 'react'
import { AlarmApiError, fetchTopTags } from '../api/client'
import type { TopTagFilters, TopTags } from '../api/types'
import { tagBars } from './tagBars'

type MetricsState =
  | { status: 'loading' }
  | { status: 'success'; data: TopTags }
  | { status: 'error'; message: string }

export function TopTagsPanel({ filters }: { filters: TopTagFilters }) {
  const { start_time: startTime, end_time: endTime, severity } = filters
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<MetricsState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchTopTags(controller.signal, { start_time: startTime, end_time: endTime, severity })
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: 'success', data })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ status: 'error', message: error instanceof AlarmApiError
            ? error.message : 'Could not load top-tag metrics. Check the service connection and try again.' })
        }
      })
    return () => controller.abort()
  }, [startTime, endTime, severity, retry])

  function retryLoad() {
    setState({ status: 'loading' })
    setRetry((value) => value + 1)
  }

  return (
    <section className="metrics-panel" aria-labelledby="top-tags-title" aria-busy={state.status === 'loading'}>
      <div className="panel-heading">
        <h2 id="top-tags-title">Top alarm tags</h2>
        <span>Up to 5 tags · Accepted events</span>
      </div>
      <p className="metrics-context">
        Uses the applied time and severity filters. The tag filter applies only to the alarm list.
      </p>
      {state.status === 'loading' && <p className="panel-state" role="status">Loading top-tag metrics…</p>}
      {state.status === 'error' && (
        <div className="panel-state error-state">
          <p role="alert">{state.message}</p>
          <button type="button" onClick={retryLoad}>Retry metrics</button>
        </div>
      )}
      {state.status === 'success' && (state.data.items.length === 0 ? (
        <p className="panel-state" role="status">No events match the metrics time and severity filters.</p>
      ) : (
        <figure className="tag-chart">
          <figcaption className="visually-hidden">
            Alarm activations per tag, ranked by event count. Bar lengths are relative to the largest count.
          </figcaption>
          <ol className="tag-ranking">
            {tagBars(state.data.items).map((item) => (
              <li key={item.tag}>
                <div className="bar-label">
                  <span className="chart-tag">{item.tag}</span>
                  <span className="bar-count">{item.event_count.toLocaleString('en-US')} events</span>
                </div>
                <div className="bar-track" aria-hidden="true">
                  <div className="bar-fill" style={{ width: `${item.width}%` }} />
                </div>
              </li>
            ))}
          </ol>
          <p className="chart-note">Counts cover the full selected period, across all pages. Duplicate imports are excluded.</p>
        </figure>
      ))}
    </section>
  )
}
