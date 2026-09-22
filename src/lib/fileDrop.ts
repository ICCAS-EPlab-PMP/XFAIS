/**
 * fileDrop.ts — Shared drag-and-drop file import utilities.
 * 共享的拖拽文件导入工具。
 *
 * Desktop mode: dropped File objects are resolved to absolute paths via
 * window.desktop.getPathForFile (webUtils.getPathForFile in preload; File.path
 * was removed in Electron 32+).
 * Web mode: dropped files are uploaded through transport.uploadFile to obtain
 * server paths; folder drops are not supported in web mode.
 */

import { ref, type Ref } from 'vue'
import type { ITransport } from './transport'
import { toastStore } from './toast'
import { globalT } from '@/i18n'
import { runLimited } from './upload'

/** Shrink rejected file names for a toast message. */
export function shortenNames(names: string[], limit = 3): string {
  const shown = names.slice(0, limit).join(', ')
  return names.length > limit ? `${shown} …` : shown
}

/** One item extracted from a drop event. */
export interface DroppedItem {
  /** Original browser File object (usable for upload / FileReader). */
  file: File
  /** Absolute path in desktop mode; empty string in web mode. */
  path: string
  /** True when the dropped item is a directory (desktop only). */
  isDirectory: boolean
}

/** Result of resolving dropped items against a transport. */
export interface DropResolution {
  /** Absolute (desktop) or server (web) paths of accepted regular files. */
  filePaths: string[]
  /** Original File objects matching filePaths (for content reads, e.g. JSON). */
  fileObjects: File[]
  /** First dropped folder path; empty when none or unsupported (web mode). */
  folderPath: string
  /** Total number of dropped folders (callers toast when web mode cannot use them). */
  folderCount: number
  /** Dropped file names rejected by the extension filter. */
  rejectedNames: string[]
}

/** Check whether a file name matches any of the given dialog-style extensions. */
export function matchesExtensions(fileName: string, extensions?: string[]): boolean {
  if (!extensions || extensions.length === 0) return true
  const all = extensions
    .flatMap((e) => e.split(','))
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean)
  if (all.includes('*')) return true
  const lower = fileName.toLowerCase()
  return all.some((ext) => lower.endsWith(ext.startsWith('.') ? ext : `.${ext}`))
}

/** Resolve a dropped File to an absolute path ('' when unavailable). */
export function getDroppedFilePath(file: File): string {
  const desktop = (window as unknown as Record<string, unknown>).desktop as
    | { getPathForFile?: (f: File) => string }
    | undefined
  if (desktop && typeof desktop.getPathForFile === 'function') {
    try {
      return desktop.getPathForFile(file)
    } catch {
      // Fall through to the legacy property.
    }
  }
  return (file as File & { path?: string }).path ?? ''
}

/**
 * Extract dropped items from a DataTransfer. Must be called synchronously
 * inside the drop handler — webkitGetAsEntry() stops working after any await.
 */
export function extractDroppedItems(dataTransfer: DataTransfer | null): DroppedItem[] {
  const items: DroppedItem[] = []
  if (!dataTransfer) return items

  if (dataTransfer.items && dataTransfer.items.length > 0) {
    for (const item of Array.from(dataTransfer.items)) {
      if (item.kind !== 'file') continue
      const entry =
        typeof (item as DataTransferItem & { webkitGetAsEntry?: () => (FileSystemEntry | null) })
          .webkitGetAsEntry === 'function'
          ? (item as DataTransferItem & { webkitGetAsEntry?: () => (FileSystemEntry | null) })
              .webkitGetAsEntry()
          : null
      const file = item.getAsFile()
      if (!file) continue
      items.push({
        file,
        path: getDroppedFilePath(file),
        isDirectory: entry?.isDirectory === true,
      })
    }
  }

  // Fallback for environments without dataTransfer.items.
  if (items.length === 0 && dataTransfer.files && dataTransfer.files.length > 0) {
    for (const file of Array.from(dataTransfer.files)) {
      items.push({ file, path: getDroppedFilePath(file), isDirectory: false })
    }
  }

  return items
}

/** Collect the extension list from dialog-style filters. */
export function extensionsFromFilters(
  filters?: Array<{ name: string; extensions: string[] }>
): string[] {
  if (!filters || filters.length === 0) return []
  return filters.flatMap((f) => f.extensions)
}

/**
 * Resolve dropped items into usable paths.
 * - Desktop: paths come straight from getDroppedFilePath.
 * - Web: each accepted file is uploaded via transport.uploadFile.
 * Folders only yield a usable folderPath in desktop mode.
 */
