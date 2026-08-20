import { useCallback, useDeferredValue, useEffect, useState } from 'react'
import { api } from './services/api'
import type {
  DashboardSummary,
  GapReport,
  GeneratedPackage,
  InventoryResponse,
  ReportsPayload,
  UseCaseSummary,
} from './types/api'

type PageKey = 'dashboard' | 'upload' | 'inventory' | 'gaps' | 'generation' | 'reports'

interface ActivityStep {
  id: string
  label: string
  status: 'pending' | 'active' | 'done' | 'error'
}

const INITIAL_STEPS: ActivityStep[] = [
  { id: 'ingest', label: 'Reading document', status: 'pending' },
  { id: 'text', label: 'Extracting text', status: 'pending' },
  { id: 'discovery', label: 'Discovering systems', status: 'pending' },
  { id: 'profile', label: 'Extracting profiles', status: 'pending' },
  { id: 'confidence', label: 'Calculating confidence', status: 'pending' },
  { id: 'inventory', label: 'Building inventory', status: 'pending' },
]

const GAP_STEPS: ActivityStep[] = [
  { id: 'mapping', label: 'Mapping automation goals', status: 'pending' },
  { id: 'dataflow', label: 'Tracing data flows', status: 'pending' },
  { id: 'gaps', label: 'Finding integration gaps', status: 'pending' },
  { id: 'recommend', label: 'Generating strategic recommendation', status: 'pending' },
  { id: 'priority', label: 'Prioritizing integrations', status: 'pending' },
]

const GEN_STEPS: ActivityStep[] = [
  { id: 'codegen', label: 'Generating connector code', status: 'pending' },
  { id: 'agentgen', label: 'Generating agent definition', status: 'pending' },
  { id: 'validate', label: 'Validating production-readiness', status: 'pending' },
]

const ARTIFACT_TABS = ['code', 'tests', 'readme'] as const

const PAGES: Array<{ key: PageKey; label: string; description: string }> = [
  { key: 'dashboard', label: 'Dashboard', description: 'Overview of system discovery and health.' },
  { key: 'upload', label: 'Upload', description: 'Ingest documents for system extraction.' },
  { key: 'inventory', label: 'System Inventory', description: 'View and export discovered systems.' },
  { key: 'gaps', label: 'Gap Analysis', description: 'Map automation goals to your system estate.' },
  { key: 'generation', label: 'Code Generation', description: 'Generate and validate integration code.' },
  { key: 'reports', label: 'Reports', description: 'Review logs and final outcomes.' },
]

const EMPTY_DASHBOARD: DashboardSummary = {
  documents: 0,
  systems: 0,
  use_cases: 0,
  artifacts: 0,
  validations: 0,
  latest_systems: [],
  integration_gaps: 0,
  average_confidence: 0,
}

const EMPTY_INVENTORY: InventoryResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 10,
}

const EMPTY_REPORTS: ReportsPayload = {
  documents: [],
  inventory: EMPTY_INVENTORY,
  use_cases: [],
  artifacts: [],
  validations: [],
}

