import type { SVGProps } from 'react'

export type IconName =
  | 'activity'
  | 'arrow-right'
  | 'check'
  | 'code'
  | 'dashboard'
  | 'document'
  | 'download'
  | 'gap'
  | 'inventory'
  | 'reports'
  | 'search'
  | 'server'
  | 'trash'
  | 'upload'
  | 'warning'

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName
  size?: number
}

export function Icon({ name, size = 18, ...props }: IconProps) {
  const commonProps = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
    ...props,
  }

  switch (name) {
    case 'dashboard':
      return <svg {...commonProps}><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>
    case 'document':
      return <svg {...commonProps}><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h5" /><path d="M9 12h6M9 16h6" /></svg>
    case 'inventory':
      return <svg {...commonProps}><path d="M4 7h16M4 12h16M4 17h16" /><circle cx="7" cy="7" r="1" /><circle cx="7" cy="12" r="1" /><circle cx="7" cy="17" r="1" /></svg>
    case 'gap':
      return <svg {...commonProps}><circle cx="6" cy="6" r="2" /><circle cx="18" cy="18" r="2" /><path d="M8 6h4a4 4 0 0 1 4 4v2" /><path d="M12 18H8a4 4 0 0 1-4-4v-2" /></svg>
    case 'code':
      return <svg {...commonProps}><path d="m8 9-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" /></svg>
    case 'reports':
      return <svg {...commonProps}><path d="M5 20V10M12 20V4M19 20v-7" /><path d="M3 20h18" /></svg>
    case 'server':
      return <svg {...commonProps}><rect x="3" y="4" width="18" height="6" rx="2" /><rect x="3" y="14" width="18" height="6" rx="2" /><path d="M7 7h.01M7 17h.01" /></svg>
    case 'activity':
      return <svg {...commonProps}><path d="M3 12h4l2-6 4 12 2-6h6" /></svg>
    case 'upload':
      return <svg {...commonProps}><path d="M12 16V4M7 9l5-5 5 5" /><path d="M4 16v4h16v-4" /></svg>
    case 'download':
      return <svg {...commonProps}><path d="M12 4v12M7 11l5 5 5-5" /><path d="M4 20h16" /></svg>
    case 'trash':
      return <svg {...commonProps}><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13" /><path d="M10 11v5M14 11v5" /></svg>
    case 'search':
      return <svg {...commonProps}><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></svg>
    case 'arrow-right':
      return <svg {...commonProps}><path d="M5 12h14M14 7l5 5-5 5" /></svg>
    case 'check':
      return <svg {...commonProps}><path d="m5 12 4 4L19 6" /></svg>
    case 'warning':
      return <svg {...commonProps}><path d="M12 3 2.8 20h18.4z" /><path d="M12 9v4M12 17h.01" /></svg>
    default:
      return null
  }
}
