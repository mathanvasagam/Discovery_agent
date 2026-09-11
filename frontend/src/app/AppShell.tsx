import type { ReactNode } from 'react'
import type { LlmStatus } from '../types/api'
import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/StatusBadge'
import { NAVIGATION, type PageKey } from './navigation'

interface AppShellProps {
  activePage: PageKey
  onNavigate: (page: PageKey) => void
  apiConnected: boolean
  llmStatus: LlmStatus
  isBusy: boolean
  onVerifyLlm: () => void
  children: ReactNode
}

export function AppShell({ activePage, onNavigate, apiConnected, llmStatus, isBusy, onVerifyLlm, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">DA</div>
          <div>
            <strong>Discovery Agent</strong>
            <span>Integration intelligence</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          <span className="nav-section-label">Workspace</span>
          {NAVIGATION.map((item) => (
            <button
              key={item.key}
              className={`sidebar-link ${activePage === item.key ? 'is-active' : ''}`}
              onClick={() => onNavigate(item.key)}
              aria-current={activePage === item.key ? 'page' : undefined}
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="environment-panel">
          <span className="nav-section-label">Environment</span>
          <div className="environment-row">
            <div><Icon name="server" size={15} /><span>API</span></div>
            <StatusBadge tone={apiConnected ? 'success' : 'error'}>{apiConnected ? 'Online' : 'Offline'}</StatusBadge>
          </div>
          <div className="environment-row">
            <div><Icon name="activity" size={15} /><span>{llmStatus.provider === 'none' ? 'AI provider' : llmStatus.provider.toUpperCase()}</span></div>
            <StatusBadge tone={llmStatus.connected ? 'success' : llmStatus.configured ? 'info' : 'neutral'}>
              {llmStatus.connected ? 'Connected' : llmStatus.configured ? 'Configured' : 'Fallback'}
            </StatusBadge>
          </div>
          <button className="sidebar-utility" onClick={onVerifyLlm} disabled={isBusy}>
            Verify provider connection
          </button>
        </div>
      </aside>

      <main className="workspace-main">
        <div className="workspace-topbar">
          <div>
            <span>Discovery Agent</span>
            <span className="topbar-separator">/</span>
            <strong>{NAVIGATION.find((item) => item.key === activePage)?.label}</strong>
          </div>
          <div className="topbar-state">
            <span className={`health-dot ${apiConnected ? 'health-ok' : 'health-error'}`} />
            {apiConnected ? 'Backend connected' : 'Backend unavailable'}
          </div>
        </div>
        <div className="workspace-content">{children}</div>
      </main>
    </div>
  )
}
