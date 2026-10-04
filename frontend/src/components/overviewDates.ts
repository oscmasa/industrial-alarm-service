export function plantDate(timestamp: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(timestamp))
  const part = (type: string) => parts.find((item) => item.type === type)!.value
  return `${part('year')}-${part('month')}-${part('day')}`
}
export function nextDay(day: string): string {
  const date = new Date(`${day}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + 1)
  return date.toISOString().slice(0, 10)
}
export function monthRange(month: string): [string, string] {
  const date = new Date(`${month}-01T12:00:00Z`)
  date.setUTCMonth(date.getUTCMonth() + 1)
  date.setUTCDate(0)
  return [`${month}-01`, date.toISOString().slice(0, 10)]
}
export function availableMonths(first: string, last: string): string[] {
  const months: string[] = []
  const date = new Date(`${first.slice(0, 7)}-01T12:00:00Z`)
  while (date.toISOString().slice(0, 7) <= last.slice(0, 7)) {
    months.push(date.toISOString().slice(0, 7))
    date.setUTCMonth(date.getUTCMonth() + 1)
  }
  return months.reverse()
}
export function dateLabel(day: string): string {
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${day}T12:00:00Z`))
}

export function compactPeriod(start: string, exclusiveEnd: string): string {
  const first = plantDate(start)
  const last = plantDate(new Date(Date.parse(exclusiveEnd) - 1).toISOString())
  const label = (day: string, year: boolean) => new Intl.DateTimeFormat('en-GB', {
    day: 'numeric', month: 'short', ...(year ? { year: 'numeric' as const } : {}), timeZone: 'UTC',
  }).format(new Date(`${day}T12:00:00Z`))
  if (first === last) return label(last, true)
  if (first.slice(0, 7) === last.slice(0, 7)) return `${Number(first.slice(8))}-${label(last, true)}`
  return `${label(first, first.slice(0, 4) !== last.slice(0, 4))} - ${label(last, true)}`
}
