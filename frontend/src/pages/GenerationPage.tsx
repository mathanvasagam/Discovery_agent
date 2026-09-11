import type { GeneratedPackage } from '../types/api'
import { EmptyState } from '../components/EmptyState'
import { Field } from '../components/Field'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { Section } from '../components/Section'
import { StatusBadge } from '../components/StatusBadge'

export interface GeneratorFormState {
  system_name: string
  category: string
  auth_method: string
  use_case_title: string
  language: string
}

type ArtifactTab = 'code' | 'tests' | 'readme'

interface GenerationPageProps {
  form: GeneratorFormState
  generatedPackage: GeneratedPackage | null
  activeTab: ArtifactTab
  isBusy: boolean
  onFormChange: (field: keyof GeneratorFormState, value: string) => void
  onGenerate: () => void
  onTabChange: (tab: ArtifactTab) => void
}

export function GenerationPage({ form, generatedPackage, activeTab, isBusy, onFormChange, onGenerate, onTabChange }: GenerationPageProps) {
  const validation = generatedPackage?.validation

  return (
    <div className="page-stack">
      <PageHeader title="Code Generation" description="Generate integration scaffolds and inspect their isolated validation outcome." />

      <div className="generation-layout">
        <Section title="Connector configuration" description="Define the integration target and generation language.">
          <div className="form-grid">
            <Field label="System name" required><input className="control" value={form.system_name} onChange={(event) => onFormChange('system_name', event.target.value)} /></Field>
            <Field label="Use-case context"><input className="control" value={form.use_case_title} onChange={(event) => onFormChange('use_case_title', event.target.value)} /></Field>
            <div className="form-grid-two">
              <Field label="Category"><input className="control" value={form.category} onChange={(event) => onFormChange('category', event.target.value)} /></Field>
              <Field label="Authentication"><input className="control" value={form.auth_method} onChange={(event) => onFormChange('auth_method', event.target.value)} /></Field>
            </div>
            <Field label="Language"><select className="control" value={form.language} onChange={(event) => onFormChange('language', event.target.value)}><option value="python">Python</option><option value="nodejs">Node.js</option></select></Field>
          </div>
          <div className="form-actions form-actions-right"><button className="button button-primary" onClick={onGenerate} disabled={isBusy}><Icon name="code" size={15} />Generate + Validate</button></div>
        </Section>

        <Section title="Validation" description="Result returned by the configured generated-code validation mode.">
          {validation ? (
            <div className="validation-summary">
              <div className="validation-primary"><StatusBadge tone={validation.status === 'pass' ? 'success' : 'error'}>{validation.status.toUpperCase()}</StatusBadge><strong>{validation.output}</strong></div>
              <div className="validation-metrics">
                <div><span>Warnings</span><strong>{validation.warnings.length}</strong></div>
                <div><span>Errors</span><strong>{validation.errors.length}</strong></div>
                <div><span>Commands</span><strong>{validation.logs.length}</strong></div>
              </div>
              {validation.errors.length > 0 && <div className="validation-errors">{validation.errors.map((error) => <p key={error}>{error}</p>)}</div>}
            </div>
          ) : (
            <EmptyState icon="activity" title="No validation result" description="Generate a connector to run the configured syntax, test, and sandbox checks." />
          )}
        </Section>
      </div>

      <Section title="Artifact workspace" description={generatedPackage ? generatedPackage.connector.filename : 'Generated code, tests, and README appear here.'}>
        {generatedPackage ? (
          <div className="artifact-workspace">
            <div className="artifact-toolbar">
              <div className="artifact-tabs" role="tablist" aria-label="Generated artifact files">
                {(['code', 'tests', 'readme'] as const).map((tab) => (
                  <button key={tab} role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? 'is-active' : ''} onClick={() => onTabChange(tab)}>{tab}</button>
                ))}
              </div>
              <div className="artifact-meta"><span>{generatedPackage.connector.language}</span><span>{generatedPackage.connector.dependencies.length} dependencies</span></div>
            </div>
            <pre className="code-viewer"><code>{activeTab === 'code' ? generatedPackage.connector.code : activeTab === 'tests' ? generatedPackage.connector.tests : generatedPackage.connector.readme}</code></pre>
            <div className="artifact-footer"><span>Dependencies</span><code>{generatedPackage.connector.dependencies.join(', ') || 'None declared'}</code></div>
          </div>
        ) : (
          <EmptyState icon="code" title="No generated artifact" description="Select a missing integration from Gap Analysis or configure a connector above." />
        )}
      </Section>
    </div>
  )
}
