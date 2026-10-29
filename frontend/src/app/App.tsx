import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { CalendarDays } from 'lucide-react'
import { queryClient } from './query-client'
import { lazy, Suspense, useEffect, useRef } from 'react'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'

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
            <Link to="/s/demo" className="brand" aria-label="SlotBook — главная">
              <span className="brand-mark">
                <CalendarDays size={20} />
              </span>
              SlotBook
            </Link>
            <Link to="/dashboard" className="header-caption">
              Кабинет специалиста
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
              <Route path="/" element={<Navigate to="/s/demo" replace />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/dashboard" element={<OwnerLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="schedule" element={<SchedulePage />} />
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
                        <Link to="/s/demo">К расписанию</Link>
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
