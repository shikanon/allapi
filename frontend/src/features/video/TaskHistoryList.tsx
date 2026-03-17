import { Button } from '@/components/ui/Button'

export function TaskHistoryList({
  title,
  subtitle,
  items,
  onQuery,
  onCancel,
  onSelect,
  onRemove,
  onClear,
}: {
  title: string
  subtitle: string
  items: string[]
  onSelect: (taskId: string) => void
  onQuery: (taskId: string) => void
  onCancel: (taskId: string) => void
  onRemove: (taskId: string) => void
  onClear: () => void
}) {
  return (
    <div>
      <div className="mb-2 text-sm font-medium text-white">{title}</div>
      <div className="text-xs text-white/60">{subtitle}</div>

      <div className="mt-3 overflow-hidden rounded-lg border border-white/10">
        {items.length === 0 ? (
          <div className="p-3 text-sm text-white/60">暂无任务</div>
        ) : (
          <div className="max-h-56 overflow-auto">
            {items.map((id) => (
              <div
                key={id}
                className="flex items-center justify-between gap-2 border-b border-white/5 px-3 py-2"
              >
                <button
                  type="button"
                  className="truncate text-left text-xs text-white/90 hover:underline"
                  onClick={() => {
                    onSelect(id)
                    onQuery(id)
                  }}
                >
                  {id}
                </button>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="secondary" onClick={() => onQuery(id)}>
                    查询
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => onCancel(id)}>
                    取消
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => onRemove(id)}>
                    移除
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {items.length ? (
        <div className="mt-3">
          <Button variant="secondary" size="sm" onClick={onClear}>
            清空本地任务列表
          </Button>
        </div>
      ) : null}
    </div>
  )
}

