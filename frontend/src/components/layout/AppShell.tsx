import type React from 'react'

import { cn } from '@/lib/utils'

export function AppShell({
  title,
  subtitle,
  children,
  className,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('mx-auto w-full max-w-6xl px-4 py-6', className)}>
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-white">{title}</h1>
        {subtitle ? (
          <p className="mt-1 text-sm text-white/70">{subtitle}</p>
        ) : null}
      </div>
      {children}
    </div>
  )
}
