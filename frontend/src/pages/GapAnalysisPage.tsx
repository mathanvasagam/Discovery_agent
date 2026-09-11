import type { GapReport, UseCaseSummary } from '../types/api'
import { EmptyState } from '../components/EmptyState'
import { Field } from '../components/Field'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { Section } from '../components/Section'
import { StatusBadge } from '../components/StatusBadge'

export interface UseCaseFormState {
  title: string
  description: string
  business_goal: string
  target_systems: string
  frequency: string
  criticality: string
}

interface GapAnalysisPageProps {
  form: UseCaseFormState
  useCases: UseCaseSummary[]
  selectedUseCaseId: number | null
  gapReport: GapReport | null
  isBusy: boolean
  onFormChange: (field: keyof UseCaseFormState, value: string) => void
  onSubmit: () => void
  onAutoDiscover: () => void
  onSelectUseCase: (id: number | null) => void
  onGenerateMissing: (systemName: string) => void
}

export function GapAnalysisPage({ form, useCases, selectedUseCaseId, gapReport, isBusy, onFormChange, onSubmit, onAutoDiscover, onSelectUseCase, onGenerateMissing }: GapAnalysisPageProps) {
  return (
    <div className="page-stack">
      <PageHeader title="Gap Analysis" description="Map automation goals to available systems, missing dependencies, and blocked data flows." />

      <div className="two-column-layout gap-config-layout">
        <Section title="Define use case" description="Describe the automation outcome and the systems expected to participate.">
          <div className="form-grid">
            <Field label="Use-case title" required><input className="control" value={form.title} onChange={(event) => onFormChange('title', event.target.value)} /></Field>
            <Field label="Business goal" hint="State the outcome in business terms." required><textarea className="control control-textarea" value={form.business_goal} onChange={(event) => onFormChange('business_goal', event.target.value)} /></Field>
            <Field label="Description"><textarea className="control control-textarea" value={form.description} onChange={(event) => onFormChange('description', event.target.value)} /></Field>
            <Field label="Target systems" hint="Comma-separated system names." required><input className="control" value={form.target_systems} onChange={(event) => onFormChange('target_systems', event.target.value)} /></Field>
            <div className="form-grid-two">
              <Field label="Frequency"><input className="control" value={form.frequency} onChange={(event) => onFormChange('frequency', event.target.value)} /></Field>
              <Field label="Criticality"><select className="control" value={form.criticality} onChange={(event) => onFormChange('criticality', event.target.value)}><option>Low</option><option>Medium</option><option>High</option><option>Critical</option></select></Field>
            </div>
          </div>
          <div className="form-actions split-actions">
            <button className="button button-primary" onClick={onSubmit} disabled={isBusy}>Analyze defined use case</button>
            <button className="button button-secondary" onClick={onAutoDiscover} disabled={isBusy}>Discover goals from documents</button>
          </div>
        </Section>

        <Section title="Analysis context" description="Select a saved use case to inspect its current integration model.">
          <Field label="Saved use case">
            <select className="control" value={selectedUseCaseId ?? ''} onChange={(event) => onSelectUseCase(event.target.value ? Number(event.target.value) : null)}>
              <option value="">Select a use case</option>
              {useCases.map((useCase) => <option key={useCase.id} value={useCase.id}>{useCase.title}</option>)}
            </select>
          </Field>
          {gapReport ? (
            <div className="analysis-summary">
              <div className="analysis-summary-row"><span>Business impact</span><StatusBadge tone={gapReport.business_impact === 'High' || gapReport.business_impact === 'Critical' ? 'error' : 'warning'}>{gapReport.business_impact}</StatusBadge></div>
              <div className="analysis-summary-row"><span>Required systems</span><strong>{gapReport.required_systems.length}</strong></div>
              <div className="analysis-summary-row"><span>Available</span><strong>{gapReport.available_systems.length}</strong></div>
              <div className="analysis-summary-row"><span>Missing</span><strong>{gapReport.missing_systems.length}</strong></div>
              <div className="recommendation-callout"><span>Recommendation</span><p>{gapReport.strategic_recommendation}</p></div>
            </div>
          ) : (
            <EmptyState icon="gap" title="No analysis selected" description="Choose or create a use case to populate the integration model." />
          )}
        </Section>
      </div>

      {gapReport && (
        <Section title="Integration gaps" description={`Current gap model for ${gapReport.use_case_title}.`}>
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>System</th><th>Status</th><th>Priority</th><th>Estimated effort</th><th className="align-right">Action</th></tr></thead>
              <tbody>
                {gapReport.gaps.map((gap) => (
                  <tr key={gap.system_name}>
                    <td><strong>{gap.system_name}</strong><span className="cell-subtext">{gap.details}</span></td>
                    <td><StatusBadge tone={gap.status === 'missing' ? 'error' : 'success'}>{gap.status}</StatusBadge></td>
                    <td><StatusBadge tone={gap.priority === 'High' || gap.priority === 'Critical' ? 'error' : gap.priority === 'Medium' ? 'warning' : 'neutral'}>{gap.priority}</StatusBadge></td>
                    <td>{gap.effort_estimate || 'Not estimated'}</td>
                    <td className="align-right">{gap.status === 'missing' ? <button className="text-button" onClick={() => onGenerateMissing(gap.system_name)}>Generate connector <Icon name="arrow-right" size={14} /></button> : <span className="muted-dash">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {gapReport && gapReport.data_flow_analysis.length > 0 && (
        <Section title="Data flows" description="Source-to-destination paths inferred for the selected automation goal.">
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Source</th><th>Destination</th><th>Entity</th><th>Trigger</th><th>Status</th></tr></thead>
              <tbody>
                {gapReport.data_flow_analysis.map((flow, index) => (
                  <tr key={`${String(flow.source)}-${String(flow.destination)}-${index}`}>
                    <td>{String(flow.source ?? '—')}</td>
                    <td>{String(flow.destination ?? '—')}</td>
                    <td>{String(flow.entity_type ?? '—')}</td>
                    <td>{String(flow.trigger ?? '—')}</td>
                    <td><StatusBadge tone={flow.is_blocked === true ? 'error' : 'success'}>{flow.is_blocked === true ? 'Blocked' : 'Flowing'}</StatusBadge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </div>
  )
}
