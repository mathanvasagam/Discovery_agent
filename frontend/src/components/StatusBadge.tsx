import type { ReactNode } from 'react'

export type StatusTone = 'success' | 'warning' | 'error' | 'neutral' | 'info'

interface StatusBadgeProps {
  tone?: StatusTone
  children: ReactNode
}

export function StatusBadge({ tone = 'neutral', children }: StatusBadgeProps) {
  return <span className={`status-badge status-${tone}`}>{children}</span>
}
