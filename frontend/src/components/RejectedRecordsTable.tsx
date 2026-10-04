import type { RejectedRecord } from '../api/types'

export function RejectedRecordsTable({ records }: { records: RejectedRecord[] }) {
  return <div className="table-scroll" tabIndex={0} role="region" aria-label="Rejected records table">
    <table><caption className="visually-hidden">Rejected source records and all their validation issues.</caption>
      <thead><tr><th scope="col">Record</th><th scope="col">Field / reason</th><th scope="col">Details</th></tr></thead>
      <tbody>{records.map(record => <tr key={record.id}>
        <td className="quality-record-number">{record.record_number.toLocaleString('en-US')}</td>
        <td><ul className="quality-issues">{record.errors.map((issue, index) => <li key={index}>
          <strong>{issue.field}</strong><span className="quality-issue-code">{issue.code}</span><p>{issue.message}</p>
        </li>)}</ul></td>
        <td><details className="original-record"><summary>View original record</summary><pre>{JSON.stringify(record.original_data, null, 2)}</pre></details></td>
      </tr>)}</tbody>
    </table>
  </div>
}
