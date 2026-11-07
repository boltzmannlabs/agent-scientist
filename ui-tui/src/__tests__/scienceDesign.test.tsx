import { PassThrough } from 'node:stream'

import { Box, renderSync } from '@sci/ink'
import { stripAnsi } from '@sci/shared/ansi'
import React from 'react'
import { expect, it } from 'vitest'

import { MessageLine } from '../components/messageLine.js'
import { ScienceWelcome } from '../components/scienceDesign.js'
import { DARK_THEME, LIGHT_THEME } from '../theme.js'
import type { SessionInfo } from '../types.js'

it.each([32, 80, 120])('renders real science components without losing user text at %i columns', async cols => {
  for (const t of [DARK_THEME, LIGHT_THEME]) {
    const info: SessionInfo = {
      model: 'fixture',
      provider: 'test',
      profile_name: 'omics',
      cwd: '/workspace/project',
      tools: { file: ['read_file'] },
      skills: { science: ['review'] }
    }

    const before = JSON.stringify(info)
    const stdout = Object.assign(new PassThrough(), { columns: cols, isTTY: false, rows: 60 })
    const stdin = Object.assign(new PassThrough(), { isTTY: false })
    const stderr = Object.assign(new PassThrough(), { isTTY: false })
    let output = ''
    stdout.on('data', chunk => {
      output += chunk.toString()
    })

    const app = renderSync(
      <Box flexDirection="column">
        <ScienceWelcome cols={cols} t={t} />
        <ScienceWelcome cols={cols} info={info} t={t} />
        <MessageLine cols={cols} msg={{ role: 'user', text: 'Review [notes].' }} t={t} />
        <MessageLine cols={cols} isStreaming msg={{ role: 'assistant', text: 'Evidence summary.' }} t={t} />
      </Box>,
      {
        stdout: stdout as NodeJS.WriteStream,
        stdin: stdin as NodeJS.ReadStream,
        stderr: stderr as NodeJS.WriteStream,
        patchConsole: false
      }
    )

    try {
      await expect.poll(() => stripAnsi(output)).toContain('Evidence summary.')
      const frame = stripAnsi(output)
      expect(frame).toContain('● You: Review [notes].')
      expect(frame).toContain('☤ Sci')
      expect(frame).toContain('omics')
      expect(frame).toContain('Agent Scientist')
      expect(frame).not.toContain('☤ Agent Scientist')
      expect(frame).toContain('Loading session…')
      expect(frame).not.toContain('No model configured')
      expect(JSON.stringify(info)).toBe(before)
    } finally {
      app.unmount()
      app.cleanup()
    }
  }
})
