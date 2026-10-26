import type { ReactNode } from 'react'
import { CalendarX2 } from 'lucide-react'

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div
      className="flex flex-col items-center rounded-xl border border-dashed border-border bg-background/60 px-5 py-8 text-center"
      role="status"
    >
      <span className="mb-3 grid size-11 place-items-center rounded-full bg-muted text-muted-foreground">
        <CalendarX2 size={20} />
      </span>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-2 max-w-xs text-sm leading-relaxed text-muted-foreground">{children}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
