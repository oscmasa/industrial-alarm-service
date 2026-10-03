export function DataQualityPage() {
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">Import traceability</p>
        <h1>Data quality</h1>
        <p className="page-description">Review import outcomes and the reasons source records were rejected.</p>
      </div>
      <section className="alarm-panel" aria-labelledby="imports-title">
        <div className="panel-heading"><h2 id="imports-title">File imports</h2></div>
        <p className="panel-state">Import results and original rejected records will be connected in the data quality phase.</p>
      </section>
    </>
  )
}
