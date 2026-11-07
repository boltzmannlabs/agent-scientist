import { Box, Text } from '@sci/ink'
import { useState } from 'react'

import { useT } from '../i18n/useT.js'
import type { Theme } from '../theme.js'

import { TextInput } from './textInput.js'

export function MaskedPrompt({ cols = 80, icon, label, onSubmit, sub, t, title, tone = 'primary' }: MaskedPromptProps) {
  const [value, setValue] = useState('')

  return (
    <Box
      backgroundColor={t.surfaces?.elevated}
      borderColor={t.color[tone]}
      borderStyle="round"
      flexDirection="column"
      paddingX={2}
      paddingY={1}
    >
      <Text bold color={t.color[tone]}>
        {icon} {title ?? label}
      </Text>

      {sub && (
        <Box flexDirection="column" marginTop={1}>
          {sub.split('\n').map((line, index) => (
            <Text
              color={line.startsWith('https://') ? t.color.accent : t.color.text}
              key={index}
              underline={line.startsWith('https://')}
            >
              {line}
            </Text>
          ))}
        </Box>
      )}
      {title && (
        <Box marginTop={1}>
          <Text color={t.color.label}>{label}</Text>
        </Box>
      )}

      <Box
        backgroundColor={t.color.completionBg}
        borderColor={t.color.sessionBorder}
        borderStyle="round"
        marginTop={1}
        paddingX={1}
      >
        <Text color={t.color.label}>{'> '}</Text>
        <TextInput
          color={t.color.text}
          columns={Math.max(1, cols - 14)}
          mask="•"
          onChange={setValue}
          onSubmit={onSubmit}
          value={value}
        />
      </Box>
    </Box>
  )
}

interface MaskedPromptProps {
  cols?: number
  icon: string
  label: string
  onSubmit: (v: string) => void
  sub?: string
  t: Theme
  title?: string
  tone?: 'primary' | 'warn'
}

interface SecurePromptProps {
  cols?: number
  onSubmit: (v: string) => void
  t: Theme
}

/** Masked prompt for the `sudo` password the backend asked for. */
export function SudoPrompt({ cols, onSubmit, t }: SecurePromptProps) {
  const T = useT()

  return <MaskedPrompt cols={cols} icon="🔐" label={T.secure.sudo.title} onSubmit={onSubmit} t={t} tone="warn" />
}

/** Masked prompt for a secret the backend wants stored under `envVar`; `prompt` is the backend's own wording. */
export function SecretPrompt({
  cols,
  envVar,
  onSubmit,
  prompt,
  t
}: SecurePromptProps & { envVar: string; prompt: string }) {
  const T = useT()

  return (
    <MaskedPrompt
      cols={cols}
      icon="🔑"
      label={prompt}
      onSubmit={onSubmit}
      sub={
        envVar === 'BOLTZMANN_API_KEY'
          ? 'Get your API key by logging in at:\nhttps://app.boltzmann.co/user-profile'
          : T.secure.secret.forEnvVar(envVar)
      }
      t={t}
      title={envVar === 'BOLTZMANN_API_KEY' ? 'Boltzmann login' : undefined}
    />
  )
}

/** Masked prompt for a password manager's master password; the value goes to the manager CLI only. */
export function VaultUnlockPrompt({ cols, displayName, onSubmit, t }: SecurePromptProps & { displayName: string }) {
  const T = useT()

  return (
    <MaskedPrompt
      cols={cols}
      icon="🔐"
      label={T.secure.vault.unlockTitle(displayName)}
      onSubmit={onSubmit}
      sub={T.secure.vault.unlockHint}
      t={t}
      tone="warn"
    />
  )
}
