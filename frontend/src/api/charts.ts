import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'

export type ChartDataset = { label?: string; data: number[] }
export type ChartDataResponse = { labels: string[]; datasets: ChartDataset[]; currency: string }

export type ChartDataParams = {
  type: 'homePage' | 'property' | 'tenant'
  elementId?: number
  frequency?: string
  start?: string
  end?: string
  currency?: string
}

export function useChartData(params: ChartDataParams) {
  return useQuery<ChartDataResponse>({
    queryKey: queryKeys.chartData.filtered({
      type: params.type,
      id: params.elementId ?? '',
      freq: params.frequency,
      start: params.start,
      end: params.end,
      currency: params.currency,
    }),
    queryFn: () =>
      apiFetch<ChartDataResponse>('/chart-data/', {
        query: {
          type: params.type,
          id: params.elementId,
          freq: params.frequency,
          start: params.start,
          end: params.end,
          currency: params.currency,
        },
      }),
    enabled: !!params.type,
    staleTime: 0,
  })
}
