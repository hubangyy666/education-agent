export class ApiError extends Error { constructor(message: string, public status = 0) { super(message) } }
export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try { response = await fetch(`/api${path}`, { ...init, credentials: 'include', headers: { 'Content-Type': 'application/json', ...init.headers } }) }
  catch { throw new ApiError('暂时无法连接学习服务，请稍后重试。') }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : '操作未成功，请检查输入后重试。', response.status)
  return data as T
}
export const post = <T = any>(path: string, body: unknown = {}) => api<T>(path, { method: 'POST', body: JSON.stringify(body) })
