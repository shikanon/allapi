import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { JsonBlock } from '@/components/ui/JsonBlock'
import { apiRequest } from '@/utils/api'

type QuoteResponse = {
  total_tokens: number
  has_video_input: boolean
  rmb_per_million_tokens: number
  amount_rmb: number
}

export function BillingPanel() {
  const [totalTokens, setTotalTokens] = useState('108900')
  const [hasVideoInput, setHasVideoInput] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<QuoteResponse | null>(null)

  const tokensNumber = useMemo(() => {
    const n = Number(totalTokens)
    if (!Number.isFinite(n)) return null
    if (!Number.isInteger(n)) return null
    if (n < 0) return null
    return n
  }, [totalTokens])

  async function onQuote() {
    if (tokensNumber === null) return
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest<QuoteResponse>('/v1/billing/quote', {
        method: 'POST',
        body: {
          total_tokens: tokensNumber,
          has_video_input: hasVideoInput,
        },
      })
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>计费报价</CardTitle>
          <CardDescription>按单价（元/100万 tokens）折算人民币金额。</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-xs text-white/70">total_tokens</div>
              <Input
                value={totalTokens}
                onChange={(e) => setTotalTokens(e.target.value)}
                inputMode="numeric"
                placeholder="例如：108900"
              />
              {tokensNumber === null ? (
                <div className="mt-2 text-sm text-red-400">请输入非负整数</div>
              ) : null}
            </div>

            <div className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2">
              <div>
                <div className="text-sm font-medium text-white">是否含视频输入</div>
                <div className="text-xs text-white/60">
                  含视频输入：28元/百万 tokens；不含：46元/百万 tokens
                </div>
              </div>
              <button
                type="button"
                className="h-9 rounded-md border border-white/15 px-3 text-sm text-white hover:bg-white/5"
                onClick={() => setHasVideoInput((v) => !v)}
              >
                {hasVideoInput ? '是' : '否'}
              </button>
            </div>

            {error ? <div className="text-sm text-red-400">{error}</div> : null}

            <div className="flex items-center gap-3">
              <Button loading={loading} onClick={onQuote} disabled={tokensNumber === null}>
                计算
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setResult(null)
                  setError('')
                }}
              >
                清空结果
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>返回结果</CardTitle>
          <CardDescription>与后端接口返回保持一致，便于你核对。</CardDescription>
        </CardHeader>
        <CardContent>
          {result ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="text-xs text-white/60">单价</div>
                  <div className="mt-1 text-sm font-semibold text-white">
                    {result.rmb_per_million_tokens} 元 / 100万 tokens
                  </div>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="text-xs text-white/60">金额</div>
                  <div className="mt-1 text-sm font-semibold text-white">
                    {result.amount_rmb} 元
                  </div>
                </div>
              </div>
              <JsonBlock value={result} />
            </div>
          ) : (
            <div className="text-sm text-white/60">暂无结果</div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

