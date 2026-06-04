export const localeStorageKey = 'x-fais-locale'

export const messages = {
  zh: {
    app: {
      name: 'X-FAIS',
      version: 'v0.1.0'
    },
    shell: {
      sections: {
        home: '工作台',
        workspace: '工作区',
        error: '恢复'
      },
      actions: {
        home: '主页',
        language: '语言'
      },
      status: {
        ready: '已就绪',
        pythonError: 'Python 需要恢复',
        pythonRestarting: 'Python 重启中',
        pythonStarting: 'Python 启动中'
      }
    },
    python: {
      detailLabel: '运行时详情',
      restart: '重试 Python 运行时',
      states: {
        error: '内置 Python 发生了意外退出。',
        restarting: '内置 Python 正在重启。',
        starting: '内置 Python 正在启动。',
        stopped: '内置 Python 已停止。'
      },
      subtitle: '内置运行时可以在不依赖系统 Python 的前提下恢复。点击重试即可重新拉起。',
      title: '内置 Python 运行时恢复'
    },
    home: {
      title: 'X-FAIS',
      subtitle: 'X-ray FAI (pyFAI) Scattering & Diffraction Suite',
      kicker: '桌面集成版 v0.1.0',
      description: '集成 pyFAI 积分引擎，提供 1D 径向积分、方位角积分、CAKE 选区积分、GIWAXS 纤维衍射 2D 积分、图像查看与批量导出等功能。',
      highlights: {
        secure: 'pyFAI 积分引擎',
        routing: '多格式数据支持',
        logs: '批量处理与导出'
      },
      heroPanel: {
        notice: '本程序基于 pyFAI/fabIO 内核提供界面支持',
        openSourceNotice: '本项目仅对部分常用 pyFAI 功能进行 GUI 集成。程序将永远开源，不做任何付费或商业开发。',
        official: '程序基座链接',
        study: '探索更多可能',
        github: '基座仓库链接',
        fabio: 'fabIO 仓库',
        polymcrystal: '开发者主页',
        contact: '联系本程序开发者定制更多常用功能',
        issueHint: '提交 Issue 反馈问题或建议',
        repositories: '程序基座开源仓库'
      },
      acknowledgments: {
        title: '致谢',
        thanks: 'AI-Agent 制作：',
        models: '使用编程模型：',
        developer: '开发组织：',
        devOrg: 'ICCAS-EP-PMP'
      },
      sections: {
        commonIntegration: '常用积分 / Common Integration',
        giwaxs: '掠入射衍射 / GIWAXS',
        imageTools: '图像工具 / Image Tools',
        h5Tools: 'HDF5/.h5 处理 / HDF5 Processing',
        pyfaiTools: 'pyFAI 辅助功能',
        comingSoon: '开发中 / Coming Soon'
      },
      badge: {
        comingSoon: '开发中'
      },
      actions: {
        openPlaceholder: '打开占位工作区',
        showLogs: '显示日志目录',
        checkUpdate: '检测更新',
        citePyFAI: '引用 pyFAI',
        citeFabIO: '引用 fabIO'
      },
      cards: {
        integrate1d: {
          title: '1D 径向积分',
          description: '批量一维径向平均积分，输出 I(q) 或 I(2θ) 曲线'
        },
        integrateAzimuth: {
          title: '方位角 χ 积分',
          description: '方位角 χ 积分，分析衍射环取向分布'
        },
        integrateCake: {
          title: 'CAKE 方位角窗口积分',
          description: '扇区选区径向积分，适用于织构与各向异性样品分析'
        },
        integrateFiber: {
          title: 'GIWAXS 纤维衍射 2D 积分',
          description: 'GIWAXS 掠入射 2D 积分，输出 qip × qoop 强度图'
        },
        viewer: {
          title: '图像查看器',
          description: 'EDF/TIFF/HDF5 图像浏览、色图控制、缩略图导航与批量 PNG 导出'
        },
        h5convert: {
          title: 'H5 格式转换',
          description: '批量将 H5 数据集转换为 TIFF、CSV 或 DAT 格式'
        },
        h5extract: {
          title: 'H5 文件提取汇总',
          description: '从嵌套目录中递归提取并汇总 H5 文件'
        },
        pngGenerate: {
          title: '批量 PNG 生成',
          description: '批量生成色图 PNG 图像'
        },
        maskMaker: {
          title: '掩膜（Mask）制作',
          description: '交互式 Mask 绘制工具，功能基于 silx/pyFAI 的 mask 模块复刻。建议有条件时直接使用 pyFAI/silx 构建掩膜以获得更完整的功能。'
        },
        pyfaiCalib: {
          title: 'pyFAI-calib2 启动器',
          description: '启动 pyFAI-calib2 探测器校准 GUI'
        },
        cellCalibrantGenerator: {
          title: '校正标样生成器',
          description: 'CIF 晶体文件 / 晶胞参数 / 手动输入 d/q/2θ 生成 .D 标样校准文件'
        }
      },
      logsToast: '日志目录位置：{path}'
    },
    integrateAzimuth: {
      title: '方位角 χ 积分',
      subtitle: '在指定径向范围内对方位角 χ 积分，输出强度随 χ 角的分布。',
      selectFile: '选择数据文件',
      run: '开始积分',
      running: '处理中...',
      chartTitle: '方位角积分曲线',
      axisLabels: {
        chiDeg: 'χ (度)',
        chiRad: 'χ (弧度)',
        intensity: '强度'
      },
      radialRange: {
        title: '径向范围',
        unit: '径向单位',
        min: '径向下限',
        max: '径向上限'
      },
      chiUnit: {
        title: '方位角输出单位',
        deg: 'χ (度) — chi_deg',
        rad: 'χ (弧度) — chi_rad'
      },
      params: {
        title: '积分参数',
        npt: '方位角点数 (npt)',
        nptRad: '径向积分点数 (npt_rad)'
      },
      azimuthRange: {
        title: '方位角范围',
        hint: '0° = 正右方向（X轴正方向），逆时针增加。留空则全360°积分。',
        min: '起始方位角 (°)',
        max: '终止方位角 (°)',
        errorMinMax: '起始方位角必须小于终止方位角。'
      },
      errors: {
        radialRange: '径向下限必须小于上限。'
      }
    },
    placeholder: {
      title: '占位工作区',
      subtitle: '具体功能页会在后续任务中接入，这里用于验证壳层、路由和布局契约。',
      badge: '预留路由'
    },
    notFound: {
      title: '未找到页面',
      subtitle: '请求的页面暂不可用，你可以安全地返回桌面主页。',
      action: '返回主页'
    },
    integrateCake: {
      title: 'CAKE 方位角窗口积分',
      description: '对指定方位角扇区执行1D径向积分，适用于织构分析、应变测量等各向异性样品场景。',
      selectFile: '选择探测器图像',
      azimuthRange: {
        title: '方位角范围',
        hint: '0° = 正右方向（X轴正方向），逆时针增加。',
        min: '起始方位角 (°)',
        max: '终止方位角 (°)',
        errorEmpty: '方位角值不能为空。',
        errorMinMax: '起始方位角必须小于终止方位角。'
      },
      run: '运行 CAKE 积分',
      imagePreview: {
        title: '图像预览',
        chartTitle: '图像与方位角范围',
        shape: '尺寸',
        sector: '方位角扇区'
      },
      resultChart: {
        title: '积分结果',
        yLabel: '强度',
        chartTitle: 'CAKE 积分 ({min}° → {max}°)'
      }
    },
      integrateFiber: {
        title: 'GIWAXS 纤维衍射 2D 积分',
        subtitle: '使用 pyFAI FiberIntegrator 执行掠入射衍射 2D 积分（qip × qoop）。',
        fileSection: '上传图像',
        inputFile: '衍射图像 (.edf / .tif / .h5)',
        rotSection: '旋转覆盖 (°)',
        sampleSection: '样品与角度',
        sampleOrientation: '样品方向 (1–8)',
        incidentAngle: '入射角 (°)',
        tiltAngle: '倾斜角 (°)',
        unitsSection: '坐标单位',
        unitIp: '面内 (ip) 单位',
        unitOop: '面外 (oop) 单位',
        rangeSection: '积分范围',
        autoRange: '自动范围（由 pyFAI 推算）',
        ipMin: 'ip 下限',
        ipMax: 'ip 上限',
        oopMin: 'oop 下限',
        oopMax: 'oop 上限',
        nptSection: '网格点数',
        nptIp: 'npt_ip（面内）',
        nptOop: 'npt_oop（面外）',
        correctSolidAngle: '立体角校正',
        runIntegration: '执行积分',
        running: '积分中…',
        result2dTitle: '积分结果',
        heatmapTitle: 'GIWAXS 图 (qip × qoop)',
        logScale: '对数显示',
        horizontalProfile: '水平截面（固定 oop）',
        verticalProfile: '竖直截面（固定 ip）',
        targetOop: '目标 oop 值',
        targetIp: '目标 ip 值',
        hProfileTitle: 'oop ≈ {oop}',
        vProfileTitle: 'ip ≈ {ip}',
        intensity: '强度',
        emptyHint: '上传图像、配置参数后，点击「执行积分」。',
        errorNoFile: '请选择衍射图像文件。',
        errorNoGeometry: '几何参数不完整。',
        errorIpRange: 'ip 下限必须小于上限。',
        errorOopRange: 'oop 下限必须小于上限。',
        errorNpt: 'npt_ip 和 npt_oop 必须 ≥ 50。',
        preview: '预览积分',
        batchExportFolder: '积分到文件夹',
        batchExportComplete: '批量导出完成',
        loadToView: '加载查看',
        moreFiles: '… 还有 {count} 个文件',
        memoryWarning: '加载查看需要将文件读入内存。选择大量文件可能导致系统卡顿或内存不足，建议按需加载。',
      },
    boundary: {
      title: '壳层出现了可恢复错误',
      subtitle: '渲染异常已被捕获，系统保持在可恢复状态。',
      action: '返回主页'
    },
    toast: {
      close: '关闭'
    },
    integrate1d: {
      title: '1D 径向积分',
      subtitle: '使用 pyFAI 对探测器图像执行批量一维径向平均积分。',
      dataFiles: '数据文件',
      selectDataFiles: '选择数据文件（.edf / .tif / .h5）',
      runIntegration: '运行积分',
      emptyState: '选择数据文件并配置参数后，点击运行积分。',
      resultTitle: '积分结果',
      chartTitle: '1D 径向积分',
      intensityLabel: '强度',
      errorPrefix: '积分失败：',
      errorTitle: '积分错误',
      successTitle: '积分完成',
      successMessage: '成功处理 {count} 条曲线。',
      exportTitle: '导出',
      exportMessage: '已导出为 {format} 至 {path}'
    },
    pngGenerate: {
      title: '批量 PNG 生成',
      subtitle: '从 H5/TIFF/EDF 文件批量生成色图映射的 PNG 图像。',
      emptyState: '选择源文件夹并配置显示设置以开始。',
      run: '开始批量导出',
      successTitle: 'PNG 生成完成',
      successMessage: '已成功生成 {count} 张图像。',
      errorTitle: 'PNG 生成错误',
      cancelledTitle: '已取消',
      cancelledMessage: '已取消生成。已完成的文件保留在输出目录中。',
      discoveredFiles: '已发现文件',
      folders: {
        title: '文件夹',
        source: '源文件夹',
        sourcePlaceholder: '选择源文件夹',
        output: '输出文件夹',
        outputPlaceholder: '选择输出文件夹',
        recursive: '递归扫描子文件夹'
      },
      jsonConfig: {
        title: 'JSON 配置',
        load: '导入 JSON',
        save: '导出 JSON',
        loadSuccessTitle: '配置已加载',
        loadSuccessMessage: '已成功导入与 Viewer 兼容的 JSON 配置。',
        loadErrorTitle: '导入失败',
        saveSuccessTitle: '配置已保存',
        saveErrorTitle: '保存失败'
      },
      display: {
        title: '显示与导出设置',
        colormap: '色图',
        useLog: '对数刻度',
        clim: '对比度范围 (CLIM)',
        climAuto: '自动',
        climManual: '手动',
        layout: '输出布局',
        layoutFlat: '统一平铺',
        layoutPerFile: '按文件分目录',
        dpi: 'DPI',
        showAxes: '显示坐标轴',
        showColorbar: '显示色标'
      },
      fileTypes: {
        title: '文件类型过滤'
      },
      scan: {
        btn: '扫描文件',
        successTitle: '扫描完成',
        successMessage: '发现 {total} 个文件。',
        errorTitle: '扫描错误'
      },
      jsonPreview: {
        title: 'JSON 预览（与 Viewer 兼容）'
      }
    },
    maskMaker: {
      title: '掩膜（Mask）制作',
      subtitle: '交互式 Mask 绘制，支持几何形状、铅笔线条与阈值遮盖，导出 silx/pyFAI 兼容格式。本工具基于 silx.image.shapes 与 pyFAI 的 mask 功能复刻，建议有条件时直接使用 pyFAI/silx 构建掩膜以获得更完整的功能。',
      empty: '选择图像文件以开始绘制 Mask。',
      toolbar: {
        file: '文件操作',
        openImage: '打开图像',
        loadMask: '加载 Mask',
        exportMask: '导出 Mask',
        drawTools: '绘制工具',
        mode: '绘制模式',
        mask: '遮盖',
        unmask: '擦除',
        edit: '编辑操作',
        undo: '撤销',
        redo: '重做',
        invert: '反转',
        clear: '清除全部'
      },
      tools: {
        pan: '平移',
        rectangle: '矩形',
        disk: '圆形',
        ellipse: '椭圆',
        polygon: '多边形',
        line: '线条'
      },
      properties: {
        imageInfo: '图像信息',
        fileName: '文件名',
        dimensions: '尺寸',
        format: '格式',
        min: '最小值',
        max: '最大值',
        std: '标准差',
        noImage: '未加载图像',
        maskStats: 'Mask 统计',
        maskedPixels: '遮盖像素',
        totalPixels: '总像素',
        percentage: '遮盖比例',
        contrast: '对比度调节',
        threshold: '阈值工具',
        thresholdMin: '下限',
        thresholdMax: '上限',
        belowMin: '遮盖低于下限的像素',
        aboveMax: '遮盖高于上限的像素',
        between: '遮盖介于上下限之间',
        notFinite: '遮盖非有限值'
      },
      canvas: {
        polygonHint: '单击添加顶点，双击闭合多边形'
      },
      export: {
        title: '导出 Mask',
        format: '导出格式',
        savePath: '保存路径',
        noPath: '未选择路径',
        browse: '浏览...',
        cancel: '取消',
        export: '导出',
        exporting: '导出中...'
      },
      messages: {
        maskLoaded: 'Mask 已加载',
        exportSuccess: 'Mask 已导出'
      },
      errors: {
        openFailed: '打开图像失败',
        loadFailed: '加载图像失败',
        shapeFailed: '绘制形状失败',
        thresholdFailed: '阈值遮盖失败',
        loadMaskFailed: '加载 Mask 失败',
        exportFailed: '导出失败'
      }
    },
    viewer: {
      title: '图像查看器',
      subtitle: '浏览 EDF / TIFF / HDF5 探测器图像，支持色图控制与 JSON 导出配置。',
      fileSection: '文件选择',
      selectFile: '选择图像文件',
      dataset: '数据集',
      channel: '通道',
      frameNav: '帧导航',
      displaySettings: '显示设置',
      colormap: '色图',
      logScale: '对数刻度',
      climMode: '对比度范围',
      climAuto: '自动',
      climManual: '手动',
      climMin: '最小值',
      climMax: '最大值',
      showAxes: '显示坐标轴',
      showColorbar: '显示色条',
      dpi: 'DPI',
      previewQuality: '预览画质',
      previewFast: '粗糙',
      previewFull: '100%',
      jsonExport: 'JSON 导出配置',
      jsonExportHint: '导出当前显示设置为 JSON 配置文件，可与 PNG 生成器页面配合进行批量处理。',
      exportJson: '导出 JSON 配置',
      emptyState: '请从侧边栏选择图像文件以开始查看。',
      rawPreview: '原始预览',
      heatmapView: '热力图',
      errorPrefix: '错误：',
      errorTitle: '查看器错误',
      exportSuccessTitle: '配置已导出',
      exportSuccessMessage: 'JSON 配置已成功导出。',
      jsonComment: '由查看器页面生成 — 可加载到 PNG 生成器中进行批量导出。',
      sourceFolderPlaceholder: '（在 PNG 生成器中指定）',
      outputFolderPlaceholder: '（在 PNG 生成器中指定）',
      thumbnailsPerRow: '每行缩略图',
      noThumbnails: '无缩略图数据',
      loadingImage: '加载图像中…',
      statsTitle: '统计 / Stats',
      statMin: '最小值',
      statMax: '最大值',
      statAdjMax: '调整最大值',
      statStd: '标准差',
      pngExport: 'PNG 导出',
      pngExportMode: '导出模式',
      exportSingle: '导出当前帧',
      exportBatch: '批量导出文件夹',
      exporting: '导出中…',
      batchSourceFolder: '源文件夹',
      batchOutputFolder: '输出文件夹',
      batchRecursive: '递归扫描子文件夹',
      loadingFullRes: '加载全分辨率…',
      selectFolder: '导入文件夹',
      recursiveScan: '递归扫描',
      thumbnailsPerPage: '每页数量',
      pageOf: '第 {current} 页 / 共 {total} 页',
      prevPage: '上一页',
      nextPage: '下一页',
      jumpToPage: '跳转',
      syncThumbnails: '同步缩略图',
      syncThumbnailsHint: '使用当前色图和对比度重新渲染缩略图。数据量较大时可能较慢。',
      noFilesInFolder: '文件夹中未找到图像文件。'
    },
    business: {
      fileDialog: {
        chooseFile: '选择文件',
        saveFile: '保存文件',
        chooseFolder: '选择文件夹',
        noSelection: '未选择文件',
        uploadFailed: '上传失败'
      },
      fileSelection: {
        selectFiles: '选择文件',
        importFolder: '导入文件夹',
        recursive: '递归扫描',
        clearAll: '清除全部',
        filesSelected: '已选择 {count} 个文件',
        noFiles: '未选择文件',
        expandAfterSelect: '选择文件后展开此区域加载预览',
        importMode: '导入模式',
        replace: '替换',
        append: '追加',
        replaceTooltip: '清除现有文件列表，仅使用新选择的文件',
        appendTooltip: '将新选择的文件追加到现有文件列表中'
      },
      sections: {
        maskImport: '掩膜导入',
        displaySettings: '显示设置',
        imagePreview: '图像预览',
        imageInfo: '图像信息',
        thumbnails: '缩略图',
        outputUnit: '输出单位',
        loading: '加载中',
        noImage: '无图像',
        beamCenter: '光斑中心',
        contrastMode: '对比度模式',
        format: '格式',
        batchFormat: '批量格式',
        fileName: '文件名'
      },
      display: {
        colormap: '色图',
        logScale: '对数强度',
        climMin: '最小值',
        climMax: '最大值',
        climAuto: '自动',
        climManual: '手动'
      },
      geometry: {
        title: '几何参数设置',
        poniMode: 'PONI 文件',
        manualMode: '手动输入',
        poniFile: '上传 .poni 文件',
        pixelSize: '像素尺寸 (µm)',
        distance: '样品-探测器距离 (mm)',
        wavelength: '波长 (Å)',
        centerX: '光束中心 X (px)',
        centerY: '光束中心 Y (px)'
      },
      mask: {
        title: '掩膜构建器',
        valueRangeMin: '最小强度',
        valueRangeMax: '最大强度',
        deadPixelThreshold: '死像素阈值',
        customMaskFile: '自定义掩膜文件',
        noCustomMask: '未加载自定义掩膜',
        maskActive: '✓ 已加载 Mask'
      },
      polarization: {
        title: '偏振校正',
        enable: '启用偏振校正',
        disabledHint: '当前：关闭（适用于实验室光源）',
        enabledHint: '0 = 非偏振（实验室），±0.99 = 同步辐射'
      },
      advancedOptions: {
        title: '高级选项',
        nptRad: '径向点数 (npt)',
        nptAzim: '方位角点数',
        radialMin: '径向最小值',
        radialMax: '径向最大值',
        unit: '单位',
        correctSolidAngle: '立体角校正',
        algorithm: '积分算法',
        integrator: '积分器引擎'
      },
      taskProgress: {
        processing: '处理中...',
        cancel: '取消'
      },
      export: {
        title: '导出结果',
        chooseFormat: '格式',
        outputPath: '输出路径',
        chooseOutputPath: '选择输出位置',
        execute: '导出',
        mode: '导出模式',
        mergeSingle: '合并为一个文件',
        exportSeparate: '分别导出',
        outputFolder: '输出文件夹',
        outputFolderPlaceholder: '选择导出文件夹'
      },
      resultSummary: {
        title: '结果摘要',
        total: '总数',
        success: '成功',
        failed: '失败',
        elapsed: '耗时'
      }
    },
    h5convert: {
      title: 'H5 格式转换',
      subtitle: '批量将 H5 数据集转换为 TIFF、CSV 或 DAT 格式。',
      step1: '步骤一：选择目录',
      step2: '步骤二：扫描 H5 文件',
      step3: '步骤三：选择数据集',
      step4: '步骤四：导出设置',
      sourceDir: '源目录（包含 H5 文件）',
      outputDir: '输出目录',
      recursive: '递归扫描子文件夹',
      refSuffix: '参考文件后缀',
      scanBtn: '扫描并加载',
      scanning: '扫描中...',
      scanResult: '共 {total} 个 H5 | 目标文件：{target} | 参考：{ref}',
      scanFailed: '扫描失败，请检查目录和后缀。',
      selectAll: '全选',
      deselectAll: '全不选',
      colExport: '导出',
      colPath: '数据集路径',
      colShape: '形状',
      colType: '数据类型',
      colKind: '类型',
      colChannels: '通道',
      allFrames: '全部帧',
      toTable: '→ 表格文件',
      imageFormat: '图像数据导出格式',
      tableFormat: '非图像数据导出格式',
      startExport: '开始导出',
      kindScalar: '标量',
      kind1d: '1维',
      kind2d: '2D 图像',
      kind3d: '3D 图像',
      kind4d: '4D 图像',
      kindImage: '图像',
      kindTable: '表格',
      fileList: {
        title: '扫描文件列表',
        expand: '展开文件列表（{total} 个文件）',
        collapse: '收起文件列表',
        empty: '未扫描到文件',
        scanning: '扫描中...',
        scanBtn: '扫描 H5 文件',
        pageSize: '每页 {size} 条',
        pageOf: '第 {current} / {total} 页',
        prevPage: '上一页',
        nextPage: '下一页',
        colIndex: '#',
        colFileName: '文件名',
        colPath: '路径',
        colSize: '大小',
        totalFiles: '共 {total} 个 H5 文件'
      }
    },
    h5extract: {
      title: 'H5 文件提取汇总',
      subtitle: '从嵌套目录中提取并汇总 H5 文件。',
      dirSection: '路径设置',
      rulesSection: '提取规则',
      sourceDir: '扫描源目录',
      targetDir: '输出目录',
      recursive: '递归扫描子文件夹',
      suffixFilter: '后缀过滤',
      suffixPlaceholder: '_master',
      suffixHint: '（例如 "_master"，留空则提取所有 .h5）',
      prependFolder: '文件名前附加所在父文件夹名称（推荐，避免同名覆盖）',
      prefix: '文件名前缀',
      prefixPlaceholder: '可选前缀...',
      conflictPolicy: '冲突处理',
      conflictRename: '自动重命名（追加序号）',
      conflictSkip: '跳过已存在文件',
      conflictOverwrite: '覆盖已存在文件',
      startExtract: '开始提取',
      fileList: {
        title: '扫描文件列表',
        expand: '展开文件列表（{total} 个文件）',
        collapse: '收起文件列表',
        empty: '未扫描到文件',
        scanning: '扫描中...',
        scanBtn: '扫描 H5 文件',
        pageSize: '每页 {size} 条',
        pageOf: '第 {current} / {total} 页',
        prevPage: '上一页',
        nextPage: '下一页',
        colIndex: '#',
        colFileName: '文件名',
        colPath: '路径',
        colSize: '大小',
        totalFiles: '共 {total} 个 H5 文件'
      }
    },
    calibrantGenerator: {
      title: '标样生成器',
      subtitle: '从 CIF 晶体结构文件生成 PyFAI 需要的 .d 标样校准文件',
      uploadFile: '上传 .cif 文件',
      selectFile: '选择 CIF 文件',
      crystalInfo: '晶体信息',
      formula: '化学式',
      latticeParams: '晶胞参数',
      intensityThreshold: '相对强度阈值 (%)',
      thresholdHint: '只有相对强度高于此值的衍射峰会被保留。建议设为 1% 以去除杂峰。',
      xrdPattern: 'XRD 衍射图谱',
      peaksPreview: '衍射峰预览',
      peaksCount: '保留 {count} 个衍射峰',
      downloadFile: '下载 .d 校准文件',
      error: {
        noFile: '请先选择 CIF 文件',
        parseError: 'CIF 文件解析失败，请检查文件格式',
        noPeaks: '当前阈值过高，没有保留任何衍射峰，请降低阈值',
      },
      table: {
        dSpacing: 'd 值 (Å)',
        intensity: '强度 (%)',
        twoTheta: '2θ (°)',
        hkl: '晶面指数',
      },
    },
    cellCalibrantGenerator: {
      title: '校正标样生成器',
      subtitle: 'CIF 晶体文件 / 晶胞参数 / 手动输入 d/q/2θ 生成 .D 标样校准文件',
      crystalSystem: '晶系',
      latticeType: '点阵类型',
      spaceGroup: '空间群',
      paramA: 'a (Å)',
      paramB: 'b (Å)',
      paramC: 'c (Å)',
      paramAlpha: 'α (°)',
      paramBeta: 'β (°)',
      paramGamma: 'γ (°)',
      materialName: '材料名称',
      materialNamePlaceholder: '例如 LaB6_SRM660b',
      dmin: '最小 d 值 (Å)',
      dminHint: '控制反射数量。值越小，衍射峰越多。',
      generate: '生成 .D 标样文件',
      generating: '生成中...',
      downloadFile: '下载 .D 校准文件',
      peaksCount: '生成 {count} 个衍射峰',
      reflectionsPreview: '衍射峰列表',
      crystalInfo: '晶体信息',
      cellParams: '晶胞参数',
      noReflectionsWarning: '未生成任何反射峰，请尝试减小 dmin 值。',
      noFile: '请先输入晶胞参数',
      generateError: '生成失败',
      cifMode: 'CIF 文件',
      cellMode: '晶胞参数',
      manualMode: '手动列表',
      inputUnit: '输入单位',
      wavelength: '波长 λ (Å)',
      inputValues: '输入数值',
      inputHint: '每行一个，支持 d / q / 2θ',
      error: {
        generateError: '生成失败，请检查参数是否正确。',
      },
      table: {
        dSpacing: 'd 值 (Å)',
        hkl: '晶面指数',
        multiplicity: '多重度',
      },
    },
    pyfaiCalib: {
      title: 'PyFAI 校准工具',
      subtitle: '检测并启动 pyFAI-calib2 探测器校准 GUI',
      checkStatus: '检测 pyFAI 状态',
      checking: '检测中...',
      embeddedPython: '内置 Python（已捆绑）',
      systemPython: '系统 Python',
      calib2Path: '可执行文件路径',
      version: '版本',
      available: '可用',
      notAvailable: '不可用',
      statusAvailable: 'pyFAI 在内置 Python 和系统 Python 中均可用。',
      statusEmbeddedOnly: 'pyFAI 仅在内置 Python 中可用。',
      statusSystemOnly: 'pyFAI 仅在系统 Python 中可用。',
      statusNotFound: '未找到 pyFAI。请先安装以使用校准工具。',
      launchBtn: '启动 pyFAI-calib2',
      launching: '启动中...',
      launchSuccess: 'pyFAI-calib2 已启动。',
      launchError: '启动 pyFAI-calib2 失败：{error}',
      installInstructions: '安装说明',
      pipCommand: '在终端（CMD 或 PowerShell）中运行以下命令：',
      copyCommand: '复制命令',
      copied: '已复制！',
      alreadyEmbedded: 'pyFAI 已安装在内置 Python 运行时中。',
      howToInstall: '安装 pyFAI',
      detectedBadge: '已检测',
      notDetectedBadge: '未检测到',
      qtBinding: 'Qt 绑定',
      qtAvailable: '可用',
      qtMissing: '缺失（需要 PySide6 或 PyQt6）',
      exportBat: '导出启动脚本',
      exportBatHint: '检测到 pyFAI 已安装。导出 .bat 脚本后，双击即可在系统默认 Python 环境中启动 pyFAI-calib2。',
      exportBatDesc: '导出一个 .bat 批处理脚本，可在任意 Windows 电脑上双击启动 pyFAI-calib2（需要已安装 Python 和 pyFAI）。',
      exporting: '导出中...',
      exportBatSuccess: '启动脚本已导出！双击 .bat 文件即可启动 pyFAI-calib2。',
      exportBatError: '导出失败，请重试。',
    }
  },
  en: {
    app: {
      name: 'X-FAIS',
      version: 'v0.1.0'
    },
    shell: {
      sections: {
        home: 'Workspace',
        workspace: 'Work Area',
        error: 'Recovery'
      },
      actions: {
        home: 'Home',
        language: 'Language'
      },
      status: {
        ready: 'Ready',
        pythonError: 'Python needs recovery',
        pythonRestarting: 'Python restarting',
        pythonStarting: 'Python starting'
      }
    },
    python: {
      detailLabel: 'Runtime Details',
      restart: 'Retry Python Runtime',
      states: {
        error: 'The bundled Python has exited unexpectedly.',
        restarting: 'The bundled Python is restarting.',
        starting: 'The bundled Python is starting.',
        stopped: 'The bundled Python has stopped.'
      },
      subtitle: 'The built-in runtime can recover without relying on system Python. Click retry to relaunch.',
      title: 'Built-in Python Runtime Recovery'
    },
    home: {
      title: 'X-FAIS',
      subtitle: 'X-ray FAI (pyFAI) Scattering & Diffraction Suite',
      kicker: 'Desktop Edition v0.1.0',
      description: 'Integrated pyFAI engine for 1D radial integration, azimuthal integration, CAKE sector integration, GIWAXS fiber 2D integration, image viewing, and batch export.',
      highlights: {
        secure: 'pyFAI Integration Engine',
        routing: 'Multi-format Data Support',
        logs: 'Batch Processing & Export'
      },
      heroPanel: {
        notice: 'This application is powered by pyFAI/fabIO',
        openSourceNotice: 'This project only integrates GUI for some common pyFAI features. The program will always be open source, with no paid or commercial development.',
        official: 'Base Homepage',
        study: 'Explore More',
        github: 'Base Repository',
        fabio: 'fabIO Repository',
        polymcrystal: 'Developer Homepage',
        contact: 'Contact the developer to customize more common features',
        issueHint: 'Submit an Issue for feedback or suggestions',
        repositories: 'Repositories'
      },
      acknowledgments: {
        title: 'Acknowledgments',
        thanks: 'Built by AI-Agent:',
        models: 'Programming models used:',
        developer: 'Development Organization: ',
        devOrg: 'ICCAS-EP-PMP'
      },
      sections: {
        commonIntegration: 'Common Integration',
        giwaxs: 'GIWAXS',
        imageTools: 'Image Tools',
        h5Tools: 'HDF5 Processing',
        pyfaiTools: 'pyFAI Utilities',
        comingSoon: 'Coming Soon'
      },
      badge: {
        comingSoon: 'Coming Soon'
      },
      actions: {
        openPlaceholder: 'Open Placeholder Workspace',
        showLogs: 'Show Log Directory',
        checkUpdate: 'Check for Updates',
        citePyFAI: 'Cite pyFAI',
        citeFabIO: 'Cite fabIO'
      },
      cards: {
        integrate1d: {
          title: '1D Radial Integration',
          description: 'Batch 1D azimuthal integration, output I(q) or I(2θ) curves'
        },
        integrateAzimuth: {
          title: 'Azimuthal χ Integration',
          description: 'Azimuthal χ integration for diffraction ring orientation analysis'
        },
        integrateCake: {
          title: 'CAKE Sector Integration',
          description: 'Sector-based radial integration for texture and anisotropic sample analysis'
        },
        integrateFiber: {
          title: 'GIWAXS Fiber 2D Integration',
          description: 'GIWAXS grazing-incidence 2D integration, output qip × qoop intensity map'
        },
        viewer: {
          title: 'Image Viewer',
          description: 'Browse EDF/TIFF/HDF5 images, colormap control, thumbnail navigation and batch PNG export'
        },
        h5convert: {
          title: 'H5 Format Converter',
          description: 'Batch convert H5 datasets to TIFF, CSV or DAT format'
        },
        h5extract: {
          title: 'H5 File Extraction',
          description: 'Recursively extract and aggregate H5 files from nested directories'
        },
        pngGenerate: {
          title: 'Batch PNG Generation',
          description: 'Generate colormapped PNG images in batch'
        },
        maskMaker: {
          title: 'Mask Maker',
          description: 'Interactive mask drawing based on silx/pyFAI mask modules. Consider using pyFAI/silx directly for more complete masking features when available.'
        },
        pyfaiCalib: {
          title: 'pyFAI-calib2 Launcher',
          description: 'Launch the pyFAI-calib2 detector calibration GUI'
        },
        cellCalibrantGenerator: {
          title: 'Calibrant Generator',
          description: 'Generate .D calibrant files from CIF / unit cell parameters / manual d/q/2θ input'
        }
      },
      logsToast: 'Log directory: {path}'
    },
    integrateAzimuth: {
      title: 'Azimuthal χ Integration',
      subtitle: 'Integrate over azimuthal angle χ within a specified radial range to obtain intensity vs χ distribution.',
      selectFile: 'Select Data File',
      run: 'Start Integration',
      running: 'Processing...',
      chartTitle: 'Azimuthal Integration Curve',
      axisLabels: {
        chiDeg: 'χ (deg)',
        chiRad: 'χ (rad)',
        intensity: 'Intensity'
      },
      radialRange: {
        title: 'Radial Range',
        unit: 'Radial Unit',
        min: 'Radial Min',
        max: 'Radial Max'
      },
      chiUnit: {
        title: 'Azimuthal Output Unit',
        deg: 'χ (deg) — chi_deg',
        rad: 'χ (rad) — chi_rad'
      },
      params: {
        title: 'Integration Parameters',
        npt: 'Azimuthal Points (npt)',
        nptRad: 'Radial Integration Points (npt_rad)'
      },
      azimuthRange: {
        title: 'Azimuthal Range',
        hint: '0° = positive X direction (right), counterclockwise. Leave empty to integrate full 360°.',
        min: 'Start Azimuth (°)',
        max: 'End Azimuth (°)',
        errorMinMax: 'Start azimuth must be less than end azimuth.'
      },
      errors: {
        radialRange: 'Radial min must be less than radial max.'
      }
    },
    placeholder: {
      title: 'Placeholder Workspace',
      subtitle: 'Specific feature pages will be integrated in follow-up tasks. This page validates the shell, routing, and layout contract.',
      badge: 'Reserved Route'
    },
    notFound: {
      title: 'Page Not Found',
      subtitle: 'The requested page is currently unavailable. You can safely return to the home page.',
      action: 'Back to Home'
    },
    integrateCake: {
      title: 'CAKE Sector Integration',
      description: 'Perform 1D radial integration over a specified azimuthal sector for texture analysis, strain measurement, and other anisotropic samples.',
      selectFile: 'Select Detector Image',
      azimuthRange: {
        title: 'Azimuthal Range',
        hint: '0° = positive X direction (right), increasing counterclockwise.',
        min: 'Start Azimuth (°)',
        max: 'End Azimuth (°)',
        errorEmpty: 'Azimuth values cannot be empty.',
        errorMinMax: 'Start azimuth must be less than end azimuth.'
      },
      run: 'Run CAKE Integration',
      imagePreview: {
        title: 'Image Preview',
        chartTitle: 'Image & Azimuthal Range',
        shape: 'Shape',
        sector: 'Azimuthal Sector'
      },
      resultChart: {
        title: 'Integration Result',
        yLabel: 'Intensity',
        chartTitle: 'CAKE Integration ({min}° → {max}°)'
      }
    },
    integrateFiber: {
      title: 'GIWAXS Fiber 2D Integration',
      subtitle: 'Perform grazing-incidence 2D integration (qip × qoop) using pyFAI FiberIntegrator.',
      fileSection: 'Upload Image',
      inputFile: 'Diffraction Image (.edf / .tif / .h5)',
      rotSection: 'Rotation Coverage (°)',
      sampleSection: 'Sample & Geometry',
      sampleOrientation: 'Sample Orientation (1–8)',
      incidentAngle: 'Incident Angle (°)',
      tiltAngle: 'Tilt Angle (°)',
      unitsSection: 'Coordinate Units',
      unitIp: 'In-plane (ip) Unit',
      unitOop: 'Out-of-plane (oop) Unit',
      rangeSection: 'Integration Range',
      autoRange: 'Auto Range (estimated by pyFAI)',
      ipMin: 'ip Lower Bound',
      ipMax: 'ip Upper Bound',
      oopMin: 'oop Lower Bound',
      oopMax: 'oop Upper Bound',
      nptSection: 'Grid Points',
      nptIp: 'npt_ip (in-plane)',
      nptOop: 'npt_oop (out-of-plane)',
      correctSolidAngle: 'Solid Angle Correction',
      runIntegration: 'Run Integration',
      running: 'Integrating...',
      result2dTitle: 'Integration Result',
      heatmapTitle: 'GIWAXS Map (qip × qoop)',
      logScale: 'Log Scale',
      horizontalProfile: 'Horizontal Profile (fixed oop)',
      verticalProfile: 'Vertical Profile (fixed ip)',
      targetOop: 'Target oop Value',
      targetIp: 'Target ip Value',
      hProfileTitle: 'oop ≈ {oop}',
      vProfileTitle: 'ip ≈ {ip}',
      intensity: 'Intensity',
      emptyHint: 'Upload an image, configure parameters, then click "Run Integration".',
      errorNoFile: 'Please select a diffraction image file.',
      errorNoGeometry: 'Incomplete geometry parameters.',
      errorIpRange: 'ip lower bound must be less than upper bound.',
      errorOopRange: 'oop lower bound must be less than upper bound.',
      errorNpt: 'npt_ip and npt_oop must be ≥ 50.',
      preview: 'Preview',
      batchExportFolder: 'Export to Folder',
      batchExportComplete: 'Batch Export Complete',
        loadToView: 'Load',
        moreFiles: '... {count} more files',
        memoryWarning: 'Loading files into memory may cause memory pressure. Load on demand.',
      },
    boundary: {
      title: 'Recoverable Error in Shell',
      subtitle: 'A rendering exception was caught. The system remains in a recoverable state.',
      action: 'Back to Home'
    },
    toast: {
      close: 'Close'
    },
    integrate1d: {
      title: '1D Radial Integration',
      subtitle: 'Batch 1D azimuthal integration of detector images using pyFAI.',
      dataFiles: 'Data Files',
      selectDataFiles: 'Select Data Files (.edf / .tif / .h5)',
      runIntegration: 'Run Integration',
      emptyState: 'Select data files and configure parameters, then click Run Integration.',
      resultTitle: 'Integration Results',
      chartTitle: '1D Radial Integration',
      intensityLabel: 'Intensity',
      errorPrefix: 'Integration failed: ',
      errorTitle: 'Integration Error',
      successTitle: 'Integration Complete',
      successMessage: 'Successfully processed {count} curve(s).',
      exportTitle: 'Export',
      exportMessage: 'Exported as {format} to {path}'
    },
    pngGenerate: {
      title: 'Batch PNG Generation',
      subtitle: 'Batch generate colormapped PNG images from H5/TIFF/EDF files.',
      emptyState: 'Select source folder and configure display settings to start.',
      run: 'Start Batch Export',
      successTitle: 'PNG Generation Complete',
      successMessage: 'Successfully generated {count} image(s).',
      errorTitle: 'PNG Generation Error',
      cancelledTitle: 'Cancelled',
      cancelledMessage: 'Generation cancelled. Completed files are retained in the output directory.',
      discoveredFiles: 'Discovered Files',
      folders: {
        title: 'Folders',
        source: 'Source Folder',
        sourcePlaceholder: 'Select Source Folder',
        output: 'Output Folder',
        outputPlaceholder: 'Select Output Folder',
        recursive: 'Recursive Subfolder Scan'
      },
      jsonConfig: {
        title: 'JSON Configuration',
        load: 'Import JSON',
        save: 'Export JSON',
        loadSuccessTitle: 'Configuration Loaded',
        loadSuccessMessage: 'Successfully imported Viewer-compatible JSON configuration.',
        loadErrorTitle: 'Import Failed',
        saveSuccessTitle: 'Configuration Saved',
        saveErrorTitle: 'Save Failed'
      },
      display: {
        title: 'Display & Export Settings',
        colormap: 'Colormap',
        useLog: 'Log Scale',
        clim: 'Contrast Range (CLIM)',
        climAuto: 'Auto',
        climManual: 'Manual',
        layout: 'Output Layout',
        layoutFlat: 'Flat Layout',
        layoutPerFile: 'Per-File Directory',
        dpi: 'DPI',
        showAxes: 'Show Axes',
        showColorbar: 'Show Colorbar'
      },
      fileTypes: {
        title: 'File Type Filter'
      },
      scan: {
        btn: 'Scan Files',
        successTitle: 'Scan Complete',
        successMessage: 'Found {total} file(s).',
        errorTitle: 'Scan Error'
      },
      jsonPreview: {
        title: 'JSON Preview (Viewer-compatible)'
      }
    },
    maskMaker: {
      title: 'Mask Maker',
      subtitle: 'Interactive mask drawing with geometric shapes & threshold masking. Export to silx/pyFAI-compatible formats. This tool replicates silx.image.shapes and pyFAI mask features — consider using pyFAI/silx directly for more complete masking capabilities.',
      empty: 'Select an image file to start drawing a mask.',
      toolbar: {
        file: 'File Operations',
        openImage: 'Open Image',
        loadMask: 'Load Mask',
        exportMask: 'Export Mask',
        drawTools: 'Draw Tools',
        mode: 'Mode',
        mask: 'Mask',
        unmask: 'Unmask',
        edit: 'Edit',
        undo: 'Undo',
        redo: 'Redo',
        invert: 'Invert',
        clear: 'Clear All'
      },
      tools: {
        pan: 'Pan',
        rectangle: 'Rectangle',
        disk: 'Circle',
        ellipse: 'Ellipse',
        polygon: 'Polygon',
        line: 'Line'
      },
      properties: {
        imageInfo: 'Image Info',
        fileName: 'File Name',
        dimensions: 'Dimensions',
        format: 'Format',
        min: 'Min',
        max: 'Max',
        std: 'Std Dev',
        noImage: 'No image loaded',
        maskStats: 'Mask Stats',
        maskedPixels: 'Masked Pixels',
        totalPixels: 'Total Pixels',
        percentage: 'Coverage',
        contrast: 'Contrast',
        threshold: 'Threshold',
        thresholdMin: 'Lower Bound',
        thresholdMax: 'Upper Bound',
        belowMin: 'Mask Below Lower Bound',
        aboveMax: 'Mask Above Upper Bound',
        between: 'Mask Between Bounds',
        notFinite: 'Mask Non-Finite'
      },
      canvas: {
        polygonHint: 'Click to add vertices, double-click to close polygon'
      },
      export: {
        title: 'Export Mask',
        format: 'Format',
        savePath: 'Save Path',
        noPath: 'No path selected',
        browse: 'Browse...',
        cancel: 'Cancel',
        export: 'Export',
        exporting: 'Exporting...'
      },
      messages: {
        maskLoaded: 'Mask loaded',
        exportSuccess: 'Mask exported successfully'
      },
      errors: {
        openFailed: 'Failed to open image',
        loadFailed: 'Failed to load image',
        shapeFailed: 'Failed to apply shape',
        thresholdFailed: 'Failed to apply threshold',
        loadMaskFailed: 'Failed to load mask',
        exportFailed: 'Failed to export mask'
      }
    },
    viewer: {
      title: 'Image Viewer',
      subtitle: 'Browse EDF / TIFF / HDF5 detector images with colormap control and JSON export configuration.',
      fileSection: 'File Selection',
      selectFile: 'Select Image File',
      dataset: 'Dataset',
      channel: 'Channel',
      frameNav: 'Frame Navigation',
      displaySettings: 'Display Settings',
      colormap: 'Colormap',
      logScale: 'Log Scale',
      climMode: 'Contrast Range',
      climAuto: 'Auto',
      climManual: 'Manual',
      climMin: 'Min',
      climMax: 'Max',
      showAxes: 'Show Axes',
      showColorbar: 'Show Colorbar',
      dpi: 'DPI',
      previewQuality: 'Preview Quality',
      previewFast: 'Fast',
      previewFull: '100%',
      jsonExport: 'JSON Export Config',
      jsonExportHint: 'Export current display settings as a JSON configuration file compatible with the PNG Generator for batch processing.',
      exportJson: 'Export JSON Config',
      emptyState: 'Select an image file from the sidebar to start viewing.',
      rawPreview: 'Raw Preview',
      heatmapView: 'Heatmap',
      errorPrefix: 'Error: ',
      errorTitle: 'Viewer Error',
      exportSuccessTitle: 'Config Exported',
      exportSuccessMessage: 'JSON configuration has been successfully exported.',
      jsonComment: 'Generated by Viewer — load into PNG Generator for batch export.',
      sourceFolderPlaceholder: '(Specify in PNG Generator)',
      outputFolderPlaceholder: '(Specify in PNG Generator)',
      thumbnailsPerRow: 'Thumbnails Per Row',
      noThumbnails: 'No Thumbnail Data',
      loadingImage: 'Loading image…',
      statsTitle: 'Stats',
      statMin: 'Min',
      statMax: 'Max',
      statAdjMax: 'Adj Max',
      statStd: 'Std Dev',
      pngExport: 'PNG Export',
      pngExportMode: 'Export Mode',
      exportSingle: 'Export Current Frame',
      exportBatch: 'Batch Export Folder',
      exporting: 'Exporting…',
      batchSourceFolder: 'Source Folder',
      batchOutputFolder: 'Output Folder',
      batchRecursive: 'Recursive Subfolder Scan',
      loadingFullRes: 'Loading full resolution…',
      selectFolder: 'Import Folder',
      recursiveScan: 'Recursive Scan',
      thumbnailsPerPage: 'Per Page',
      pageOf: 'Page {current} of {total}',
      prevPage: 'Previous',
      nextPage: 'Next',
      jumpToPage: 'Go',
      syncThumbnails: 'Sync Thumbnails',
      syncThumbnailsHint: 'Re-render thumbnails with current colormap and contrast. May be slow with large datasets.',
      noFilesInFolder: 'No image files found in folder.'
    },
    business: {
      fileDialog: {
        chooseFile: 'Choose File',
        saveFile: 'Save File',
        chooseFolder: 'Choose Folder',
        noSelection: 'No file selected',
        uploadFailed: 'Upload Failed'
      },
      fileSelection: {
        selectFiles: 'Select Files',
        importFolder: 'Import Folder',
        recursive: 'Recursive',
        clearAll: 'Clear All',
        filesSelected: '{count} file(s) selected',
        noFiles: 'No files selected',
        expandAfterSelect: 'Expand after selecting a file',
        importMode: 'Import Mode',
        replace: 'Replace',
        append: 'Append',
        replaceTooltip: 'Clear existing file list and use only newly selected files',
        appendTooltip: 'Append newly selected files to the existing file list'
      },
      sections: {
        maskImport: 'Mask Import',
        displaySettings: 'Display Settings',
        imagePreview: 'Image Preview',
        imageInfo: 'Image Info',
        thumbnails: 'Thumbnails',
        outputUnit: 'Output Unit',
        loading: 'Loading...',
        noImage: 'No image',
        beamCenter: 'Beam Center',
        contrastMode: 'Contrast Mode',
        format: 'Format',
        batchFormat: 'Batch Format',
        fileName: 'File Name'
      },
      display: {
        colormap: 'Colormap',
        logScale: 'Log scale',
        climMin: 'Min',
        climMax: 'Max',
        climAuto: 'Auto',
        climManual: 'Manual'
      },
      geometry: {
        title: 'Geometry Parameters',
        poniMode: 'PONI File',
        manualMode: 'Manual Input',
        poniFile: 'Upload .poni File',
        pixelSize: 'Pixel Size (µm)',
        distance: 'Sample-Detector Distance (mm)',
        wavelength: 'Wavelength (Å)',
        centerX: 'Beam Center X (px)',
        centerY: 'Beam Center Y (px)'
      },
      mask: {
        title: 'Mask Builder',
        valueRangeMin: 'Min Intensity',
        valueRangeMax: 'Max Intensity',
        deadPixelThreshold: 'Dead Pixel Threshold',
        customMaskFile: 'Custom Mask File',
        noCustomMask: 'No custom mask loaded',
        maskActive: '✓ Mask Loaded'
      },
      polarization: {
        title: 'Polarization Correction',
        enable: 'Enable Polarization Correction',
        disabledHint: 'Currently: off (suitable for lab sources)',
        enabledHint: '0 = unpolarized (lab), ±0.99 = synchrotron'
      },
      advancedOptions: {
        title: 'Advanced Options',
        nptRad: 'Radial Points (npt)',
        nptAzim: 'Azimuthal Points',
        radialMin: 'Radial Min',
        radialMax: 'Radial Max',
        unit: 'Unit',
        correctSolidAngle: 'Solid Angle Correction',
        algorithm: 'Integration Algorithm',
        integrator: 'Integrator Engine'
      },
      taskProgress: {
        processing: 'Processing...',
        cancel: 'Cancel'
      },
      export: {
        title: 'Export Results',
        chooseFormat: 'Format',
        outputPath: 'Output Path',
        chooseOutputPath: 'Choose Output Location',
        execute: 'Export',
        mode: 'Export Mode',
        mergeSingle: 'Merge into single file',
        exportSeparate: 'Export separately',
        outputFolder: 'Output Folder',
        outputFolderPlaceholder: 'Select Export Folder'
      },
      resultSummary: {
        title: 'Result Summary',
        total: 'Total',
        success: 'Success',
        failed: 'Failed',
        elapsed: 'Elapsed'
      }
    },
    h5convert: {
      title: 'H5 Format Converter',
      subtitle: 'Batch convert H5 datasets to TIFF, CSV, or DAT format.',
      step1: 'Step 1: Select Directory',
      step2: 'Step 2: Scan H5 Files',
      step3: 'Step 3: Select Datasets',
      step4: 'Step 4: Export Settings',
      sourceDir: 'Source Directory (containing H5 files)',
      outputDir: 'Output Directory',
      recursive: 'Recursive Subfolder Scan',
      refSuffix: 'Reference File Suffix',
      scanBtn: 'Scan & Load',
      scanning: 'Scanning...',
      scanResult: '{total} H5 files | Target: {target} | Reference: {ref}',
      scanFailed: 'Scan failed. Please check the directory and suffix.',
      selectAll: 'Select All',
      deselectAll: 'Deselect All',
      colExport: 'Export',
      colPath: 'Dataset Path',
      colShape: 'Shape',
      colType: 'Data Type',
      colKind: 'Kind',
      colChannels: 'Channels',
      allFrames: 'All Frames',
      toTable: '→ Table File',
      imageFormat: 'Image Data Export Format',
      tableFormat: 'Non-image Data Export Format',
      startExport: 'Start Export',
      kindScalar: 'Scalar',
      kind1d: '1D',
      kind2d: '2D Image',
      kind3d: '3D Image',
      kind4d: '4D Image',
      kindImage: 'Image',
      kindTable: 'Table',
      fileList: {
        title: 'Scanned File List',
        expand: 'Expand file list ({total} files)',
        collapse: 'Collapse file list',
        empty: 'No files scanned',
        scanning: 'Scanning...',
        scanBtn: 'Scan H5 Files',
        pageSize: '{size} per page',
        pageOf: 'Page {current} / {total}',
        prevPage: 'Previous',
        nextPage: 'Next',
        colIndex: '#',
        colFileName: 'File Name',
        colPath: 'Path',
        colSize: 'Size',
        totalFiles: '{total} H5 files in total'
      }
    },
    h5extract: {
      title: 'H5 File Extraction',
      subtitle: 'Extract and aggregate H5 files from nested directories.',
      dirSection: 'Path Settings',
      rulesSection: 'Extraction Rules',
      sourceDir: 'Source Directory',
      targetDir: 'Output Directory',
      recursive: 'Recursive Subfolder Scan',
      suffixFilter: 'Suffix Filter',
      suffixPlaceholder: '_master',
      suffixHint: '(e.g. "_master"; leave empty to extract all .h5)',
      prependFolder: 'Prepend parent folder name to filename (recommended to avoid overwrites)',
      prefix: 'Filename Prefix',
      prefixPlaceholder: 'Optional prefix...',
      conflictPolicy: 'Conflict Handling',
      conflictRename: 'Auto-rename (append sequence number)',
      conflictSkip: 'Skip existing files',
      conflictOverwrite: 'Overwrite existing files',
      startExtract: 'Start Extraction',
      fileList: {
        title: 'Scanned File List',
        expand: 'Expand file list ({total} files)',
        collapse: 'Collapse file list',
        empty: 'No files scanned',
        scanning: 'Scanning...',
        scanBtn: 'Scan H5 Files',
        pageSize: '{size} per page',
        pageOf: 'Page {current} / {total}',
        prevPage: 'Previous',
        nextPage: 'Next',
        colIndex: '#',
        colFileName: 'File Name',
        colPath: 'Path',
        colSize: 'Size',
        totalFiles: '{total} H5 files in total'
      }
    },
    calibrantGenerator: {
      title: 'Calibrant Generator',
      subtitle: 'Generate .d calibrant files from CIF crystal structure files for PyFAI',
      uploadFile: 'Upload .cif File',
      selectFile: 'Select CIF File',
      crystalInfo: 'Crystal Info',
      formula: 'Formula',
      latticeParams: 'Lattice Parameters',
      intensityThreshold: 'Relative Intensity Threshold (%)',
      thresholdHint: 'Only diffraction peaks with relative intensity above this value will be retained. Suggested: 1% to filter noise.',
      xrdPattern: 'XRD Pattern',
      peaksPreview: 'Peak Preview',
      peaksCount: '{count} peak(s) retained',
      downloadFile: 'Download .d Calibrant File',
      error: {
        noFile: 'Please select a CIF file first',
        parseError: 'Failed to parse CIF file. Please check the file format.',
        noPeaks: 'Threshold too high. No peaks retained. Try a lower value.',
      },
      table: {
        dSpacing: 'd-spacing (Å)',
        intensity: 'Intensity (%)',
        twoTheta: '2θ (°)',
        hkl: 'hkl',
      },
    },
    cellCalibrantGenerator: {
      title: 'Calibrant Generator',
      subtitle: 'Generate .D calibrant files from CIF / unit cell parameters / manual d/q/2θ input',
      crystalSystem: 'Crystal System',
      latticeType: 'Lattice Type',
      spaceGroup: 'Space Group',
      paramA: 'a (Å)',
      paramB: 'b (Å)',
      paramC: 'c (Å)',
      paramAlpha: 'α (°)',
      paramBeta: 'β (°)',
      paramGamma: 'γ (°)',
      materialName: 'Material Name',
      materialNamePlaceholder: 'e.g. LaB6_SRM660b',
      dmin: 'Min d-spacing (Å)',
      dminHint: 'Controls the number of reflections. Smaller values produce more peaks.',
      generate: 'Generate .D Calibrant File',
      generating: 'Generating...',
      downloadFile: 'Download .D Calibrant File',
      peaksCount: '{count} peak(s) generated',
      reflectionsPreview: 'Reflection List',
      crystalInfo: 'Crystal Info',
      cellParams: 'Cell Parameters',
      noReflectionsWarning: 'No reflections generated. Try reducing the dmin value.',
      noFile: 'Please enter cell parameters first',
      generateError: 'Generation Failed',
      cifMode: 'CIF File',
      cellMode: 'Cell Parameters',
      manualMode: 'Manual List',
      inputUnit: 'Input Unit',
      wavelength: 'Wavelength λ (Å)',
      inputValues: 'Input Values',
      inputHint: 'One per line, supports d / q / 2θ',
      error: {
        generateError: 'Generation failed. Please check your parameters.',
      },
      table: {
        dSpacing: 'd-spacing (Å)',
        hkl: 'hkl',
        multiplicity: 'Multiplicity',
      },
    },
    pyfaiCalib: {
      title: 'PyFAI Calibration Tool',
      subtitle: 'Detect and launch the pyFAI-calib2 detector calibration GUI',
      checkStatus: 'Check pyFAI Status',
      checking: 'Checking...',
      embeddedPython: 'Embedded Python (bundled)',
      systemPython: 'System Python',
      calib2Path: 'Executable Path',
      version: 'Version',
      available: 'Available',
      notAvailable: 'Not Available',
      statusAvailable: 'pyFAI is available in both embedded and system Python.',
      statusEmbeddedOnly: 'pyFAI is only available in the embedded Python.',
      statusSystemOnly: 'pyFAI is only available in system Python.',
      statusNotFound: 'pyFAI not found. Please install it first to use the calibration tool.',
      launchBtn: 'Launch pyFAI-calib2',
      launching: 'Launching...',
      launchSuccess: 'pyFAI-calib2 has been launched.',
      launchError: 'Failed to launch pyFAI-calib2: {error}',
      installInstructions: 'Installation Instructions',
      pipCommand: 'Run the following command in a terminal (CMD or PowerShell):',
      copyCommand: 'Copy Command',
      copied: 'Copied!',
      alreadyEmbedded: 'pyFAI is already installed in the embedded Python runtime.',
      howToInstall: 'Install pyFAI',
      detectedBadge: 'Detected',
      notDetectedBadge: 'Not Detected',
      qtBinding: 'Qt Binding',
      qtAvailable: 'Available',
      qtMissing: 'Missing (PySide6 or PyQt6 required)',
      exportBat: 'Export Launcher Script',
      exportBatHint: 'pyFAI detected. Export a .bat script to launch pyFAI-calib2 using your system Python environment.',
      exportBatDesc: 'Export a .bat batch script that can launch pyFAI-calib2 on any Windows PC with a double-click (requires Python and pyFAI installed).',
      exporting: 'Exporting...',
      exportBatSuccess: 'Launcher script exported! Double-click the .bat file to start pyFAI-calib2.',
      exportBatError: 'Export failed, please try again.',
    }
  }
} as const

export type AppLocale = keyof typeof messages
