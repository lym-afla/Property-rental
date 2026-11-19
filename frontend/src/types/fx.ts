// Mirrors `FXSerializer` in
// `property_rental/rentals/api/serializers.py`. Field names MUST match the
// serializer exactly (snake_case preserved on purpose).
export type FX = {
  id: number
  date: string
  from_currency: string
  to_currency: string
  rate: string  // Decimal as string
}

export type FXBrowseParams = {
  base?: string
  quote?: string
  start?: string
  end?: string
}

export type SharedFXRow = {
  date: string
  from_currency: string
  to_currency: string
  rate: string | null
  direction: string
  kind: 'direct' | 'derived' | 'identity'
  path: string[]
  sources: string[]
  observation_date: string | null
  carried_forward: boolean
  status: 'completed' | 'carried' | 'held' | null
  statuses: Record<string, 'completed' | 'carried' | 'held'>
  source_date: string | null
  provisional: boolean
  effective_date: string | null
  release_id: string
  snapshot_id: string | null
  error: string | null
  details_token: string | null
}

export type SharedFXPage = {
  backend: 'mirror'
  status: 'ok' | 'empty' | 'unsynced'
  release_id: string | null
  count: number
  first: string
  next: string | null
  results: SharedFXRow[]
}

export type FXDetails = {
  status: 'ok'
  result: {
    release_id: string
    snapshot_id: string
    policy_id: string
    path: string[]
    observation_ids: string[]
    observation_dates: Record<string, string>
    sources: Record<string, string[]>
  }
}
