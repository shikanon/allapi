import { cn } from '@/lib/utils'

export type TabItem<T extends string> = {
  key: T
  label: string
}

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem<T>[]
  value: T
  onChange: (next: T) => void
  className?: string
}) {
  return (
    <div className={cn('inline-flex rounded-lg border border-white/10 bg-white/5 p-1', className)}>
      {items.map((it) => {
        const active = it.key === value
        return (
          <button
            key={it.key}
            onClick={() => onChange(it.key)}
            className={cn(
              'h-9 rounded-md px-3 text-sm transition-colors',
              active
                ? 'bg-[#111B2E] text-white'
                : 'text-white/70 hover:text-white'
            )}
            type="button"
          >
            {it.label}
          </button>
        )
      })}
    </div>
  )
}

