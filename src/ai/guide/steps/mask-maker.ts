/**
 * mask-maker.ts — Guided tour for the mask maker.
 * View reports: filesCount (image loaded), extras.maskEdits (maskVersion
 * counter), extras.exported.
 */

import type { GuideDefinition } from '../types'

export const MASK_MAKER_GUIDE: GuideDefinition = {
  routeName: 'mask-maker',
  title: { zh: '掩膜制作', en: 'Mask Maker' },
  steps: [
    {
      id: 'open',
      aiId: 'mask:open',
      title: { zh: '打开图像', en: 'Open an image' },
      tip: {
        zh: '打开需要制作掩膜的 2D 图像',
        en: 'Open the 2D image you want to mask',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'draw',
      title: { zh: '绘制掩膜区域', en: 'Draw mask regions' },
      tip: {
        zh: '用左侧工具在坏区/光束挡块上画矩形或形状；也可在右栏按阈值自动掩蔽',
        en: 'Draw rectangles/shapes over dead areas & beamstop with the toolbar; or threshold-mask from the right panel',
      },
      done: (s) => Number(s?.extras?.maskEdits ?? 0) > 0,
    },
    {
      id: 'export',
      aiId: 'mask:export',
      title: { zh: '导出掩膜', en: 'Export the mask' },
      tip: {
        zh: '导出的掩膜可在各积分页的“掩膜导入”中复用',
        en: 'The exported mask plugs into the Mask Import section of the integration views',
      },
      done: (s) => s?.extras?.exported === true,
      autoClick: true,
      allowWhen: (s) => (s?.filesCount ?? 0) > 0,
    },
  ],
}
