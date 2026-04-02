import { test, expect } from '@playwright/test'

const BASE_URL = 'http://127.0.0.1:4176/'
const SETTINGS_KEY = 'arel-wars-aw1-settings-v1'
const RESUME_KEY = 'arel-wars-aw1-resume-v1'
const QUICKSAVE_KEY = 'arel-wars-aw1-quicksave-v1'

const LEGACY_SETTINGS = {
  audioEnabled: false,
  masterVolume: 0.25,
  autoAdvanceEnabled: false,
  autoSaveEnabled: true,
  resumeOnLaunch: true,
  reducedEffects: true,
}

test('migrates legacy settings payload', async ({ page }) => {
  test.setTimeout(120000)

  await page.addInitScript(({ settingsKey, legacySettings }) => {
    const guardKey = '__aw1_phase17_settings_seeded__'
    if (!window.sessionStorage.getItem(guardKey)) {
      window.localStorage.clear()
      window.localStorage.setItem(settingsKey, JSON.stringify(legacySettings))
      window.sessionStorage.setItem(guardKey, '1')
    }
  }, {
    settingsKey: SETTINGS_KEY,
    legacySettings: LEGACY_SETTINGS,
  })

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 120000 })
  await page.waitForFunction(
    () => typeof window.__aw1RecoverySystem?.getSnapshot === 'function',
    null,
    { timeout: 120000 },
  )

  const migrationState = await page.evaluate((settingsKey) => {
    const settingsPayload = JSON.parse(window.localStorage.getItem(settingsKey) || 'null')
    const snapshot = window.__aw1RecoverySystem?.getSnapshot?.() ?? null
    return {
      settingsPayload,
      snapshot: snapshot ? {
        audioEnabled: snapshot.settingsState.audioEnabled,
        reducedEffects: snapshot.settingsState.reducedEffects,
        autoAdvanceEnabled: snapshot.settingsState.autoAdvanceEnabled,
        hasResumeSession: snapshot.persistenceState.hasResumeSession,
      } : null,
    }
  }, SETTINGS_KEY)

  expect(migrationState.settingsPayload?.version).toBe(2)
  expect(migrationState.settingsPayload?.schema).toBe('aw1-settings')
  expect(migrationState.settingsPayload?.audioEnabled).toBe(false)
  expect(migrationState.settingsPayload?.reducedEffects).toBe(true)
  expect(migrationState.snapshot).toBeTruthy()
  expect(migrationState.snapshot?.audioEnabled).toBe(false)
  expect(migrationState.snapshot?.reducedEffects).toBe(true)
  expect(migrationState.snapshot?.autoAdvanceEnabled).toBe(false)
  expect(typeof migrationState.snapshot?.hasResumeSession).toBe('boolean')
})

test('migrates legacy resume session payload', async ({ page }) => {
  test.setTimeout(120000)

  await page.addInitScript(() => {
    const guardKey = '__aw1_phase17_resume_clear__'
    if (!window.sessionStorage.getItem(guardKey)) {
      window.localStorage.clear()
      window.sessionStorage.setItem(guardKey, '1')
    }
  })

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 120000 })
  await page.waitForFunction(
    () => typeof window.__aw1RecoverySystem?.quickSave === 'function' && typeof window.__aw1RecoverySystem?.getSnapshot === 'function',
    null,
    { timeout: 120000 },
  )

  await page.evaluate(({ resumeKey, quicksaveKey, settingsKey, legacySettings }) => {
    const system = window.__aw1RecoverySystem
    if (!system?.quickSave?.()) {
      throw new Error('quick save bootstrap failed')
    }

    const quickSavePayload = JSON.parse(window.localStorage.getItem(quicksaveKey) || 'null')
    if (!quickSavePayload) {
      throw new Error('missing quick save payload')
    }

    delete quickSavePayload.version
    delete quickSavePayload.schema
    delete quickSavePayload.savedAtIso
    quickSavePayload.slotLabel = 'legacy-resume'
    quickSavePayload.settings = {
      ...legacySettings,
      resumeOnLaunch: true,
    }

    window.localStorage.setItem(settingsKey, JSON.stringify(legacySettings))
    window.localStorage.setItem(resumeKey, JSON.stringify(quickSavePayload))
  }, {
    resumeKey: RESUME_KEY,
    quicksaveKey: QUICKSAVE_KEY,
    settingsKey: SETTINGS_KEY,
    legacySettings: LEGACY_SETTINGS,
  })

  await page.reload({ waitUntil: 'networkidle', timeout: 120000 })
  await page.waitForFunction(
    () => Boolean(window.__aw1RecoverySystem?.getSnapshot?.()),
    null,
    { timeout: 120000 },
  )
  await page.waitForTimeout(1500)

  const migrationState = await page.evaluate(({ settingsKey, resumeKey }) => {
    const settingsPayload = JSON.parse(window.localStorage.getItem(settingsKey) || 'null')
    const resumePayload = JSON.parse(window.localStorage.getItem(resumeKey) || 'null')
    const snapshot = window.__aw1RecoverySystem?.getSnapshot?.() ?? null
    return {
      settingsPayload,
      resumePayload,
      snapshot: snapshot ? {
        sessionRevision: snapshot.persistenceState.sessionRevision,
        scenePhase: snapshot.campaignState.scenePhase,
      } : null,
    }
  }, {
    settingsKey: SETTINGS_KEY,
    resumeKey: RESUME_KEY,
  })

  expect(migrationState.settingsPayload?.version).toBe(2)
  expect(migrationState.settingsPayload?.schema).toBe('aw1-settings')
  expect(migrationState.resumePayload?.version).toBe(2)
  expect(migrationState.resumePayload?.schema).toBe('aw1-session')
  expect(migrationState.resumePayload?.slotLabel).toBe('resume-session')
  expect(migrationState.snapshot).toBeTruthy()
  expect(migrationState.snapshot?.sessionRevision).toBeGreaterThan(0)
  expect(typeof migrationState.snapshot?.scenePhase).toBe('string')
})
