export function DashboardHeader() {
  return (
    <header className="dashboard-header">
      <a className="brand" href="/" aria-label="AquaLine alarm dashboard home">
        <span className="brand-mark" aria-hidden="true">A</span>
        <span>AquaLine <span className="brand-detail">/ Industrial alarms</span></span>
      </a>
      <span className="plant-label">Water treatment & bottling</span>
    </header>
  )
}
