// frontend/src/components/states/SkeletonTable.tsx
//
// Loading placeholder for DataTable. Renders `rows` grey rows of `cols`
// shimmering cells plus a faux pagination footer so the layout doesn't
// jump when the real data arrives.
//
// The default 5x5 grid matches the default DataTable `pageSize` of 10
// visually (5 rows is enough to communicate "table loading" without
// stealing half the viewport).
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type Props = {
  rows?: number
  cols?: number
}

export function SkeletonTable({ rows = 5, cols = 5 }: Props) {
  return (
    <div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {Array.from({ length: cols }).map((_, c) => (
                <TableHead key={c}>
                  <Skeleton className="h-4 w-24" />
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: rows }).map((_, r) => (
              <TableRow key={r}>
                {Array.from({ length: cols }).map((_, c) => (
                  <TableCell key={c}>
                    <Skeleton className="h-4 w-full max-w-[160px]" />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end space-x-2 py-4">
        <Skeleton className="h-7 w-20" />
        <Skeleton className="h-7 w-20" />
      </div>
    </div>
  )
}
