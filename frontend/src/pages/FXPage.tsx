import { useEffect, useId, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { useFX, useFXDetails } from '@/api/fx'
import { apiErrorMessage } from '@/api/client'
import { queryKeys } from '@/api/keys'
import { SkeletonTable } from '@/components/states/SkeletonTable'
import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDate } from '@/lib/format'
import type { FXBrowseParams, SharedFXRow } from '@/types/fx'
import { LegacyFXRates } from './LegacyFXRates'

const currencies = ['USD', 'EUR', 'GBP', 'RUB', 'CHF', 'PLN', 'CNY', 'USDT', 'USDC']

function RateDetails({ row, onClose }: { row: SharedFXRow | null; onClose: () => void }) {
  const query = useFXDetails(row?.details_token ?? null)
  const result = query.data?.result
  return <Dialog open={Boolean(row)} onOpenChange={(open) => { if (!open) onClose() }}>
    <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>Rate provenance</DialogTitle>
        <DialogDescription>{row?.from_currency} → {row?.to_currency} · {formatDate(row?.date)}</DialogDescription>
      </DialogHeader>
      {query.isLoading && <p role="status">Loading provenance…</p>}
      {query.isError && <ErrorState message="Provenance is temporarily unavailable. The table retains its synced rates." onRetry={() => query.refetch()} />}
      {result && <dl className="grid gap-2 break-words text-sm">
        <dt className="text-muted-foreground">Path</dt><dd>{result.path.join(' → ')}</dd>
        <dt className="text-muted-foreground">Snapshot sources</dt><dd>{[...new Set(Object.values(result.sources).flat())].join(', ') || 'Policy'}</dd>
        <dt className="text-muted-foreground">Snapshot observation dates (anchors)</dt>
        <dd>{Object.entries(result.observation_dates).map(([currency, date]) => <div key={currency}>{currency}: {formatDate(date)}</div>)}</dd>
        <dt className="text-muted-foreground">Release</dt><dd>{result.release_id}</dd>
        <dt className="text-muted-foreground">Snapshot</dt><dd>{result.snapshot_id}</dd>
        <dt className="text-muted-foreground">Policy</dt><dd>{result.policy_id}</dd>
        <dt className="text-muted-foreground">Snapshot observations</dt><dd>{result.observation_ids.map((id) => <div key={id}>{id}</div>)}</dd>
      </dl>}
    </DialogContent>
  </Dialog>
}

