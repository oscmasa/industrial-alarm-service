import type { AlarmList, AlarmQueryFilters, TopTagFilters, TopTags } from './types'

export class AlarmApiError extends Error {}

async function requestJson<T>(path: string, parameters: URLSearchParams, signal: AbortSignal, resource: string): Promise<T> {
  const response = await fetch(`${path}?${parameters}`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new AlarmApiError(response.status === 503
      ? 'The alarm service is temporarily unavailable. Please try again.'
      : response.status === 422
        ? 'The service could not accept these filters. Review their values and try again.'
        : `Could not load ${resource}. Please try again.`)
  }
  return response.json() as Promise<T>
}

export function fetchAlarms(page: number, pageSize: number, signal: AbortSignal, filters: AlarmQueryFilters = {}): Promise<AlarmList> {
  const parameters = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  for (const [name, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') parameters.set(name, value)
  }
  return requestJson('/api/alarms', parameters, signal, 'alarms')
}

export function fetchTopTags(signal: AbortSignal, filters: TopTagFilters = {}): Promise<TopTags> {
  const parameters = new URLSearchParams({ limit: '5' })
  for (const name of ['start_time', 'end_time', 'severity'] as const) {
    const value = filters[name]
    if (value) parameters.set(name, value)
  }
  return requestJson('/api/metrics/top-tags', parameters, signal, 'top-tag metrics')
}
