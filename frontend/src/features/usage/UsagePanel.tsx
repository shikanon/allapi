import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Drawer } from '@/components/ui/Drawer'
import { Input } from '@/components/ui/Input'
import { JsonBlock } from '@/components/ui/JsonBlock'
import { apiRequest } from '@/utils/api'

type UsageItem = {
  id: number
  endpoint: string
  task_id: string | null
  request_id: string
  tokens_charged: number
  amount_rmb: number | null
  rmb_per_million_tokens: number | null
  has_video_input: boolean | null
  balance_before: number
  balance_after: number
  status: string
  upstream_status_code: number | null
  error_message: string | null
  created_at: string
}

type UsageListResponse = {
  items: UsageItem[]
  limit: number
  offset: number
}

function toDateInputValue(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function UsagePanel() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [items, setItems] = useState<UsageItem[]>([])
  const [selected, setSelected] = useState<UsageItem | null>(null)

  const [startDate, setStartDate] = useState(() => {
    const d = new Date(Date.now() - 7 * 24 * 3600 * 1000)
    return toDateInputValue(d)
  })
  const [endDate, setEndDate] = useState(() => toDateInputValue(new Date()))

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest<UsageListResponse>('/v1/usage?limit=50&charged_only=true')
      setItems(data.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const start = new Date(`${startDate}T00:00:00`)
    const end = new Date(`${endDate}T23:59:59`)
    return items.filter((it) => {
      const t = new Date(it.created_at)
      return t >= start && t <= end
    })
  }, [items, startDate, endDate])

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <CardTitle>用量记录</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              className="w-[150px]"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <Input
              className="w-[150px]"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
            <Button size="sm" loading={loading} onClick={load}>
              刷新
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {error ? <div className="mb-3 text-sm text-red-400">{error}</div> : null}

        <div className="overflow-hidden rounded-lg border border-white/10">
          <div className="grid grid-cols-12 gap-2 border-b border-white/10 bg-white/5 px-3 py-2 text-xs text-white/60">
            <div className="col-span-3">时间</div>
            <div className="col-span-2">task_id</div>
            <div className="col-span-2">Token 用量</div>
            <div className="col-span-2">人民币</div>
            <div className="col-span-3">状态</div>
          </div>

          {filtered.length === 0 ? (
            <div className="p-4 text-sm text-white/60">暂无记录</div>
          ) : (
            <div className="max-h-[520px] overflow-auto">
              {filtered.map((it) => (
                <button
                  key={it.id}
                  type="button"
                  className="grid w-full grid-cols-12 gap-2 border-b border-white/5 px-3 py-2 text-left text-sm text-white/90 hover:bg-white/5"
                  onClick={() => setSelected(it)}
                >
                  <div className="col-span-3 text-xs text-white/70">
                    {new Date(it.created_at).toLocaleString()}
                  </div>
                  <div className="col-span-2 truncate text-xs text-white/70">
                    {it.task_id ?? '-'}
                  </div>
                  <div className="col-span-2 text-xs">
                    {it.tokens_charged}
                  </div>
                  <div className="col-span-2 text-xs">
                    {it.amount_rmb == null ? '-' : it.amount_rmb.toFixed(4)}
                  </div>
                  <div className="col-span-3 flex items-center gap-2 text-xs">
                    <span
                      className={
                        it.status === 'success'
                          ? 'text-green-400'
                          : it.status === 'failed'
                            ? 'text-red-400'
                            : 'text-white/70'
                      }
                    >
                      {it.status}
                    </span>
                    {it.upstream_status_code ? (
                      <span className="text-white/50">({it.upstream_status_code})</span>
                    ) : null}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <Drawer
          open={!!selected}
          title="记录详情"
          onClose={() => setSelected(null)}
        >
          {selected ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="text-xs text-white/60">余额变化</div>
                  <div className="mt-1 text-sm font-semibold text-white">
                    {selected.balance_before} → {selected.balance_after}
                  </div>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="text-xs text-white/60">request_id</div>
                  <div className="mt-1 break-all text-xs text-white/90">
                    {selected.request_id}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="text-xs text-white/60">Token 用量</div>
                  <div className="mt-1 text-sm font-semibold text-white">{selected.tokens_charged}</div>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="text-xs text-white/60">人民币</div>
                  <div className="mt-1 text-sm font-semibold text-white">
                    {selected.amount_rmb == null ? '-' : selected.amount_rmb.toFixed(4)}
                  </div>
                  {selected.rmb_per_million_tokens != null ? (
                    <div className="mt-1 text-xs text-white/60">
                      单价：{selected.rmb_per_million_tokens} 元 / 100万 tokens
                    </div>
                  ) : null}
                </div>
              </div>

              {selected.error_message ? (
                <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">
                  {selected.error_message}
                </div>
              ) : null}

              <JsonBlock value={selected} />
            </div>
          ) : null}
        </Drawer>
      </CardContent>
    </Card>
  )
}
