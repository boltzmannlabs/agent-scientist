import { PassThrough } from 'node:stream'

import { renderSync } from '@sci/ink'
import { stripAnsi } from '@sci/shared/ansi'
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { GatewayProvider } from '../app/gatewayContext.js'
import type { GatewayServices } from '../app/interfaces.js'
import { $uiState } from '../app/uiStore.js'
import { isPreviewImage, supportsInlineGraphics } from '../components/imagePreview.js'
import { Md } from '../components/markdown.js'
import { DEFAULT_THEME } from '../theme.js'

afterEach(() => {
  $uiState.set({ ...$uiState.get(), sid: null, busy: false })
})

const paint = async (text: string, request: ReturnType<typeof vi.fn>) => {
  const stdout = new PassThrough()
  const stdin = new PassThrough()
  const stderr = new PassThrough()
  Object.assign(stdout, { columns: 80, rows: 30, isTTY: false })
  Object.assign(stdin, { isTTY: false })
  Object.assign(stderr, { isTTY: false })
  let output = ''
  stdout.on('data', chunk => {
    output += chunk.toString()
  })
  $uiState.set({ ...$uiState.get(), sid: 'conversation-a', busy: false })
  const value = { gw: { request } } as unknown as GatewayServices

  const instance = renderSync(
    <GatewayProvider value={value}>
      <Md cols={70} t={DEFAULT_THEME} text={text} />
    </GatewayProvider>,
    {
      stdout: stdout as NodeJS.WriteStream,
      stdin: stdin as NodeJS.ReadStream,
      stderr: stderr as NodeJS.WriteStream,
      patchConsole: false
    }
  )

  await vi.waitFor(() => {
    expect(stripAnsi(output)).toContain('Image preview')
  })
  instance.unmount()
  instance.cleanup()

  return output
}

describe('terminal image previews', () => {
  it('renders a native media directive as image pixels and retains the original link', async () => {
    const request = vi.fn().mockResolvedValue({
      ok: true,
      graphics: 'unicode',
      grid: [
        [
          [255, 0, 0, 255, 0, 0, 255, 255],
          [0, 255, 0, 255, 255, 255, 255, 255]
        ]
      ]
    })

    const output = await paint('Reaction figure\nMEDIA:/work/figure.png', request)
    expect(request).toHaveBeenCalledWith(
      'image.preview',
      expect.objectContaining({
        session_id: 'conversation-a',
        path: '/work/figure.png',
        cols: 70
      })
    )
    expect(stripAnsi(output)).toContain('▀')
    expect(stripAnsi(output)).toContain('/work/figure.png')
  })

  it('renders a saved Figure row in dashboard chat even when the server uses kitty', async () => {
    expect(supportsInlineGraphics({ SCI_TUI_DASHBOARD: '1', TERM: 'xterm-kitty' }, true)).toBe(false)

    const request = vi.fn().mockResolvedValue({
      ok: true,
      graphics: 'unicode',
      grid: [[[0, 0, 0, 255, 255, 255, 255, 255]]]
    })

    const output = await paint('Files:\n- Figure: /work/figure.png (also .svg and editable .cdxml there)', request)
    expect(request).toHaveBeenCalledWith('image.preview', expect.objectContaining({ path: '/work/figure.png' }))
    expect(stripAnsi(output)).toContain('▀')
  })

  it('supports local raster images while leaving vector, document and remote links unchanged', () => {
    expect(isPreviewImage('/work/figure.png')).toBe(true)
    expect(isPreviewImage('C:\\work\\figure.JPG')).toBe(true)

    for (const path of ['/work/figure.svg', '/work/figure.cdxml', 'https://host/figure.png', '/work/input.json']) {
      expect(isPreviewImage(path)).toBe(false)
    }
  })

  it('retains the file link and explains unavailable previews without losing the response', async () => {
    const request = vi.fn().mockResolvedValue({ ok: false })
    const output = await paint('Saved figure\nMEDIA:/work/missing.png', request)
    expect(stripAnsi(output)).toContain('Image preview unavailable')
    expect(stripAnsi(output)).toContain('/work/missing.png')
  })

  it.each(['plain', 'quoted', 'backticks'])('previews %s image paths containing spaces', async format => {
    const request = vi.fn().mockResolvedValue({
      ok: true,
      graphics: 'unicode',
      grid: [[[0, 0, 0, 255, 255, 255, 255, 255]]]
    })

    const path = '/work/reaction diagrams/figure.png'
    const reference = format === 'quoted' ? `"${path}"` : format === 'backticks' ? `\`${path}\`` : path
    const output = await paint(`MEDIA:${reference}`, request)
    expect(request).toHaveBeenCalledWith('image.preview', expect.objectContaining({ path }))
    expect(stripAnsi(output)).toContain('▀')
    expect(stripAnsi(output)).toContain(path)
  })

  it('selects graphics from the viewing terminal and avoids inherited protocols in VS Code', () => {
    expect(supportsInlineGraphics({ TERM: 'xterm-kitty' }, true)).toBe(true)
    expect(supportsInlineGraphics({ TERM_PROGRAM: 'ghostty' }, true)).toBe(true)
    expect(supportsInlineGraphics({ KITTY_WINDOW_ID: '1', TERM_PROGRAM: 'vscode' }, true)).toBe(false)
    expect(supportsInlineGraphics({ KITTY_WINDOW_ID: '1', TERM_PROGRAM: 'WezTerm' }, true)).toBe(false)
    expect(supportsInlineGraphics({ TERM: 'xterm-kitty' }, false)).toBe(false)
    expect(supportsInlineGraphics({ TERM: 'xterm-256color' }, true)).toBe(false)
  })
})
