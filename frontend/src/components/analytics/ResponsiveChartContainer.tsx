import { ResponsiveContainer, type ResponsiveContainerProps } from 'recharts'

const initialDimension = { width: 1, height: 300 }

export function ResponsiveChartContainer({
  initialDimension: providedInitialDimension = initialDimension,
  minWidth = 0,
  ...props
}: ResponsiveContainerProps) {
  return <ResponsiveContainer minWidth={minWidth} initialDimension={providedInitialDimension} {...props} />
}
