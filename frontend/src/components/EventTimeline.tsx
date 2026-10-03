import { useState } from 'react'
import type { Overview } from '../api/types'
import { dateLabel } from './overviewDates'

export function EventTimeline({ daily }: { daily: Overview['daily'] }) {
  const [showAverage, setShowAverage] = useState(true)
  const maximum = Math.max(1, ...daily.map(d => Math.max(d.event_count, Number(d.moving_average_7_days ?? 0))))
  const step = 720 / daily.length
  const y = (value: number) => 230 - value / maximum * 190
  const paths: string[] = []
  let connected = false
  daily.forEach((day, index) => {
    if (day.moving_average_7_days === null) { connected = false; return }
    paths.push(`${connected ? 'L' : 'M'}${60 + step * (index + .5)},${y(Number(day.moving_average_7_days))}`)
    connected = true
  })
  return <section className="alarm-panel">
    <div className="panel-heading"><h2>Events over time</h2><label><input type="checkbox" checked={showAverage} onChange={e => setShowAverage(e.target.checked)} /> 7-day average</label></div>
    <p className="metrics-context">Daily events · The line averages the current day and six preceding days. It starts only where historical dates support it.</p>
    <svg className="event-timeline" viewBox="0 0 820 280" role="img" aria-label="Daily event counts and seven-day moving average">
      {[0, .5, 1].map(fraction => <g key={fraction}><line x1="60" x2="780" y1={y(maximum * fraction)} y2={y(maximum * fraction)} stroke="#c5d9ed" /><text x="50" y={y(maximum * fraction) + 4} textAnchor="end">{Math.round(maximum * fraction)}</text></g>)}
      {daily.map((day, index) => <rect key={day.date} x={60 + step * index + step * .15} y={y(day.event_count)} width={step * .7} height={230 - y(day.event_count)} fill="#8bb7e3"><title>{dateLabel(day.date)}: {day.event_count} events</title></rect>)}
      {showAverage && <path d={paths.join(' ')} fill="none" stroke="#174f87" strokeWidth="2.5" />}
      {[0, Math.floor((daily.length - 1) / 2), daily.length - 1].filter((v,i,a) => a.indexOf(v) === i).map(index => <text key={index} x={60 + step * (index + .5)} y="258" textAnchor="middle">{daily[index].date.slice(5)}</text>)}
    </svg>
    <details className="timeline-data"><summary>View daily counts</summary><div className="table-scroll"><table><thead><tr><th>Date</th><th>Events</th><th>7-day average</th></tr></thead><tbody>{daily.map(day => <tr key={day.date}><td>{dateLabel(day.date)}</td><td>{day.event_count}</td><td>{day.moving_average_7_days ?? 'Insufficient historical dates'}</td></tr>)}</tbody></table></div></details>
  </section>
}
