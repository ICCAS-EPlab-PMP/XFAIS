/**
 * image-math.ts — Guided tour for image arithmetic.
 * View reports: filesCount (operands picked), phase, extras.saved.
 */

import type { GuideDefinition } from '../types'

export const IMAGE_MATH_GUIDE: GuideDefinition = {
  routeName: 'image-math',
  title: { zh: '图像运算', en: 'Image Math' },
  steps: [
    {
      id: 'image1',
      aiId: 'math:image1',
      title: { zh: '选择图像 A', en: 'Pick image A' },
      tip: {
        zh: '第一个操作数，可配系数（如归一化透过率）',
        en: 'The first operand, with an optional factor (e.g. transmission normalization)',
      },
      done: (s) => (s?.filesCount ?? 0) >= 1,
      autoClick: true,
    },
    {
      id: 'image2',
      aiId: 'math:image2',
      title: { zh: '选择图像 B', en: 'Pick image B' },
      tip: {
        zh: '第二个操作数；结果 = A×k₁ ± B×k₂',
        en: 'The second operand; result = A×k₁ ± B×k₂',
      },
      done: (s) => (s?.filesCount ?? 0) >= 2,
      autoClick: true,
    },
    {
      id: 'run',
      aiId: 'math:run',
      title: { zh: '执行运算', en: 'Compute' },
      tip: {
        zh: '加/减运算即时预览结果图像',
        en: 'Add/subtract computes and previews the result image instantly',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'save',
      aiId: 'math:save',
      title: { zh: '保存结果', en: 'Save the result' },
      tip: {
        zh: '选择输出目录与格式（HDF5/EDF/TIFF）后保存',
        en: 'Choose the output folder and format (HDF5/EDF/TIFF), then save',
      },
      done: (s) => s?.extras?.saved === true,
    },
  ],
}
