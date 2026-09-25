/**
 * shims.d.ts — Type declarations for Vite `?raw` markdown imports.
 *
 * More specific than vite/client's generic `*?raw` declaration, so the two
 * coexist without redeclaration errors.
 */

declare module '*.md?raw' {
  const content: string
  export default content
}
