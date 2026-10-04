import type { Overview, TopTagFilters } from '../api/types'
import { compactPeriod, plantDate } from './overviewDates'

export function PeriodComparison({ data, filters }: { data: Overview; filters: TopTagFilters }) {
  const previous = data.comparison
  const first = plantDate(filters.start_time!)
  const end = plantDate(filters.end_time!)
  const days = Math.round((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${first}T00:00:00Z`)) / 86400000)
  const change = previous.change_percent === null ? null : Number(previous.change_percent)
  const direction = change === null ? '' : change > 0 ? 'more events' : change < 0 ? 'fewer events' : 'no change'
  return <article className="period-comparison">
    <span>Events vs. preceding {days} {days === 1 ? 'day' : 'days'}</span>
    <div className="comparison-delta"><strong>{change === null ? 'Unavailable' : `${change > 0 ? '+' : ''}${previous.change_percent}%`}</strong><small>{direction}</small></div>
    <div className="comparison-row"><span>Selected: {compactPeriod(filters.start_time!, filters.end_time!)}</span><b>{data.total_events.toLocaleString('en-US')} events</b></div>
    <div className="comparison-row"><span>Previous: {compactPeriod(previous.start_time, previous.end_time)}</span><b>{previous.event_count === null ? 'No history' : `${previous.event_count.toLocaleString('en-US')} events`}</b></div>
    {change === null && <small>{previous.event_count === null ? 'Insufficient historical dates' : 'Percentage unavailable: zero baseline'}</small>}
  </article>
}