function App() {
  const [activePage, setActivePage] = useState<PageKey>('dashboard')
  const [activeTab, setActiveTab] = useState<'code' | 'tests' | 'readme'>('code')
  const [dashboard, setDashboard] = useState<DashboardSummary>(EMPTY_DASHBOARD)
  const [inventory, setInventory] = useState<InventoryResponse>(EMPTY_INVENTORY)
  const [reports, setReports] = useState<ReportsPayload>(EMPTY_REPORTS)
  const [useCases, setUseCases] = useState<UseCaseSummary[]>([])
  const [selectedUseCaseId, setSelectedUseCaseId] = useState<number | null>(null)
  const [gapReport, setGapReport] = useState<GapReport | null>(null)
  const [generatedPackage, setGeneratedPackage] = useState<GeneratedPackage | null>(null)
  const [statusMessage, setStatusMessage] = useState('')
  const [apiError, setApiError] = useState('')
  const [isBusy, setIsBusy] = useState(false)
  const [activitySteps, setActivitySteps] = useState<ActivityStep[]>([])

  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [categoryFilter, setCategoryFilter] = useState('')

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [useCaseForm, setUseCaseForm] = useState({
    title: 'Invoice Automation',
    description: 'Automatically create invoices from Salesforce opportunities.',
    business_goal: 'Automatically create invoices from Salesforce opportunities.',
    target_systems: 'Salesforce, NetSuite, Stripe',
    frequency: 'Daily',
    criticality: 'High',
  })
  const [generatorForm, setGeneratorForm] = useState({
    system_name: 'Salesforce',
    category: 'CRM',
    auth_method: 'OAuth2',
    use_case_title: 'Invoice Automation',
    language: 'python',
  })

  const categories = Array.from(new Set(inventory.items.map((item) => item.category))).sort()

  const refreshDashboard = useCallback(async () => {
    try {
      const [dashboardData, reportsData, useCaseData] = await Promise.all([
        api.getDashboard(),
        api.getReports(),
        api.getUseCases(),
      ])
      setDashboard(dashboardData)
      setReports(reportsData)
      setUseCases(useCaseData)
      setSelectedUseCaseId((current) => current ?? (useCaseData.length > 0 ? useCaseData[0].id : null))
    } catch (error) {
      console.error(error)
    }
  }, [])

  const refreshInventory = useCallback(async () => {
    try {
      const response = await api.getInventory({
        search: deferredSearch,
        category: categoryFilter,
      })
      setInventory(response)
    } catch (error) {
      console.error(error)
    }
  }, [categoryFilter, deferredSearch])

  useEffect(() => {
    const loadDashboard = async () => {
      setIsBusy(true)
      setApiError('')
      try {
        await refreshDashboard()
      } catch (error) {
        setApiError(error instanceof Error ? error.message : 'Unable to reach backend API.')
      } finally {
        setIsBusy(false)
      }
    }
    void loadDashboard()
  }, [refreshDashboard])

  useEffect(() => {
    void refreshInventory().catch((error) => {
      setApiError(error instanceof Error ? error.message : 'Unable to refresh inventory.')
    })
  }, [refreshInventory])

  useEffect(() => {
    if (!selectedUseCaseId) {
      setGapReport(null)
      return
    }
    api.getGapReport(selectedUseCaseId)
      .then(setGapReport)
      .catch((error) => {
        setApiError(error instanceof Error ? error.message : 'Unable to load gap report.')
      })
  }, [selectedUseCaseId])

  function startActivity(steps: ActivityStep[]) {
    setActivitySteps(steps.map((step) => ({ ...step, status: 'active' })))
  }

  function completeActivity() {
    setActivitySteps((steps) => steps.map((step) => ({ ...step, status: 'done' })))
  }

  async function handleUpload() {
    if (!selectedFile) return
    setIsBusy(true)
    setApiError('')
    try {
      startActivity(INITIAL_STEPS)
      const result = await api.uploadDocument(selectedFile)
      completeActivity()

      setStatusMessage(`Uploaded ${result.document.filename}. Discovered ${result.systems.length} systems.`)
      await Promise.all([refreshDashboard(), refreshInventory()])
      setSelectedFile(null)
      setActivitySteps([])
      setActivePage('inventory')
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Upload failed.')
      setActivitySteps([])
    } finally {
      setIsBusy(false)
    }
  }

  async function handleUseCaseSubmit() {
    setIsBusy(true)
    setApiError('')
    try {
      startActivity(GAP_STEPS)
      const created = await api.createUseCase({
        title: useCaseForm.title,
        description: useCaseForm.description,
        business_goal: useCaseForm.business_goal,
        target_systems: useCaseForm.target_systems.split(',').map((item) => item.trim()).filter(Boolean),
        frequency: useCaseForm.frequency,
        criticality: useCaseForm.criticality,
      })
      completeActivity()

      setSelectedUseCaseId(created.id)
      setStatusMessage(`Created use case: ${created.title}`)
      await refreshDashboard()
      const report = await api.getGapReport(created.id)
      setGapReport(report)
      setActivitySteps([])
      setActivePage('gaps')
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Could not create use case.')
      setActivitySteps([])
    } finally {
      setIsBusy(false)
    }
  }

  async function handleAutoDiscoverGoals() {
    setIsBusy(true)
    setApiError('')
    try {
      startActivity([
        { id: 'discover-goals', label: 'Discovering automation goals from uploaded documents', status: 'active' },
      ])
      const result = await api.discoverGoals()
      completeActivity()

      const cases = await api.getUseCases()
      setUseCases(cases)

      if (result.use_cases && result.use_cases.length > 0) {
        const firstCase = result.use_cases[0]
        setSelectedUseCaseId(firstCase.id)
        const report = await api.getGapReport(firstCase.id)
        setGapReport(report)
        setStatusMessage(`Discovered ${result.use_cases.length} goals. Selected "${firstCase.title}".`)
      } else {
        setStatusMessage('No new automation goals discovered.')
      }

      await refreshDashboard()
      setActivitySteps([])
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Could not discover goals.')
      setActivitySteps([])
    } finally {
      setIsBusy(false)
    }
  }

  async function handleGenerateConnector() {
    setIsBusy(true)
    setApiError('')
    try {
      startActivity(GEN_STEPS)
      const result = await api.generateConnector(generatorForm)
      completeActivity()

      setGeneratedPackage(result)
      setStatusMessage(`Generated ${result.connector.filename} with ${result.validation.status.toUpperCase()} validation`)
      await refreshDashboard()
      setActivitySteps([])
      setActivePage('generation')
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Could not generate connector.')
      setActivitySteps([])
    } finally {
      setIsBusy(false)
    }
  }

  async function handleClearInventory() {
    if (!confirm('Are you sure you want to clear the entire inventory?')) return
    setIsBusy(true)
    try {
      await api.clearInventory()
      setStatusMessage('Inventory cleared.')
      await Promise.all([refreshDashboard(), refreshInventory()])
    } catch {
      setApiError('Failed to clear inventory.')
    } finally {
      setIsBusy(false)
    }
  }

  function loadMissingSystem(systemName: string) {
    setGeneratorForm((current) => ({
      ...current,
      system_name: systemName,
      use_case_title: gapReport?.use_case_title ?? current.use_case_title,
    }))
    setActivePage('generation')
  }

  const currentPage = PAGES.find((p) => p.key === activePage) ?? PAGES[0]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span>Discovery Agent</span>
        </div>
        <nav className="sidebar-nav">
          {PAGES.map((p) => (
            <button
              key={p.key}
              className={`nav-link ${activePage === p.key ? 'active' : ''}`}
              onClick={() => setActivePage(p.key)}
            >
              {p.label}
            </button>
          ))}
        </nav>
        <div className="mt-4 pt-4 border-t text-xs text-muted">
          {isBusy ? 'System working...' : statusMessage || 'Ready'}
          {apiError && <p className="text-error mt-1">{apiError}</p>}
        </div>
      </aside>

      <main className="main-content">
        <header className="page-header">
          <h1>{currentPage.label}</h1>
          <p>{currentPage.description}</p>
        </header>

        {isBusy && activitySteps.length > 0 && (
          <div className="card" style={{ borderColor: 'var(--primary)', borderWidth: '2px' }}>
            <h3 className="card-title flex items-center gap-2">
              <span className="animate-pulse">●</span> Agent Activity Monitor
            </h3>
            <div className="space-y-3">
              {activitySteps.map(step => (
                <div key={step.id} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {step.status === 'done' ? (
                      <span style={{ color: 'var(--success)', fontWeight: 'bold' }}>✓</span>
                    ) : step.status === 'active' ? (
                      <div className="animate-spin" style={{ width: '12px', height: '12px', border: '2px solid var(--primary)', borderTopColor: 'transparent', borderRadius: '50%' }} />
                    ) : (
                      <div style={{ width: '12px', height: '12px', border: '2px solid var(--card-border)', borderRadius: '50%' }} />
                    )}
                    <span className={step.status === 'active' ? 'font-bold text-primary' : step.status === 'pending' ? 'text-muted' : ''}>
                      {step.label}
                    </span>
                  </div>
                  {step.status === 'active' && <span className="text-xs text-primary animate-pulse italic">Processing...</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {activePage === 'dashboard' && !isBusy && (
          <div className="space-y-6">
            <div className="card text-center py-10 border-0 bg-white" style={{ background: 'linear-gradient(to bottom, #f8fafc, #ffffff)' }}>
              <h2 className="text-3xl font-extrabold text-slate-900 mb-4 tracking-tight">Discovery Agent Demo Console</h2>
              <p className="text-lg text-slate-600 max-w-2xl mx-auto">Transform operational knowledge into integration-ready architectures.</p>
            </div>

            <div className="metric-grid">
              <div className="metric-card bg-white border shadow-sm">
                <span className="metric-label font-medium uppercase tracking-wider text-xs">Systems Found</span>
                <span className="metric-value text-3xl text-primary">{dashboard.systems}</span>
              </div>
              <div className="metric-card bg-white border shadow-sm">
                <span className="metric-label font-medium uppercase tracking-wider text-xs">Confidence</span>
                <span className="metric-value text-3xl text-success">{dashboard.average_confidence}%</span>
              </div>
              <div className="metric-card bg-white border shadow-sm">
                <span className="metric-label font-medium uppercase tracking-wider text-xs">Integration Gaps</span>
                <span className="metric-value text-3xl text-error">{dashboard.integration_gaps}</span>
              </div>
              <div className="metric-card bg-white border shadow-sm">
                <span className="metric-label font-medium uppercase tracking-wider text-xs">Connectors Generated</span>
                <span className="metric-value text-3xl">{dashboard.artifacts}</span>
              </div>
            </div>

            <div className="grid-cols-2">
              <div className="card shadow-sm border">
                <h3 className="card-title">Recent Systems Discovered</h3>
                <div className="space-y-2">
                  {dashboard.latest_systems.map((s) => (
                    <div key={`${s.name}-${s.id}`} className="flex items-center justify-between p-2 hover:bg-slate-50 rounded">
                      <div>
                        <div className="font-semibold text-slate-800">{s.name}</div>
                        <div className="text-xs text-muted">{s.category}</div>
                      </div>
                      <span className={`badge ${s.confidence_score >= 0.95 ? 'badge-success' : 'badge-warning'}`}>
                        {Math.round(s.confidence_score * 100)}%
                      </span>
                    </div>
                  ))}
                  {dashboard.latest_systems.length === 0 && <p className="text-muted text-sm text-center py-4">No systems found yet. Upload a document to begin.</p>}
                </div>
              </div>

              <div className="card shadow-sm border">
                <h3 className="card-title">Discovery Pipeline Status</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-slate-50 border rounded">
                    <div>
                      <div className="font-semibold text-slate-800">Level 1: System Discovery</div>
                      <div className="text-xs text-muted">Deterministic extraction + evidence mapping</div>
                    </div>
                    <span className="badge badge-success">Active</span>
                  </div>
                  <div className="flex items-center justify-between p-3 border rounded">
                    <div>
                      <div className="font-semibold text-slate-800">Level 2: Gap Analysis</div>
                      <div className="text-xs text-muted">Map discovered systems to integration goals</div>
                    </div>
                    <button
                      className="button button-outline text-xs py-1 px-3"
                      style={{ borderColor: 'var(--primary)', color: 'var(--primary)' }}
                      onClick={() => {
                        setActivePage('gaps');
                        handleAutoDiscoverGoals();
                      }}
                    >
                      Discover Goals
                    </button>
                  </div>
                  <div className="flex items-center justify-between p-3 border rounded">
                    <div>
                      <div className="font-semibold text-slate-800">Level 3: Code Gen</div>
                      <div className="text-xs text-muted">Awaiting gap identification</div>
                    </div>
                    <span className="badge badge-outline text-slate-600">Ready</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activePage === 'upload' && !isBusy && (
          <div className="grid-cols-2">
            <div className="card">
              <h3 className="card-title">Ingest Document</h3>
              <label className="upload-area">
                <p className="mb-2">Click to select or drag and drop</p>
                <p className="text-xs text-muted">PDF, TXT, MD, DOCX</p>
                <input
                  type="file"
                  hidden
                  onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                />
                {selectedFile && <p className="mt-4 font-semibold text-primary">{selectedFile.name}</p>}
              </label>
              <button
                className="button button-primary w-full mt-4"
                disabled={!selectedFile || isBusy}
                onClick={handleUpload}
              >
                {isBusy ? 'Processing...' : 'Run Discovery'}
              </button>
            </div>
            <div className="card">
              <h3 className="card-title">Uploaded Files</h3>
              <div className="space-y-2">
                {reports.documents.map((d) => (
                  <div key={d.id} className="flex justify-between text-sm p-2 border-b">
                    <span>{d.filename}</span>
                    <span className="text-muted">{(Number(d.size_bytes) / 1024).toFixed(1)} KB</span>
                  </div>
                ))}

              </div>
            </div>
          </div>
        )}

        {activePage === 'inventory' && (
          <div className="card">
            <div className="flex justify-between items-center mb-4">
              <div className="flex gap-2">
                <input
                  className="input mb-0"
                  placeholder="Search by system..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{ width: '240px' }}
                />
                <select className="select mb-0" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
                  <option value="">All Categories</option>
                  {categories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="flex gap-2">
                <button onClick={handleClearInventory} className="button button-outline" style={{ color: 'var(--error)', borderColor: 'var(--error)' }}>Clear</button>
                <a href={api.inventoryJsonExportUrl()} className="button button-outline">JSON</a>
                <a href={api.inventoryCsvExportUrl()} className="button button-outline">CSV</a>
              </div>
            </div>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>System</th>
                    <th>Category</th>
                    <th>Confidence</th>
                    <th>Status</th>
                    <th>Evidence Source</th>
                  </tr>
                </thead>
                <tbody>
                  {inventory.items.map((s) => (
                    <tr key={`${s.id}-${s.name}`}>
                      <td>
                        <div className="font-semibold">{s.name}</div>
                        <div className="text-xs text-muted">{s.auth_method} Auth</div>
                      </td>
                      <td>{s.category}</td>
                      <td>
                        <span className={`badge ${s.confidence_score >= 0.95 ? 'badge-success' : s.confidence_score >= 0.7 ? 'badge-warning' : 'badge-error'}`}>
                          {Math.round(s.confidence_score * 100)}%
                        </span>
                      </td>
                      <td>
                        {s.human_review_required ? (
                          <span className="badge badge-error animate-pulse">Needs Review</span>
                        ) : (
                          <span className="badge badge-success">Verified</span>
                        )}
                      </td>
                      <td>
                        <div className="text-xs text-muted italic">"{s.evidence}"</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activePage === 'gaps' && !isBusy && (
          <div className="grid-cols-2">
            <div className="card">
              <h3 className="card-title">Define Use Case</h3>
              <input
                className="input"
                placeholder="Title"
                value={useCaseForm.title}
                onChange={e => setUseCaseForm({ ...useCaseForm, title: e.target.value })}
              />
              <textarea
                className="textarea"
                placeholder="Description"
                value={useCaseForm.description}
                onChange={e => setUseCaseForm({ ...useCaseForm, description: e.target.value })}
              />
              <input
                className="input"
                placeholder="Target Systems (comma separated)"
                value={useCaseForm.target_systems}
                onChange={e => setUseCaseForm({ ...useCaseForm, target_systems: e.target.value })}
              />
              <button
                className="button button-primary w-full"
                onClick={handleUseCaseSubmit}
                disabled={isBusy}
              >
                Analyze Gaps (Manual)
              </button>
              <div className="text-center text-xs text-muted my-2">— OR —</div>
              <button
                className="button button-outline w-full"
                onClick={handleAutoDiscoverGoals}
                disabled={isBusy}
                style={{ borderColor: 'var(--primary)', color: 'var(--primary)' }}
              >
                Auto-Discover Goals from Documents
              </button>
            </div>
            <div className="card">
              <h3 className="card-title">Integration Roadmap</h3>
              <select
                className="select"
                value={selectedUseCaseId ?? ''}
                onChange={e => setSelectedUseCaseId(Number(e.target.value))}
              >
                <option value="">Select a Goal...</option>
                {useCases.map(u => <option key={u.id} value={u.id}>{u.title}</option>)}
              </select>
              {gapReport && (
                <div className="mt-4 p-4 bg-muted-light rounded border" style={{ borderLeft: '4px solid var(--primary)' }}>
                  <div className="font-bold text-primary mb-1">STRATEGIC RECOMMENDATION</div>
                  <div className="text-sm italic">{gapReport.strategic_recommendation}</div>
                </div>
              )}
              {gapReport && (
                <div className="mt-4 p-4 bg-slate-50 rounded border">
                  <div className="font-bold">{gapReport.use_case_title}</div>
                  <div className="text-sm text-muted mb-2">{gapReport.business_goal}</div>
                  <span className="badge badge-error">{gapReport.business_impact} Impact</span>
                </div>
              )}
            </div>

            {gapReport && (
              <div className="card">
                <h3 className="card-title">Integration Gaps & Effort</h3>
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>System</th>
                        <th>Status</th>
                        <th>Priority</th>
                        <th>Est. Effort</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gapReport.gaps.map(g => (
                        <tr key={g.system_name}>
                          <td className="font-semibold">{g.system_name}</td>
                          <td>
                            <span className={`badge ${g.status === 'missing' ? 'badge-error' : 'badge-success'}`}>
                              {g.status.toUpperCase()}
                            </span>
                          </td>
                          <td>
                            <span className={`badge ${g.priority === 'High' || g.priority === 'Critical' ? 'badge-error' : 'badge-warning'}`}>
                              {g.priority}
                            </span>
                          </td>
                          <td>{g.effort_estimate}</td>
                          <td>
                            {g.status === 'missing' ? (
                              <button className="text-primary font-bold hover:underline" onClick={() => loadMissingSystem(g.system_name)}>
                                GENERATE
                              </button>
                            ) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            {gapReport && gapReport.data_flow_analysis.length > 0 && (
              <div className="card">
                <h3 className="card-title">Data Flow Analysis</h3>
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Source</th>
                        <th>Destination</th>
                        <th>Entity</th>
                        <th>Trigger</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gapReport.data_flow_analysis.map((flow, i) => (
                        <tr key={i}>
                          <td>{flow.source}</td>
                          <td>{flow.destination}</td>
                          <td>{flow.entity_type}</td>
                          <td>{flow.trigger}</td>
                          <td>
                            {flow.is_blocked ? (
                              <span className="text-error font-bold">BLOCKED</span>
                            ) : (
                              <span className="text-success">FLOWING</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {activePage === 'generation' && !isBusy && (
          <div className="grid-cols-2">
            <div className="card">
              <h3 className="card-title">Generator Options</h3>
              <input
                className="input"
                placeholder="System Name"
                value={generatorForm.system_name}
                onChange={e => setGeneratorForm({ ...generatorForm, system_name: e.target.value })}
              />
              <div className="grid-cols-2">
                <input
                  className="input"
                  placeholder="Category"
                  value={generatorForm.category}
                  onChange={e => setGeneratorForm({ ...generatorForm, category: e.target.value })}
                />
                <input
                  className="input"
                  placeholder="Auth"
                  value={generatorForm.auth_method}
                  onChange={e => setGeneratorForm({ ...generatorForm, auth_method: e.target.value })}
                />
              </div>
              <select
                className="select"
                value={generatorForm.language}
                onChange={e => setGeneratorForm({ ...generatorForm, language: e.target.value })}
              >
                <option value="python">Python</option>
                <option value="nodejs">Node.js</option>
              </select>
              <button
                className="button button-primary w-full"
                onClick={handleGenerateConnector}
                disabled={isBusy}
              >
                Generate + Validate
              </button>
            </div>
            <div className="card">
              <h3 className="card-title">Artifact Preview</h3>
              {generatedPackage ? (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="font-mono text-sm font-bold text-primary">{generatedPackage.connector.filename}</span>
                    <span className={`badge ${generatedPackage.validation.status === 'pass' ? 'badge-success' : 'badge-error'}`}>
                      {generatedPackage.validation.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="flex gap-1 border-b mb-4">
                    {ARTIFACT_TABS.map((tab) => (
                      <button
                        key={tab}
                        className={`nav-link ${activeTab === tab ? 'active' : ''}`}
                        onClick={() => setActiveTab(tab)}
                        style={{ padding: '0.5rem 1rem', fontSize: '0.8rem' }}
                      >
                        {tab.toUpperCase()}
                      </button>
                    ))}
                  </div>

                  <pre className="bg-slate-900 text-slate-100 p-4 rounded text-xs overflow-auto max-h-[500px]">
                    {activeTab === 'code' && generatedPackage.connector.code}
                    {activeTab === 'tests' && generatedPackage.connector.tests}
                    {activeTab === 'readme' && generatedPackage.connector.readme}
                  </pre>

                  <div className="p-3 bg-muted-light rounded border">
                    <div className="text-xs font-bold mb-1">DEPENDENCIES</div>
                    <code className="text-xs">{generatedPackage.connector.dependencies.join(', ') || 'None'}</code>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-muted">
                  <p>No artifact generated yet.</p>
                  <p className="text-xs">Identify a gap in Level 2 and click 'GENERATE'</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activePage === 'reports' && (
          <div className="card">
            <h3 className="card-title">Operation History</h3>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Action</th>
                    <th>Resource</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.validations.map((v, i) => (
                    <tr key={i}>
                      <td className="text-xs">Just now</td>
                      <td>Validation</td>
                      <td>{v.filename || 'Inline Code'}</td>
                      <td>
                        <span className={`badge ${v.status === 'pass' ? 'badge-success' : 'badge-error'}`}>
                          {v.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
export default App
