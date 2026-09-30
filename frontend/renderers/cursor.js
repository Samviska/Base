// 光标取值：把数据坐标 x 吸附到最近的数据点上。
//
// 渲染器与 UI 都要用这个结果（前者画交点、后者显示数值），所以抽成纯函数、
// 只在这里实现一次——两处各写一遍迟早会算出不同的数。
//
// **聚合模式下要如实说明**：此时前端拿到的是"每像素列的 min/max"，
// 并不是原始采样点。光标落到哪一列，返回的就是那一列的极值。

/** 在升序数组里找最接近 value 的下标；空数组返回 -1。 */
export function nearestIndex(values, value) {
  if (!values?.length) return -1
  let best = 0
  let bestDistance = Infinity
  for (let i = 0; i < values.length; i += 1) {
    const distance = Math.abs(values[i] - value)
    if (distance < bestDistance) {
      bestDistance = distance
      best = i
    }
  }
  return best
}

/**
 * 把 x 吸附到某条序列最近的点上。
 * 返回 `{ series, index, x, y, ymin, ymax, aggregated }`；没有数据时返回 null。
 *
 * `aggregated` 表示这个点来自像素列聚合：此时 y 只是该列的极值，
 * 不是某个真实采样值——界面必须把这件事说出来。
 */
export function snapToSeries(seriesList, name, x) {
  if (!Array.isArray(seriesList) || !seriesList.length) return null
  const series = seriesList.find((item) => item.name === name) || seriesList[0]
  const index = nearestIndex(series?.x, x)
  if (index < 0) return null

  const ymin = series.ymin?.[index] ?? null
  const ymax = series.ymax?.[index] ?? null
  const y = ymax === null || ymax === undefined ? ymin : ymax
  return {
    series: series.name,
    index,
    x: series.x[index],
    y,
    ymin,
    ymax,
    aggregated: ymin !== ymax,
  }
}
