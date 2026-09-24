/**
 * viewer.ts — Guided tour for the passive image viewer.
 * View reports: filesCount (selected), phase ('done' = image displayed),
 * extras.exported (single PNG export clicked).
 */

import type { GuideDefinition } from '../types'

export const VIEWER_GUIDE: GuideDefinition = {
  routeName: 'viewer',
  title: { zh: '图像查看器', en: 'Image Viewer' },
  steps: [
    {
      id: 'files',
      aiId: 'viewer:files',
      title: { zh: '打开图像文件', en: 'Open an image file' },
      tip: {
        zh: '选择文件或整个文件夹；H5 多通道/多帧可在此切换',
        en: 'Pick a file or a whole folder; switch H5 channels/frames here too',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'inspect',
      title: { zh: '检查图像', en: 'Inspect the image' },
      tip: {
        zh: '调整色图/对数/对比度找到最佳显示；可开启像素信息读取 q 值',
        en: 'Tune colormap/log/contrast for the best display; enable pixel info to read q values',
      },
      done: (s) => s?.phase === 'done',
    },
    {
      id: 'export',
      aiId: 'viewer:export',
      title: { zh: '导出 PNG', en: 'Export PNG' },
      tip: {
        zh: '单帧导出为出版级 PNG（可设 DPI）',
        en: 'Export the current frame as a publication-ready PNG (DPI adjustable)',
      },
      done: (s) => s?.extras?.exported === true,
      allowWhen: (s) => s?.phase === 'done',
    },
  ],
}
