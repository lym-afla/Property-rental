// frontend/src/components/charts/CurrencyExposureChart.tsx
//
// Horizontal bar chart showing portfolio exposure grouped by currency.
//
// The chart fetches TWO `with_stats` snapshots:
//   - `currency=<userCurrency>` -> FX-converted totals so every bar sits
//                                  on a single-currency axis and is
//                                  directly comparable. `userCurrency` is
//                                  the user's `default_currency` (USD by
//                                  default).
//   - `currency='native'` -> each property's native-currency total so the
//                            table can show the face-value amount per
//                            currency group alongside the user-currency
//                            figure.
//
// Grouping key is the property's NATIVE `currency` (RUB/GBP/etc.) — that
// is what the user thinks of as "exposure to currency X". The BAR VALUES
// are FX-converted into the user's `default_currency`, so the chart is a
// single-currency comparison rather than a mix of ₽/£/$ amounts that
// can't be visually ranked.
//
// Honest about what `with_stats` supports: the endpoint only computes
// ALL-TIME and YTD aggregates — it does NOT support arbitrary date
// ranges. The previous version exposed a timeline selector (YTD / 3m /
// 6m / 12m / 3Y / 5Y / All) that mapped to an `as_of` param, but
// `as_of` is only the upper bound of the all-time window — it does NOT
// produce "last 3 months" totals. The selector was therefore misleading
// (a "Last 3 months" click returned all-time net income), so it has
// been removed. The chart now shows ALL-TIME net income by currency
// with a clear title.
import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { usePropertiesWithStats } from '@/api/properties'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'
import { useSession } from '@/context/SessionProvider'
import { colorForCategory } from './_chartTheme'

type ExposureRow = {
  currency: string    // native currency (RUB/GBP) — Y axis label + table key
  nativeValue: number // sum of native-currency net income across properties
  usdValue: number    // same sum, FX-converted to user currency (the chart value)
}

export function CurrencyExposureChart() {
  // The user's preferred display currency drives the FX-converted totals
  // (the bar values). Falls back to USD when the session has not loaded
  // yet or the user never picked a currency.
  const { user } = useSession()
  const userCurrency = user?.default_currency || 'USD'

  // Two parallel snapshots: user-currency-converted (for the chart axis)
  // and native (for the table's "face value" column). React Query dedupes
  // them by query key. `asOf` is intentionally omitted — `with_stats`
  // defaults to today, which (as the upper bound of the all-time window)
  // includes every transaction.
  const usdStats = usePropertiesWithStats(undefined, userCurrency)
  const nativeStats = usePropertiesWithStats(undefined, 'native')

  const chartData = useMemo(() => {
    const byCurrency = new Map<string, ExposureRow>()
    // USD-converted values drive the bar lengths; group properties by
    // their NATIVE currency so the Y axis still labels the exposure the
    // user cares about.
    for (const p of usdStats.data ?? []) {
      const cur = p.currency || '???'
      const usdValue = Math.abs(p.net_income_all_time ?? 0)
      const existing = byCurrency.get(cur)
      if (existing) existing.usdValue += usdValue
      else byCurrency.set(cur, { currency: cur, nativeValue: 0, usdValue })
    }
    // Native-currency totals fill the table's "face value" column.
    for (const p of nativeStats.data ?? []) {
      const cur = p.currency || '???'
      const nativeValue = Math.abs(p.net_income_all_time ?? 0)
      const existing = byCurrency.get(cur)
      if (existing) existing.nativeValue += nativeValue
      else byCurrency.set(cur, { currency: cur, nativeValue, usdValue: 0 })
    }
    return Array.from(byCurrency.values()).sort((a, b) => b.usdValue - a.usdValue)
  }, [usdStats.data, nativeStats.data])

  const tableData = useMemo(
    () => ({
      // Two value columns: native-currency face value + user-currency.
      headers: ['Currency', 'Native', userCurrency],
      rows: chartData.map(row => [
        row.currency,
        formatCurrency(row.nativeValue, row.currency),
        formatCurrency(row.usdValue, userCurrency),
      ]),
    }),
    [chartData, userCurrency],
  )

  if (usdStats.isLoading || nativeStats.isLoading) {
    return (
      <ChartCard
        title="Net income by currency"
        description={`All-time net income (${userCurrency}-converted)`}
        tableData={tableData}
      >
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      </ChartCard>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartCard
        title="Net income by currency"
        description={`All-time net income (${userCurrency}-converted)`}
        tableData={tableData}
      >
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          No data
        </div>
      </ChartCard>
    )
  }

  return (
    <ChartCard
      title="Net income by currency"
      description={`All-time net income (${userCurrency}-converted)`}
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis type="number" tickFormatter={(v) => formatCurrencyAxis(v, userCurrency)} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="currency" tick={{ fontSize: 12 }} width={50} />
          <Tooltip formatter={(v) => formatCurrency(Number(v), userCurrency)} />
          <Bar dataKey="usdValue" name={`Net income (${userCurrency})`}>
            {chartData.map((entry, i) => (
              <Cell key={`cell-${i}`} fill={colorForCategory(entry.currency, i)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
