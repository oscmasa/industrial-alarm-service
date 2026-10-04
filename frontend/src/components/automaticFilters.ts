import type { TopTagFilters, Severity } from '../api/types'

export function createDebouncer(delay = 400) {
  let timer: ReturnType<typeof setTimeout> | undefined
  const cancel = () => { clearTimeout(timer); timer = undefined }
  return {
    cancel,
    schedule(action: () => void) {
      cancel()
      timer = setTimeout(() => { timer = undefined; action() }, delay)
    },
  }
}

export function overviewFilters(start: string, end: string, tag: string, code: string, severity: Severity | ''): TopTagFilters | null {
  for (const day of [start, end]) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null
    const date = new Date(`${day}T00:00:00Z`)
    const year = Number(day.slice(0, 4))
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== day || year < 1901 || year > 9998) return null
  }
  const days = (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000 + 1
  if (days < 1 || days > 366) return null
  const exclusiveEnd = new Date(Date.parse(`${end}T00:00:00Z`) + 86400000).toISOString().slice(0, 10)
  return { start_time: `${start}T00:00:00-05:00`, end_time: `${exclusiveEnd}T00:00:00-05:00`, tag: tag || undefined, alarm_code: code || undefined, severity: severity || undefined }
}
