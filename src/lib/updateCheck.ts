// 更新检查：多源拉取最新版本信息（OSS 国内源优先，GitHub API 兜底）+ 语义化版本比较。
//
// 发版流程（与应用代码解耦）：
//   1. 上传新版本安装包到 OSS 桶根目录（文件名带版本号，如 X-FAIS-0.3.4-setup-x64.exe）；
//   2. 覆盖上传 latest.json（结构见下方 LatestReleaseInfo / OSS_LATEST_URL 处示例）。
//
// latest.json 示例：
//   {
//     "version": "0.3.4",
//     "date": "2026-10-22",
//     "downloads": [
//       { "label": "Windows 安装包", "url": "https://xfais.oss-cn-beijing.aliyuncs.com/X-FAIS-0.3.4-setup-x64.exe" },
//       { "label": "Windows 便携版", "url": "https://xfais.oss-cn-beijing.aliyuncs.com/X-FAIS-0.3.4-portable-x64.exe" }
//     ]
//   }
// downloads 第一项视为首选下载（安装包排在最前）。

export interface UpdateDownload {
  label?: string
  url: string
}

export interface LatestReleaseInfo {
  version: string
  date?: string
  downloads: UpdateDownload[]
  /** 命中的更新源：oss = 国内主源，github = 海外兜底 */
  source: 'oss' | 'github'
}

// 主源：阿里云 OSS 公共读直链（桶 xfais，北京地域），国内直连
const OSS_LATEST_URL = 'https://xfais.oss-cn-beijing.aliyuncs.com/latest.json'
// 兜底源：团队库 GitHub Releases API（海外用户 / OSS 不可达时）
const GITHUB_RELEASES_API = 'https://api.github.com/repos/ICCAS-EPlab-PMP/XFAIS/releases/latest'

const FETCH_TIMEOUT_MS = 8000

async function fetchWithTimeout(url: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
  try {
    return await fetch(url, { ...init, signal: controller.signal })
  } finally {
    window.clearTimeout(timer)
  }
}

interface OssLatestJson {
  version?: unknown
  date?: unknown
  downloads?: unknown
}

async function fetchFromOss(): Promise<LatestReleaseInfo | null> {
  // 时间戳参数绕开中间层对 JSON 的缓存，保证发版后新版本号立即可见
  const resp = await fetchWithTimeout(`${OSS_LATEST_URL}?t=${Date.now()}`, { cache: 'no-store' })
  if (!resp.ok) return null
  const data = (await resp.json()) as OssLatestJson
  const version = typeof data.version === 'string' ? data.version.trim() : ''
  if (!version) return null
  const downloads = Array.isArray(data.downloads)
    ? data.downloads.filter(
        (item): item is UpdateDownload =>
          !!item &&
          typeof item === 'object' &&
          typeof (item as UpdateDownload).url === 'string' &&
          (item as UpdateDownload).url.length > 0
      )
    : []
  if (downloads.length === 0) return null
  return {
    version,
    date: typeof data.date === 'string' ? data.date : undefined,
    downloads,
    source: 'oss'
  }
}

async function fetchFromGithub(): Promise<LatestReleaseInfo | null> {
  const resp = await fetchWithTimeout(GITHUB_RELEASES_API, {
    headers: { Accept: 'application/vnd.github+json' }
  })
  if (!resp.ok) return null
  const data = (await resp.json()) as { tag_name?: string; html_url?: string }
  const version = (data.tag_name ?? '').replace(/^v/, '')
  if (!version) return null
  const releaseUrl =
    data.html_url ?? 'https://github.com/ICCAS-EPlab-PMP/XFAIS/releases/latest'
  return {
    version,
    downloads: [{ label: 'GitHub Release', url: releaseUrl }],
    source: 'github'
  }
}

/**
 * 依次尝试各更新源，返回第一个有效结果；全部失败返回 null（由调用方决定提示方式）。
 */
export async function fetchLatestRelease(): Promise<LatestReleaseInfo | null> {
  const sources: Array<() => Promise<LatestReleaseInfo | null>> = [fetchFromOss, fetchFromGithub]
  for (const source of sources) {
    try {
      const info = await source()
      if (info) return info
    } catch {
      // 单源失败（超时/不可达/响应异常）静默，继续下一源
    }
  }
  return null
}

/**
 * 语义化版本比较（x.y.z 数字段；带预发布后缀视为低于同号正式版）。
 * 返回 >0 表示 a 更新，<0 表示 b 更新，0 表示相同。
 */
export function compareVersions(a: string, b: string): number {
  const parse = (v: string): { nums: number[]; pre: string } => {
    const [core, pre] = v.trim().replace(/^v/, '').split('-', 2)
    const nums = core
      .split('.')
      .map((seg) => {
        const n = Number.parseInt(seg, 10)
        return Number.isFinite(n) ? n : 0
      })
    while (nums.length < 3) nums.push(0)
    return { nums: nums.slice(0, 3), pre: pre ?? '' }
  }
  const va = parse(a)
  const vb = parse(b)
  for (let i = 0; i < 3; i++) {
    if (va.nums[i] !== vb.nums[i]) return va.nums[i] - vb.nums[i]
  }
  if (va.pre === vb.pre) return 0
  if (va.pre === '') return 1
  if (vb.pre === '') return -1
  return va.pre < vb.pre ? -1 : 1
}

/** 远端版本是否比当前版本新（相等或更旧都返回 false，避免误报） */
export function isNewerVersion(remote: string, current: string): boolean {
  return compareVersions(remote, current) > 0
}

/** 首选下载链接（latest.json 中 downloads 的第一项，发版时把安装包排在最前） */
export function primaryDownloadUrl(info: LatestReleaseInfo): string {
  return info.downloads[0]?.url ?? ''
}
