import { Icon } from './Icon'

export interface OperationContext {
  title: string
  description: string
  steps: string[]
}

interface WorkflowProgressProps {
  operation: OperationContext
}

export function WorkflowProgress({ operation }: WorkflowProgressProps) {
  return (
    <div className="operation-panel" role="status" aria-live="polite">
      <div className="operation-spinner" aria-hidden="true" />
      <div className="operation-copy">
        <strong>{operation.title}</strong>
        <p>{operation.description}</p>
        <div className="operation-scope" aria-label="Operation scope">
          {operation.steps.map((step) => (
            <span key={step}><Icon name="activity" size={13} />{step}</span>
          ))}
        </div>
      </div>
    </div>
  )
}
