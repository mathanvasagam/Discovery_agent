import type { HTMLAttributes, ReactNode } from 'react'

interface SectionProps extends HTMLAttributes<HTMLElement> {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  compact?: boolean
}

export function Section({ title, description, actions, children, compact = false, className = '', ...props }: SectionProps) {
  return (
    <section className={`surface ${compact ? 'surface-compact' : ''} ${className}`.trim()} {...props}>
      {(title || description || actions) && (
        <div className="surface-header">
          <div>
            {title && <h2>{title}</h2>}
            {description && <p>{description}</p>}
          </div>
          {actions && <div className="surface-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}
