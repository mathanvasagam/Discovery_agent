import { useCallback, useDeferredValue, useEffect, useState } from 'react'
import { AppShell } from './app/AppShell'
import { NAVIGATION, type PageKey } from './app/navigation'
import { WorkflowProgress, type OperationContext } from './components/WorkflowProgress'
import { DashboardPage } from './pages/DashboardPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { GapAnalysisPage, type UseCaseFormState } from './pages/GapAnalysisPage'
import { GenerationPage, type GeneratorFormState } from './pages/GenerationPage'
import { InventoryPage } from './pages/InventoryPage'
import { ReportsPage } from './pages/ReportsPage'
import { api } from './services/api'
import type { DashboardSummary, GapReport, GeneratedPackage, InventoryResponse, LlmStatus, ReportsPayload, RuntimeStatus, UseCaseSummary } from './types/api'

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

const EMPTY_INVENTORY: InventoryResponse = { items: [], total: 0, page: 1, page_size: 10 }
const EMPTY_REPORTS: ReportsPayload = { documents: [], inventory: EMPTY_INVENTORY, use_cases: [], artifacts: [], validations: [] }
const EMPTY_LLM_STATUS: LlmStatus = { provider: 'none', configured: false, model: null }

const OPERATIONS: Record<'upload' | 'gaps' | 'discover' | 'generate' | 'provider', OperationContext> = {
  upload: {
    title: 'Discovery request running',
    description: 'Waiting for the backend to complete document processing and persist its evidence-backed results.',
    steps: ['Content extraction', 'System discovery', 'Evidence persistence'],
  },
  gaps: {
    title: 'Gap analysis running',
    description: 'Waiting for the backend to map the defined business goal against the current system inventory.',
    steps: ['Required systems', 'Data-flow mapping', 'Gap prioritization'],
  },
  discover: {
    title: 'Goal discovery running',
    description: 'Waiting for the backend to infer automation goals from the documents already available in the workspace.',
    steps: ['Document evidence', 'Use-case extraction', 'Gap model refresh'],
  },
  generate: {
    title: 'Connector generation running',
    description: 'Waiting for code generation and the configured validation mode to return a final artifact result.',
    steps: ['Connector scaffold', 'Tests and metadata', 'Validation'],
  },
  provider: {
    title: 'Provider verification running',
    description: 'Checking configured AI providers in failover order and selecting the first healthy connection.',
    steps: ['Configuration check', 'Provider request'],
  },
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
  const [llmStatus, setLlmStatus] = useState<LlmStatus>(EMPTY_LLM_STATUS)
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null)
  const [statusMessage, setStatusMessage] = useState('')
  const [apiError, setApiError] = useState('')
  const [apiConnected, setApiConnected] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  const [operation, setOperation] = useState<OperationContext | null>(null)

  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [categoryFilter, setCategoryFilter] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const [useCaseForm, setUseCaseForm] = useState<UseCaseFormState>({
    title: 'Invoice Automation',
    description: 'Automatically create invoices from Salesforce opportunities.',
    business_goal: 'Automatically create invoices from Salesforce opportunities.',
    target_systems: 'Salesforce, NetSuite, Stripe',
    frequency: 'Daily',
    criticality: 'High',
  })

  const [generatorForm, setGeneratorForm] = useState<GeneratorFormState>({
    system_name: 'Salesforce',
    category: 'CRM',
    auth_method: 'OAuth2',
    use_case_title: 'Invoice Automation',
    language: 'python',
  })

  const categories = Array.from(new Set(inventory.items.map((item) => item.category))).sort()

  const refreshDashboard = useCallback(async () => {
    const [dashboardData, reportsData, useCaseData, healthData] = await Promise.all([
      api.getDashboard(),
      api.getReports(),
      api.getUseCases(),
      api.getHealth(),
    ])
    setDashboard(dashboardData)
    setReports(reportsData)
    setUseCases(useCaseData)
    setLlmStatus(healthData.llm)
    setRuntimeStatus(healthData.runtime ?? null)
    setSelectedUseCaseId((current) => current ?? (useCaseData.length > 0 ? useCaseData[0].id : null))
    setApiConnected(true)
  }, [])

  const refreshInventory = useCallback(async () => {
    const response = await api.getInventory({ search: deferredSearch, category: categoryFilter })
    setInventory(response)
  }, [categoryFilter, deferredSearch])

  useEffect(() => {
    const loadDashboard = async () => {
      setIsBusy(true)
      setApiError('')
      try {
        await refreshDashboard()
      } catch (error) {
        setApiConnected(false)
        setApiError(error instanceof Error ? error.message : 'Unable to reach backend API.')
      } finally {
        setIsBusy(false)
      }
    }
    void loadDashboard()
  }, [refreshDashboard])

  useEffect(() => {
    let cancelled = false
    api.getInventory({ search: deferredSearch, category: categoryFilter })
      .then((response) => {
        if (!cancelled) setInventory(response)
      })
      .catch((error) => {
        if (!cancelled) setApiError(error instanceof Error ? error.message : 'Unable to refresh inventory.')
      })
    return () => { cancelled = true }
  }, [categoryFilter, deferredSearch])

  useEffect(() => {
    if (!selectedUseCaseId) return
    let cancelled = false
    api.getGapReport(selectedUseCaseId)
      .then((report) => {
        if (!cancelled) setGapReport(report)
      })
      .catch((error) => {
        if (!cancelled) setApiError(error instanceof Error ? error.message : 'Unable to load gap report.')
      })
    return () => { cancelled = true }
  }, [selectedUseCaseId])

  function beginOperation(context: OperationContext) {
    setIsBusy(true)
    setOperation(context)
    setApiError('')
  }

  function finishOperation() {
    setIsBusy(false)
    setOperation(null)
  }

  async function handleUpload() {
    if (!selectedFile) return
    beginOperation(OPERATIONS.upload)
    try {
      const result = await api.uploadDocument(selectedFile)
      setStatusMessage(`Uploaded ${String(result.document.filename)}. Discovered ${result.systems.length} systems.`)
      await Promise.all([refreshDashboard(), refreshInventory()])
      setSelectedFile(null)
      setActivePage('inventory')
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Upload failed.')
    } finally {
      finishOperation()
    }
  }

  async function handleUseCaseSubmit() {
    beginOperation(OPERATIONS.gaps)
    try {
      const created = await api.createUseCase({
        title: useCaseForm.title,
        description: useCaseForm.description,
        business_goal: useCaseForm.business_goal,
        target_systems: useCaseForm.target_systems.split(',').map((item) => item.trim()).filter(Boolean),
        frequency: useCaseForm.frequency,
        criticality: useCaseForm.criticality,
      })
      setSelectedUseCaseId(created.id)
      setStatusMessage(`Created use case: ${created.title}`)
      await refreshDashboard()
      setGapReport(await api.getGapReport(created.id))
      setActivePage('gaps')
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Could not create use case.')
    } finally {
      finishOperation()
    }
  }

  async function handleAutoDiscoverGoals() {
    beginOperation(OPERATIONS.discover)
    try {
      const result = await api.discoverGoals()
      const cases = await api.getUseCases()
      setUseCases(cases)
      if (result.use_cases?.length > 0) {
        const firstCase = result.use_cases[0]
        setSelectedUseCaseId(firstCase.id)
        setGapReport(await api.getGapReport(firstCase.id))
        setStatusMessage(`Discovered ${result.use_cases.length} goal${result.use_cases.length === 1 ? '' : 's'}. Selected “${firstCase.title}”.`)
        setActivePage('gaps')
      } else {
        setStatusMessage('No new automation goals were discovered from the current document set.')
      }
      await refreshDashboard()
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Could not discover goals.')
    } finally {
      finishOperation()
    }
  }

  async function handleGenerateConnector() {
    beginOperation(OPERATIONS.generate)
    try {
      const result = await api.generateConnector(generatorForm)
      setGeneratedPackage(result)
      setStatusMessage(`Generated ${result.connector.filename} with ${result.validation.status.toUpperCase()} validation`)
      await refreshDashboard()
      setActivePage('generation')
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Could not generate connector.')
    } finally {
      finishOperation()
    }
  }

  async function handleClearInventory() {
    if (!confirm('Clear the entire discovered-system inventory? This action cannot be undone.')) return
    beginOperation({ title: 'Clearing inventory', description: 'Waiting for the backend to remove the current inventory records.', steps: ['Inventory deletion', 'Dashboard refresh'] })
    try {
      await api.clearInventory()
      setStatusMessage('Inventory cleared.')
      await Promise.all([refreshDashboard(), refreshInventory()])
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Failed to clear inventory.')
    } finally {
      finishOperation()
    }
  }

  async function handleVerifyLlm() {
    beginOperation(OPERATIONS.provider)
    try {
      const result = await api.verifyLlm()
      setLlmStatus(result)
      setStatusMessage(result.message ?? 'AI provider connection check complete.')
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Could not verify an AI provider connection.')
    } finally {
      finishOperation()
    }
  }

  function loadMissingSystem(systemName: string) {
    setGeneratorForm((current) => ({ ...current, system_name: systemName, use_case_title: gapReport?.use_case_title ?? current.use_case_title }))
    setActivePage('generation')
  }

  const currentPage = NAVIGATION.find((item) => item.key === activePage) ?? NAVIGATION[0]

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage} apiConnected={apiConnected} llmStatus={llmStatus} isBusy={isBusy} onVerifyLlm={handleVerifyLlm}>
      {(apiError || statusMessage) && (
        <div className={`notice ${apiError ? 'notice-error' : 'notice-success'}`} role={apiError ? 'alert' : 'status'}>
          <strong>{apiError ? 'Request failed' : 'Workspace update'}</strong>
          <span>{apiError || statusMessage}</span>
        </div>
      )}

      {isBusy && operation && <WorkflowProgress operation={operation} />}

      {activePage === 'dashboard' && <DashboardPage dashboard={dashboard} llmStatus={llmStatus} runtimeStatus={runtimeStatus} onNavigate={setActivePage} onDiscoverGoals={handleAutoDiscoverGoals} />}
      {activePage === 'upload' && <DocumentsPage selectedFile={selectedFile} reports={reports} isBusy={isBusy} onFileSelect={setSelectedFile} onUpload={handleUpload} />}
      {activePage === 'inventory' && <InventoryPage inventory={inventory} search={search} categoryFilter={categoryFilter} categories={categories} jsonExportUrl={api.inventoryJsonExportUrl()} csvExportUrl={api.inventoryCsvExportUrl()} onSearch={setSearch} onCategoryChange={setCategoryFilter} onClear={handleClearInventory} />}
      {activePage === 'gaps' && <GapAnalysisPage form={useCaseForm} useCases={useCases} selectedUseCaseId={selectedUseCaseId} gapReport={gapReport} isBusy={isBusy} onFormChange={(field, value) => setUseCaseForm((current) => ({ ...current, [field]: value }))} onSubmit={handleUseCaseSubmit} onAutoDiscover={handleAutoDiscoverGoals} onSelectUseCase={(id) => { setSelectedUseCaseId(id); if (!id) setGapReport(null) }} onGenerateMissing={loadMissingSystem} />}
      {activePage === 'generation' && <GenerationPage form={generatorForm} generatedPackage={generatedPackage} activeTab={activeTab} isBusy={isBusy} onFormChange={(field, value) => setGeneratorForm((current) => ({ ...current, [field]: value }))} onGenerate={handleGenerateConnector} onTabChange={setActiveTab} />}
      {activePage === 'reports' && <ReportsPage reports={reports} />}

      <footer className="page-footer">
        <span>{currentPage.label}</span>
        <span>Discovery Agent · evidence-backed integration planning</span>
      </footer>
    </AppShell>
  )
}

export default App
