import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description: string
  eyebrow?: string
  actions?: ReactNode
}

export function PageHeader({ title, description, eyebrow = 'Workspace', actions }: PageHeaderProps) {
  return (
    <header className="page-heading">
      <div className="page-heading-copy">
        <span className="page-eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-heading-actions">{actions}</div>}
    </header>
  )
}
