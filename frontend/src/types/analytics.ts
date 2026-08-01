import { z } from 'zod'

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

function isCalendarDate(value: string): boolean {
  if (!ISO_DATE_PATTERN.test(value)) return false
  if (value.startsWith('0000-')) return false
  const parsed = new Date(`${value}T00:00:00.000Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

export const isoDateSchema = z.string().refine(isCalendarDate, {
  message: 'Expected a valid ISO date in YYYY-MM-DD format',
})
export const analyticsGrainSchema = z.enum(['month', 'quarter', 'year'])
export const analyticsCurrencySchema = z.string().regex(/^[A-Z]{3}$/)
export const propertyBreakdownMeasureSchema = z.enum([
  'property_value',
  'equity',
  'debt',
  'rental_income',
])

export type AnalyticsGrain = z.infer<typeof analyticsGrainSchema>
export type PropertyBreakdownMeasure = z.infer<typeof propertyBreakdownMeasureSchema>
export type PortfolioAnalyticsParams = {
  start?: string
  end?: string
  currency?: string
  grain?: AnalyticsGrain
  comparison?: 'previous_period' | null
  propertyIds?: readonly number[]
}
export type ProfitLossParams = Pick<
  PortfolioAnalyticsParams,
  'end' | 'currency' | 'propertyIds'
> & { end: string; currency: string }
export type PropertyBreakdownParams = PortfolioAnalyticsParams & {
  measure: PropertyBreakdownMeasure
}
export type TenantRentPerformanceParams = Pick<
  PortfolioAnalyticsParams,
  'start' | 'end' | 'grain' | 'comparison'
>

export const seriesDefinitionSchema = z
  .object({
    key: z.string().trim().min(1),
    label: z.string().trim().min(1),
    kind: z.string().trim().min(1),
  })
  .strict()

const profitLossCategoryKeySchema = z.string().trim().min(1).refine(
  (key) => !['total_revenue', 'total_expenses', 'net_income'].includes(key),
  { message: 'Category key collides with a total row key' },
)

const profitLossValuesSchema = z.record(z.string(), z.number())
const profitLossCategoryRowBase = {
  key: profitLossCategoryKeySchema,
  label: z.string().trim().min(1),
  values: profitLossValuesSchema,
}
const profitLossRowSchema = z.discriminatedUnion('kind', [
  z.object({ ...profitLossCategoryRowBase, kind: z.literal('income') }).strict(),
  z.object({ ...profitLossCategoryRowBase, kind: z.literal('expense') }).strict(),
  z.object({ key: z.literal('total_revenue'), label: z.string().trim().min(1), kind: z.literal('total_revenue'), values: profitLossValuesSchema }).strict(),
  z.object({ key: z.literal('total_expenses'), label: z.string().trim().min(1), kind: z.literal('total_expenses'), values: profitLossValuesSchema }).strict(),
  z.object({ key: z.literal('net_income'), label: z.string().trim().min(1), kind: z.literal('net_income'), values: profitLossValuesSchema }).strict(),
])

export const profitLossSchema = z
  .object({
    metric: z.literal('profit_and_loss'),
    currency: analyticsCurrencySchema,
    scale: z.literal(1),
    end: isoDateSchema,
    columns: z.array(z.object({
      key: z.string().trim().min(1),
      label: z.string().trim().min(1),
      start: isoDateSchema,
      end: isoDateSchema,
    }).strict()).min(1),
    rows: z.array(profitLossRowSchema),
  })
  .strict()
  .superRefine((value, context) => {
    const columnKeys = value.columns.map(({ key }) => key)
    if (new Set(columnKeys).size !== columnKeys.length) {
      context.addIssue({ code: 'custom', path: ['columns'], message: 'column keys must be unique' })
    }
    if (columnKeys.some((key) => !/^\d{4}$/.test(key)) || columnKeys.some((key, index) => index > 0 && key <= columnKeys[index - 1])) {
      context.addIssue({ code: 'custom', path: ['columns'], message: 'columns must be chronological years' })
    }
    if (columnKeys.at(-1) !== value.end.slice(0, 4)) {
      context.addIssue({ code: 'custom', path: ['columns'], message: 'final column must be the statement end year' })
    }
    value.columns.forEach((column, index) => {
      const isFinal = index === value.columns.length - 1
      const expectedLabel = isFinal ? `${column.key}YTD` : column.key
      if (column.label !== expectedLabel) {
        context.addIssue({ code: 'custom', path: ['columns', index, 'label'], message: `label must be ${expectedLabel}` })
      }
    })
    if (value.columns.some((column) => column.key !== column.start.slice(0, 4) || column.key !== column.end.slice(0, 4))) {
      context.addIssue({ code: 'custom', path: ['columns'], message: 'column boundaries must stay within the keyed year' })
    }
    value.columns.forEach((column, index) => {
      if (column.end < column.start) {
        context.addIssue({ code: 'custom', path: ['columns', index, 'end'], message: 'end must be on or after start' })
      }
    })
    const expectedKeys = new Set(columnKeys)
    const rowKeys = value.rows.map(({ key }) => key)
    if (new Set(rowKeys).size !== rowKeys.length) {
      context.addIssue({ code: 'custom', path: ['rows'], message: 'row keys must be unique' })
    }
    for (const kind of ['total_revenue', 'total_expenses', 'net_income'] as const) {
      if (value.rows.filter((row) => row.kind === kind).length !== 1) {
        context.addIssue({ code: 'custom', path: ['rows'], message: `statement must contain exactly one ${kind} row` })
      }
    }
    value.rows.forEach((row, index) => {
      const actualKeys = Object.keys(row.values)
      if (actualKeys.length !== expectedKeys.size || actualKeys.some((key) => !expectedKeys.has(key))) {
        context.addIssue({ code: 'custom', path: ['rows', index, 'values'], message: 'values must contain exactly every declared column key' })
      }
    })
  })

const dynamicPointSchema = z
  .object({
    period_start: isoDateSchema,
    period_end: isoDateSchema,
  })
  .catchall(z.number().nullable())

const cashFlowSeriesDefinitionSchema = z
  .object({
    key: z.string().trim().min(1),
    label: z.string().trim().min(1),
    kind: z.enum([
      'income_category',
      'expense_category',
      'income_total',
      'expense_total',
      'net',
      'cumulative',
    ]),
  })
  .strict()

const cashFlowPointSchema = z
  .object({
    period_start: isoDateSchema,
    period_end: isoDateSchema,
    total_income: z.number(),
    total_expenses: z.number(),
    net_income: z.number(),
    cumulative_net_income: z.number(),
  })
  .catchall(z.number().nullable())

const occupancySeriesSchema = z.tuple([
  z.object({ key: z.literal('capacity'), label: z.literal('Capacity'), kind: z.literal('capacity') }).strict(),
  z.object({ key: z.literal('occupied'), label: z.literal('Occupied'), kind: z.literal('occupied') }).strict(),
  z.object({ key: z.literal('vacant'), label: z.literal('Vacant'), kind: z.literal('vacant') }).strict(),
  z.object({ key: z.literal('occupancy_rate'), label: z.literal('Occupancy rate'), kind: z.literal('percentage') }).strict(),
])

const occupancyPointSchema = z
  .object({
    period_start: isoDateSchema,
    period_end: isoDateSchema,
    capacity: z.number().int().nonnegative(),
    occupied: z.number().int().nonnegative(),
    vacant: z.number().int().nonnegative(),
    occupancy_rate: z.number().min(0).max(100),
  })
  .strict()
  .superRefine((point, context) => {
    if (point.occupied + point.vacant !== point.capacity) {
      context.addIssue({
        code: 'custom',
        path: ['capacity'],
        message: 'occupied plus vacant must equal capacity',
      })
    }
    const expectedRate = point.capacity === 0
      ? 0
      : (point.occupied / point.capacity) * 100
    if (Math.abs(point.occupancy_rate - expectedRate) > 0.000001) {
      context.addIssue({
        code: 'custom',
        path: ['occupancy_rate'],
        message: 'occupancy_rate must match occupied divided by capacity',
      })
    }
  })

const timeSeriesBaseShape = {
  metric: z.string().trim().min(1),
  grain: analyticsGrainSchema,
  currency: analyticsCurrencySchema.nullable(),
  scale: z.literal(1),
  start: isoDateSchema,
  end: isoDateSchema,
  series: z.array(seriesDefinitionSchema),
  points: z.array(dynamicPointSchema),
}

type TimeSeriesValidationValue = {
  start: string
  end: string
  series: Array<{ key: string }>
  points: Array<
    Record<string, unknown> & { period_start: string; period_end: string }
  >
}

function validateTimeSeries(
  value: TimeSeriesValidationValue,
  context: z.core.$RefinementCtx<unknown>,
  requireAllSeriesKeys = true,
): void {
  if (value.end < value.start) {
    context.addIssue({
      code: 'custom',
      path: ['end'],
      message: 'end must be on or after start',
    })
  }
  const keys = value.series.map((series) => series.key)
  const reservedPointKeys = new Set([
    'period_start',
    'period_end',
    ...Object.getOwnPropertyNames(Object.prototype),
  ])
  keys.forEach((key, seriesIndex) => {
    if (reservedPointKeys.has(key)) {
      context.addIssue({
        code: 'custom',
        path: ['series', seriesIndex, 'key'],
        message: 'series key collides with a reserved point key',
      })
    }
  })
  if (new Set(keys).size !== keys.length) {
    context.addIssue({
      code: 'custom',
      path: ['series'],
      message: 'series keys must be unique',
    })
  }
  const expectedKeys = new Set(['period_start', 'period_end', ...keys])
  value.points.forEach((point, pointIndex) => {
    if (point.period_end < point.period_start) {
      context.addIssue({
        code: 'custom',
        path: ['points', pointIndex, 'period_end'],
        message: 'period_end must be on or after period_start',
      })
    }
    for (const key of Object.keys(point)) {
      if (!expectedKeys.has(key)) {
        context.addIssue({
          code: 'custom',
          path: ['points', pointIndex, key],
          message: 'point contains an undeclared series key',
        })
      }
    }
    for (const key of keys) {
      if (requireAllSeriesKeys && !Object.hasOwn(point, key)) {
        context.addIssue({
          code: 'custom',
          path: ['points', pointIndex, key],
          message: 'point is missing a declared series key',
        })
      }
    }
  })
}

function makeTimeSeriesSchema<T extends z.ZodRawShape>(overrides: T) {
  return z
    .object({ ...timeSeriesBaseShape, ...overrides })
    .strict()
    .superRefine((value, context) =>
      validateTimeSeries(value as TimeSeriesValidationValue, context),
    )
}

export const timeSeriesSchema = makeTimeSeriesSchema({})
export const portfolioCashFlowSchema = makeTimeSeriesSchema({
  metric: z.literal('portfolio_cash_flow'),
  currency: analyticsCurrencySchema,
  series: z.array(cashFlowSeriesDefinitionSchema),
  points: z.array(cashFlowPointSchema),
}).superRefine((value, context) => {
  const required = [
    ['total_income', 'income_total'],
    ['total_expenses', 'expense_total'],
    ['net_income', 'net'],
    ['cumulative_net_income', 'cumulative'],
  ] as const
  for (const [key, kind] of required) {
    if (!value.series.some((series) => series.key === key && series.kind === kind)) {
      context.addIssue({
        code: 'custom',
        path: ['series'],
        message: `cash-flow series must declare ${key} as ${kind}`,
      })
    }
  }
})
export const expenseDriversSchema = makeTimeSeriesSchema({
  metric: z.literal('expense_drivers'),
  currency: analyticsCurrencySchema,
  series: z.array(
    z.object({
      key: z.string().trim().min(1),
      label: z.string().trim().min(1),
      kind: z.literal('expense_category'),
    }).strict(),
  ),
})
export const portfolioOccupancySchema = z
  .object({
    metric: z.literal('portfolio_occupancy'),
    grain: analyticsGrainSchema,
    currency: z.null(),
    scale: z.literal(1),
    start: isoDateSchema,
    end: isoDateSchema,
    series: occupancySeriesSchema,
    points: z.array(occupancyPointSchema),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.end < value.start) {
      context.addIssue({ code: 'custom', path: ['end'], message: 'end must be on or after start' })
    }
    value.points.forEach((point, index) => {
      if (point.period_end < point.period_start) {
        context.addIssue({ code: 'custom', path: ['points', index, 'period_end'], message: 'period_end must be on or after period_start' })
      }
    })
  })

const valuationCoverageStatusSchema = z.enum([
  'ok',
  'stale_valuation',
  'partial_valuation',
  'missing_valuation',
  'missing_currency',
])
const independentValuationStatusSchema = z.enum([
  'ok',
  'stale_valuation',
  'missing_valuation',
  'missing_currency',
])

export const portfolioSummarySchema = z
  .object({
    currency: analyticsCurrencySchema,
    scale: z.literal(1),
    start: isoDateSchema,
    end: isoDateSchema,
    property_count: z.number().int().nonnegative(),
    rental_inventory_count: z.number().int().nonnegative(),
    occupied: z.number().int().nonnegative(),
    occupancy_rate: z.number().min(0).max(100),
    revenue: z.number(),
    costs: z.number().nonnegative(),
    net_income: z.number(),
    property_value: z.number().nullable(),
    debt: z.number().nullable(),
    equity: z.number().nullable(),
    valuation_status: valuationCoverageStatusSchema,
    property_value_status: independentValuationStatusSchema,
    debt_status: independentValuationStatusSchema,
  })
  .strict()
  .refine((value) => value.end >= value.start, {
    path: ['end'],
    message: 'end must be on or after start',
  })

export const propertyContributionSchema = z
  .object({
    metric: z.literal('property_contribution'),
    currency: analyticsCurrencySchema,
    scale: z.literal(1),
    start: isoDateSchema,
    end: isoDateSchema,
    portfolio_net_income: z.number(),
    rows: z.array(
      z
        .object({
          property_id: z.number().int().positive(),
          property_name: z.string().trim().min(1),
          revenue: z.number(),
          costs: z.number().nonnegative(),
          net_income: z.number(),
          portfolio_share: z.number().nullable(),
        })
        .strict(),
    ),
  })
  .strict()
  .refine((value) => value.end >= value.start, {
    path: ['end'],
    message: 'end must be on or after start',
  })

const yieldStatusSchema = z.enum([
  'ok',
  'stale_valuation',
  'missing_valuation',
  'missing_currency',
  'zero_valuation',
  'negative_valuation',
  'zero_equity',
  'negative_equity',
])

export const propertyYieldsSchema = z
  .object({
    metric: z.literal('property_yields'),
    currency: analyticsCurrencySchema,
    scale: z.literal(1),
    start: isoDateSchema,
    end: isoDateSchema,
    rows: z.array(
      z
        .object({
          property_id: z.number().int().positive(),
          property_name: z.string().trim().min(1),
          valuation_date: isoDateSchema.nullable(),
          property_value: z.number().nullable(),
          debt: z.number().nullable(),
          equity: z.number().nullable(),
          annualized_revenue: z.number().nullable(),
          annualized_costs: z.number().nullable(),
          gross_yield: z.number().nullable(),
          equity_yield: z.number().nullable(),
          status: yieldStatusSchema,
        })
        .strict(),
    ),
  })
  .strict()
  .refine((value) => value.end >= value.start, {
    path: ['end'],
    message: 'end must be on or after start',
  })

const propertyBreakdownCoverageSchema = z
  .object({
    period_start: isoDateSchema,
    period_end: isoDateSchema,
    property_id: z.number().int().positive(),
    status: z.enum([
      'ok',
      'stale_valuation',
      'missing_valuation',
      'missing_currency',
    ]),
  })
  .strict()
  .refine((value) => value.period_end >= value.period_start, {
    path: ['period_end'],
    message: 'period_end must be on or after period_start',
  })

export const propertyBreakdownSchema = z.object({
  ...timeSeriesBaseShape,
  metric: z.literal('property_breakdown'),
  currency: analyticsCurrencySchema,
  measure: propertyBreakdownMeasureSchema,
  measure_label: z.string().trim().min(1),
  coverage: z.array(propertyBreakdownCoverageSchema),
}).strict().superRefine((value, context) =>
  validateTimeSeries(value as TimeSeriesValidationValue, context, false),
)

const propertyValuationPointSchema = z
  .object({
    period_start: isoDateSchema,
    period_end: isoDateSchema,
    total_value: z.number().nullable(),
    debt: z.number().nullable(),
    equity: z.number().nullable(),
    status: z.enum([
      'ok',
      'missing_value',
      'missing_debt',
      'missing_value_and_debt',
      'interpolated',
      'carried_forward',
    ]),
  })
  .strict()
  .refine((value) => value.period_end >= value.period_start, {
    path: ['period_end'],
    message: 'period_end must be on or after period_start',
  })

const propertyValuationSeriesSchema = z.tuple([
  z
    .object({
      key: z.literal('total_value'),
      label: z.literal('Total value'),
      kind: z.literal('total'),
    })
    .strict(),
  z
    .object({
      key: z.literal('debt'),
      label: z.literal('Debt'),
      kind: z.literal('debt'),
    })
    .strict(),
  z
    .object({
      key: z.literal('equity'),
      label: z.literal('Equity'),
      kind: z.literal('equity'),
    })
    .strict(),
])

export const propertyValuationSchema = z
  .object({
    metric: z.literal('property_valuation'),
    grain: z.literal('record'),
    currency: analyticsCurrencySchema.nullable(),
    scale: z.literal(1),
    start: isoDateSchema,
    end: isoDateSchema,
    status: z.enum([
      'ok',
      'partial_valuation',
      'missing_valuation',
      'missing_currency',
    ]),
    series: propertyValuationSeriesSchema,
    points: z.array(propertyValuationPointSchema),
  })
  .strict()
  .refine((value) => value.end >= value.start, {
    path: ['end'],
    message: 'end must be on or after start',
  })

export const tenantIssueSchema = z.enum([
  'missing_rent_rate',
  'missing_expected_currency',
  'missing_expected_fx',
  'missing_received_currency',
  'missing_received_fx',
  'incomplete_opening_history',
  'incomplete_cumulative_history',
])

const tenantRentPointSchema = z
  .object({
    period_start: isoDateSchema,
    period_end: isoDateSchema,
    expected: z.number().nullable(),
    received: z.number().nullable(),
    variance: z.number().nullable(),
    cumulative_arrears: z.number().nullable(),
    status: z.enum([
      'ok',
      'missing_rent_rate',
      'missing_currency',
      'missing_fx',
      'incomplete_history',
    ]),
    issues: z.array(tenantIssueSchema),
  })
  .strict()
  .refine((value) => value.period_end >= value.period_start, {
    path: ['period_end'],
    message: 'period_end must be on or after period_start',
  })

const tenantRentSeriesSchema = z.tuple([
  z
    .object({
      key: z.literal('expected'),
      label: z.literal('Expected rent'),
      kind: z.literal('expected'),
    })
    .strict(),
  z
    .object({
      key: z.literal('received'),
      label: z.literal('Received rent'),
      kind: z.literal('received'),
    })
    .strict(),
  z
    .object({
      key: z.literal('variance'),
      label: z.literal('Variance'),
      kind: z.literal('variance'),
    })
    .strict(),
  z
    .object({
      key: z.literal('cumulative_arrears'),
      label: z.literal('Cumulative arrears'),
      kind: z.literal('cumulative'),
    })
    .strict(),
])

export const tenantRentPerformanceSchema = z
  .object({
    metric: z.literal('tenant_rent_performance'),
    grain: analyticsGrainSchema,
    currency: analyticsCurrencySchema,
    scale: z.literal(1),
    start: isoDateSchema,
    end: isoDateSchema,
    opening_arrears: z.number().nullable(),
    opening_issues: z.array(tenantIssueSchema),
    status: z.enum([
      'ok',
      'partial_data',
      'missing_rent_rate',
      'missing_currency',
      'missing_fx',
      'incomplete_history',
    ]),
    issues: z.array(tenantIssueSchema),
    series: tenantRentSeriesSchema,
    points: z.array(tenantRentPointSchema),
  })
  .strict()
  .refine((value) => value.end >= value.start, {
    path: ['end'],
    message: 'end must be on or after start',
  })

export type TimeSeriesResponse = z.infer<typeof timeSeriesSchema>
export type PortfolioCashFlowResponse = z.infer<typeof portfolioCashFlowSchema>
export type ExpenseDriversResponse = z.infer<typeof expenseDriversSchema>
export type PortfolioOccupancyResponse = z.infer<
  typeof portfolioOccupancySchema
>
export type PortfolioSummaryResponse = z.infer<typeof portfolioSummarySchema>
export type ProfitLossResponse = z.infer<typeof profitLossSchema>
export type PropertyContributionResponse = z.infer<
  typeof propertyContributionSchema
>
export type PropertyYieldsResponse = z.infer<typeof propertyYieldsSchema>
export type PropertyBreakdownResponse = z.infer<typeof propertyBreakdownSchema>
export type PropertyValuationAnalyticsResponse = z.infer<
  typeof propertyValuationSchema
>
export type TenantRentPerformanceResponse = z.infer<
  typeof tenantRentPerformanceSchema
>
