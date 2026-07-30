import { chartSeriesStyle, type SeriesVisualToken } from './chartTheme'

const tokens: SeriesVisualToken[] = [
  'primary',
  'secondary',
  'tertiary',
  'quaternary',
  'quinary',
  'senary',
  'septenary',
  'octonary',
  'nonary',
  'default',
]

function PatternMark({ token }: { token: SeriesVisualToken }) {
  switch (token) {
    case 'primary':
      return null
    case 'secondary':
      return <path d="M-2 2 L2 -2 M0 8 L8 0 M6 10 L10 6" stroke="white" strokeOpacity="0.75" strokeWidth="1.5" />
    case 'tertiary':
      return <path d="M0 0 L8 8 M8 0 L0 8" stroke="white" strokeOpacity="0.7" strokeWidth="1" />
    case 'quaternary':
      return <circle cx="4" cy="4" r="1.5" fill="white" fillOpacity="0.8" />
    case 'quinary':
      return <path d="M2 0 V8 M6 0 V8" stroke="white" strokeOpacity="0.75" strokeWidth="1" />
    case 'senary':
      return <path d="M0 4 H8 M4 0 V8" stroke="white" strokeOpacity="0.75" strokeWidth="1" />
    case 'septenary':
      return <circle cx="4" cy="4" r="2.5" fill="none" stroke="white" strokeOpacity="0.8" strokeWidth="1" />
    case 'octonary':
      return <path d="M-2 6 L2 10 M0 0 L8 8 M6 -2 L10 2" stroke="white" strokeOpacity="0.75" strokeWidth="1.5" />
    case 'nonary':
      return <path d="M0 2 L2 4 L4 2 L6 4 L8 2 M0 6 L2 8 L4 6 L6 8 L8 6" fill="none" stroke="white" strokeOpacity="0.8" strokeWidth="1" />
    default:
      return <circle cx="2" cy="2" r="1" fill="white" fillOpacity="0.8" />
  }
}

export function ChartPatternDefs({ prefix }: { prefix: string }) {
  return <defs>
    {tokens.map((token) => {
      const color = chartSeriesStyle(token).color
      return <pattern key={token} id={`${prefix}-${token}`} width="8" height="8" patternUnits="userSpaceOnUse">
        <rect width="8" height="8" fill={color} />
        <PatternMark token={token} />
      </pattern>
    })}
  </defs>
}
