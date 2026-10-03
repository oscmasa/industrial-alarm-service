import type { AlarmList, AlarmQueryFilters } from './types'

export class AlarmApiError extends Error {}

export async function fetchAlarms(page: number, pageSize: number, signal: AbortSignal, filters: AlarmQueryFilters = {}): Promise<AlarmList> {
  const parameters = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  for (const [name, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') parameters.set(name, value)
  }
  const response = await fetch(`/api/alarms?${parameters}`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new AlarmApiError(response.status === 503
      ? 'The alarm service is temporarily unavailable. Please try again.'
      : response.status === 422
        ? 'The service could not accept these filters. Review their values and try again.'
        : 'Could not load alarms. Please try again.')
  }
  return response.json() as Promise<AlarmList>
}
