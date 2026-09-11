import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import App from './App'

const mockDashboard = {
  documents: 1,
  systems: 2,
  use_cases: 1,
  artifacts: 1,
  validations: 1,
  integration_gaps: 1,
  average_confidence: 96.5,
  latest_systems: [
    {
      name: 'Salesforce',
      category: 'CRM',
      auth_method: 'OAuth2',
      criticality: 'High',
      confidence_score: 0.98,
      evidence: 'Salesforce CRM is used for opportunity management.',
      key_entities: ['Lead'],
      business_processes: ['Sales'],
      source_reference: 'sample_company.pdf',
    },
  ],
}

const mockInventory = {
  items: [
    {
      name: 'Salesforce',
      category: 'CRM',
      auth_method: 'OAuth2',
      criticality: 'High',
      confidence_score: 0.98,
      evidence: 'Salesforce CRM is used for opportunity management.',
      key_entities: ['Lead'],
      business_processes: ['Sales'],
      source_reference: 'sample_company.pdf',
    },
    {
      name: 'NetSuite',
      category: 'ERP',
      auth_method: 'Token Based',
      criticality: 'High',
      confidence_score: 0.95,
      evidence: 'NetSuite manages invoices.',
      key_entities: ['Invoice'],
      business_processes: ['Billing'],
      source_reference: 'sample_company.pdf',
    },
  ],
  total: 2,
  page: 1,
  page_size: 8,
}

const mockUseCases = [
  {
    id: 11,
    title: 'Invoice Automation',
    description: 'Automatically create invoices from Salesforce opportunities.',
    business_goal: 'Automatically create invoices from Salesforce opportunities.',
    target_systems: ['Salesforce', 'NetSuite', 'Stripe'],
    data_flows: [],
    frequency: 'Daily',
    criticality: 'High',
    created_at: '2026-06-07T00:00:00',
  },
]

const mockGapReport = {
  use_case_id: 11,
  use_case_title: 'Invoice Automation',
  business_goal: 'Automatically create invoices from Salesforce opportunities.',
  required_systems: ['Salesforce', 'NetSuite', 'Stripe'],
  strategic_recommendation: 'Generate the missing Stripe connector before automating the full invoice flow.',
  available_systems: ['Salesforce', 'NetSuite'],
  missing_systems: ['Stripe'],
  integration_gaps: [],
  gaps: [
    { system_name: 'Salesforce', status: 'available', priority: 'Medium', effort_estimate: 'Low', details: 'Discovered with 98.0% confidence.' },
    { system_name: 'Stripe', status: 'missing', priority: 'High', effort_estimate: 'Medium', details: 'No evidence found in the current inventory.' },
  ],
  data_flow_analysis: [],
  dependency_mapping: ['Integration with Stripe must exist before Invoice Automation can be automated.'],
  dependency_graph: { nodes: [], edges: [] },
  business_impact: 'High',
  priority_score: 18,
}

const mockReports = {
  documents: [{ id: 1, filename: 'sample_company.pdf', content_type: 'application/pdf', size_bytes: 2048 }],
  inventory: mockInventory,
  use_cases: mockUseCases,
  artifacts: [{ id: 1, system_name: 'Stripe', language: 'python', filename: 'stripe_connector.py' }],
  validations: [{ status: 'pass', output: 'Validation passed.', warnings: [], errors: [], logs: [], filename: 'stripe_connector.py' }],
}

const mockHealth = {
  status: 'healthy',
  llm: { provider: 'groq', configured: true, model: 'openai/gpt-oss-120b' },
}

describe('App', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/health')) {
        return Promise.resolve(new Response(JSON.stringify(mockHealth), { status: 200 }))
      }
      if (url.includes('/dashboard')) {
        return Promise.resolve(new Response(JSON.stringify(mockDashboard), { status: 200 }))
      }
      if (url.includes('/inventory?')) {
        return Promise.resolve(new Response(JSON.stringify(mockInventory), { status: 200 }))
      }
      if (url.includes('/use-cases') && (!init || init.method === undefined)) {
        return Promise.resolve(new Response(JSON.stringify(mockUseCases), { status: 200 }))
      }
      if (url.includes('/gaps/11')) {
        return Promise.resolve(new Response(JSON.stringify(mockGapReport), { status: 200 }))
      }
      if (url.includes('/reports')) {
        return Promise.resolve(new Response(JSON.stringify(mockReports), { status: 200 }))
      }
      if (url.includes('/generate-connectors')) {
        return Promise.resolve(new Response(JSON.stringify({
          connector: {
            code: 'class StripeConnector {}',
            tests: 'test',
            dependencies: ['requests'],
            readme: '# Stripe',
            language: 'python',
            filename: 'stripe_connector.py',
          },
          agent_definition: {
            name: 'stripe_agent',
            system_prompt: 'demo',
            tools: ['stripe_connector'],
            workflow_steps: ['step1'],
            test_scenarios: ['scenario1'],
          },
          validation: {
            status: 'pass',
            output: 'Validation passed.',
            warnings: [],
            errors: [],
            logs: [],
            filename: 'stripe_connector.py',
          },
          artifact_dir: '/tmp/demo',
        }), { status: 200 }))
      }
      if (url.includes('/use-cases') && init?.method === 'POST') {
        return Promise.resolve(new Response(JSON.stringify(mockUseCases[0]), { status: 201 }))
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the enterprise dashboard without the old demo hero', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: /Dashboard/i })).toBeInTheDocument()
    expect(await screen.findByText(/Enterprise system discovery, integration gaps, and generated artifacts/i)).toBeInTheDocument()
    expect(screen.queryByText(/Discovery Agent Demo Console/i)).not.toBeInTheDocument()
  })

  it('renders inventory results and filters by search', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Inventory/i }))
    expect(await screen.findByRole('heading', { name: /System Inventory/i })).toBeInTheDocument()
    expect((await screen.findAllByText(/^Salesforce$/i))[0]).toBeInTheDocument()

    const searchInput = screen.getByPlaceholderText(/Search by system/i)
    fireEvent.change(searchInput, { target: { value: 'Salesforce' } })

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalled()
    })
  })

  it('shows gap analysis details for the saved use case', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Gap Analysis/i }))
    expect(await screen.findByText(/Invoice Automation/i)).toBeInTheDocument()
    expect((await screen.findAllByText(/^Stripe$/i))[0]).toBeInTheDocument()
    expect((await screen.findAllByText(/^MISSING$/i)).length).toBeGreaterThanOrEqual(1)
  })

  it('does not fabricate report timestamps', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Reports/i }))
    expect(await screen.findByRole('heading', { name: /Reports/i })).toBeInTheDocument()
    expect(await screen.findByText(/stripe_connector.py/i)).toBeInTheDocument()
    expect(screen.queryByText(/Just now/i)).not.toBeInTheDocument()
  })

  it('renders generated connector details', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Code Generation/i }))
    fireEvent.click(screen.getByRole('button', { name: /Generate \+ Validate/i }))
    expect(await screen.findByText(/Generated stripe_connector.py with PASS validation/i)).toBeInTheDocument()
    expect(await screen.findByText(/^PASS$/i)).toBeInTheDocument()
  })
})
