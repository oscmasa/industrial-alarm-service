import type { AlarmQueryFilters, Severity } from '../api/types'

export interface FilterFields {
  startTime: string
  endTime: string
  severity: Severity | ''
  tag: string
}

export const EMPTY_FILTERS: FilterFields = {
  startTime: '', endTime: '', severity: '', tag: '',
}

export type FilterErrors = Partial<Record<keyof FilterFields, string>>

type FilterResult =
  | { valid: true; filters: AlarmQueryFilters }
  | { valid: false; errors: FilterErrors }

function plantTimeToUtc(value: string): string | null {
  // The exercise uses the plant's UTC-05 clock, never the browser's timezone.
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(value)) return null
  if (value.startsWith('0000-')) return null
  const full = value.length === 16 ? `${value}:00` : value
  const calendarDate = new Date(`${full}Z`)
  if (!Number.isFinite(calendarDate.getTime()) || calendarDate.toISOString().slice(0, 19) !== full) return null
  const instant = new Date(`${full}-05:00`)
  if (!Number.isFinite(instant.getTime())) return null
  const utc = instant.toISOString()
  return /^\d{4}-/.test(utc) ? utc : null
}

export function validateFilters(fields: FilterFields): FilterResult {
  const errors: FilterErrors = {}
  const filters: AlarmQueryFilters = {}
  for (const [field, parameter] of [['startTime', 'start_time'], ['endTime', 'end_time']] as const) {
    if (fields[field]) {
      const instant = plantTimeToUtc(fields[field])
      if (instant === null) errors[field] = 'Enter a valid date and time.'
      else filters[parameter] = instant
    }
  }
  if (filters.start_time && filters.end_time && Date.parse(filters.start_time) >= Date.parse(filters.end_time)) {
    errors.endTime = 'End time must be later than start time.'
  }
  if (fields.severity) {
    if (['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].includes(fields.severity)) filters.severity = fields.severity
    else errors.severity = 'Choose a supported severity.'
  }
  const tag = fields.tag.trim().toUpperCase()
  if (tag) {
    if (tag.length > 64 || !/^[A-Z][A-Z0-9_]*$/.test(tag)) {
      errors.tag = 'Use a tag starting with a letter, followed by letters, digits or underscores (maximum 64 characters).'
    } else filters.tag = tag
  }
  return Object.keys(errors).length > 0 ? { valid: false, errors } : { valid: true, filters }
}
