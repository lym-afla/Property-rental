import { chartSeriesStyle, type SeriesVisualToken } from './chartTheme'

const tokens: SeriesVisualToken[] = ['primary', 'secondary', 'tertiary', 'default']

export function ChartPatternDefs({ prefix }: { prefix: string }) {
  return <defs>
    {tokens.map((token, index) => {
      const color = chartSeriesStyle(token).color
      return <pattern key={token} id={`${prefix}-${token}`} width="8" height="8" patternUnits="userSpaceOnUse">
        <rect width="8" height="8" fill={color} />
        {index === 1 && <path d="M-2 2 L2 -2 M0 8 L8 0 M6 10 L10 6" stroke="white" strokeOpacity="0.75" strokeWidth="1.5" />}
        {index === 2 && <path d="M0 0 L8 8 M8 0 L0 8" stroke="white" strokeOpacity="0.7" strokeWidth="1" />}
        {index === 3 && <circle cx="4" cy="4" r="1.5" fill="white" fillOpacity="0.8" />}
      </pattern>
    })}
  </defs>
}