export function FXPage() {
  const queryClient = useQueryClient()
  const browsingId = useId()
  const [generation, setGeneration] = useState(0)
  const [filters, setFilters] = useState<FXBrowseParams>({ base: 'USD', quote: 'EUR' })
  const [pages, setPages] = useState<(string | null)[]>([null])
  const [selected, setSelected] = useState<SharedFXRow | null>(null)
  const query = useFX(filters, pages[pages.length - 1], `${browsingId}:${generation}`)
  const data = query.data
  useEffect(() => {
    if (data && !Array.isArray(data) && data.first && pages[0] === null) {
      queryClient.setQueryData(queryKeys.fx.browse(filters, data.first, `${browsingId}:${generation}`), data)
      setPages([data.first])
    }
  }, [browsingId, data, filters, generation, pages, queryClient])
  function restartRange() {
    setGeneration((previous) => previous + 1)
    setPages([null])
    setSelected(null)
  }
  function changeFilter(key: keyof FXBrowseParams, value: string) {
    setFilters((previous) => ({ ...previous, [key]: value || undefined }))
    restartRange()
  }
  if (Array.isArray(data)) return <LegacyFXRates data={data} />
  return <div className="space-y-4">
    <div>
      <h1 className="text-2xl font-bold">FX Rates</h1>
      <p className="text-sm text-muted-foreground">Shared daily reference rates. Choose one pair and up to 31 days.</p>
      <p className="text-xs text-muted-foreground">Rates sync automatically. Viewing a derived pair creates no reference records.</p>
    </div>
    <div className="flex flex-wrap items-end gap-3">
      {(['base', 'quote'] as const).map((key) => <div key={key} className="space-y-1">
        <label id={`fx-${key}-label`} className="text-xs text-muted-foreground">{key === 'base' ? 'From currency' : 'To currency'}</label>
        <Select value={filters[key]} onValueChange={(value) => { if (value) changeFilter(key, value) }}>
          <SelectTrigger aria-labelledby={`fx-${key}-label`} className="w-28"><SelectValue /></SelectTrigger>
          <SelectContent>{currencies.map((currency) => <SelectItem key={currency} value={currency}>{currency}</SelectItem>)}</SelectContent>
        </Select>
      </div>)}
      {(['start', 'end'] as const).map((key) => <div key={key} className="space-y-1">
        <label htmlFor={`fx-${key}`} className="text-xs text-muted-foreground">{key === 'start' ? 'Start date' : 'End date'}</label>
        <Input id={`fx-${key}`} type="date" value={filters[key] ?? ''} onChange={(event) => changeFilter(key, event.target.value)} className="w-[150px]" />
      </div>)}
      <Button variant="outline" onClick={restartRange}>Refresh range</Button>
    </div>
    {query.isLoading && <SkeletonTable />}
    {query.isError && <ErrorState message={`Failed to load FX rates. ${apiErrorMessage(query.error, 'Please retry.')}`} onRetry={restartRange} />}
    {data?.status === 'unsynced' && <EmptyState title="Shared rates have not synced yet" description="The scheduled FX sync has not completed. Rates are unavailable until it succeeds." />}
    {data?.status === 'empty' && <EmptyState title="No shared rates in this range" description="No completed snapshots are available. Try another date range after the next sync." />}
    {data?.status === 'ok' && <>
      <p className="text-xs text-muted-foreground">{data.count} valuation dates. Pages retain the release selected when this range was opened.</p>
      <div className="rounded-md border">
        <Table><TableHeader><TableRow>
          <TableHead>Valuation date</TableHead><TableHead>Direction</TableHead><TableHead className="text-right">Rate</TableHead><TableHead>Method</TableHead><TableHead>Source</TableHead><TableHead>Oldest anchor observation</TableHead><TableHead>Status</TableHead><TableHead><span className="sr-only">Details</span></TableHead>
        </TableRow></TableHeader><TableBody>
          {data.results.map((row) => <TableRow key={row.date}>
            <TableCell className="whitespace-nowrap">{formatDate(row.date)}</TableCell>
            <TableCell className="whitespace-nowrap">{row.direction}</TableCell>
            <TableCell className="text-right tabular-nums">{row.rate ?? `Rate unavailable: ${row.error?.replaceAll('_', ' ') ?? 'missing FX'}`}</TableCell>
            <TableCell>{row.kind === 'direct' ? 'Direct' : row.kind === 'derived' ? 'Derived' : 'Identity'}</TableCell>
            <TableCell>{row.sources.join(', ') || 'Policy'}</TableCell>
            <TableCell className="whitespace-nowrap">{formatDate(row.observation_date)}</TableCell>
            <TableCell><div className="flex flex-wrap gap-1">{row.carried_forward && <Badge variant="secondary">Carried forward</Badge>}{row.provisional && <Badge variant="secondary">Provisional</Badge>}{!row.carried_forward && !row.provisional && row.rate && 'Completed'}</div></TableCell>
            <TableCell><Button variant="outline" size="sm" disabled={!row.details_token} onClick={() => setSelected(row)}>Details</Button></TableCell>
          </TableRow>)}
        </TableBody></Table>
      </div>
      <div className="flex items-center justify-between">
        <Button variant="outline" disabled={pages.length === 1} onClick={() => setPages((previous) => previous.slice(0, -1))}>Previous</Button>
        <span className="text-xs text-muted-foreground">Page {pages.length}</span>
        <Button variant="outline" disabled={!data.next} onClick={() => setPages((previous) => [...previous, data.next])}>Next</Button>
      </div>
    </>}
    <RateDetails row={selected} onClose={() => setSelected(null)} />
  </div>
}
