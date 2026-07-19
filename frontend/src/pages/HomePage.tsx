import { useSession } from '@/context/SessionProvider'

export function HomePage() {
  const { user } = useSession()
  return (
    <div>
      <h1 className="text-2xl font-bold">Welcome, {user?.first_name || user?.username}</h1>
      <p className="text-muted-foreground mt-2">Dashboard arrives in Plan C.</p>
    </div>
  )
}
