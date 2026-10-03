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

export type TopTagFilters = Pick<AlarmQueryFilters, 'start_time' | 'end_time' | 'severity'>

export interface TagCount {
  tag: string
  event_count: number
}

export interface TopTags {
  items: TagCount[]
  limit: number
}
