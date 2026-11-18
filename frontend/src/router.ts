// 极简路由：只有首页 / 和讨论页 /d/:id 两个地址，不引入路由库。

import { useSyncExternalStore } from 'react'

const subscribe = (cb: () => void) => {
  window.addEventListener('popstate', cb)
  return () => window.removeEventListener('popstate', cb)
}

export function usePath(): string {
  return useSyncExternalStore(subscribe, () => window.location.pathname)
}

export function navigate(to: string) {
  if (to === window.location.pathname) return
  window.history.pushState(null, '', to)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function matchDiscussion(path: string): string | null {
  const m = /^\/d\/([0-9a-f]+)\/?$/.exec(path)
  return m ? m[1] : null
}
