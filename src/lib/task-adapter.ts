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

/**
 * Build the geometry payload consumed by FiberIntegratorService.build_integrator.
 * Shared by the integrate_fiber (2D) and fiber_1d_roi (ROI 1D) paths so that
 * rot1/rot2/rot3 and unit conversions are identical between them.
 *
 * - Manual mode: sends manual_params with rot1/rot2/rot3 (radians).
 * - PONI mode: sends poni_path + optional rot_overrides when the user enables
 *   "Override PONI rotations" (overridePoniRot). Legacy use_poni_rot3 /
 *   override_rot3_rad fields are kept for backward compatibility.
 *
 * 构建 FiberIntegratorService.build_integrator 消费的 geometry 载荷。
 * 2D 积分与 ROI 1D 积分共用，确保 rot1/rot2/rot3 及单位转换完全一致。
 */
const buildFiberGeometry = (params: Record<string, unknown>): Record<string, unknown> => {
  const geometry = buildNormalizedGeometry(params.geometry)
  const manualGeo = asRecord(geometry.manual)
  const overridePoni = asBoolean(params.overridePoniRot, false)
  const poniPath = asString(geometry.poni_path)
  const rot1Rad = asNumber(params.rot1Deg, 0) * Math.PI / 180
  const rot2Rad = asNumber(params.rot2Deg, 0) * Math.PI / 180
  const rot3Rad = asNumber(params.rot3Deg, 0) * Math.PI / 180
  return {
    manual: poniPath ? undefined : {
      dist: asNumber(manualGeo.dist_mm, 200) / 1000,
      poni1: asNumber(manualGeo.center_y_px, 512) * asNumber(manualGeo.pixel_size_um, 172) * 1e-6,
      poni2: asNumber(manualGeo.center_x_px, 512) * asNumber(manualGeo.pixel_size_um, 172) * 1e-6,
      wavelength: asNumber(manualGeo.wavelength_A, 1.5418) * 1e-10,
      rot1: asNumber(manualGeo.rot1_deg, 0) * Math.PI / 180,
      rot2: asNumber(manualGeo.rot2_deg, 0) * Math.PI / 180,
      rot3: asNumber(manualGeo.rot3_deg, 0) * Math.PI / 180,
      pixel_size_um: asNumber(manualGeo.pixel_size_um, 172),
    },
    poni_path: poniPath,
    poni_bytes: geometry.poni_bytes,
    rot_overrides: (poniPath && overridePoni) ? {
      rot1: rot1Rad,
      rot2: rot2Rad,
      rot3: rot3Rad,
    } : undefined,
    // Legacy fields (backward compat) / 旧字段（向后兼容）
    override_rot3_rad: rot3Rad,
    use_poni_rot3: !overridePoni,
  }
}

// ── Public API ───────────────────────────────────────────────────────────────

