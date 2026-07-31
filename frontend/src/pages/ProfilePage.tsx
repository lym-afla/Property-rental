// frontend/src/pages/ProfilePage.tsx
//
// Profile page (Task 8 of Plan B2).
//
// Three tabs:
//   - "User details" — read-only display of the user record plus an Edit
//     dialog for the basic profile fields (`first_name`, `last_name`,
//     `email`). Edits go through `PATCH /auth/me/` via `useUpdateMe`.
//   - "Settings" — `<ProfileSettingsForm>` (B1 Task 11) bound to
//     `useUpdateMe` (same `PATCH /auth/me/` endpoint). The form already
//     carries the corrected `use_default_currency_for_all_data` field name.
//   - "Change password" — three-field form bound to
//     `POST /auth/change-password/` via `useChangePassword`.
//
// All three tabs share a single `useMe()` query. Mutations either prime
// the cache directly (`useUpdateMe`) or don't need to (password change
// uses `update_session_auth_hash` server-side).
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Pencil } from 'lucide-react'
import { toast } from 'sonner'

import { getRuntimeConfig, useMe, useUpdateMe, useChangePassword } from '@/api/auth'
import { ProfileSettingsForm } from '@/components/forms/ProfileSettingsForm'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { ErrorState } from '@/components/states/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'

export function ProfilePage() {
  const { localPasswordAuthEnabled } = getRuntimeConfig()
  const meQuery = useMe()
  const [editOpen, setEditOpen] = useState(false)

  if (meQuery.isLoading) {
    return <ProfileSkeleton />
  }

  if (meQuery.isError || !meQuery.data) {
    return (
      <ErrorState
        message="Failed to load profile"
        onRetry={() => meQuery.refetch()}
      />
    )
  }

  const user = meQuery.data

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Profile</h1>

      <Tabs defaultValue="details">
        <TabsList>
          <TabsTrigger value="details">User details</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          {localPasswordAuthEnabled && <TabsTrigger value="password">Change password</TabsTrigger>}
        </TabsList>

        {/* User details --------------------------------------------- */}
        <TabsContent value="details" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Account</CardTitle>
              <CardDescription>
                Your user identity and contact details.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
                <Detail label="Username" value={user.username} />
                <Detail label="Email" value={user.email || '—'} />
                <Detail
                  label="First name"
                  value={user.first_name || '—'}
                />
                <Detail label="Last name" value={user.last_name || '—'} />
                <Detail
                  label="Roles"
                  value={
                    [
                      user.is_landlord && 'Landlord',
                      user.is_tenant && 'Tenant',
                    ]
                      .filter(Boolean)
                      .join(', ') || '—'
                  }
                />
                <Detail
                  label="Default currency"
                  value={user.default_currency ?? '—'}
                />
              </dl>
              <div className="mt-4">
                <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                  <Pencil className="h-4 w-4" />
                  Edit profile
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings -------------------------------------------------- */}
        <TabsContent value="settings" className="pt-4">
          <SettingsTab user={user} showEffectiveDate={localPasswordAuthEnabled} />
        </TabsContent>

        {/* Change password ------------------------------------------- */}
        {localPasswordAuthEnabled && (
          <TabsContent value="password" className="pt-4">
            <ChangePasswordTab />
          </TabsContent>
        )}
      </Tabs>

      {/* Edit profile dialog */}
      <EntityFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        title="Profile"
        mode="edit"
      >
        <EditProfileForm
          defaultValues={{
            first_name: user.first_name,
            last_name: user.last_name,
            email: user.email,
          }}
          user={user}
          onDone={() => setEditOpen(false)}
        />
      </EntityFormDialog>
    </div>
  )
}

// ---- Settings tab --------------------------------------------------------

function SettingsTab({ user, showEffectiveDate }: {
  user: NonNullable<ReturnType<typeof useMe>['data']>
  showEffectiveDate: boolean
}) {
  const updateMe = useUpdateMe()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Application settings</CardTitle>
        <CardDescription>
          Currency, chart, and as-of-date preferences used across the app.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ProfileSettingsForm
          defaultValues={{
            default_currency: (user.default_currency ?? 'USD') as never,
            use_default_currency_for_all_data:
              user.use_default_currency_for_all_data,
            chart_frequency: user.chart_frequency,
            chart_timeline: user.chart_timeline as never,
            digits: user.digits,
            effective_date: user.effective_date,
          }}
          showEffectiveDate={showEffectiveDate}
          onSubmit={(values) =>
            updateMe.mutate(values as Partial<typeof user>, {
              onSuccess: () => toast.success('Settings saved'),
              onError: () => toast.error('Failed to save settings'),
            })
          }
          isSubmitting={updateMe.isPending}
        />
      </CardContent>
    </Card>
  )
}

// ---- Change password tab -------------------------------------------------

const passwordSchema = z
  .object({
    old_password: z.string().min(1, 'Required'),
    new_password1: z.string().min(8, 'Must be at least 8 characters'),
    new_password2: z.string().min(1, 'Required'),
  })
  .refine((data) => data.new_password1 === data.new_password2, {
    path: ['new_password2'],
    message: "The two password fields didn't match.",
  })

type PasswordInput = z.input<typeof passwordSchema>

function ChangePasswordTab() {
  const changePassword = useChangePassword()
  const form = useForm<PasswordInput>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { old_password: '', new_password1: '', new_password2: '' },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change password</CardTitle>
        <CardDescription>
          Your session stays valid after the password changes — no re-login
          required.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((values) =>
              changePassword.mutate(values, {
                onSuccess: () => {
                  toast.success('Password changed')
                  form.reset()
                },
                onError: () =>
                  toast.error('Failed to change password'),
              }),
            )}
            className="space-y-4"
          >
            <FormField
              control={form.control}
              name="old_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Current password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="current-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="new_password1"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="new_password2"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm new password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" disabled={changePassword.isPending}>
              {changePassword.isPending ? 'Saving…' : 'Change password'}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}

// ---- Edit profile form (inside the dialog) ------------------------------

const editSchema = z.object({
  first_name: z.string().optional().default(''),
  last_name: z.string().optional().default(''),
  email: z.string().email('Enter a valid email').or(z.literal('')).optional(),
})
type EditInput = z.input<typeof editSchema>
type EditOutput = z.output<typeof editSchema>

function EditProfileForm({
  defaultValues,
  user,
  onDone,
}: {
  defaultValues: EditInput
  user: NonNullable<ReturnType<typeof useMe>['data']>
  onDone: () => void
}) {
  const updateMe = useUpdateMe()
  const form = useForm<EditInput, unknown, EditOutput>({
    resolver: zodResolver(editSchema),
    defaultValues,
  })

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit((values) =>
          updateMe.mutate(values as Partial<typeof user>, {
            onSuccess: () => {
              toast.success('Profile updated')
              onDone()
            },
            onError: () => toast.error('Failed to update profile'),
          }),
        )}
        className="space-y-4"
      >
        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="first_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>First name</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="last_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Last name</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input type="email" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={updateMe.isPending}>
          {updateMe.isPending ? 'Saving…' : 'Save'}
        </Button>
      </form>
    </Form>
  )
}

// ---- Helpers --------------------------------------------------------------

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  )
}

function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-10 w-96" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
