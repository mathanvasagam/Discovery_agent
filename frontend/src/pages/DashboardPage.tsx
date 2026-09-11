import type { DashboardSummary, LlmStatus, RuntimeStatus } from '../types/api'
import type { PageKey } from '../app/navigation'
import { EmptyState } from '../components/EmptyState'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { Section } from '../components/Section'
import { StatusBadge } from '../components/StatusBadge'

interface DashboardPageProps {
  dashboard: DashboardSummary
  llmStatus: LlmStatus
  runtimeStatus: RuntimeStatus | null
  onNavigate: (page: PageKey) => void
  onDiscoverGoals: () => void
}

export function DashboardPage({ dashboard, llmStatus, runtimeStatus, onNavigate, onDiscoverGoals }: DashboardPageProps) {
  const metrics = [
    { label: 'Discovered systems', value: dashboard.systems, context: `${dashboard.documents} source document${dashboard.documents === 1 ? '' : 's'}` },
    { label: 'Heuristic confidence', value: `${dashboard.average_confidence}%`, context: 'Average discovery score' },
    { label: 'Open integration gaps', value: dashboard.integration_gaps, context: `${dashboard.use_cases} mapped use case${dashboard.use_cases === 1 ? '' : 's'}` },
    { label: 'Generated artifacts', value: dashboard.artifacts, context: `${dashboard.validations} validation run${dashboard.validations === 1 ? '' : 's'}` },
  ]

  return (
    <div className="page-stack">
      <PageHeader title="Dashboard" description="Enterprise system discovery, integration gaps, and generated artifacts at a glance." />

      <div className="metric-strip" aria-label="Workspace metrics">
        {metrics.map((metric) => (
          <div className="metric-item" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.context}</small>
          </div>
        ))}
      </div>

      <div className="dashboard-grid">
        <Section title="Recent systems" description="Most recently discovered systems and the evidence score attached to each record.">
          {dashboard.latest_systems.length > 0 ? (
            <div className="compact-list">
              {dashboard.latest_systems.map((system) => (
                <div className="compact-list-row" key={`${system.id ?? system.name}-${system.name}`}>
                  <div className="system-identity">
                    <div className="system-avatar">{system.name.slice(0, 2).toUpperCase()}</div>
                    <div>
                      <strong>{system.name}</strong>
                      <span>{system.category} · {system.source_reference}</span>
                    </div>
                  </div>
                  <div className="row-meta">
                    <span>{Math.round(system.confidence_score * 100)}% heuristic</span>
                    <StatusBadge tone={system.human_review_required ? 'warning' : 'success'}>
                      {system.human_review_required ? 'Review' : 'Evidence found'}
                    </StatusBadge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon="document"
              title="No systems discovered yet"
              description="Upload an operational document to build the first evidence-backed inventory record."
              action={<button className="button button-primary" onClick={() => onNavigate('upload')}>Upload document</button>}
            />
          )}
        </Section>

        <Section title="Pipeline" description="The three operational stages available in this workspace.">
          <div className="pipeline-list">
            <button className="pipeline-row" onClick={() => onNavigate('upload')}>
              <span className="pipeline-index">01</span>
              <div><strong>Discover systems</strong><span>Extract system evidence from enterprise documents.</span></div>
              <Icon name="arrow-right" size={16} />
            </button>
            <button className="pipeline-row" onClick={onDiscoverGoals}>
              <span className="pipeline-index">02</span>
              <div><strong>Analyze integration gaps</strong><span>Map automation goals to available and missing systems.</span></div>
              <Icon name="arrow-right" size={16} />
            </button>
            <button className="pipeline-row" onClick={() => onNavigate('generation')}>
              <span className="pipeline-index">03</span>
              <div><strong>Generate connectors</strong><span>Create Python or Node.js integration scaffolds and validate them.</span></div>
              <Icon name="arrow-right" size={16} />
            </button>
          </div>
        </Section>
      </div>

      <Section title="Trust & runtime" description="Security, privacy, persistence, and AI execution controls currently active for this workspace." compact>
        <div className="runtime-grid">
          <div className="runtime-item">
            <span>Persistence</span>
            <strong>{runtimeStatus?.database === 'postgresql' ? 'Managed PostgreSQL' : 'Local SQLite'}</strong>
            <small>{runtimeStatus?.privacy_mode === 'ephemeral-originals' ? 'Original uploads are removed after redacted extraction.' : 'Original upload retention is enabled.'}</small>
          </div>
          <div className="runtime-item">
            <span>Workspace boundary</span>
            <strong>{runtimeStatus?.workspace_isolation ? 'Isolated workspace' : 'Shared development workspace'}</strong>
            <small>{runtimeStatus?.rate_limits ? 'Signed workspace identity with request quotas enabled.' : 'Rate limiting is disabled for this runtime.'}</small>
          </div>
          <div className="runtime-item">
            <span>AI execution</span>
            <strong>{llmStatus.configured ? `${llmStatus.provider.toUpperCase()}${llmStatus.connected ? ' connected' : ' configured'}` : 'Deterministic fallback'}</strong>
            <small>{llmStatus.failover_order?.length ? `Failover: ${llmStatus.failover_order.join(' → ')}` : (llmStatus.model ?? 'Core discovery can operate without an external model.')}</small>
          </div>
          <div className="runtime-item">
            <span>Generated-code validation</span>
            <strong>{runtimeStatus?.validation_mode === 'static' ? 'Static-only hosted mode' : runtimeStatus?.validation_mode === 'docker' ? 'Docker-isolated runtime' : runtimeStatus?.validation_mode ?? 'Unknown mode'}</strong>
            <small>{runtimeStatus?.validation_mode === 'static' ? 'Public demo never executes generated connector code.' : 'Validation mode is controlled by the backend environment.'}</small>
          </div>
        </div>
      </Section>
    </div>
  )
}
