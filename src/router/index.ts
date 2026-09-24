import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: {
        titleKey: 'home.title',
        sectionKey: 'shell.sections.home',
        descriptionKey: 'home.subtitle'
      }
    },
    {
      path: '/workspace/integrate-1d',
      name: 'integrate-1d',
      component: () => import('@/views/workspace/Integrate1dView.vue'),
      meta: {
        titleKey: 'integrate1d.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'integrate1d.subtitle'
      }
    },
    {
      path: '/workspace/integrate-azimuth',
      name: 'integrate-azimuth',
      component: () => import('@/views/workspace/IntegrateAzimuthView.vue'),
      meta: {
        titleKey: 'integrateAzimuth.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'integrateAzimuth.subtitle'
      }
    },
    {
      path: '/workspace/integrate-cake',
      name: 'integrate-cake',
      component: () => import('@/views/IntegrateCakeView.vue'),
      meta: {
        titleKey: 'integrateCake.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'integrateCake.description'
      }
    },
    {
      path: '/workspace/integrate-fiber',
      name: 'integrate-fiber',
      component: () => import('@/views/workspace/IntegrateFiberView.vue'),
      meta: {
        titleKey: 'integrateFiber.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'integrateFiber.subtitle'
      }
    },
    {
      path: '/workspace/viewer',
      name: 'viewer',
      component: () => import('@/views/workspace/ViewerView.vue'),
      meta: {
        titleKey: 'viewer.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'viewer.subtitle'
      }
    },
    {
      path: '/workspace/h5-toolkit',
      name: 'h5-toolkit',
      component: () => import('@/views/workspace/H5ToolkitView.vue'),
      meta: {
        titleKey: 'h5toolkit.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'h5toolkit.subtitle'
      }
    },
    // Legacy routes redirect to the merged toolkit page / 旧路由重定向到合并后的工具页
    {
      path: '/workspace/h5convert',
      redirect: { name: 'h5-toolkit' }
    },
    {
      path: '/workspace/h5-extract',
      redirect: { name: 'h5-toolkit' }
    },
    {
      path: '/workspace/mask-maker',
      name: 'mask-maker',
      component: () => import('@/views/workspace/MaskMakerView.vue'),
      meta: {
        titleKey: 'maskMaker.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'maskMaker.subtitle'
      }
    },
    {
      path: '/workspace/png-generate',
      name: 'png-generate',
      component: () => import('@/views/workspace/PngGenerateView.vue'),
      meta: {
        titleKey: 'pngGenerate.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'pngGenerate.subtitle'
      }
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: {
        titleKey: 'settings.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'settings.subtitle'
      }
    },
    {
      path: '/workspace/pyfai-calib',
      name: 'pyfai-calib',
      component: () => import('@/views/workspace/PyfaicalibView.vue'),
      meta: {
        titleKey: 'pyfaiCalib.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'pyfaiCalib.subtitle'
      }
    },
    {
      path: '/workspace/calibration',
      name: 'calibration',
      component: () => import('@/views/workspace/CalibrationView.vue'),
      meta: {
        titleKey: 'calibration.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'calibration.subtitle'
      }
    },
    {
      path: '/workspace/cell-calibrant-generator',
      name: 'cell-calibrant-generator',
      component: () => import('@/views/workspace/CellCalibrantGeneratorView.vue'),
      meta: {
        titleKey: 'cellCalibrantGenerator.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'cellCalibrantGenerator.subtitle'
      }
    },
    {
      path: '/workspace/bg-subtract',
      name: 'bg-subtract',
      component: () => import('@/views/workspace/BgSubtractView.vue'),
      meta: {
        titleKey: 'bgSubtract.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'bgSubtract.description',
      },
    },
    {
      path: '/workspace/image-math',
      name: 'image-math',
      component: () => import('@/views/workspace/ImageMathView.vue'),
      meta: {
        titleKey: 'imageMath.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'imageMath.description',
      },
    },
    {
      path: '/workspace/image-stitch',
      name: 'image-stitch',
      component: () => import('@/views/workspace/ImageStitchView.vue'),
      meta: {
        titleKey: 'imageStitch.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'imageStitch.description',
      },
    },
    {
      path: '/workspace/orientation-analysis',
      name: 'orientation-analysis',
      component: () => import('@/views/workspace/OrientationAnalysisView.vue'),
      meta: {
        titleKey: 'orientationAnalysis.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'orientationAnalysis.subtitle',
      },
    },
    {
      path: '/workspace/lamellar-analysis',
      name: 'lamellar-analysis',
      component: () => import('@/views/workspace/LamellarAnalysisView.vue'),
      meta: {
        titleKey: 'lamellar.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'lamellar.subtitle',
      },
    },
    {
      path: '/workspace/poni-importer',
      name: 'poni-importer',
      component: () => import('@/views/workspace/PoniImporterView.vue'),
      meta: {
        titleKey: 'poniImporter.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'poniImporter.subtitle',
      },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: {
        titleKey: 'notFound.title',
        sectionKey: 'shell.sections.error',
        descriptionKey: 'notFound.subtitle'
      }
    }
  ]
})

export default router
