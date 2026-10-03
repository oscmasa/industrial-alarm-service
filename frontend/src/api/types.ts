export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface Alarm {
  id: number
  event_id: string
  source_system: string
  import_id: string
  occurred_at: string
  tag: string
  alarm_code: string
  severity: Severity
  message: string | null
  value: string | null
  unit: string | null
  warnings: string[]
}

export interface Pagination {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface AlarmList {
  items: Alarm[]
  pagination: Pagination
}

export interface AlarmQueryFilters {
  start_time?: string
  end_time?: string
  severity?: Severity
  tag?: string
}

export type TopTagFilters = AlarmQueryFilters & { alarm_code?: string }

export interface TagCount {
  tag: string
  event_count: number
}

export interface TopTags {
  items: TagCount[]
  limit: number
}

export interface AvailableDates { timezone: string; first_event: string | null; last_event: string | null }
export interface SignalCatalog { items: { tag: string; equipment_name: string; unit: string; alarm_types: string[] }[] }
export interface Overview {
  total_events: number
  severity_counts: Record<Severity, number>
  daily: { date: string; event_count: number; moving_average_7_days: string | null }[]
  comparison: { start_time: string; end_time: string; event_count: number | null; change_percent: string | null; unavailable_reason: string | null }
}
