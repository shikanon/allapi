import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { JsonBlock } from '@/components/ui/JsonBlock'
import { Textarea } from '@/components/ui/Textarea'
import { useAuthStore } from '@/store/authStore'
import { useTaskHistoryStore } from '@/store/taskHistoryStore'
import { apiRequest } from '@/utils/api'
import { TaskHistoryList } from '@/features/video/TaskHistoryList'

type CreateResp = { id: string; status?: string }

const EMPTY_TASK_HISTORY: string[] = []

export function VideoDebugPanel() {
  const token = useAuthStore((s) => s.token)
  const history = useTaskHistoryStore((s) => s.byToken[token] ?? EMPTY_TASK_HISTORY)
  const addTask = useTaskHistoryStore((s) => s.addTask)
  const removeTask = useTaskHistoryStore((s) => s.removeTask)
  const clearToken = useTaskHistoryStore((s) => s.clearToken)

  const [createJson, setCreateJson] = useState(() =>
    JSON.stringify(
      {
        model: 'next-light',
        duration: 5,
        content: [{ type: 'text', text: '生成一个简单的测试视频' }],
      },
      null,
      2
    )
  )
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState('')
  const [createdTaskId, setCreatedTaskId] = useState('')

  const [taskId, setTaskId] = useState('')
  const [queryLoading, setQueryLoading] = useState(false)
  const [queryError, setQueryError] = useState('')
  const [queryResult, setQueryResult] = useState<unknown>(null)

  const [cancelLoading, setCancelLoading] = useState(false)
  const [cancelError, setCancelError] = useState('')
  const [cancelResult, setCancelResult] = useState<unknown>(null)

  const [polling, setPolling] = useState(false)
  const [pollIntervalSec, setPollIntervalSec] = useState(5)

  const activeTaskId = useMemo(() => (taskId || createdTaskId).trim(), [taskId, createdTaskId])

  async function onCreate() {
    setCreateError('')
    setCreateLoading(true)
    try {
      const payload = JSON.parse(createJson) as unknown
      const resp = await apiRequest<CreateResp>('/v1/video/tasks', {
        method: 'POST',
        body: payload,
      })
      setCreatedTaskId(resp.id)
      setTaskId(resp.id)
      addTask(token, resp.id)
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : String(e))
    } finally {
      setCreateLoading(false)
    }
  }

  async function onQuery(id: string) {
    const tid = id.trim()
    if (!tid) return
    setQueryError('')
    setQueryLoading(true)
    try {
      const resp = await apiRequest<unknown>(`/v1/video/tasks/${encodeURIComponent(tid)}`)
      setQueryResult(resp)
    } catch (e) {
      setQueryError(e instanceof Error ? e.message : String(e))
    } finally {
      setQueryLoading(false)
    }
  }

  async function onCancel(id: string) {
    const tid = id.trim()
    if (!tid) return
    setCancelError('')
    setCancelLoading(true)
    try {
      const resp = await apiRequest<unknown>(
        `/v1/video/tasks/${encodeURIComponent(tid)}/cancel`,
        {
          method: 'POST',
          body: {},
        }
      )
      setCancelResult(resp)
    } catch (e) {
      setCancelError(e instanceof Error ? e.message : String(e))
    } finally {
      setCancelLoading(false)
    }
  }

  useEffect(() => {
    if (!polling) return
    const tid = activeTaskId
    if (!tid) return

    const handle = window.setInterval(() => {
      onQuery(tid)
    }, Math.max(2, pollIntervalSec) * 1000)
    return () => window.clearInterval(handle)
  }, [polling, pollIntervalSec, activeTaskId])

  return (
    <div className="grid gap-4 lg:grid-cols-12">
      <div className="lg:col-span-5">
        <Card>
          <CardHeader>
            <CardTitle>API 调试</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              <div>
                <div className="mb-2 text-sm font-medium text-white">创建任务</div>
                <div className="text-xs text-white/60">填写 JSON 请求体，点击发送。</div>
                <div className="mt-3">
                  <Textarea value={createJson} onChange={(e) => setCreateJson(e.target.value)} />
                </div>
                {createError ? (
                  <div className="mt-2 text-sm text-red-400">{createError}</div>
                ) : null}
                <div className="mt-3 flex items-center gap-3">
                  <Button loading={createLoading} onClick={onCreate}>
                    发送创建请求
                  </Button>
                  {createdTaskId ? (
                    <div className="text-xs text-white/70">task_id：{createdTaskId}</div>
                  ) : null}
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                <div className="mb-3 text-sm font-medium text-white">查询 / 取消</div>
                <div className="grid gap-3">
                  <Input
                    value={taskId}
                    onChange={(e) => setTaskId(e.target.value)}
                    placeholder="输入 task_id"
                  />

                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={queryLoading}
                      onClick={() => onQuery(activeTaskId)}
                    >
                      查询
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      loading={cancelLoading}
                      onClick={() => onCancel(activeTaskId)}
                    >
                      取消任务
                    </Button>

                    <div className="ml-auto flex items-center gap-2">
                      <span className="text-xs text-white/60">轮询</span>
                      <button
                        type="button"
                        className="h-9 rounded-md border border-white/15 px-3 text-sm text-white hover:bg-white/5"
                        onClick={() => setPolling((v) => !v)}
                      >
                        {polling ? '已开启' : '未开启'}
                      </button>
                      <Input
                        className="w-[90px]"
                        type="number"
                        min={2}
                        max={60}
                        value={String(pollIntervalSec)}
                        onChange={(e) => setPollIntervalSec(Number(e.target.value) || 5)}
                      />
                      <span className="text-xs text-white/60">秒</span>
                    </div>
                  </div>

                  {queryError ? (
                    <div className="text-sm text-red-400">{queryError}</div>
                  ) : null}
                  {cancelError ? (
                    <div className="text-sm text-red-400">{cancelError}</div>
                  ) : null}
                </div>
              </div>

              <div>
                <TaskHistoryList
                  title="我的任务（本控制台创建）"
                  subtitle="仅展示你在本页面创建过的 task_id（保存在浏览器本地）。"
                  items={history}
                  onSelect={(id) => setTaskId(id)}
                  onQuery={(id) => {
                    setTaskId(id)
                    onQuery(id)
                  }}
                  onCancel={(id) => {
                    setTaskId(id)
                    onCancel(id)
                  }}
                  onRemove={(id) => removeTask(token, id)}
                  onClear={() => clearToken(token)}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="lg:col-span-7">
        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>查询结果</CardTitle>
            </CardHeader>
            <CardContent>
              {queryResult ? (
                <JsonBlock value={queryResult} />
              ) : (
                <div className="text-sm text-white/60">暂无结果</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>取消结果</CardTitle>
            </CardHeader>
            <CardContent>
              {cancelResult ? (
                <JsonBlock value={cancelResult} />
              ) : (
                <div className="text-sm text-white/60">暂无结果</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
