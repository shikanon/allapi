import { cn } from '@/lib/utils'

export function JsonBlock({
  value,
  className,
}: {
  value: unknown
  className?: string
}) {
  let text = ''
  try {
    text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  } catch {
    text = String(value)
  }

  return (
    <pre
      className={cn(
        'max-h-96 overflow-auto rounded-lg border border-white/10 bg-black/30 p-3 text-xs leading-5 text-white/90',
        className
      )}
    >
      <code>{text}</code>
    </pre>
  )
}

