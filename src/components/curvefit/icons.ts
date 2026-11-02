/**
 * Inline SVG icon set (hand-drawn, 24×24 stroke paths). No icon library.
 * Rendered by AppIcon.vue via v-html inside a stroke-currentColor <svg>.
 */
export const ICONS: Record<string, string> = {
  // brand: tiny spectrum curve
  logo:
    '<path d="M2 18c2.2 0 2.6-9 4.8-9 2 0 2.4 6 3.8 6 1.6 0 2-11 4.2-11 2 0 2.4 8 4 8 1.4 0 1.6-5 3.2-5" />',

  // toolbar
  import: '<path d="M12 3v10m0 0 4-4m-4 4-4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  flask: '<path d="M9 3h6M10 3v5.5L4.8 17a2.4 2.4 0 0 0 2.1 3.6h10.2a2.4 2.4 0 0 0 2.1-3.6L14 8.5V3"/><path d="M7.5 14h9"/>',
  wave: '<path d="M2 12c2 0 2.5-5 4.5-5S9 14 11 14s2.5-9 4.5-9S18 12 20 12s2-2 2-2"/><path d="M3 19h18" stroke-dasharray="2 3"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  play: '<path d="M7 4.5v15l12-7.5z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
  abort: '<circle cx="12" cy="12" r="9"/><path d="M6.5 6.5l11 11"/>',
  undo: '<path d="M4 9h9a5 5 0 0 1 0 10H8"/><path d="M4 9l4-4M4 9l4 4"/>',
  redo: '<path d="M20 9h-9a5 5 0 0 0 0 10h5"/><path d="M20 9l-4-4M20 9l-4 4"/>',
  export: '<path d="M12 15V5m0 0 4 4m-4-4-4 4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  download: '<path d="M12 4v11m0 0 4-4m-4 4-4-4"/><path d="M5 20h14"/>',

  // window
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5 5l1.4 1.4M17.6 17.6 19 19M19 5l-1.4 1.4M6.4 17.6 5 19"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"/>',
  min: '<path d="M5 12h14"/>',
  max: '<rect x="5.5" y="5.5" width="13" height="13" rx="1"/>',
  restore: '<rect x="4.5" y="8.5" width="11" height="11" rx="1"/><path d="M8.5 8.5v-3h11v11h-3"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',

  // steps
  data: '<ellipse cx="12" cy="5.5" rx="8" ry="2.8"/><path d="M4 5.5v13c0 1.5 3.6 2.8 8 2.8s8-1.3 8-2.8v-13"/><path d="M4 12c0 1.5 3.6 2.8 8 2.8s8-1.3 8-2.8"/>',
  baseline: '<path d="M3 20h18"/><path d="M3 16c3-1 4.5-9 7.5-9s4 6 6 6c2.5 0 3-4 4.5-4" /><path d="M3 7.5C6 7 8 9.5 12 9.5s6-3 9-2" stroke-dasharray="2.5 2.5"/>',
  peak: '<path d="M3 20h18"/><path d="M4 20 9.5 6l4 10 2.5-6L20 20"/><circle cx="9.5" cy="6" r="1.6"/>',
  fit: '<path d="M3 20h18"/><path d="M3 14c4 4 7-3 10-3s4 5 8 2" /><path d="M5 8c2.5 0 4.5 2.5 5.5 5M14 13c1.5 2.5 4 3.5 6 3" stroke-dasharray="2.5 2.5"/>',
  report: '<path d="M6 3h9l4 4v14H6z"/><path d="M14.5 3v4.5H19"/><path d="M9 12h7M9 15.5h7M9 8.5h3"/>',

  // misc
  trash: '<path d="M4.5 6.5h15M9.5 6V4.5A1.5 1.5 0 0 1 11 3h2a1.5 1.5 0 0 1 1.5 1.5V6"/><path d="M6.5 6.5 7.4 19a2 2 0 0 0 2 1.9h5.2a2 2 0 0 0 2-1.9l.9-12.5"/><path d="M10 10.5v6M14 10.5v6"/>',
  lock: '<rect x="6" y="11" width="12" height="9" rx="1.5"/><path d="M8.5 11V8a3.5 3.5 0 0 1 7 0v3"/>',
  unlock: '<rect x="6" y="11" width="12" height="9" rx="1.5"/><path d="M8.5 11V8a3.5 3.5 0 0 1 6.8-1"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeoff: '<path d="M4 4l16 16"/><path d="M9.9 5.9A9.5 9.5 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3.2 3.9M6 7.3A16 16 0 0 0 2.5 12S6 18.5 12 18.5a9.7 9.7 0 0 0 4-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  reset: '<path d="M4.5 5.5v5h5"/><path d="M4.7 10.4A8 8 0 1 1 6 16.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  chevronDown: '<path d="M6 9.5l6 6 6-6"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/>',
  alert: '<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5"/><path d="M12 17.5h.01"/>',
  chart: '<path d="M4 4v16h16"/><path d="M7.5 15.5v-4M11.5 15.5V8M15.5 15.5v-6.5M19.5 15.5V5.5"/>',
  file: '<path d="M6 3h9l4 4v14H6z"/><path d="M14.5 3v4.5H19"/>',
  restore2: '<path d="M12 5a7 7 0 1 1-6.3 4"/><path d="M5 4v5h5"/>',
}
