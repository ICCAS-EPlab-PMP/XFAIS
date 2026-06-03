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
      path: '/workspace/h5convert',
      name: 'h5convert',
      component: () => import('@/views/workspace/H5ConvertView.vue'),
      meta: {
        titleKey: 'h5convert.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'h5convert.subtitle'
      }
    },
    {
      path: '/workspace/h5-extract',
      name: 'h5-extract',
      component: () => import('@/views/workspace/H5ExtractView.vue'),
      meta: {
        titleKey: 'h5extract.title',
        sectionKey: 'shell.sections.workspace',
        descriptionKey: 'h5extract.subtitle'
      }
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
