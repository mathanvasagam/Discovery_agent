export interface InventorySystem {
  id?: number
  name: string
  category: string
  auth_method: string
  key_entities: string[]
  business_processes: string[]
  criticality: 'Low' | 'Medium' | 'High'
  confidence_score: number
  evidence: string
  inference_note?: string
  human_review_required?: boolean
  source_reference: string
  page_number?: number | null
  line_number?: number | null
}

export interface InventoryResponse {
  items: InventorySystem[]
  total: number
  page: number
  page_size: number
}

export interface DashboardSummary {
  documents: number
  systems: number
  use_cases: number
  artifacts: number
  validations: number
  latest_systems: InventorySystem[]
  integration_gaps: number
  average_confidence: number
}

export interface LlmStatus {
  provider: string
  configured: boolean
  connected?: boolean
  model: string | null
  message?: string
  failover_order?: string[]
  attempted_providers?: string[]
  providers?: Record<string, { configured: boolean; model: string | null }>
}

export interface RuntimeStatus {
  environment: string
  validation_mode: string
  workspace_isolation: boolean
  rate_limits: boolean
  original_upload_retention: boolean
  database: string
  privacy_mode: string
}

export interface HealthStatus {
  status: string
  llm: LlmStatus
  runtime?: RuntimeStatus
}

export interface UseCaseCreateRequest {
  title: string
  description: string
  business_goal: string
  target_systems: string[]
  frequency: string
  criticality: string
}

export interface ConnectorGenerationRequest {
  system_name: string
  category: string
  auth_method: string
  use_case_title: string
  language: string
}

export interface UseCaseSummary {
  id: number
  title: string
  description: string
  business_goal: string
  target_systems: string[]
  data_flows: Array<Record<string, string>>
  frequency: string
  criticality: string
  created_at: string
}

export interface GapEntry {
  system_name: string
  status: 'available' | 'missing'
  priority: 'Low' | 'Medium' | 'High' | 'Critical'
  priority_score?: number
  effort_estimate: string
  details: string
  dependencies?: string[]
}

export interface GapReport {
  use_case_id: number
  use_case_title: string
  business_goal: string
  strategic_recommendation: string
  required_systems: string[]
  available_systems: string[]
  missing_systems: string[]
  integration_gaps: GapEntry[]
  gaps: GapEntry[]
  data_flow_analysis: Array<Record<string, string | boolean>>
  dependency_mapping: string[]
  dependency_graph: {
    nodes: Array<Record<string, string>>
    edges: Array<Record<string, string | boolean>>
  }
  business_impact: string
  priority_score: number
}

export interface ValidationResult {
  status: 'pass' | 'fail'
  output: string
  warnings: string[]
  errors: string[]
  logs: Array<{
    command: string[]
    returncode: number
    stdout: string
    stderr: string
  }>
  filename?: string
}

export interface GeneratedPackage {
  connector: {
    code: string
    tests: string
    dependencies: string[]
    readme: string
    config_files?: Record<string, string>
    language: string
    filename: string
    test_filename?: string
  }
  agent_definition: {
    name: string
    system_prompt: string
    tools: string[]
    workflow_steps: string[]
    test_scenarios: string[]
    description?: string
  }
  validation: ValidationResult
  artifact_dir: string
}

export interface ReportsPayload {
  documents: Array<Record<string, string | number>>
  inventory: InventoryResponse
  use_cases: UseCaseSummary[]
  artifacts: Array<Record<string, string | number>>
  validations: ValidationResult[]
}
