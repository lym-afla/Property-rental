import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function App() {
  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <Card className="w-96">
        <CardHeader>
          <CardTitle>Property Rental SPA</CardTitle>
        </CardHeader>
        <CardContent>
          <Button>shadcn works</Button>
        </CardContent>
      </Card>
    </div>
  )
}

export default App
