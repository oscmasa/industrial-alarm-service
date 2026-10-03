import type { AlarmList } from './types'

export class AlarmApiError extends Error {}

export async function fetchAlarms(page: number, pageSize: number, signal: AbortSignal): Promise<AlarmList> {
  const parameters = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  const response = await fetch(`/api/alarms?${parameters}`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new AlarmApiError(response.status === 503
      ? 'The alarm service is temporarily unavailable. Please try again.'
      : 'Could not load alarms. Please try again.')
  }
  return response.json() as Promise<AlarmList>
}
