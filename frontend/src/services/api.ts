import type {
  DashboardSummary,
  GapReport,
  GeneratedPackage,
  InventoryResponse,
  ReportsPayload,
  UseCaseSummary,
  ValidationResult,
} from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

type InventoryQuery = {
  search?: string
  category?: string
  criticality?: string
  page?: number
  pageSize?: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) {
    const body = await response.text()
    throw new Error(body || `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  baseUrl: API_BASE_URL,

  getDashboard() {
    return request<DashboardSummary>('/dashboard')
  },

  getDocuments() {
    return request<Array<Record<string, string | number>>>('/documents')
  },

  uploadDocument(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return request<{ document: Record<string, string | number>; systems: unknown[] }>('/documents/upload', {
      method: 'POST',
      body: formData,
    })
  },

  getInventory(query: InventoryQuery = {}) {
    const params = new URLSearchParams()
    if (query.search) params.set('search', query.search)
    if (query.category) params.set('category', query.category)
    if (query.criticality) params.set('criticality', query.criticality)
    params.set('page', String(query.page ?? 1))
    params.set('page_size', String(query.pageSize ?? 10))
    return request<InventoryResponse>(`/inventory?${params.toString()}`)
  },

  clearInventory() {
    return fetch(`${API_BASE_URL}/inventory`, { method: 'DELETE' })
  },

  getUseCases() {
    return request<UseCaseSummary[]>('/use-cases')
  },

  discoverGoals() {
    return request<{ use_cases: UseCaseSummary[] }>('/use-cases/discover', {
      method: 'POST',
    })
  },

  createUseCase(payload: Record<string, unknown>) {
    return request<UseCaseSummary>('/use-cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  getGapReport(useCaseId: number) {
    return request<GapReport>(`/gaps/${useCaseId}`)
  },

  runGapAnalysis(payload: Record<string, unknown>) {
    return request<GapReport>('/gap-analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  generateConnector(payload: Record<string, unknown>) {
    return request<GeneratedPackage>('/generate-connectors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  validateArtifact(payload: Record<string, unknown>) {
    return request<ValidationResult>('/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  getReports() {
    return request<ReportsPayload>('/reports')
  },

  getArtifacts() {
    return request<Array<Record<string, string | number>>>('/artifacts')
  },

  getValidations() {
    return request<ValidationResult[]>('/validations')
  },

  inventoryJsonExportUrl() {
    return `${API_BASE_URL}/inventory/export/json`
  },

  inventoryCsvExportUrl() {
    return `${API_BASE_URL}/inventory/export/csv`
  },
}
