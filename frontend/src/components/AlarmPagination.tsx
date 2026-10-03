import type { Pagination } from '../api/types'

export function AlarmPagination({ pagination, onPageChange }: {
  pagination: Pagination
  onPageChange: (page: number) => void
}) {
  const { page, page_size: pageSize, total, total_pages: totalPages } = pagination
  const first = total === 0 || page > totalPages ? 0 : (page - 1) * pageSize + 1
  const last = first === 0 ? 0 : Math.min(page * pageSize, total)
  return (
    <nav className="pagination" aria-label="Alarm pagination">
      <p>{first.toLocaleString('en-US')}–{last.toLocaleString('en-US')} of {total.toLocaleString('en-US')} events</p>
      <div className="pagination-controls">
        <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Previous</button>
        <span>Page {page.toLocaleString('en-US')} of {Math.max(1, totalPages).toLocaleString('en-US')}</span>
        <button type="button" disabled={page >= totalPages || page >= 100000} onClick={() => onPageChange(page + 1)}>Next</button>
      </div>
    </nav>
  )
}
