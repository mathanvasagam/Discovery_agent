import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

interface EmptyStateProps {
  icon?: IconName
  title: string
  description: string
  action?: ReactNode
}

export function EmptyState({ icon = 'inventory', title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon"><Icon name={icon} size={20} /></div>
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  )
}