export const normalizeTaskParams = (command: string, params: Record<string, unknown>): Record<string, unknown> => {
  const geometry = buildNormalizedGeometry(params.geometry)
  const mask = asRecord(params.mask)
  const maskConfig = asRecord(params.maskConfig)
  const activeMask = Object.keys(mask).length > 0 ? mask : maskConfig
  const polarizationFactor = asOptionalNumber(params.polarizationFactor)

  // H5 dataset/frame/channel — forwarded to the integration handlers so users
  // can pick which dataset, frame (4-D), and channel to integrate. Defaults:
  // auto-detected dataset, first frame, channel 0. See H5Selector.vue.
  const h5DatasetPath = asString(params.dataset) ?? asString(params.h5Dataset)
  const h5Channel = typeof params.channel === 'number' || typeof params.channel === 'string'
    ? params.channel
    : undefined
  const frameIndex = asNumber(params.frame, 0)

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
        h5_dataset_path: h5DatasetPath,
        h5_channel: h5Channel,
        frame_index: frameIndex,
        options: {
          npt: asNumber(advanced.nptRad, 1000),
          npt_azim: asNumber(advanced.nptAzim, 360),
          unit: normalizeUnit(advanced.unit) ?? 'q_nm^-1',
          method: asString(advanced.algorithm ?? advanced.method) ?? 'splitpixel',
          integrator: asString(advanced.integrator) ?? 'ng',
          radial_min: asOptionalNumber(advanced.radialMin),
          radial_max: asOptionalNumber(advanced.radialMax),
          correct_solid_angle: asBoolean(advanced.correctSolidAngle, true),
          drop_empty_bins: asBoolean(advanced.dropEmptyBins, true),
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
        h5_dataset_path: h5DatasetPath,
        h5_channel: h5Channel,
        frame_index: frameIndex,
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
          drop_empty_bins: asBoolean(params.dropEmptyBins, true),
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
        h5_dataset_path: h5DatasetPath,
        h5_channel: h5Channel,
        frame_index: frameIndex,
        options: {
          npt_rad: asNumber(advanced.nptRad, 1000),
          npt_azim: asNumber(advanced.nptAzim, 360),
          unit: normalizeUnit(advanced.unit) ?? 'q_nm^-1',
          radial_min: asOptionalNumber(advanced.radialMin),
          radial_max: asOptionalNumber(advanced.radialMax),
          azimuth_min: asOptionalNumber(params.azimuthMin),
          azimuth_max: asOptionalNumber(params.azimuthMax),
          correct_solid_angle: asBoolean(advanced.correctSolidAngle, true),
          drop_empty_bins: asBoolean(advanced.dropEmptyBins, true),
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
        npt_oop: asNumber(params.nptOop, 400),
        method: asString(params.method)
      }
      // Shared geometry builder keeps rot1/rot2/rot3 + unit conversions
      // identical to the ROI 1D path.
      // 共享 geometry 构建器，确保 rot1/rot2/rot3 与单位转换与 ROI 1D 路径一致。
      const geometryForFiber = buildFiberGeometry(params)
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
        resultIndex: typeof params.resultIndex === 'number' ? params.resultIndex : params.result_index,
        result_index: typeof params.resultIndex === 'number' ? params.resultIndex : params.result_index,
        thumbnailOnly: typeof params.thumbnailOnly === 'boolean' ? params.thumbnailOnly : undefined,
        thumbnail_only: typeof params.thumbnailOnly === 'boolean' ? params.thumbnailOnly : (typeof params.thumbnail_only === 'boolean' ? params.thumbnail_only : undefined),
        settings: asRecord(params.settings),
        geometry: action === 'fiber_1d_roi' ? buildFiberGeometry(params) : asRecord(params.geometry),
        config: params.config,
        includeImageData: typeof params.includeImageData === 'boolean' ? params.includeImageData : undefined,
        include_image_data: typeof params.include_image_data === 'boolean' ? params.include_image_data : undefined,
        folder: asString(params.folder),
        recursive: typeof params.recursive === 'boolean' ? params.recursive : undefined,
        thumb_render_settings: params.thumb_render_settings,
        start: params.start,
        count: params.count,
        // azimuth_mask overlay fields (passed through verbatim; consumed only
        // by the viewer_config 'azimuth_mask' action). / 方位角遮罩叠加字段
        // （原样透传，仅被 viewer_config 的 'azimuth_mask' action 消费）。
        azimuth_min: typeof params.azimuth_min === 'number' ? params.azimuth_min
          : (typeof params.azimuthMin === 'number' ? params.azimuthMin : undefined),
        azimuth_max: typeof params.azimuth_max === 'number' ? params.azimuth_max
          : (typeof params.azimuthMax === 'number' ? params.azimuthMax : undefined),
        radial_unit: asString(params.radial_unit) ?? asString(params.radialUnit),
        radial_min: typeof params.radial_min === 'number' ? params.radial_min
          : (typeof params.radialMin === 'number' ? params.radialMin : undefined),
        radial_max: typeof params.radial_max === 'number' ? params.radial_max
          : (typeof params.radialMax === 'number' ? params.radialMax : undefined),
        // pixel_info overlay fields (passed through verbatim; consumed only by
        // the viewer_config 'pixel_info' action). / 像素信息字段（原样透传，
        // 仅被 viewer_config 的 'pixel_info' action 消费）。
        pixelX: typeof params.pixelX === 'number' ? params.pixelX
          : (typeof params.pixel_x === 'number' ? params.pixel_x : undefined),
        pixelY: typeof params.pixelY === 'number' ? params.pixelY
          : (typeof params.pixel_y === 'number' ? params.pixel_y : undefined),
        unit: asString(params.unit),
        // line_profile fields (passed through verbatim; consumed only by the
        // viewer_config 'line_profile' action). Endpoints use row/col semantics
        // matching the backend: pixelX = col, pixelY = row. / 沿线剖面字段
        // （原样透传，仅被 viewer_config 的 'line_profile' action 消费）。
        // 端点采用与后端一致的 row/col 语义：pixelX = col, pixelY = row。
        row0: typeof params.row0 === 'number' ? params.row0
          : (typeof params.pixelY0 === 'number' ? params.pixelY0 : undefined),
        col0: typeof params.col0 === 'number' ? params.col0
          : (typeof params.pixelX0 === 'number' ? params.pixelX0 : undefined),
        row1: typeof params.row1 === 'number' ? params.row1
          : (typeof params.pixelY1 === 'number' ? params.pixelY1 : undefined),
        col1: typeof params.col1 === 'number' ? params.col1
          : (typeof params.pixelX1 === 'number' ? params.pixelX1 : undefined),
        width: typeof params.width === 'number' ? params.width : undefined,
        n_samples: typeof params.n_samples === 'number' ? params.n_samples
          : (typeof params.nSamples === 'number' ? params.nSamples : undefined),
        aggregate: asString(params.aggregate),
        // fiber_1d_roi fields (passed through verbatim for GIWAXS ROI 1D integration)
        // GIWAXS ROI 1D 积分字段（原样透传）
        fiberParams: asRecord(params.fiberParams),
        ipRange: Array.isArray(params.ipRange) ? params.ipRange : undefined,
        oopRange: Array.isArray(params.oopRange) ? params.oopRange : undefined,
        npt1d: typeof params.npt1d === 'number' ? params.npt1d : 100,
        positiveQOnly: typeof params.positiveQOnly === 'boolean' ? params.positiveQOnly : undefined,
        absoluteIntensity: typeof params.absoluteIntensity === 'boolean' ? params.absoluteIntensity : undefined,
        correctSolidAngle: typeof params.correctSolidAngle === 'boolean' ? params.correctSolidAngle : undefined,
        maskConfig: asRecord(params.maskConfig),
        // fiber_result_mpl_preview fields (annotated WYSIWYG preview + PNG export).
        // The whole pngOptions object is forwarded verbatim so colormap/clim/
        // showLabels/no-data-fill/border/edge-color reach the backend renderer.
        // 带坐标轴预览与 PNG 导出字段：pngOptions 整体原样透传。
        unitIp: asString(params.unitIp),
        unitOop: asString(params.unitOop),
        pngOptions: asRecord(params.pngOptions),
      }
    }
    case 'mask_maker': {
      const action = asString(params.action)
      // load_preview action: same as viewer_config image loading.
      // `settings` (colormap / log / clim) MUST be forwarded — the backend
      // re-renders the preview with them; dropping it left manual contrast
      // with no effect. / load_preview 与 viewer_config 的图像加载一致。
      // `settings`（色图/对数/clim）必须透传——后端据此重渲染预览；
      // 丢失该字段会导致手动对比度完全无效。
      if (action === 'load_preview' || action === 'load') {
        const filePath = asString(params.filePath)
        return {
          action: 'load_preview',
          filePath,
          files: filePath ? [filePath] : [],
          frame: asNumber(params.frame, 0),
          frame_index: asNumber(params.frame, 0),
          dataset: asString(params.dataset),
          h5_dataset_path: asString(params.dataset),
          channel: typeof params.channel === 'number' || typeof params.channel === 'string' ? params.channel : undefined,
          h5_channel: typeof params.channel === 'number' || typeof params.channel === 'string' ? params.channel : undefined,
          settings: asRecord(params.settings),
        }
      }
      // All other mask operations: pass through as-is (draw_shape, apply_threshold, export_mask, load_mask)
      return { ...params }
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
    case 'orientation_analysis': {
      const inputMode = asString(params.inputMode) ?? 'curves'
      const bgRaw = asRecord(params.background)
      const refChi = Array.isArray(bgRaw.referenceChi) ? bgRaw.referenceChi : null
      const refInt = Array.isArray(bgRaw.referenceIntensity) ? bgRaw.referenceIntensity : null
      const hermansRaw = asRecord(params.hermans)
      const fwhmRaw = asRecord(params.fwhm)
      const wilchinskyRaw = asRecord(params.wilchinsky)
      const cellRaw = asRecord(wilchinskyRaw.cell)
      const reflectionsRaw = Array.isArray(wilchinskyRaw.reflections) ? wilchinskyRaw.reflections : []
      const base: Record<string, unknown> = {
        input_mode: inputMode,
        methods: Array.isArray(params.methods)
          ? params.methods.filter((m): m is string => typeof m === 'string')
          : ['hermans'],
        // NOTE: "scattering_geometry" (transmission/reflection) is kept distinct
        // from the PONI "geometry" dict used in image mode — the Python handler
        // maps scattering_geometry → analyze_orientation(geometry=...).
        // 注意：「scattering_geometry」（透射/反射）与图像模式的 PONI「geometry」
        // 字典分开；Python handler 把 scattering_geometry 映射到 analyze_orientation。
        scattering_geometry: asString(params.scatteringGeometry) ?? 'transmission',
        symmetry: asString(params.symmetry) ?? 'auto',
        missing: asString(params.missing) ?? 'interp',
        crystallinity: asOptionalNumber(params.crystallinity),
        background: {
          mode: asString(bgRaw.mode) ?? 'constant',
          auto_estimate: asBoolean(bgRaw.autoEstimate, true),
          constant: asOptionalNumber(bgRaw.constant),
          reference_scale: asOptionalNumber(bgRaw.referenceScale),
          reference_curve: (refChi && refInt) ? [refChi, refInt] : undefined,
        },
        hermans: {
          chi_zero: asString(hermansRaw.chiZero) ?? 'meridian',
          equatorial_to_chain: asBoolean(hermansRaw.equatorialToChain, true),
          reference_chi_deg: asOptionalNumber(hermansRaw.referenceChiDeg),
        },
        fwhm: { peak_window: asOptionalNumber(fwhmRaw.peakWindow) },
        wilchinsky: {
          cell: asNumber(cellRaw.a, 0) > 0 ? {
            a: asNumber(cellRaw.a, 0), b: asNumber(cellRaw.b, 0),
            c: asNumber(cellRaw.c, 0), beta: asNumber(cellRaw.beta, 90),
          } : undefined,
          reflections: reflectionsRaw.map((r) => {
            const rr = asRecord(r)
            return {
              h: asNumber(rr.h, 0), k: asNumber(rr.k, 0), l: asNumber(rr.l, 0),
              cos2: asNumber(rr.cos2, asNumber(rr.cos2Chi, 0)),
            }
          }),
          unique_axis: asString(wilchinskyRaw.uniqueAxis) ?? 'b',
        },
      }
      if (inputMode === 'image') {
        const fileList = Array.isArray(params.files) && params.files.length > 0
          ? params.files.filter((f): f is string => typeof f === 'string')
          : (asString(params.filePath) ? [params.filePath] : [])
        Object.assign(base, {
          files: fileList,
          geometry,
          valid_min: asNumber(activeMask.valueRangeMin, 0),
          valid_max: asNumber(activeMask.valueRangeMax, 1e10),
          custom_mask_path: asString(activeMask.customMaskPath),
          h5_dataset_path: h5DatasetPath,
          h5_channel: h5Channel,
          frame_index: frameIndex,
          options: {
            npt: asNumber(params.npt, 360),
            npt_rad: asNumber(params.nptRad, 100),
            unit: normalizeUnit(params.chiUnit) ?? 'chi_deg',
            radial_unit: normalizeUnit(params.radialUnit) ?? 'q_nm^-1',
            radial_min: asOptionalNumber(params.radialMin),
            radial_max: asOptionalNumber(params.radialMax),
            azimuth_min: asOptionalNumber(params.azimuthMin),
            azimuth_max: asOptionalNumber(params.azimuthMax),
            drop_empty_bins: asBoolean(params.dropEmptyBins, true),
            polarization_factor: polarizationFactor,
            dead_pixel_threshold: asOptionalNumber(activeMask.deadPixelThreshold),
            custom_mask_path: asString(activeMask.customMaskPath),
          },
        })
      } else {
        base.chi = Array.isArray(params.chi)
          ? params.chi.filter((v): v is number => typeof v === 'number') : []
        base.intensity = Array.isArray(params.intensity)
          ? params.intensity.filter((v): v is number => typeof v === 'number') : []
      }
      return base
    }
    case 'lamellar_analysis': {
      const inputMode = asString(params.inputMode) ?? 'curves'
      const bgRaw = asRecord(params.background)
      const braggRaw = asRecord(params.bragg)
      const corrRaw = asRecord(params.correlation)
      const base: Record<string, unknown> = {
        input_mode: inputMode,
        q_unit: asString(params.qUnit) ?? 'nm^-1',
        methods: Array.isArray(params.methods)
          ? params.methods.filter((m): m is string => typeof m === 'string')
          : ['bragg', 'correlation'],
        background: {
          mode: asString(bgRaw.mode) ?? 'auto',
          constant: asOptionalNumber(bgRaw.constant),
        },
        minority_phase: asString(params.minorityPhase) ?? 'crystalline',
        bragg: {
          smooth_window: asOptionalNumber(braggRaw.smoothWindow),
          q_min: asOptionalNumber(braggRaw.qMin),
          q_max: asOptionalNumber(braggRaw.qMax),
        },
        correlation: {
          r_max_nm: asOptionalNumber(corrRaw.rMaxNm),
        },
      }
      if (inputMode === 'image') {
        const fileList = Array.isArray(params.files) && params.files.length > 0
          ? params.files.filter((f): f is string => typeof f === 'string')
          : (asString(params.filePath) ? [params.filePath] : [])
        Object.assign(base, {
          files: fileList,
          geometry,
          valid_min: asNumber(activeMask.valueRangeMin, 0),
          valid_max: asNumber(activeMask.valueRangeMax, 1e10),
          custom_mask_path: asString(activeMask.customMaskPath),
          h5_dataset_path: h5DatasetPath,
          h5_channel: h5Channel,
          frame_index: frameIndex,
          options: {
            npt: asNumber(params.npt, 1000),
            radial_unit: normalizeUnit(params.radialUnit) ?? 'q_nm^-1',
            radial_min: asOptionalNumber(params.radialMin),
            radial_max: asOptionalNumber(params.radialMax),
            drop_empty_bins: asBoolean(params.dropEmptyBins, true),
            polarization_factor: polarizationFactor,
            dead_pixel_threshold: asOptionalNumber(activeMask.deadPixelThreshold),
            custom_mask_path: asString(activeMask.customMaskPath),
          },
        })
      } else {
        base.q = Array.isArray(params.q)
          ? params.q.filter((v): v is number => typeof v === 'number') : []
        base.intensity = Array.isArray(params.intensity)
          ? params.intensity.filter((v): v is number => typeof v === 'number') : []
      }
      return base
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
    case 'orientation_analysis': {
      const numArray = (v: unknown): number[] =>
        Array.isArray(v) ? v.filter((x): x is number => typeof x === 'number') : []
      const mapSingle = (src: Record<string, unknown>) => ({
        chi: numArray(src.chi),
        intensity: numArray(src.intensity),
        foldedIntensity: numArray(src.folded_intensity),
        correctedIntensity: numArray(src.corrected_intensity),
        background: numArray(src.background),
        foldInfo: asRecord(src.fold_info),
        backgroundInfo: asRecord(src.background_info),
        results: Array.isArray(src.results) ? src.results.map((entry) => asRecord(entry)) : [],
        crystallinityHint: asRecord(src.crystallinity_hint),
        warnings: Array.isArray(src.warnings)
          ? src.warnings.filter((w): w is string => typeof w === 'string') : [],
        quality: asRecord(src.quality),
        sourceLabel: asString(src.source_label),
      })
      // Batch mode: same conditions, one analysis per file + per-file failures.
      // 批量模式：同条件逐文件分析 + 逐文件失败列表。
      if (Array.isArray(result.items)) {
        return {
          kind: 'result',
          data: {
            batch: true,
            items: result.items.map((entry) => mapSingle(asRecord(entry))),
            failed: Array.isArray(result.failed) ? result.failed : [],
          }
        }
      }
      return {
        kind: 'result',
        data: mapSingle(result)
      }
    }
    case 'lamellar_analysis': {
      const numArray = (v: unknown): number[] =>
        Array.isArray(v) ? v.filter((x): x is number => typeof x === 'number') : []
      return {
        kind: 'result',
        data: {
          q: numArray(result.q_nm),
          intensity: numArray(result.intensity),
          correctedIntensity: numArray(result.corrected_intensity),
          background: asRecord(result.background),
          gammaR: numArray(result.gamma_r),
          gamma: numArray(result.gamma),
          results: Array.isArray(result.results) ? result.results.map((entry) => asRecord(entry)) : [],
          warnings: Array.isArray(result.warnings)
            ? result.warnings.filter((w): w is string => typeof w === 'string') : [],
          quality: asRecord(result.quality),
          sourceLabel: asString(result.source_label),
        }
      }
    }
    case 'viewer_config':
    case 'load_preview':
    case 'mask_maker': {
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
