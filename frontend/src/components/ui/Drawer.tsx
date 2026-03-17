import type React from 'react'

import { cn } from '@/lib/utils'

export function Drawer({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
        role="button"
        tabIndex={0}
      />
      <div className="absolute right-0 top-0 h-full w-full max-w-xl border-l border-white/10 bg-[#0B1220]">
        <div className="flex items-center justify-between border-b border-white/10 p-4">
          <div className="text-sm font-semibold text-white">{title}</div>
          <button
            type="button"
            className={cn(
              'rounded-md px-3 py-1.5 text-sm text-white/80 hover:bg-white/5 hover:text-white'
            )}
            onClick={onClose}
          >
            关闭
          </button>
        </div>
        <div className="h-[calc(100%-57px)] overflow-auto p-4">{children}</div>
      </div>
    </div>
  )
}
