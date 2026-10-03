/** Preserve decimal precision: format the API string without converting to Number. */
export function formatMeasuredValue(value: string | null, unit: string | null): string {
  if (value === null) return 'Not available'
  const compact = value.includes('.') ? value.replace(/0+$/, '').replace(/\.$/, '') : value
  if (!unit) return `${compact} (unit not specified)`
  if (unit === 'boolean') {
    if (compact === '1') return '1 — Active'
    if (compact === '0') return '0 — Inactive'
    return `${compact} (binary signal)`
  }
  return `${compact} ${unit === 'degC' ? '°C' : unit}`
}
