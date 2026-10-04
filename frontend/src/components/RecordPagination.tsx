import type { Pagination } from '../api/types'

export function RecordPagination({ pagination, busy, resource, onChange }: {
  pagination: Pagination; busy: boolean; resource: string; onChange: (page: number) => void
}) {
  const { page, total, total_pages: pages, page_size: size } = pagination
  const first = !total || page > pages ? 0 : (page - 1) * size + 1
  const last = first ? Math.min(page * size, total) : 0
  return <nav className="pagination" aria-label={`${resource} pagination`}>
    <p>{first.toLocaleString('en-US')}-{last.toLocaleString('en-US')} of {total.toLocaleString('en-US')} {resource}</p>
    <div className="pagination-controls">
      <button type="button" disabled={busy || page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
      <span>Page {page.toLocaleString('en-US')} of {Math.max(1, pages).toLocaleString('en-US')}</span>
      <button type="button" disabled={busy || page >= pages || page >= 100000} onClick={() => onChange(page + 1)}>Next</button>
    </div>
  </nav>
}
