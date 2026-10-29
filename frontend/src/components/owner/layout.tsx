import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { currentOwner, logoutOwner, sessionKey, type Identity } from '@/lib/owner-api'
import { clearOwnerSession } from '@/lib/owner-session'
import { ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'

export function OwnerLayout() {
  const location = useLocation()
  const client = useQueryClient()
  const session = useQuery<Identity | null>({
    queryKey: sessionKey,
    queryFn: ({ signal }) => currentOwner(AbortSignal.any([signal, AbortSignal.timeout(10_000)])),
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
  })
  const logout = useMutation({
    mutationKey: ['owner', 'logout'],
    retry: false,
    gcTime: 0,
    mutationFn: () => logoutOwner(session.data!.csrf_token),
    onSuccess: () => clearOwnerSession(client),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 403) void session.refetch()
    },
  })
  if (session.data === null || (session.error instanceof ApiError && session.error.status === 401))
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    )
  if (session.isPending || session.isFetching) return <p role="status">Проверяем вход…</p>
  if (session.isError)
    return (
      <EmptyState
        title="Не удалось проверить вход"
        action={<Button onClick={() => void session.refetch()}>Повторить попытку</Button>}
      >
        Проверьте соединение. Данные кабинета появятся после проверки сессии.
      </EmptyState>
    )
  const owner = session.data
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <p className="eyebrow">Кабинет специалиста</p>
          <h1>{owner.specialist?.display_name ?? 'Ваш кабинет'}</h1>
          <p className="break-all text-sm text-muted-foreground">{owner.email}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {owner.specialist && (
            <Button asChild variant="outline">
              <Link to={`/s/${owner.specialist.slug}`}>Страница записи</Link>
            </Button>
          )}
          <Button
            variant="outline"
            disabled={logout.isPending}
            onClick={() => {
              if (!logout.isPending) logout.mutate()
            }}
          >
            {logout.isPending ? 'Выходим…' : 'Выйти'}
          </Button>
        </div>
      </div>
      {logout.isError && (
        <p role="alert" className="text-sm text-red-700">
          Не удалось выйти. Сессия может оставаться активной; повторите выход.
        </p>
      )}
      <nav aria-label="Кабинет" className="flex gap-2 border-b border-border pb-4">
        {[
          ['/dashboard', 'Записи'],
          ['/dashboard/schedule', 'Расписание'],
        ].map(([to, label]) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              `rounded-xl px-4 py-3 text-sm font-medium ${isActive ? 'bg-primary text-white' : 'bg-card hover:bg-muted'}`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      {owner.specialist ? (
        <Outlet key={owner.id} context={owner} />
      ) : (
        <EmptyState title="Профиль специалиста не настроен">
          Обратитесь к администратору для настройки расписания.
        </EmptyState>
      )}
    </div>
  )
}
