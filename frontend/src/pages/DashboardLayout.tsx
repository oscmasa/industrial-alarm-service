import { useState } from 'react'
import { DashboardHeader } from '../components/DashboardHeader'
import { DashboardNavigation } from '../components/DashboardNavigation'
import type { DashboardView } from '../components/DashboardNavigation'
import { AlarmHistoryPage } from './AlarmHistoryPage'
import { OverviewPage } from './OverviewPage'
import { DataQualityPage } from './DataQualityPage'

export function DashboardLayout() {
  const [active, setActive] = useState<DashboardView>('overview')
  const [visited, setVisited] = useState<DashboardView[]>(['overview'])

  function changeView(view: DashboardView) {
    setActive(view)
    setVisited((current) => current.includes(view) ? current : [...current, view])
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to dashboard content</a>
      <DashboardHeader />
      <DashboardNavigation active={active} onChange={changeView} />
      <main id="main-content" className="dashboard-main">
        <section id="view-overview" aria-label="Overview" hidden={active !== 'overview'}><OverviewPage /></section>
        <section id="view-alarms" aria-label="Alarm history" hidden={active !== 'alarms'}>
          {visited.includes('alarms') && <AlarmHistoryPage />}
        </section>
        <section id="view-quality" aria-label="Data quality" hidden={active !== 'quality'}>
          {visited.includes('quality') && <DataQualityPage />}
        </section>
      </main>
    </div>
  )
}
