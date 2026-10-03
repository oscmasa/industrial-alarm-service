import { TopTagsPanel } from '../components/TopTagsPanel'

export function OverviewPage() {
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">Water treatment and bottling</p>
        <h1>Production line overview</h1>
        <p className="page-description">Explore the distribution of recorded alarm events.</p>
      </div>
      <TopTagsPanel filters={{}} />
      <section className="alarm-panel" aria-labelledby="timeline-title">
        <div className="panel-heading"><h2 id="timeline-title">Events over time</h2></div>
        <p className="panel-state">Daily totals, available dates and period comparisons will be connected in the analytics phase.</p>
      </section>
    </>
  )
}
