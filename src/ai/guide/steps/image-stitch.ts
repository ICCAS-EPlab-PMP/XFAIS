/**
 * image-stitch.ts — Guided tour for image stitching.
 * View reports: filesCount (valid images ≥2), phase, extras.saved.
 */

import type { GuideDefinition } from '../types'

export const IMAGE_STITCH_GUIDE: GuideDefinition = {
  routeName: 'image-stitch',
  title: { zh: '图像拼接', en: 'Image Stitch' },
  steps: [
    {
      id: 'images',
      aiId: 'stitch:add',
      title: { zh: '添加至少两张图像', en: 'Add at least two images' },
      tip: {
        zh: '每张图填像素尺寸与平移偏移（绝对或相对，µm/mm）',
        en: 'For each image set pixel size and offset (absolute or relative, µm/mm)',
      },
      done: (s) => (s?.filesCount ?? 0) >= 2,
      autoClick: true,
    },
    {
      id: 'run',
      aiId: 'stitch:run',
      title: { zh: '执行拼接', en: 'Stitch' },
      tip: {
        zh: '按所选策略（均值/求和/最大/首图）拼成大画布',
        en: 'Stitch into one large canvas with the chosen strategy (mean/sum/max/first)',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'save',
      aiId: 'stitch:save',
      title: { zh: '保存拼接结果', en: 'Save the stitch' },
      tip: {
        zh: '选择输出目录与格式后保存大图',
        en: 'Choose the output folder and format, then save the canvas',
      },
      done: (s) => s?.extras?.saved === true,
    },
  ],
}
