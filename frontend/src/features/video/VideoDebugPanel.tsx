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

  const [mode, setMode] = useState<'create' | 'generate'>('create')
  const [generateTimeout, setGenerateTimeout] = useState(300)
  const [generatePollInterval, setGeneratePollInterval] = useState(2)
  const [wsStatus, setWsStatus] = useState('')
  const [wsMessage, setWsMessage] = useState('')

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

  async function onGenerateWS() {
    setCreateError('')
    setWsStatus('connecting')
    setWsMessage('正在连接 WebSocket...')
    setQueryResult(null)
    setCreateLoading(true)

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/v1/video/tasks/ws`
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setWsStatus('open')
      setWsMessage('连接成功，正在发送参数...')
      try {
        const payload = JSON.parse(createJson) as Record<string, unknown>
        ws.send(
          JSON.stringify({
            token,
            payload: {
              ...payload,
              timeout_seconds: generateTimeout,
              poll_interval_seconds: generatePollInterval,
            },
          })
        )
      } catch (e) {
        setCreateError(`JSON 解析错误: ${e instanceof Error ? e.message : String(e)}`)
        ws.close()
      }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          type: string
          status?: string
          message?: string
          task_id?: string
          data?: unknown
          detail?: unknown
        }

        if (data.type === 'status') {
          setWsStatus(data.status || 'running')
          setWsMessage(data.message || '任务进行中...')
          if (data.task_id) {
            setCreatedTaskId(data.task_id)
            setTaskId(data.task_id)
            addTask(token, data.task_id)
          }
        } else if (data.type === 'result') {
          setWsStatus('succeeded')
          setWsMessage('生成成功！')
          setQueryResult(data.data)
          setCreateLoading(false)
        } else if (data.type === 'error') {
          setWsStatus('error')
          setWsMessage(data.message || '发生错误')
          setCreateError(data.message || '一键生成失败')
          if (data.detail) {
            setQueryResult(data.detail)
          }
          setCreateLoading(false)
        }
      } catch (e) {
        console.error('WS message error:', e)
      }
    }

    ws.onerror = () => {
      setWsStatus('error')
      setWsMessage('WebSocket 连接失败')
      setCreateError('WebSocket 建立连接失败')
      setCreateLoading(false)
    }

    ws.onclose = () => {
      setCreateLoading(false)
    }
  }

  async function onCreate() {
    if (mode === 'generate') {
      return onGenerateWS()
    }

    setCreateError('')
    setCreateLoading(true)
    setQueryResult(null)
    try {
      const payload = JSON.parse(createJson) as Record<string, unknown>
      const endpoint = '/v1/video/tasks'

      const resp = await apiRequest<CreateResp>(endpoint, {
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
                <div className="mb-4 flex gap-2 border-b border-white/10 pb-2">
                  <button
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      mode === 'create'
                        ? 'border-b-2 border-blue-500 text-white'
                        : 'text-white/60 hover:text-white'
                    }`}
                    onClick={() => setMode('create')}
                  >
                    创建任务 (Create)
                  </button>
                  <button
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      mode === 'generate'
                        ? 'border-b-2 border-blue-500 text-white'
                        : 'text-white/60 hover:text-white'
                    }`}
                    onClick={() => setMode('generate')}
                  >
                    一键生成 (Generate)
                  </button>
                </div>

                <div className="mb-2 text-sm font-medium text-white">
                  {mode === 'create' ? '创建任务' : '一键生成并等待结果'}
                </div>
                <div className="text-xs text-white/60">
                  {mode === 'create'
                    ? '填写 JSON 请求体，点击发送。创建成功后需手动查询结果。'
                    : '填写 JSON 请求体，点击发送。服务端将轮询直到任务成功产出或超时。'}
                </div>

                {mode === 'generate' && (
                  <div className="mt-4 space-y-3">
                    <div className="grid grid-cols-2 gap-4 rounded-lg border border-white/10 bg-white/5 p-3">
                      <div className="space-y-1.5">
                        <label className="text-xs text-white/60">轮询间隔 (秒)</label>
                        <Input
                          type="number"
                          min={0.2}
                          max={10}
                          step={0.1}
                          value={generatePollInterval}
                          onChange={(e) => setGeneratePollInterval(Number(e.target.value))}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs text-white/60">超时限制 (秒)</label>
                        <Input
                          type="number"
                          min={1}
                          max={1800}
                          value={generateTimeout}
                          onChange={(e) => setGenerateTimeout(Number(e.target.value))}
                        />
                      </div>
                    </div>

                    {createLoading && wsStatus && (
                      <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-3">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
                          <span className="text-xs font-medium text-blue-400">
                            {wsStatus.toUpperCase()}
                          </span>
                        </div>
                        <div className="mt-1 text-xs text-white/80">{wsMessage}</div>
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-3">
                  <Textarea value={createJson} onChange={(e) => setCreateJson(e.target.value)} />
                </div>
                {createError ? (
                  <div className="mt-2 text-sm text-red-400">{createError}</div>
                ) : null}
                <div className="mt-3 flex items-center gap-3">
                  <Button loading={createLoading} onClick={onCreate}>
                    {mode === 'create' ? '发送创建请求' : '一键生成并轮询结果'}
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
