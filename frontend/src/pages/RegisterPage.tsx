import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useRegister } from '@/api/auth'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const register = useRegister()
  const navigate = useNavigate()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors({})
    if (password !== passwordConfirm) {
      setErrors({ password: 'Passwords do not match' })
      return
    }
    register.mutate(
      { username, email, password },
      {
        onSuccess: () => navigate('/'),
        onError: (err) => {
          if (err instanceof ApiError && err.body && typeof err.body === 'object') {
            setErrors(err.body as Record<string, string>)
          } else {
            setErrors({ general: 'Registration failed' })
          }
        },
      }
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Create account</CardTitle>
          <CardDescription>Register as a landlord to manage your properties.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
              {errors.username && <p className="text-sm text-destructive" role="alert">{errors.username}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
              {errors.email && <p className="text-sm text-destructive" role="alert">{errors.email}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required />
              {errors.password && <p className="text-sm text-destructive" role="alert">{errors.password}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="passwordConfirm">Confirm password</Label>
              <Input id="passwordConfirm" type="password" value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} autoComplete="new-password" required />
            </div>
            {errors.general && <p className="text-sm text-destructive" role="alert">{errors.general}</p>}
            <Button type="submit" className="w-full" disabled={register.isPending}>
              {register.isPending ? 'Creating…' : 'Register'}
            </Button>
            <p className="text-sm text-center text-muted-foreground">
              Already have an account? <Link to="/login" className="underline">Log in</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
