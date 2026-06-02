// task-adapter.ts — Pure data transformation for task parameter normalization and result adaptation.
// Extracted from electron/main.ts to enable reuse and testing.

// ── Helper functions (module-private) ────────────────────────────────────────

const asRecord = (value: unknown): Record<string, unknown> => {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return {}
}

const asString = (value: unknown): string | undefined => {
  return typeof value === 'string' && value.length > 0 ? value : undefined
}

const asNumber = (value: unknown, fallback: number): number => {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

const asOptionalNumber = (value: unknown): number | undefined => {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

const asBoolean = (value: unknown, fallback: boolean): boolean => {
  return typeof value === 'boolean' ? value : fallback
}

const normalizeUnit = (value: unknown): string | undefined => {
  switch (value) {
    case 'q_nm':
      return 'q_nm^-1'
    case 'q_A':
      return 'q_A^-1'
    case '2th_deg':
      return '2th_deg'
    case '2th_rad':
      return '2th_rad'
    case 'chi_deg':
      return 'chi_deg'
    case 'chi_rad':
      return 'chi_rad'
    case 'q_nm^-1':
    case 'q_A^-1':
    case 'r_mm':
      return value
    default:
      return undefined
  }
}

const buildNormalizedGeometry = (geometryInput: unknown): Record<string, unknown> => {
  const geometry = asRecord(geometryInput)
  const poniPath = asString(geometry.poniPath) ?? asString(geometry.poni_path)
  if (poniPath) {
    return { poni_path: poniPath }
  }

  return {
    manual: {
      pixel_size_um: asNumber(geometry.pixel1 ?? geometry.pixel2, 172),
      dist_mm: asNumber(geometry.distance ?? geometry.dist_mm, 200),
      wavelength_A: asNumber(geometry.wavelength ?? geometry.wavelength_A, 1.5418),
      center_x_px: asNumber(geometry.centerX ?? geometry.center_x_px, 512),
      center_y_px: asNumber(geometry.centerY ?? geometry.center_y_px, 512),
      rot1_deg: asNumber(geometry.rot1 ?? geometry.rot1_deg, 0),
      rot2_deg: asNumber(geometry.rot2 ?? geometry.rot2_deg, 0),
      rot3_deg: asNumber(geometry.rot3 ?? geometry.rot3_deg, 0)
    }
  }
}

// ── Public API ───────────────────────────────────────────────────────────────

export const normalizeTaskParams = (command: string, params: Record<string, unknown>): Record<string, unknown> => {
  const geometry = buildNormalizedGeometry(params.geometry)
  const mask = asRecord(params.mask)
  const maskConfig = asRecord(params.maskConfig)
  const activeMask = Object.keys(mask).length > 0 ? mask : maskConfig
  const polarizationFactor = asOptionalNumber(params.polarizationFactor)

  switch (command) {
    case 'integrate1d': {
      const advanced = asRecord(params.advanced)
      const fileList = Array.isArray(params.files) && params.files.length > 0
        ? params.files.filter((f): f is string => typeof f === 'string')
        : (asString(params.filePath) ? [params.filePath] : [])
      return {
        files: fileList,
        geometry,
        valid_min: asNumber(activeMask.valueRangeMin, 0),
        valid_max: asNumber(activeMask.valueRangeMax, 1e10),
        custom_mask_path: asString(activeMask.customMaskPath),
        options: {
          npt: asNumber(advanced.nptRad, 1000),
          npt_azim: asNumber(advanced.nptAzim, 360),
          unit: normalizeUnit(advanced.unit) ?? 'q_nm^-1',
          method: asString(advanced.algorithm ?? advanced.method) ?? 'splitpixel',
          integrator: asString(advanced.integrator) ?? 'ng',
          radial_min: asOptionalNumber(advanced.radialMin),
          radial_max: asOptionalNumber(advanced.radialMax),
          correct_solid_angle: asBoolean(advanced.correctSolidAngle, true),
          polarization_factor: polarizationFactor,
          dead_pixel_threshold: asOptionalNumber(activeMask.deadPixelThreshold),
          custom_mask_path: asString(activeMask.customMaskPath)
        }
      }
    }
    case 'integrate_azimuth': {
      const fileList = Array.isArray(params.files) && params.files.length > 0
        ? params.files.filter((f): f is string => typeof f === 'string')
        : (asString(params.filePath) ? [params.filePath] : [])
      return {
        files: fileList,
        geometry,
        valid_min: asNumber(activeMask.valueRangeMin, 0),
        valid_max: asNumber(activeMask.valueRangeMax, 1e10),
        custom_mask_path: asString(activeMask.customMaskPath),
        options: {
          npt: asNumber(params.npt, 360),
          npt_rad: asNumber(params.nptRad, 100),
          unit: normalizeUnit(params.chiUnit) ?? 'chi_deg',
          radial_unit: normalizeUnit(params.radialUnit) ?? 'q_nm^-1',
          radial_min: asOptionalNumber(params.radialMin),
          radial_max: asOptionalNumber(params.radialMax),
          azimuth_min: asOptionalNumber(params.azimuthMin),
          azimuth_max: asOptionalNumber(params.azimuthMax),
          correct_solid_angle: true,
          polarization_factor: polarizationFactor,
          dead_pixel_threshold: asOptionalNumber(activeMask.deadPixelThreshold),
          custom_mask_path: asString(activeMask.customMaskPath)
        }
      }
    }
    case 'integrate_cake': {
      const advanced = asRecord(params.advancedOptions)
      const fileList = Array.isArray(params.files) && params.files.length > 0
        ? params.files.filter((f): f is string => typeof f === 'string')
        : (asString(params.filePath) ? [params.filePath] : [])
      return {
        files: fileList,
        geometry,
        valid_min: asNumber(activeMask.valueRangeMin, 0),
        valid_max: asNumber(activeMask.valueRangeMax, 1e10),
        custom_mask_path: asString(activeMask.customMaskPath),
        options: {
          npt_rad: asNumber(advanced.nptRad, 1000),
          npt_azim: asNumber(advanced.nptAzim, 360),
          unit: normalizeUnit(advanced.unit) ?? 'q_nm^-1',
          radial_min: asOptionalNumber(advanced.radialMin),
          radial_max: asOptionalNumber(advanced.radialMax),
          azimuth_min: asOptionalNumber(params.azimuthMin),
          azimuth_max: asOptionalNumber(params.azimuthMax),
          correct_solid_angle: asBoolean(advanced.correctSolidAngle, true),
          polarization_factor: polarizationFactor,
          dead_pixel_threshold: asOptionalNumber(activeMask.deadPixelThreshold),
          custom_mask_path: asString(activeMask.customMaskPath)
        }
      }
    }
    case 'integrate_fiber': {
      const fileList = Array.isArray(params.files) && params.files.length > 0
        ? params.files.filter((f): f is string => typeof f === 'string')
        : (asString(params.filePath) ? [params.filePath] : [])
      const fiberParams = {
        rot1_deg: asNumber(params.rot1Deg, 0),
        rot2_deg: asNumber(params.rot2Deg, 0),
        rot3_deg: asNumber(params.rot3Deg, 0),
        sample_orientation: asNumber(params.sampleOrientation, 1),
        incident_rad: asNumber(params.incidentAngleDeg, 0) * Math.PI / 180,
        tilt_rad: asNumber(params.tiltAngleDeg, 0) * Math.PI / 180,
        unit_ip: asString(params.unitIp) ?? 'qip_nm^-1',
        unit_oop: asString(params.unitOop) ?? 'qoop_nm^-1',
        use_auto: asBoolean(params.autoRange, true),
        ip_range: Array.isArray(params.ipRange) ? params.ipRange : undefined,
        oop_range: Array.isArray(params.oopRange) ? params.oopRange : undefined,
        npt_ip: asNumber(params.nptIp, 400),
        npt_oop: asNumber(params.nptOop, 400)
      }
      const manualGeo = asRecord(geometry.manual)
      const geometryForFiber = {
        manual: geometry.poni_path ? undefined : {
          dist: asNumber(manualGeo.dist_mm, 200) / 1000,
          poni1: asNumber(manualGeo.center_y_px, 512) * asNumber(manualGeo.pixel_size_um, 172) * 1e-6,
          poni2: asNumber(manualGeo.center_x_px, 512) * asNumber(manualGeo.pixel_size_um, 172) * 1e-6,
          wavelength: asNumber(manualGeo.wavelength_A, 1.5418) * 1e-10,
          rot1: asNumber(manualGeo.rot1_deg, 0) * Math.PI / 180,
          rot2: asNumber(manualGeo.rot2_deg, 0) * Math.PI / 180,
          rot3: asNumber(params.rot3Deg, 0) * Math.PI / 180,
          pixel_size_um: asNumber(manualGeo.pixel_size_um, 172)
        },
        poni_path: geometry.poni_path,
        poni_bytes: geometry.poni_bytes,
        override_rot3_rad: asNumber(params.rot3Deg, 0) * Math.PI / 180,
        use_poni_rot3: true
      }
      return {
        files: fileList,
        geometry: geometryForFiber,
        params: fiberParams,
        outputPath: asString(params.outputPath) ?? undefined,
        outputFormat: asString(params.outputFormat) ?? undefined,
        options: {
          valid_min: asNumber(activeMask.valueRangeMin, 0),
          valid_max: asNumber(activeMask.valueRangeMax, 1e10),
          correct_solid_angle: asBoolean(params.correctSolidAngle, true),
          polarization_factor: polarizationFactor,
          dead_pixel_threshold: asOptionalNumber(activeMask.deadPixelThreshold),
          custom_mask_path: asString(activeMask.customMaskPath)
        }
      }
    }
    case 'viewer_config':
    case 'load_preview': {
      const filePath = asString(params.filePath)
      const action = command === 'load_preview' ? 'load_preview' : (asString(params.action) ?? 'inspect')
      return {
        action,
        filePath,
        files: Array.isArray(params.files) && params.files.length > 0 ? params.files : (filePath ? [filePath] : []),
        frame: asNumber(params.frame, 0),
        frame_index: asNumber(params.frame, 0),
        dataset: asString(params.dataset),
        h5_dataset_path: asString(params.dataset),
        channel: typeof params.channel === 'number' || typeof params.channel === 'string' ? params.channel : undefined,
        h5_channel: typeof params.channel === 'number' || typeof params.channel === 'string' ? params.channel : undefined,
        source_path: asString(params.sourcePath),
        output_path: asString(params.output_path) ?? asString(params.outputPath),
        batchCachePath: asString(params.batchCachePath),
        batch_cache_path: asString(params.batchCachePath) ?? asString(params.batch_cache_path),
        resultIndex: typeof params.resultIndex === 'number' ? params.resultIndex : params.resultIndex,
        result_index: typeof params.resultIndex === 'number' ? params.resultIndex : params.result_index,
        thumbnailOnly: typeof params.thumbnailOnly === 'boolean' ? params.thumbnailOnly : undefined,
        thumbnail_only: typeof params.thumbnailOnly === 'boolean' ? params.thumbnailOnly : (typeof params.thumbnail_only === 'boolean' ? params.thumbnail_only : undefined),
        settings: asRecord(params.settings),
        geometry: asRecord(params.geometry),
        config: params.config,
        includeImageData: typeof params.includeImageData === 'boolean' ? params.includeImageData : undefined,
        include_image_data: typeof params.include_image_data === 'boolean' ? params.include_image_data : undefined,
        folder: asString(params.folder),
        recursive: typeof params.recursive === 'boolean' ? params.recursive : undefined,
        thumb_render_settings: params.thumb_render_settings,
        start: params.start,
        count: params.count,
      }
    }
    case 'h5convert': {
      const datasetsRaw = params.datasets
      const datasetConfig: Record<string, unknown> = {}
      if (Array.isArray(datasetsRaw)) {
        for (const item of datasetsRaw) {
          const entry = asRecord(item)
          const dsPath = asString(entry.path)
          if (dsPath) {
            datasetConfig[dsPath] = {
              export: entry.export !== false,
              channels: Array.isArray(entry.channels) ? entry.channels : undefined,
            }
          }
        }
      }
      return {
        source_dir: asString(params.sourceDir) ?? asString(params.source_dir) ?? '',
        output_dir: asString(params.outputDir) ?? asString(params.output_dir) ?? '',
        master_suffix: asString(params.refSuffix) ?? asString(params.master_suffix) ?? '_master',
        image_format: asString(params.imageFormat) ?? asString(params.image_format) ?? 'tiff',
        table_format: asString(params.tableFormat) ?? asString(params.table_format) ?? 'csv',
        dataset_config: datasetConfig,
        datasets: datasetsRaw,
      }
    }
    case 'h5convert_scan': {
      return {
        source_dir: asString(params.sourceDir) ?? asString(params.source_dir) ?? '',
        master_suffix: asString(params.refSuffix) ?? asString(params.master_suffix) ?? '_master',
        recursive: asBoolean(params.recursive ?? true, true),
      }
    }
    case 'h5_extract': {
      return {
        source_dir: asString(params.sourceDir) ?? asString(params.source_dir) ?? '',
        output_dir: asString(params.targetDir) ?? asString(params.output_dir) ?? asString(params.outputDir) ?? '',
        suffix_filter: asString(params.suffix) ?? asString(params.suffix_filter) ?? '',
        prepend_folder: asBoolean(params.prependFolder ?? params.prepend_folder, true),
        prefix: asString(params.prefix) ?? '',
        conflict_policy: asString(params.conflictPolicy) ?? asString(params.conflict_policy) ?? 'rename',
      }
    }
    case 'h5_list_files': {
      return {
        source_dir: asString(params.sourceDir) ?? asString(params.source_dir) ?? '',
        suffix_filter: asString(params.suffix) ?? asString(params.suffix_filter) ?? '',
        recursive: asBoolean(params.recursive ?? true, true),
      }
    }
    default:
      return params
  }
}

// ── Result adaptation ────────────────────────────────────────────────────────

export type AdaptedTaskOutcome =
  | { kind: 'result'; data: unknown }
  | { kind: 'error'; error: string; code?: string }

export const adaptViewerResult = (result: Record<string, unknown>): unknown => {
  const baseResult = {
    metadata: asRecord(result.metadata),
    stats: result.stats,
    contrast: result.contrast,
    thumbnails: Array.isArray(result.thumbnails) ? result.thumbnails : undefined,
    nextStart: typeof result.nextStart === 'number' ? result.nextStart : result.nextStart ?? undefined,
    chunkSize: typeof result.chunkSize === 'number' ? result.chunkSize : undefined,
    axisIp: Array.isArray(result.axisIp) ? result.axisIp : undefined,
    axisOop: Array.isArray(result.axisOop) ? result.axisOop : undefined,
    filename: asString(result.filename),
    stem: asString(result.stem),
    displayB64: asString(result.displayB64),
  }

  if (Array.isArray(result.imageData)) {
    return {
      ...baseResult,
      imageData: result.imageData,
      fullImageB64: result.fullImageB64,
      previewB64: result.previewB64
    }
  }
  // Lightweight mode: no imageData matrix, PNG delivered via binary frame
    return {
      ...baseResult,
      imageData: null,
      fullImageB64: result.fullImageB64 ?? '__binary_blob__',
      previewB64: result.previewB64,
    }
  }

export const isViewerDisplayResult = (result: Record<string, unknown>): boolean => {
  return Array.isArray(result.imageData)
    || typeof result.fullImageB64 === 'string'
    || typeof result.previewB64 === 'string'
}

export const adaptTaskResult = (command: string, rawResult: unknown): AdaptedTaskOutcome => {
  const result = asRecord(rawResult)
  if (result.status === 'error') {
    return {
      kind: 'error',
      error: asString(result.message) ?? 'Task failed',
      code: asString(result.code)
    }
  }

  switch (command) {
    case 'integrate1d': {
      const results = Array.isArray(result.results) ? result.results : []
      const failed = Array.isArray(result.failed) ? result.failed : []
      return {
        kind: 'result',
        data: {
          results: results.map((entry, index) => {
            const item = asRecord(entry)
            return {
              radial: Array.isArray(item.radial) ? item.radial : [],
              intensity: Array.isArray(item.intensity) ? item.intensity : [],
              label: asString(item.filename) ?? `Curve ${index + 1}`
            }
          }),
          failed
        }
      }
    }
    case 'integrate_azimuth': {
      const results = Array.isArray(result.results) ? result.results : []
      const failed = Array.isArray(result.failed) ? result.failed : []
      return {
        kind: 'result',
        data: {
          results: results.map((entry, index) => {
            const item = asRecord(entry)
            return {
              chi: Array.isArray(item.radial) ? item.radial : [],
              intensity: Array.isArray(item.intensity) ? item.intensity : [],
              label: asString(item.filename) ?? `Curve ${index + 1}`
            }
          }),
          failed
        }
      }
    }
    case 'integrate_cake': {
      const traces = Array.isArray(result.traces) ? result.traces : []
      const failed = Array.isArray(result.failed) ? result.failed : []
      return {
        kind: 'result',
        data: {
          traces: traces.map((entry, index) => {
            const item = asRecord(entry)
            return {
              x: Array.isArray(item.x) ? item.x : [],
              y: Array.isArray(item.y) ? item.y : [],
              name: asString(item.name) ?? `Curve ${index + 1}`
            }
          }),
          failed
        }
      }
    }
    case 'viewer_config':
    case 'load_preview': {
      return {
        kind: 'result',
        data: isViewerDisplayResult(result) ? adaptViewerResult(result) : rawResult
      }
    }
    case 'h5convert_scan': {
      const datasets = Array.isArray(result.datasets) ? result.datasets : []
      return {
        kind: 'result',
        data: {
          datasets: datasets.map((entry: unknown) => {
            const item = asRecord(entry)
            return {
              path: asString(item.path) ?? '',
              shape: asString(item.shape) ?? '',
              dtype: asString(item.dtype) ?? '',
              ndim: typeof item.ndim === 'number' ? item.ndim : 0,
              kind: asString(item.kind) ?? '',
            }
          }),
          totalH5: typeof result.totalH5 === 'number' ? result.totalH5 : 0,
          targetH5: typeof result.targetH5 === 'number' ? result.targetH5 : 0,
          refFile: asString(result.refFile) ?? '',
        }
      }
    }
    case 'h5convert':
    case 'h5_extract': {
      return {
        kind: 'result',
        data: {
          total: typeof result.total === 'number' ? result.total : 0,
          success: typeof result.success === 'number' ? result.success : 0,
          failed: typeof result.failed === 'number' ? result.failed : 0,
          elapsed: typeof result.elapsed === 'number' ? result.elapsed : 0,
        }
      }
    }
    case 'h5_list_files': {
      const files = Array.isArray(result.files) ? result.files : []
      return {
        kind: 'result',
        data: {
          files: files.map((entry: unknown) => {
            const item = asRecord(entry)
            return {
              path: asString(item.path) ?? '',
              name: asString(item.name) ?? '',
              size: typeof item.size === 'number' ? item.size : 0,
              parentDir: asString(item.parentDir) ?? '',
            }
          }),
          total: typeof result.total === 'number' ? result.total : 0,
        }
      }
    }
    default:
      return { kind: 'result', data: rawResult }
  }
}
