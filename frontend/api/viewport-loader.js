// 视口数据加载：按帧节流 + 代次作废（docs/protocol.md §4）。
//
// 为什么不直接在 wheel / mousemove 里发请求：连续缩放时每秒能发出几十次，
// 后端堆积、响应回来时视口早变了——交互反而更卡。这是本项目最典型的性能塌方点。
//
// raf / cancelRaf 可注入，便于在 Node 里用假帧驱动测试。

export function createViewportLoader({ request, onData, onError, raf, cancelRaf }) {
  const requestFrame = raf || globalThis.requestAnimationFrame
  const cancelFrame = cancelRaf || globalThis.cancelAnimationFrame

  let queued = null
  let frameId = 0
  let generation = 0

  // 同一帧内多次调用只保留最后一次：中间那些视口没人看得到
  function schedule(job) {
    queued = job
    if (!frameId) frameId = requestFrame(flush)
  }

  async function flush() {
    frameId = 0
    const job = queued
    queued = null
    if (!job) return

    const mine = (generation += 1)
    try {
      const payload = await request(job)
      if (mine === generation) onData(payload, job)
    } catch (error) {
      if (mine === generation) onError(error, job)
    }
  }

  // 作废在途请求（关数据源、换文件、卸载时调用）
  function cancel() {
    if (frameId) cancelFrame(frameId)
    frameId = 0
    queued = null
    generation += 1
  }

  return {
    schedule,
    cancel,
    get generation() {
      return generation
    },
  }
}
