import { useState } from 'react'
import type { FormEvent } from 'react'
import type { AlarmQueryFilters, Severity } from '../api/types'
import { EMPTY_FILTERS, validateFilters } from './filterValidation'
import type { FilterErrors, FilterFields } from './filterValidation'

const plantFormatter = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'America/Bogota', dateStyle: 'medium', timeStyle: 'short', hourCycle: 'h23',
})

export function AlarmFilters({ appliedFilters, onApply }: {
  appliedFilters: AlarmQueryFilters
  onApply: (filters: AlarmQueryFilters) => void
}) {
  const [fields, setFields] = useState<FilterFields>(EMPTY_FILTERS)
  const [errors, setErrors] = useState<FilterErrors>({})

  function updateField<K extends keyof FilterFields>(field: K, value: FilterFields[K]) {
    setFields((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: undefined }))
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const result = validateFilters(fields)
    if (!result.valid) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setFields((current) => ({ ...current, tag: result.filters.tag ?? '' }))
    onApply(result.filters)
  }

  function clear() {
    setFields(EMPTY_FILTERS)
    setErrors({})
    onApply({})
  }

  const summary = [
    appliedFilters.start_time ? `From ${plantFormatter.format(new Date(appliedFilters.start_time))}` : '',
    appliedFilters.end_time ? `Before ${plantFormatter.format(new Date(appliedFilters.end_time))}` : '',
    appliedFilters.severity ? `Severity ${appliedFilters.severity}` : '',
    appliedFilters.tag ? `Tag ${appliedFilters.tag}` : '',
  ].filter(Boolean).join(' · ')

  return (
    <section className="filter-panel" aria-labelledby="filters-title">
      <details className="filter-disclosure">
      <summary id="filters-title">Filters <span className="filter-count">{Object.keys(appliedFilters).length > 0 ? `${Object.keys(appliedFilters).length} applied` : 'Optional'}</span></summary>
      <p id="time-help" className="filter-help">Use Bogotá time (UTC−05:00). Results include the start time and exclude the end time.</p>
      <form onSubmit={apply}>
        <div className="filter-fields">
          <div className="filter-field">
            <label htmlFor="start-time">Start date and time</label>
            <input id="start-time" type="datetime-local" step="1" value={fields.startTime}
              onChange={(event) => updateField('startTime', event.target.value)}
              aria-invalid={Boolean(errors.startTime)} aria-describedby="time-help start-error" />
            <span id="start-error" className="field-error">{errors.startTime}</span>
          </div>
          <div className="filter-field">
            <label htmlFor="end-time">End date and time</label>
            <input id="end-time" type="datetime-local" step="1" value={fields.endTime}
              onChange={(event) => updateField('endTime', event.target.value)}
              aria-invalid={Boolean(errors.endTime)} aria-describedby="time-help end-error" />
            <span id="end-error" className="field-error">{errors.endTime}</span>
          </div>
          <div className="filter-field">
            <label htmlFor="severity">Severity</label>
            <select id="severity" value={fields.severity}
              onChange={(event) => updateField('severity', event.target.value as Severity | '')}
              aria-invalid={Boolean(errors.severity)} aria-describedby="severity-error">
              <option value="">All severities</option>
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
              <option value="CRITICAL">Critical</option>
            </select>
            <span id="severity-error" className="field-error">{errors.severity}</span>
          </div>
          <div className="filter-field">
            <label htmlFor="tag">Tag</label>
            <input id="tag" type="text" value={fields.tag} placeholder="e.g. PUMP_01_FLOW"
              onChange={(event) => updateField('tag', event.target.value)}
              aria-invalid={Boolean(errors.tag)} aria-describedby="tag-error" />
            <span id="tag-error" className="field-error">{errors.tag}</span>
          </div>
        </div>
        <div className="filter-actions">
          <button type="submit" className="primary-button">Apply filters</button>
          <button type="button" onClick={clear}>Clear filters</button>
          <span>Edit fields, then apply to update results.</span>
        </div>
        {Object.values(errors).some(Boolean) && <p className="field-error" role="alert">Review the highlighted filters before applying.</p>}
      </form>
      </details>
      <p className="filter-summary" role="status">{summary ? `Applied: ${summary}` : 'All recorded alarms · No filters applied'}</p>
    </section>
  )
}
