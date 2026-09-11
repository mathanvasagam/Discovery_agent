import type { InventoryResponse } from '../types/api'
import { EmptyState } from '../components/EmptyState'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { Section } from '../components/Section'
import { StatusBadge } from '../components/StatusBadge'

interface InventoryPageProps {
  inventory: InventoryResponse
  search: string
  categoryFilter: string
  categories: string[]
  jsonExportUrl: string
  csvExportUrl: string
  onSearch: (value: string) => void
  onCategoryChange: (value: string) => void
  onClear: () => void
}

export function InventoryPage({ inventory, search, categoryFilter, categories, jsonExportUrl, csvExportUrl, onSearch, onCategoryChange, onClear }: InventoryPageProps) {
  return (
    <div className="page-stack">
      <PageHeader
        title="System Inventory"
        description="Review the evidence-backed system estate discovered from uploaded documents."
        actions={
          <div className="button-group">
            <a className="button button-secondary" href={jsonExportUrl}><Icon name="download" size={15} />JSON</a>
            <a className="button button-secondary" href={csvExportUrl}><Icon name="download" size={15} />CSV</a>
          </div>
        }
      />

      <Section compact>
        <div className="table-toolbar">
          <div className="toolbar-filters">
            <label className="search-control">
              <Icon name="search" size={15} />
              <input aria-label="Search system inventory" placeholder="Search by system..." value={search} onChange={(event) => onSearch(event.target.value)} />
            </label>
            <select aria-label="Filter by category" className="compact-select" value={categoryFilter} onChange={(event) => onCategoryChange(event.target.value)}>
              <option value="">All categories</option>
              {categories.map((category) => <option key={category} value={category}>{category}</option>)}
            </select>
          </div>
          <div className="toolbar-meta">
            <span>{inventory.total} system{inventory.total === 1 ? '' : 's'}</span>
            <button className="button button-destructive-ghost" onClick={onClear}><Icon name="trash" size={15} />Clear inventory</button>
          </div>
        </div>

        {inventory.items.length > 0 ? (
          <div className="table-scroll table-scroll-flush">
            <table className="data-table inventory-table">
              <thead><tr><th>System</th><th>Category</th><th>Heuristic confidence</th><th>Review state</th><th>Evidence</th></tr></thead>
              <tbody>
                {inventory.items.map((system) => (
                  <tr key={`${system.id ?? system.name}-${system.name}`}>
                    <td>
                      <div className="system-cell"><strong>{system.name}</strong><span>{system.auth_method} · {system.criticality} criticality</span></div>
                    </td>
                    <td>{system.category}</td>
                    <td><span className="confidence-value">{Math.round(system.confidence_score * 100)}%</span><span className="cell-subtext">heuristic score</span></td>
                    <td>
                      <StatusBadge tone={system.human_review_required ? 'warning' : 'success'}>
                        {system.human_review_required ? 'Needs review' : 'Evidence found'}
                      </StatusBadge>
                    </td>
                    <td className="evidence-cell">
                      <span title={system.evidence}>{system.evidence}</span>
                      <small>{system.source_reference}{system.page_number ? ` · page ${system.page_number}` : ''}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="inventory" title="No systems match this view" description="Upload a document or clear the current search and category filters." />
        )}
      </Section>
    </div>
  )
}
