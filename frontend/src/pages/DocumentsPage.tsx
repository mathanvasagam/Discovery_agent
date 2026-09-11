import { useState } from 'react'
import type { ReportsPayload } from '../types/api'
import { EmptyState } from '../components/EmptyState'
import { Field } from '../components/Field'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { Section } from '../components/Section'

interface DocumentsPageProps {
  selectedFile: File | null
  reports: ReportsPayload
  isBusy: boolean
  onFileSelect: (file: File | null) => void
  onUpload: () => void
}

export function DocumentsPage({ selectedFile, reports, isBusy, onFileSelect, onUpload }: DocumentsPageProps) {
  const [isDragging, setIsDragging] = useState(false)

  return (
    <div className="page-stack">
      <PageHeader title="Documents" description="Ingest operational documentation and discover the systems referenced inside it." />

      <div className="two-column-layout documents-layout">
        <Section title="Run discovery" description="The server validates file type and size before extraction begins.">
          <Field label="Source document" hint="PDF, DOCX, XLSX, CSV, TXT, Markdown, and supported image formats." required>
            <label
              className={`dropzone ${isDragging ? 'is-dragging' : ''}`}
              onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(event) => {
                event.preventDefault()
                setIsDragging(false)
                onFileSelect(event.dataTransfer.files?.[0] ?? null)
              }}
            >
              <input type="file" hidden onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)} />
              <Icon name="upload" size={22} />
              <strong>{selectedFile ? selectedFile.name : 'Choose a file or drop it here'}</strong>
              <span>{selectedFile ? `${(selectedFile.size / 1024).toFixed(1)} KB selected` : 'File-size limits are enforced by backend policy.'}</span>
            </label>
          </Field>
          <div className="form-actions form-actions-right">
            <button className="button button-primary" disabled={!selectedFile || isBusy} onClick={onUpload}>
              <Icon name="activity" size={15} />
              Run discovery
            </button>
          </div>
        </Section>

        <Section title="What happens next" description="A discovery request executes the backend pipeline without fabricated client-side stage timing.">
          <ol className="process-list">
            <li><span>1</span><div><strong>Extract content</strong><p>The ingestor selects the parser for the document type and produces normalized text.</p></div></li>
            <li><span>2</span><div><strong>Discover systems</strong><p>Deterministic catalog matching is combined with optional evidence-checked LLM assistance.</p></div></li>
            <li><span>3</span><div><strong>Persist evidence</strong><p>System records, confidence metadata, source references, and review state are stored.</p></div></li>
          </ol>
        </Section>
      </div>

      <Section title="Uploaded documents" description="Documents currently reported by the backend workspace.">
        {reports.documents.length > 0 ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Filename</th><th>Content type</th><th className="align-right">Size</th></tr></thead>
              <tbody>
                {reports.documents.map((document) => (
                  <tr key={String(document.id ?? document.filename)}>
                    <td className="cell-primary"><Icon name="document" size={15} />{String(document.filename)}</td>
                    <td>{String(document.content_type ?? 'Unknown')}</td>
                    <td className="align-right mono-cell">{(Number(document.size_bytes ?? 0) / 1024).toFixed(1)} KB</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="document" title="No uploaded documents" description="The document list will populate after the first successful upload." />
        )}
      </Section>
    </div>
  )
}
