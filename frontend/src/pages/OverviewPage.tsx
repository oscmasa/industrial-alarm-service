import { useEffect, useState } from 'react'
import { fetchAvailableDates, fetchCatalog, fetchOverview } from '../api/client'
import type { AvailableDates, SignalCatalog, Overview, Severity, TopTagFilters } from '../api/types'
import { TopTagsPanel } from '../components/TopTagsPanel'
import { EventTimeline } from '../components/EventTimeline'
import { availableMonths, dateLabel, monthRange, nextDay, plantDate } from '../components/overviewDates'

export function OverviewPage() {
  const [setup, setSetup] = useState<{dates: AvailableDates; catalog: SignalCatalog} | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [month, setMonth] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [tag, setTag] = useState('')
  const [code, setCode] = useState('')
  const [severity, setSeverity] = useState<Severity | ''>('')
  const [filters, setFilters] = useState<TopTagFilters | null>(null)
  const [shownFilters, setShownFilters] = useState<TopTagFilters | null>(null)
  const [data, setData] = useState<Overview | null>(null)
  const [loading, setLoading] = useState(true)
  const [validation, setValidation] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([fetchAvailableDates(controller.signal), fetchCatalog(controller.signal)]).then(([dates, catalog]) => {
      if (controller.signal.aborted) return
      setSetup({dates, catalog})
      if (!dates.last_event) { setLoading(false); return }
      const selected = plantDate(dates.last_event).slice(0,7)
      const [first, last] = monthRange(selected)
      setMonth(selected); setStart(first); setEnd(last)
      setFilters({start_time: `${first}T00:00:00-05:00`, end_time: `${nextDay(last)}T00:00:00-05:00`})
    }).catch((err: unknown) => { if (!controller.signal.aborted) { setError(err instanceof Error ? err.message : 'Could not load overview.'); setLoading(false) } })
    return () => controller.abort()
  }, [retry])
  useEffect(() => {
    if (!filters) return
    const controller = new AbortController()
    fetchOverview(controller.signal, filters).then(result => {
      if (!controller.signal.aborted) { setData(result); setShownFilters(filters); setLoading(false) }
    }).catch((err: unknown) => { if (!controller.signal.aborted) { setError(err instanceof Error ? err.message : 'Could not load overview.'); setLoading(false) } })
    return () => controller.abort()
  }, [filters])
  const types = [...new Set((setup?.catalog.items ?? []).filter(item => !tag || item.tag === tag).flatMap(item => item.alarm_types))].sort()
  function apply() {
    const days = (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000 + 1
    if (!start || !end || !Number.isFinite(days) || days < 1 || days > 366) { setValidation('Choose a valid period of 1 to 366 days.'); return }
    setValidation(''); setLoading(true); setError('')
    setFilters({start_time: `${start}T00:00:00-05:00`, end_time: `${nextDay(end)}T00:00:00-05:00`, tag: tag || undefined, alarm_code: code || undefined, severity: severity || undefined})
  }
  const peak = data?.daily.reduce((best, day) => day.event_count > best.event_count ? day : best, data.daily[0])
  return <>
    <div className="page-heading"><p className="eyebrow">Water treatment and bottling</p><h1>Production line overview</h1><p className="page-description">Historical alarm activations - Bogota time (UTC-05:00)</p></div>
    {setup?.dates.first_event && setup.dates.last_event && <>
      <p className="page-description">Available records: {dateLabel(plantDate(setup.dates.first_event))} - {dateLabel(plantDate(setup.dates.last_event))}</p>
      <form className="filter-panel" onSubmit={e => {e.preventDefault(); apply()}}>
        <div className="filter-field overview-month"><label htmlFor="overview-month">Month</label><select id="overview-month" value={month} onChange={e => {setMonth(e.target.value); const range = monthRange(e.target.value); setStart(range[0]); setEnd(range[1])}}>{availableMonths(plantDate(setup.dates.first_event!), plantDate(setup.dates.last_event!)).map(value => <option key={value} value={value}>{new Intl.DateTimeFormat('en-GB', {month: 'long', year: 'numeric', timeZone: 'UTC'}).format(new Date(`${value}-01T12:00:00Z`))}</option>)}</select></div>
        <details className="overview-more"><summary>More filters</summary><div className="filter-fields">
          <div className="filter-field"><label htmlFor="overview-start">From (included)</label><input id="overview-start" type="date" value={start} onChange={e => setStart(e.target.value)} /></div>
          <div className="filter-field"><label htmlFor="overview-end">Through (included)</label><input id="overview-end" type="date" value={end} onChange={e => setEnd(e.target.value)} /></div>
          <div className="filter-field"><label htmlFor="overview-tag">Tag</label><select id="overview-tag" value={tag} onChange={e => {const value = e.target.value; setTag(value); if (value && !setup.catalog.items.find(item => item.tag === value)?.alarm_types.includes(code)) setCode('')}}><option value="">All tags</option>{setup.catalog.items.map(item => <option key={item.tag}>{item.tag}</option>)}</select></div>
          <div className="filter-field"><label htmlFor="overview-type">Alarm type</label><select id="overview-type" value={code} onChange={e => setCode(e.target.value)}><option value="">All alarm types</option>{types.map(value => <option key={value} value={value}>{value.replaceAll('_',' ')}</option>)}</select></div>
          <div className="filter-field"><label htmlFor="overview-severity">Severity</label><select id="overview-severity" value={severity} onChange={e => setSeverity(e.target.value as Severity | '')}><option value="">All severities</option>{['LOW','MEDIUM','HIGH','CRITICAL'].map(value => <option key={value}>{value}</option>)}</select></div>
        </div></details>
        <div className="filter-actions"><button type="submit" className="primary-button">Apply filters</button><button type="button" onClick={() => {setTag(''); setCode(''); setSeverity(''); const range = monthRange(month); setStart(range[0]); setEnd(range[1])}}>Reset fields</button></div>
        {validation && <p role="alert" className="error-state">{validation}</p>}
      </form>
    </>}
    {shownFilters && <p className="filter-summary">Showing {dateLabel(shownFilters.start_time!.slice(0,10))} through {dateLabel(plantDate(new Date(Date.parse(shownFilters.end_time!) - 1).toISOString()))} - {shownFilters.tag ?? 'All tags'} - {shownFilters.alarm_code?.replaceAll('_',' ') ?? 'All alarm types'} - {shownFilters.severity ?? 'All severities'}{loading && <span className="refresh-notice" role="status"> Updating results… Previous results remain visible.</span>}</p>}
    {loading && !data && <p className="panel-state" role="status">Loading overview...</p>}
    {error && <div className="panel-state error-state"><p role="alert">{error}</p><button onClick={() => {setError(''); setLoading(true); if (filters) setFilters({...filters}); else setRetry(value => value + 1)}}>Retry overview</button></div>}
    {setup && !setup.dates.first_event && <p className="panel-state">No accepted alarm events are available yet.</p>}
    {data && shownFilters && <div aria-busy={loading}>
      <div className="overview-cards">
        <article><span>Recorded events</span><strong>{data.total_events.toLocaleString('en-US')}</strong></article>
        <article className="critical-card"><span>Critical events</span><strong>{data.severity_counts.CRITICAL.toLocaleString('en-US')}</strong></article>
        <article><span>Peak day</span><strong>{peak?.event_count ? peak.event_count.toLocaleString('en-US') : 'No events'}</strong><small>{peak?.event_count ? dateLabel(peak.date) : 'Within selected filters'}</small></article>
        <article><span>Previous equal-length period</span><strong>{data.comparison.change_percent !== null ? `${Number(data.comparison.change_percent) > 0 ? '+' : ''}${data.comparison.change_percent}%` : 'Unavailable'}</strong><small>{data.comparison.event_count === null ? 'Insufficient historical dates' : `${data.comparison.event_count.toLocaleString('en-US')} previous events${data.comparison.change_percent === null ? ' - Zero baseline' : ''}`}</small></article>
      </div>
      <p className="chart-note">Previous period: {dateLabel(plantDate(data.comparison.start_time))} through {dateLabel(plantDate(new Date(Date.parse(data.comparison.end_time) - 1).toISOString()))}. Zero events do not prove uninterrupted monitoring or healthy equipment.</p>
      <div className="overview-charts">
        <EventTimeline daily={data.daily} />
        <TopTagsPanel filters={shownFilters} />
      </div>
    </div>}
  </>
}
