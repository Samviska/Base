// 通信客户端：建连、发命令、按 id 配对响应、分发服务端事件。
//
// 只依赖契约（消息结构），**不得引用 UI 组件与渲染器**（modules/api-client.md §4）：
// 一旦引用，通信层就跟着界面一起改，接口稳定也就无从谈起。
//
// 本模块不产生界面文案：错误只带 code，显示由 UI 按文案表映射。

export const CLIENT_STATE = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  OPEN: 'open',
  CLOSED: 'closed',
}

// 后端错误对象 → Error：保留 code 与 detail，界面才能显示"哪儿错了"
function toError(error) {
  const err = new Error(error?.message || '后端返回了错误')
  err.code = error?.code || 'INTERNAL'
  err.detail = error?.detail || {}
  return err
}

export function createClient({ url }) {
  let socket = null
  let nextId = 1
  let state = CLIENT_STATE.IDLE
  const pending = new Map()
  const eventHandlers = new Map()
  const stateHandlers = new Set()

  function setState(next) {
    if (state === next) return
    state = next
    stateHandlers.forEach((handler) => handler(state))
  }

  function connect() {
    if (socket && (state === CLIENT_STATE.OPEN || state === CLIENT_STATE.CONNECTING)) {
      return Promise.resolve()
    }
    setState(CLIENT_STATE.CONNECTING)

    return new Promise((resolve, reject) => {
      let settled = false
      const ws = new WebSocket(url)
      socket = ws

      ws.onopen = () => {
        settled = true
        setState(CLIENT_STATE.OPEN)
        resolve()
      }

      ws.onmessage = (event) => {
        let message
        try {
          message = JSON.parse(event.data)
        } catch {
          return // 后端不会发坏消息；真发了也只能丢，界面没有可展示的东西
        }
        dispatch(message)
      }

      // 错误事件之后一定会来 close，统一在 close 里收尾，避免两处状态打架
      ws.onerror = () => {}

      ws.onclose = () => {
        socket = null
        // 在途请求全部失败：否则界面停在加载中，比报错更难查
        const failure = new Error('与后端的连接已断开')
        failure.code = 'DISCONNECTED'
        pending.forEach((entry) => entry.reject(failure))
        pending.clear()
        setState(CLIENT_STATE.CLOSED)
        if (!settled) {
          settled = true
          reject(failure)
        }
      }
    })
  }

  function dispatch(message) {
    const { id, type } = message
    if (id === undefined || id === null) {
      eventHandlers.get(type)?.forEach((handler) => handler(message.payload))
      return
    }
    const entry = pending.get(id)
    if (!entry) return // 代次作废后迟到的响应：丢弃，不覆盖新数据
    pending.delete(id)
    if (message.ok) entry.resolve(message.payload)
    else entry.reject(toError(message.error))
  }

  function request(type, payload = {}) {
    if (!socket || state !== CLIENT_STATE.OPEN) {
      const err = new Error('尚未连接后端')
      err.code = 'NOT_CONNECTED'
      return Promise.reject(err)
    }
    const id = nextId
    nextId += 1
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject })
      socket.send(JSON.stringify({ id, type, payload }))
    })
  }

  function on(type, handler) {
    if (!eventHandlers.has(type)) eventHandlers.set(type, new Set())
    eventHandlers.get(type).add(handler)
    return () => eventHandlers.get(type)?.delete(handler)
  }

  function onState(handler) {
    stateHandlers.add(handler)
    handler(state)
    return () => stateHandlers.delete(handler)
  }

  function close() {
    // 页面卸载时显式关闭，否则后端会留下已经没人用的连接
    if (socket) {
      socket.onclose = null
      socket.close()
      socket = null
    }
    setState(CLIENT_STATE.CLOSED)
  }

  return {
    connect,
    request,
    on,
    onState,
    close,
    get state() {
      return state
    },
  }
}
