import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { CalendarDays } from 'lucide-react'
import { queryClient } from './query-client'
import { lazy, Suspense } from 'react'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'

const SpecialistPage = lazy(() =>
  import('@/pages/specialist').then((module) => ({ default: module.SpecialistPage })),
)

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
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
            <span className="header-caption">Время для встречи</span>
          </div>
        </header>
        <main id="main" className="site-width main-content">
          <Suspense
            fallback={
              <p role="status" className="text-muted-foreground">
                Открываем расписание…
              </p>
            }
          >
            <Routes>
              <Route path="/" element={<Navigate to="/s/demo" replace />} />
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
