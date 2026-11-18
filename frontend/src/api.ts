// 后端 HTTP 接口。浏览器只和自己的后端通信，大模型 Key 永远不会出现在前端（P-07）。

import type {
  AbortResponse,
  CreateDiscussionRequest,
  DiscussionDetail,
  DiscussionListResponse,
  ErrorCode,
  RegenerateLineupRequest,
  StartResponse,
} from './types'

export class ApiFailure extends Error {
  status: number
  code: ErrorCode
  details: Record<string, unknown> | null

  constructor(status: number, code: ErrorCode, message: string, details: Record<string, unknown> | null) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  } catch {
    throw new ApiFailure(0, 'INTERNAL_ERROR', '无法连接服务器，请检查网络', null)
  }
  const body = await res.json().catch(() => null)
  // 登录过期或未登录：通知外壳切到登录页
  if (res.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('aps:unauthorized'))
  if (!res.ok) {
    throw new ApiFailure(res.status, body?.code ?? 'INTERNAL_ERROR', body?.message ?? '请求失败', body?.details ?? null)
  }
  return body as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  authStatus: () => request<{ required: boolean; authenticated: boolean }>('/auth/status'),
  login: (password: string) => post<{ ok: boolean }>('/auth/login', { password }),
  list: () => request<DiscussionListResponse>('/discussions'),
  detail: (id: string) => request<DiscussionDetail>(`/discussions/${id}`),
  create: (req: CreateDiscussionRequest) => post<DiscussionDetail>('/discussions', req),
  regenerate: (id: string, req: RegenerateLineupRequest) => post<DiscussionDetail>(`/discussions/${id}/lineup/regenerate`, req),
  start: (id: string) => post<StartResponse>(`/discussions/${id}/start`),
  abort: (id: string) => post<AbortResponse>(`/discussions/${id}/abort`),
  streamUrl: (id: string, after: number) => `/api/discussions/${id}/stream?after=${after}`,
}
