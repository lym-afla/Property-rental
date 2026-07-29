import { SlidersHorizontal } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import type {
  DashboardComparison,
  DashboardCurrency,
  DashboardFilterState,
  DashboardGrain,
} from './filters'

type PropertyOption = { id: number; name: string }

type Props = {
  filters: DashboardFilterState
  properties: readonly PropertyOption[]
  onChange: (filters: DashboardFilterState) => void
  onReset: () => void
}

const CURRENCIES: DashboardCurrency[] = ['USD', 'EUR', 'GBP', 'RUB']
const DESKTOP_FILTER_QUERY = '(min-width: 768px)'
const GRAINS: { value: DashboardGrain; label: string }[] = [
  { value: 'month', label: 'Monthly' },
  { value: 'quarter', label: 'Quarterly' },
  { value: 'year', label: 'Yearly' },
]

export function DashboardFilters({ filters, properties, onChange, onReset }: Props) {
  const isDesktop = useDesktopFilterLayout()
  const update = (patch: Partial<DashboardFilterState>) =>
    onChange({ ...filters, ...patch })

  const toggleProperty = (propertyId: number, checked: boolean) => {
    const propertyIds = checked
      ? [...filters.propertyIds, propertyId]
      : filters.propertyIds.filter((id) => id !== propertyId)
    update({ propertyIds })
  }

  return (
    <div
      className="sticky top-0 z-30 rounded-xl border bg-background/95 p-3 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/85"
      aria-label="Global dashboard filters"
    >
      <div className="grid grid-cols-2 gap-2 md:flex md:flex-wrap md:items-end">
        <label className="min-w-0 space-y-1 text-xs font-medium text-muted-foreground">
          <span>From</span>
          <Input
            type="date"
            aria-label="Start date"
            value={filters.start}
            max={filters.end}
            onChange={(event) => update({ start: event.target.value })}
            className="min-h-11"
          />
        </label>
        <label className="min-w-0 space-y-1 text-xs font-medium text-muted-foreground">
          <span>As of</span>
          <Input
            type="date"
            aria-label="As of date"
            value={filters.end}
            min={filters.start}
            onChange={(event) => update({ end: event.target.value })}
            className="min-h-11"
          />
        </label>
        <div className="space-y-1 text-xs font-medium text-muted-foreground">
          <span>Currency</span>
          <Select
            value={filters.currency}
            onValueChange={(currency) => update({ currency: currency as DashboardCurrency })}
          >
            <SelectTrigger aria-label="Reporting currency" className="min-h-11 w-full md:w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CURRENCIES.map((currency) => (
                <SelectItem className="min-h-11" key={currency} value={currency}>{currency}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {isDesktop ? (
          <div className="flex items-end gap-2">
            <AdvancedSelects filters={filters} update={update} />
            <PropertyMenu
              filters={filters}
              properties={properties}
              onToggle={toggleProperty}
            />
          </div>
        ) : (
          <Sheet>
            <SheetTrigger asChild>
              <Button type="button" variant="outline" className="min-h-11">
                <SlidersHorizontal />
                Filters
              </Button>
            </SheetTrigger>
            <SheetContent side="bottom" aria-describedby="dashboard-filter-description">
              <SheetHeader>
                <SheetTitle>Dashboard filters</SheetTitle>
                <SheetDescription id="dashboard-filter-description">
                  Refine frequency, comparison, and portfolio scope.
                </SheetDescription>
              </SheetHeader>
              <div className="grid gap-5 overflow-y-auto pb-4">
                <AdvancedSelects filters={filters} update={update} mobile />
                <fieldset className="space-y-2">
                  <legend className="text-sm font-medium">Properties</legend>
                  {properties.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No properties available.</p>
                  ) : (
                    properties.map((property) => (
                      <label key={property.id} className="flex min-h-11 items-center gap-3 rounded-lg border px-3 text-sm">
                        <Checkbox
                          aria-label={property.name}
                          checked={filters.propertyIds.includes(property.id)}
                          onCheckedChange={(checked) => toggleProperty(property.id, checked === true)}
                        />
                        {property.name}
                      </label>
                    ))
                  )}
                </fieldset>
              </div>
            </SheetContent>
          </Sheet>
        )}

        <Button
          type="button"
          variant="ghost"
          className="min-h-11 md:ml-auto"
          aria-label="Reset dashboard filters"
          onClick={onReset}
        >
          Reset
        </Button>
      </div>
    </div>
  )
}

function useDesktopFilterLayout() {
  const [isDesktop, setIsDesktop] = useState(() => {
    if (typeof window.matchMedia !== 'function') return true
    return window.matchMedia(DESKTOP_FILTER_QUERY).matches
  })

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return

    const mediaQuery = window.matchMedia(DESKTOP_FILTER_QUERY)
    const updateLayout = () => setIsDesktop(mediaQuery.matches)
    mediaQuery.addEventListener('change', updateLayout)
    updateLayout()

    return () => mediaQuery.removeEventListener('change', updateLayout)
  }, [])

  return isDesktop
}

function AdvancedSelects({
  filters,
  update,
  mobile = false,
}: {
  filters: DashboardFilterState
  update: (patch: Partial<DashboardFilterState>) => void
  mobile?: boolean
}) {
  return (
    <>
      <div className="space-y-1 text-xs font-medium text-muted-foreground">
        <span>Frequency</span>
        <Select
          value={filters.grain}
          onValueChange={(grain) => update({ grain: grain as DashboardGrain })}
        >
          <SelectTrigger aria-label="Frequency" className={mobile ? 'min-h-11 w-full' : 'min-h-11 w-32'}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {GRAINS.map((grain) => (
              <SelectItem className="min-h-11" key={grain.value} value={grain.value}>{grain.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1 text-xs font-medium text-muted-foreground">
        <span>Comparison</span>
        <Select
          value={filters.comparison ?? 'none'}
          onValueChange={(comparison) =>
            update({ comparison: comparison === 'none' ? null : comparison as DashboardComparison })
          }
        >
          <SelectTrigger aria-label="Comparison" className={mobile ? 'min-h-11 w-full' : 'min-h-11 w-40'}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem className="min-h-11" value="none">No comparison</SelectItem>
            <SelectItem className="min-h-11" value="previous_period">Previous period</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </>
  )
}

function PropertyMenu({
  filters,
  properties,
  onToggle,
}: {
  filters: DashboardFilterState
  properties: readonly PropertyOption[]
  onToggle: (propertyId: number, checked: boolean) => void
}) {
  const label = filters.propertyIds.length === 0
    ? 'All properties'
    : `${filters.propertyIds.length} selected`
  return (
    <div className="space-y-1 text-xs font-medium text-muted-foreground">
      <span>Properties</span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="outline" className="min-h-11 min-w-36" aria-label="Properties">
            {label}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="min-w-56">
          <DropdownMenuLabel>Select properties</DropdownMenuLabel>
          {properties.map((property) => (
            <DropdownMenuCheckboxItem
              key={property.id}
              className="min-h-11"
              checked={filters.propertyIds.includes(property.id)}
              onCheckedChange={(checked) => onToggle(property.id, checked === true)}
              onSelect={(event) => event.preventDefault()}
            >
              {property.name}
            </DropdownMenuCheckboxItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
