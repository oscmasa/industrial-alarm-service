import type { Alarm, Severity } from '../api/types'
import { formatMeasuredValue } from './measuredValue'

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'America/Bogota',
  year: 'numeric', month: 'short', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
})

const severityLabels: Record<Severity, string> = {
  LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical',
}

const warningLabels: Record<string, string> = {
  VALUE_TRIGGER_MISMATCH: 'Captured value differs from the alarm trigger',
  SEVERITY_DIFFERS_FROM_DEFAULT: 'Historical severity differs from the catalog default',
}

export function AlarmTable({ alarms }: { alarms: Alarm[] }) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Alarm history table">
      <table>
        <caption className="visually-hidden">
          Alarm activations, newest first. Dates use America/Bogota (UTC-05).
        </caption>
        <thead>
          <tr>
            <th scope="col">Occurred at <span className="column-note">UTC-05</span></th>
            <th scope="col">Tag / event</th>
            <th scope="col">Condition</th>
            <th scope="col">Severity</th>
            <th scope="col">Message</th>
            <th scope="col">Measured value</th>
            <th scope="col">Warnings</th>
          </tr>
        </thead>
        <tbody>
          {alarms.map((alarm) => (
            <tr key={alarm.id}>
              <td className="date-cell">
                <time dateTime={alarm.occurred_at} title={`UTC: ${alarm.occurred_at}`}>
                  {dateFormatter.format(new Date(alarm.occurred_at))}
                </time>
              </td>
              <td><span className="tag-name">{alarm.tag}</span><span className="event-id">{alarm.event_id}</span></td>
              <td>{alarm.alarm_code.replaceAll('_', ' ')}</td>
              <td><span className={`severity severity-${alarm.severity.toLowerCase()}`}>{severityLabels[alarm.severity]}</span></td>
              <td className="message-cell">{alarm.message ?? <span className="muted">Not recorded</span>}</td>
              <td className="value-cell">
                {alarm.value === null ? <span className="muted">Not available</span>
                  : formatMeasuredValue(alarm.value, alarm.unit)}
              </td>
              <td>{alarm.warnings.length > 0 ? (
                <details className="warning-details">
                  <summary>{alarm.warnings.length} warning{alarm.warnings.length === 1 ? '' : 's'}</summary>
                  <ul>{alarm.warnings.map((warning) => <li key={warning}>{warningLabels[warning] ?? warning}</li>)}</ul>
                </details>
              ) : <span className="muted">None</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
