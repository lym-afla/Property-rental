import { useState, type ReactNode } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

type Props = {
  title: string
  description?: string
  controls?: ReactNode  // frequency selector, timeline dropdown, etc.
  tableData?: { headers: string[]; rows: (string | number)[][] }  // for "view as table"
  // Optional override for the table body. When provided (e.g. by charts
  // that need pagination or per-cell formatting), it replaces the default
  // <Table> rendering. The toggle button is still shown iff `tableData`
  // is set; `tableRenderer` only customizes HOW the rows are displayed.
  tableRenderer?: ReactNode
  children: ReactNode   // the chart (ResponsiveContainer)
}

export function ChartCard({ title, description, controls, tableData, tableRenderer, children }: Props) {
  const [showTable, setShowTable] = useState(false)
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div>
          <CardTitle className="text-lg">{title}</CardTitle>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        <div className="flex items-center gap-2">
          {controls}
          {tableData && (
            <Button variant="ghost" size="sm" onClick={() => setShowTable(!showTable)}>
              {showTable ? 'Chart' : 'Table'}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {showTable && tableData ? (
          tableRenderer ?? (
            <Table>
              <TableHeader>
                <TableRow>{tableData.headers.map(h => <TableHead key={h}>{h}</TableHead>)}</TableRow>
              </TableHeader>
              <TableBody>
                {tableData.rows.map((row, i) => (
                  <TableRow key={i}>{row.map((cell, j) => <TableCell key={j}>{cell}</TableCell>)}</TableRow>
                ))}
              </TableBody>
            </Table>
          )
        ) : (
          <div className="h-[300px] w-full">{children}</div>
        )}
        {description && <span className="sr-only">{description}</span>}
      </CardContent>
    </Card>
  )
}
