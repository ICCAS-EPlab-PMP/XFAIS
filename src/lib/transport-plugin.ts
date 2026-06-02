/**
 * transport-plugin.ts — Vue plugin for transport injection.
 *
 * Installs the transport instance via provide/inject so any component
 * can use `useTransport()` to access it without prop drilling.
 */

import type { App } from 'vue'
import { createTransport, TransportProvider } from './transport'
import type { ITransport } from './transport'

export const TransportPlugin = {
  install(app: App) {
    const transport = createTransport()
    app.provide(TransportProvider, transport)
  }
}