import type { ReportsPayload } from '../types/api'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { Section } from '../components/Section'
import { StatusBadge } from '../components/StatusBadge'

interface ReportsPageProps {
  reports: ReportsPayload
}

export function ReportsPage({ reports }: ReportsPageProps) {
  return (
    <div className="page-stack">
      <PageHeader title="Reports" description="Inspect validation history and operational output produced by the workspace." />

      <div className="report-summary">
        <div><span>Documents</span><strong>{reports.documents.length}</strong></div>
        <div><span>Inventory records</span><strong>{reports.inventory.total}</strong></div>
        <div><span>Use cases</span><strong>{reports.use_cases.length}</strong></div>
        <div><span>Artifacts</span><strong>{reports.artifacts.length}</strong></div>
      </div>

      <Section title="Validation history" description="Only values returned by the backend are displayed; no synthetic timestamps are added.">
        {reports.validations.length > 0 ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Resource</th><th>Status</th><th>Output</th><th className="align-right">Warnings</th><th className="align-right">Errors</th></tr></thead>
              <tbody>
                {reports.validations.map((validation, index) => (
                  <tr key={`${validation.filename ?? 'validation'}-${index}`}>
                    <td><strong>{validation.filename ?? 'Inline artifact'}</strong></td>
                    <td><StatusBadge tone={validation.status === 'pass' ? 'success' : 'error'}>{validation.status}</StatusBadge></td>
                    <td>{validation.output || '—'}</td>
                    <td className="align-right mono-cell">{validation.warnings.length}</td>
                    <td className="align-right mono-cell">{validation.errors.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="reports" title="No validation history" description="Validation runs will appear here after connector generation or manual validation." />
        )}
      </Section>
    </div>
  )
}
