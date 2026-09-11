import type { ReactNode } from 'react'

interface FieldProps {
  label: string
  hint?: string
  required?: boolean
  children: ReactNode
}

export function Field({ label, hint, required = false, children }: FieldProps) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {required && <span className="field-required">Required</span>}
      </span>
      {hint && <span className="field-hint">{hint}</span>}
      {children}
    </label>
  )
}
