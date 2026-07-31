import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

export function FinancialDefinitions() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="min-h-11 min-w-11 rounded-full"
          aria-label="Yield definitions"
        >
          <span
            aria-hidden="true"
            className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-muted text-sm font-semibold text-muted-foreground"
          >
            i
          </span>
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yield definitions</DialogTitle>
          <DialogDescription className="space-y-3">
            <span className="block">Gross yield — annualized rental income net of costs divided by the latest property value.</span>
            <span className="block">Equity yield — annualized rental income net of costs divided by equity.</span>
            <span className="block">Equity — latest property value less latest debt, using records available as of the selected date.</span>
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  )
}
