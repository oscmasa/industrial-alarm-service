export function normalizeIssueCode(value: string): string | null {
  const code = value.trim().toUpperCase()
  return !code || /^[A-Z][A-Z0-9_]{0,63}$/.test(code) ? code : null
}
export function auditTime(timestamp: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'America/Bogota', day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).format(new Date(timestamp))
}