export async function resolveDroppedFiles(
  items: DroppedItem[],
  transport: ITransport,
  extensions?: string[]
): Promise<DropResolution> {
  const files = items.filter((i) => !i.isDirectory)
  const folders = items.filter((i) => i.isDirectory)

  const filePaths: string[] = []
  const fileObjects: File[] = []
  const rejectedNames: string[] = []
  const needUpload: DroppedItem[] = []

  for (const item of files) {
    if (!matchesExtensions(item.file.name, extensions)) {
      rejectedNames.push(item.file.name)
      continue
    }
    if (item.path) {
      filePaths.push(item.path)
      fileObjects.push(item.file)
    } else {
      needUpload.push(item)
    }
  }

  // Web mode: no local paths — upload each accepted file to get a server path.
  // Bounded-concurrency uploads (order preserved) keep multi-file drops fast.
  // Same-name files are chained serially: the server picks conflict suffixes
  // via an exists() check, so two concurrent same-name writes would race.
  const lastByName = new Map<string, Promise<unknown>>()
  const serverPaths = await runLimited(
    needUpload.map((item) => () => {
      const prev = lastByName.get(item.file.name) ?? Promise.resolve()
      const task = prev.then(() =>
        transport.uploadFile(item.file).catch(() => ''),
      )
      lastByName.set(item.file.name, task)
      return task
    }),
    3,
  )
  serverPaths.forEach((serverPath, index) => {
    if (serverPath) {
      filePaths.push(serverPath)
      fileObjects.push(needUpload[index].file)
    }
  })

  return {
    filePaths,
    fileObjects,
    folderPath: folders.length > 0 ? folders[0].path : '',
    folderCount: folders.length,
    rejectedNames,
  }
}

/** True when a drag event carries files (used to ignore text/node drags). */
function dragHasFiles(e: DragEvent): boolean {
  return !!e.dataTransfer && Array.from(e.dataTransfer.types ?? []).includes('Files')
}

export interface DropZoneOptions {
  /** Transport used for web-mode uploads. */
  transport: ITransport
  /** Accepted file extensions; empty means all files. A getter keeps it reactive to prop changes. */
  extensions?: string[] | (() => string[])
  /** Called with resolved file paths and the first dropped folder path. */
  onDrop: (resolution: DropResolution) => void | Promise<void>
}

export interface DropZone {
  isDragging: Ref<boolean>
  onDragEnter: (e: DragEvent) => void
  onDragOver: (e: DragEvent) => void
  onDragLeave: (e: DragEvent) => void
  onDrop: (e: DragEvent) => void
}

/**
 * Composable that turns any element into a file drop target.
 * Bind all four handlers (@dragenter/@dragover/@dragleave/@drop) and use
 * isDragging for highlight styling.
 */
export function useDropZone(options: DropZoneOptions): DropZone {
  const isDragging = ref(false)
  let depth = 0

  function onDragEnter(e: DragEvent): void {
    if (!dragHasFiles(e)) return
    e.preventDefault()
    depth += 1
    isDragging.value = true
  }

  function onDragOver(e: DragEvent): void {
    if (!dragHasFiles(e)) return
    e.preventDefault()
  }

  function onDragLeave(e: DragEvent): void {
    if (!dragHasFiles(e)) return
    depth = Math.max(0, depth - 1)
    if (depth === 0) isDragging.value = false
  }

  function onDrop(e: DragEvent): void {
    if (!dragHasFiles(e)) return
    e.preventDefault()
    depth = 0
    isDragging.value = false
    const exts =
      typeof options.extensions === 'function' ? options.extensions() : options.extensions
    const items = extractDroppedItems(e.dataTransfer)
    void resolveDroppedFiles(items, options.transport, exts)
      .then((resolution) => options.onDrop(resolution))
      .catch(() => {
        isDragging.value = false
      })
  }

  return { isDragging, onDragEnter, onDragOver, onDragLeave, onDrop }
}

export interface ImportDropZoneOptions {
  /** Transport used for web-mode uploads. */
  transport: ITransport
  /** Accepted file extensions; empty means all files. */
  extensions?: string[] | (() => string[])
  /** Apply a batch of dropped file paths (same semantics as manual selection). */
  onFiles: (paths: string[]) => void | Promise<void>
  /** Apply a dropped folder path (desktop only): set state + rescan. */
  onFolder: (folderPath: string) => void | Promise<void>
}

/**
 * Drop zone for the common "select files / import folder" card.
 * Standardizes the reaction: folder drop → onFolder, file drop → onFiles,
 * with toasts for web-mode folder drops, extra folders, and rejected types.
 */
export function createImportDropZone(options: ImportDropZoneOptions): DropZone {
  return useDropZone({
    transport: options.transport,
    extensions: options.extensions,
    onDrop(resolution) {
      if (resolution.folderPath) {
        void options.onFolder(resolution.folderPath)
        if (resolution.folderCount > 1) {
          toastStore.push({
            title: globalT('business.fileSelection.importFolder'),
            message: globalT('business.fileSelection.dropIgnoredFolders', {
              count: resolution.folderCount - 1,
            }),
            tone: 'info',
          })
        }
        return
      }
      if (resolution.filePaths.length > 0) {
        void options.onFiles(resolution.filePaths)
        if (resolution.folderCount > 0) {
          toastStore.push({
            title: globalT('business.fileSelection.selectFiles'),
            message: globalT('business.fileDialog.dropFolderWebUnsupported'),
            tone: 'info',
          })
        }
        return
      }
      if (resolution.folderCount > 0) {
        // Folders were dropped but none usable (web mode).
        toastStore.push({
          title: globalT('business.fileSelection.importFolder'),
          message: globalT('business.fileDialog.dropFolderWebUnsupported'),
          tone: 'error',
        })
        return
      }
      if (resolution.rejectedNames.length > 0) {
        toastStore.push({
          title: globalT('business.fileSelection.selectFiles'),
          message: globalT('business.fileDialog.dropTypeMismatch', {
            names: shortenNames(resolution.rejectedNames),
          }),
          tone: 'error',
        })
      }
    },
  })
}
