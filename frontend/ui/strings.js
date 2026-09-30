// 界面文案集中在这里：逻辑代码里不出现硬编码文案（acceptance.md「插件机制」一节）。
// 当前只做简体中文（D11）；将来加语言时，换的就是这一个模块。
//
// 渲染器画布内的提示（轴降级标注等）不在这里：它属于渲染器自带的附属元素，
// 由渲染器自己创建与维护，否则第三方渲染插件都得依赖本文件。

export const strings = {
  appTitle: '嵌入式数据可视化',
  subtitle: '日志 → 契约数据 → 滤波 → 聚合 → 画布',

  backend: '后端地址',
  connect: '连接',
  reconnect: '重新连接',
  open: '打开',
  filePath: '数据文件路径',
  fileHint: '当前只支持契约 JSON（数据源插件机制尚未实现）',
  series: '序列',
  noSeries: '尚未打开数据',

  connection: {
    idle: '未连接',
    connecting: '连接中…',
    open: '已连接',
    closed: '连接已断开',
  },

  aggregatedOn: '当前为聚合显示（每像素列取 min/max）',
  aggregatedOff: '原始点显示',
  points: '点数',
  viewport: '视口',

  errorCodes: {
    NOT_CONNECTED: '尚未连接后端，请先点"连接"',
    DISCONNECTED: '与后端的连接已断开',
    FILE_NOT_FOUND: '文件不存在或无法读取',
    CONTRACT_VIOLATION: '数据不符合契约',
    PLUGIN_NOT_FOUND: '指定的插件不存在',
    PLUGIN_FAILED: '插件执行失败',
    INVALID_REQUEST: '请求参数不合法',
    UNKNOWN_TYPE: '后端不认识这条消息',
    INTERNAL: '后端内部错误',
  },
}
