import { test, expect } from '@playwright/test'
import fs from 'node:fs'

test('export aw1 verification replay suite', async ({ page }) => {
  await page.goto('http://127.0.0.1:4175/', { waitUntil: 'networkidle', timeout: 120000 })
  await page.waitForFunction(
    () => typeof window.__aw1RecoverySystem?.buildVerificationReplaySuite === 'function',
    null,
    { timeout: 120000 },
  )
  const suite = await page.evaluate(() => {
    const system = window.__aw1RecoverySystem
    return system?.buildVerificationReplaySuite?.() ?? null
  })
  expect(suite).toBeTruthy()
  fs.writeFileSync(
    '/Users/lpaiu/vs/others/arelwars/recovery/arel_wars1/parsed_tables/AW1.candidate_replay_suite.json',
    JSON.stringify(suite, null, 2),
  )
})
