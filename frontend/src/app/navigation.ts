import type { IconName } from '../components/Icon'

export type PageKey = 'dashboard' | 'upload' | 'inventory' | 'gaps' | 'generation' | 'reports'

export interface NavigationItem {
  key: PageKey
  label: string
  description: string
  icon: IconName
}

export const NAVIGATION: NavigationItem[] = [
  {
    key: 'dashboard',
    label: 'Dashboard',
    description: 'Enterprise system discovery, integration gaps, and generated artifacts at a glance.',
    icon: 'dashboard',
  },
  {
    key: 'upload',
    label: 'Documents',
    description: 'Ingest operational documentation and discover the systems referenced inside it.',
    icon: 'document',
  },
  {
    key: 'inventory',
    label: 'System Inventory',
    description: 'Review the evidence-backed system estate discovered from uploaded documents.',
    icon: 'inventory',
  },
  {
    key: 'gaps',
    label: 'Gap Analysis',
    description: 'Map automation goals to available systems, missing dependencies, and blocked data flows.',
    icon: 'gap',
  },
  {
    key: 'generation',
    label: 'Code Generation',
    description: 'Generate integration scaffolds and inspect their isolated validation outcome.',
    icon: 'code',
  },
  {
    key: 'reports',
    label: 'Reports',
    description: 'Inspect validation history and operational output produced by the workspace.',
    icon: 'reports',
  },
]
