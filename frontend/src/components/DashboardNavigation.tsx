export type DashboardView = 'overview' | 'alarms' | 'quality'

const views: { id: DashboardView; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'alarms', label: 'Alarm history' },
  { id: 'quality', label: 'Data quality' },
]

export function DashboardNavigation({ active, onChange }: {
  active: DashboardView
  onChange: (view: DashboardView) => void
}) {
  return (
    <nav className="dashboard-navigation" aria-label="Dashboard views">
      {views.map(({ id, label }) => (
        <button key={id} type="button" aria-pressed={active === id}
          aria-controls={`view-${id}`} onClick={() => onChange(id)}>{label}</button>
      ))}
    </nav>
  )
}
