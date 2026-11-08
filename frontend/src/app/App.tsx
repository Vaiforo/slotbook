import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { CalendarDays } from 'lucide-react'
import { queryClient } from './query-client'
import { lazy, Suspense, useEffect, useRef } from 'react'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { CatalogPage } from '@/pages/catalog'
import { RegisterPage } from '@/pages/register'
import { AccountOverview, AccountProfile, AccountSecurity } from '@/pages/account'
import { useOutletContext } from 'react-router-dom'
import type { Identity } from '@/lib/owner-api'

const ProfessionalPage = lazy(() =>
  import('@/pages/professional').then((m) => ({ default: m.ProfessionalPage })),
)
const ShiftsPage = lazy(() => import('@/pages/shifts').then((m) => ({ default: m.ShiftsPage })))

const SpecialistPage = lazy(() =>
  import('@/pages/specialist').then((module) => ({ default: module.SpecialistPage })),
)

const ManagePage = lazy(() =>
  import('@/pages/manage').then((module) => ({ default: module.ManagePage })),
)

const LoginPage = lazy(() => import('@/pages/login').then((m) => ({ default: m.LoginPage })))
const OwnerLayout = lazy(() =>
  import('@/components/owner/layout').then((m) => ({ default: m.OwnerLayout })),
)
const DashboardPage = lazy(() =>
  import('@/pages/dashboard').then((m) => ({ default: m.DashboardPage })),
)
const SchedulePage = lazy(() =>
  import('@/pages/schedule').then((m) => ({ default: m.SchedulePage })),
)

function DashboardEntry() {
  const user = useOutletContext<Identity>()
  return user.role === 'specialist' ? <DashboardPage /> : <AccountOverview />
}

function SpecialistSchedule() {
  const user = useOutletContext<Identity>()
  return user.role === 'specialist' ? <SchedulePage /> : <Navigate to="/dashboard" replace />
}

function ProfessionalEntry({ shifts = false }: { shifts?: boolean }) {
  const user = useOutletContext<Identity>()
  return user.role === 'specialist' ? (
    shifts ? (
      <ShiftsPage />
    ) : (
      <ProfessionalPage />
    )
  ) : (
    <Navigate to="/dashboard" replace />
  )
}

function RouteFocus() {
  const { pathname } = useLocation()
  const previous = useRef(pathname)
  useEffect(() => {
    if (previous.current === pathname) return
    previous.current = pathname
    document.getElementById('main')?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <RouteFocus />
        <a className="skip-link" href="#main">
          Перейти к содержимому
        </a>
        <header className="site-header">
          <div className="site-width flex items-center justify-between gap-3">
            <Link to="/" className="brand" aria-label="SlotBook — главная">
              <span className="brand-mark">
                <CalendarDays size={20} />
              </span>
              SlotBook
            </Link>
            <Link to="/dashboard" className="header-caption">
              Личный кабинет
            </Link>
          </div>
        </header>
        <main id="main" tabIndex={-1} className="site-width main-content">
          <Suspense
            fallback={
              <p role="status" className="text-muted-foreground">
                Открываем страницу…
              </p>
            }
          >
            <Routes>
              <Route path="/" element={<CatalogPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/dashboard" element={<OwnerLayout />}>
                <Route index element={<DashboardEntry />} />
                <Route path="profile" element={<AccountProfile />} />
                <Route path="security" element={<AccountSecurity />} />
                <Route path="schedule" element={<SpecialistSchedule />} />
                <Route path="professional" element={<ProfessionalEntry />} />
                <Route path="shifts" element={<ProfessionalEntry shifts />} />
              </Route>
              <Route path="/manage/:id" element={<ManagePage />} />
              <Route path="/s/:slug" element={<SpecialistPage />} />
              <Route
                path="*"
                element={
                  <EmptyState
                    title="Страница не найдена"
                    action={
                      <Button asChild>
                        <Link to="/">В каталог</Link>
                      </Button>
                    }
                  >
                    Проверьте адрес или откройте расписание специалиста.
                  </EmptyState>
                }
              />
            </Routes>
          </Suspense>
        </main>
        <footer className="site-width site-footer">
          <span>SlotBook</span>
          <span>Меньше переписки. Больше времени.</span>
        </footer>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
