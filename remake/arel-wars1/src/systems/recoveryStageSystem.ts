import type {
  RecoveryAudioState,
  RecoveryBattleChainState,
  RecoveryBattleEntityState,
  RecoveryBattleEffectState,
  RecoveryBattleModel,
  RecoveryBattleObjectiveState,
  RecoveryBattleProjectileState,
  RecoveryBattlePreviewState,
  RecoveryBattleEffectTemplate,
  RecoveryBattleHeroTemplate,
  RecoveryBattleItemTemplate,
  RecoveryBattleProjectileTemplate,
  RecoveryBattleSkillTemplate,
  RecoveryBattleUnitTemplate,
  RecoveryBattleWaveDirective,
  RecoveryBattleChannelState,
  RecoveryCatalog,
  RecoveryDialogueEvent,
  RecoveryGameplayActionId,
  RecoveryGameplayState,
  RecoveryHudGhostState,
  RecoveryLaneBattleState,
  RecoveryResolvedOpcodeCue,
  RecoveryPreviewFrame,
  RecoveryPreviewManifest,
  RecoveryPreviewStem,
  RecoveryPersistenceState,
  RecoveryRuntimeBlueprint,
  RecoveryScriptEntry,
  RecoverySceneScriptDirective,
  RecoverySceneScriptStep,
  RecoverySettingsState,
  RecoveryStageBattleProfile,
  RecoveryStageBlueprint,
  RecoveryStageRenderState,
  RecoveryStageSnapshot,
  RecoveryStageStoryboard,
  RecoveryTowerUpgradeLevels,
  RecoveryTutorialChainCue,
} from '../recovery-types'

const MIN_DIALOGUE_DURATION_MS = 1400
const MAX_DIALOGUE_DURATION_MS = 4200
const STORYBOARD_GAP_MS = 900
const RESULT_HOLD_MS = 1800
const REWARD_REVIEW_MS = 2400
const UNLOCK_REVEAL_MS = 2200
const WORLDMAP_HOLD_MS = 1600
const DEPLOY_BRIEFING_MS = 1800
const UPGRADE_PROGRESS_RECOVERY_PER_BEAT = 0.012
const SKILL_COOLDOWN_MS = 2600
const ITEM_COOLDOWN_MS = 3200
const AUTO_SAVE_INTERVAL_MS = 4000
const SETTINGS_STORAGE_KEY = 'arel-wars-aw1-settings-v1'
const RESUME_STORAGE_KEY = 'arel-wars-aw1-resume-v1'
const QUICKSAVE_STORAGE_KEY = 'arel-wars-aw1-quicksave-v1'
const GENERIC_OPCODE_VARIANTS = new Set([
  'cmd-02:05',
  'cmd-05:03',
  'cmd-08:00',
  'cmd-10:00',
  'cmd-18:00',
  'cmd-43:00',
])
const HERO_RETURN_COOLDOWN_MS = 2200

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function oscillate(nowMs: number, periodMs: number, phaseOffsetMs: number): number {
  const phase = ((nowMs + phaseOffsetMs) % periodMs) / periodMs
  return 0.5 + Math.sin(phase * Math.PI * 2) * 0.5
}

function dialogueDurationMs(event: RecoveryDialogueEvent): number {
  const base = event.kind === 'caption' ? 1900 : 1500
  const charWeight = event.kind === 'caption' ? 24 : 30
  return clamp(base + event.text.length * charWeight, MIN_DIALOGUE_DURATION_MS, MAX_DIALOGUE_DURATION_MS)
}

function normalizeScriptEvents(entry: RecoveryScriptEntry): RecoveryDialogueEvent[] {
  return entry.eventPreview?.filter((event) => event.text?.trim().length > 0) ?? []
}

function scriptFamilyId(path: string): string {
  const match = path.match(/\/(\d{4})\.zt1$/)
  return match ? match[1].slice(0, 3) : '000'
}

function chooseScripts(catalog: RecoveryCatalog, limit: number): RecoveryScriptEntry[] {
  const scripts = catalog.featuredScripts.filter((entry) => (entry.eventPreview?.length ?? 0) > 0)
  const preferred = scripts.filter((entry) => entry.locale === 'en')
  const fallback = scripts.filter((entry) => entry.locale !== 'en')
  return [...preferred, ...fallback].slice(0, limit)
}

function choosePreviewEntries(previewManifest: RecoveryPreviewManifest, limit: number): RecoveryPreviewStem[] {
  const preferred = [...previewManifest.featuredEntries]
  if (preferred.length >= limit) {
    return preferred.slice(0, limit)
  }

  const extras = previewManifest.stems.filter((entry) => !preferred.some((item) => item.stem === entry.stem))
  return [...preferred, ...extras].slice(0, limit)
}

function normalizeTimingValues(values: number[]): number[] {
  return values.filter((value) => Number.isFinite(value) && value > 0 && value !== 255)
}

function archetypeCycleMs(archetypeRecord: RecoveryRuntimeBlueprint['featuredArchetypes'][number] | undefined): number {
  if (!archetypeRecord) {
    return 1200
  }

  const markers = archetypeRecord.activeRows.flatMap((row) => [
    ...normalizeTimingValues(row.timingWindowACompact),
    ...normalizeTimingValues(row.timingWindowBCompact),
  ])
  if (markers.length === 0) {
    return Math.max(420, 320 + archetypeRecord.buffRows.length * 80)
  }
  return Math.max(markers.reduce((sum, value) => sum + value, 0), 420)
}

function includesAny(value: string, needles: string[]): boolean {
  const haystack = value.toLowerCase()
  return needles.some((needle) => haystack.includes(needle))
}

interface ResolvedSceneCommandSignals {
  hasFocus: boolean
  hasPresentation: boolean
  hasEmphasis: boolean
  hasSceneLayout: boolean
  hasSceneTransition: boolean
  hasBattleHudFocus: boolean
  hasTowerFocus: boolean
  hasManaFocus: boolean
  hasPopulationFocus: boolean
  hasSkillFocus: boolean
  hasItemFocus: boolean
  hasSystemFocus: boolean
  hasQuestFocus: boolean
  hasGuidedFocus: boolean
  hasPortraitAssignment: boolean
}

type RecoveryCampaignMenuAction =
  | 'continue-campaign'
  | 'direct-deploy'
  | 'replay-active-stage'

interface RecoveryCampaignMenuEntry {
  label: string
  description: string
  action: RecoveryCampaignMenuAction
}

function buildStoryboards(
  catalog: RecoveryCatalog,
  previewManifest: RecoveryPreviewManifest,
  runtimeBlueprint: RecoveryRuntimeBlueprint | null,
): RecoveryStageStoryboard[] {
  const scripts = chooseScripts(catalog, 6)
  const previews = choosePreviewEntries(previewManifest, Math.max(6, scripts.length))
  if (scripts.length === 0 || previews.length === 0) {
    return []
  }

  const stageBlueprintsByFamily = new Map<string, RecoveryStageBlueprint>()
  runtimeBlueprint?.stageBlueprints.forEach((entry) => {
    stageBlueprintsByFamily.set(entry.familyId, entry)
  })

  return scripts.map((script, index) => {
    const previewStem = previews[index % previews.length]
    const familyId = scriptFamilyId(script.path)
    return {
      id: `${index}-${script.path}-${previewStem.stem}`,
      scriptPath: script.path,
      scriptFamilyId: familyId,
      locale: script.locale,
      scriptEventCount: script.eventCount ?? script.eventPreview?.length ?? 0,
      scriptEvents: normalizeScriptEvents(script),
      sceneScriptSteps: [],
      previewStem,
      stageBlueprint: stageBlueprintsByFamily.get(familyId) ?? null,
    }
  })
}

type RecoveryBattleSide = 'allied' | 'enemy'
type RecoveryBattleLaneId = RecoveryLaneBattleState['laneId']
type RecoveryBattleUnitRole = RecoveryBattleWaveDirective['role'] | 'hero'

interface RecoveryBattleUnitRuntime {
  id: number
  side: RecoveryBattleSide
  laneId: RecoveryBattleLaneId
  role: RecoveryBattleUnitRole
  hero: boolean
  memberLabel: string | null
  source: string
  hp: number
  maxHp: number
  power: number
  speed: number
  range: number
  cooldownBeats: number
  attackPeriodBeats: number
  positionRatio: number
  templateId: string
  projectileTemplateId: string | null
  effectTemplateId: string | null
  populationCost: number
  manaCost: number
  attackStyle: 'melee' | 'projectile' | 'siege' | 'support'
}

interface RecoveryBattleProjectileRuntime {
  id: number
  side: RecoveryBattleSide
  laneId: RecoveryBattleLaneId
  source: string
  positionRatio: number
  velocity: number
  strength: number
  ttlBeats: number
  effectTemplateId: string | null
}

interface RecoveryBattleEffectRuntime {
  id: number
  side: RecoveryBattleSide
  laneId: RecoveryBattleLaneId
  positionRatio: number
  kind: string
  renderFamily: RecoveryBattleEffectState['renderFamily']
  blendMode: string
  emitterSemanticId: string | null
  ttlBeats: number
  intensity: number
}

interface RecoveryEntityVisualRuntime {
  spriteState: RecoveryBattleEntityState['spriteState']
  stateWeight: number
  hitFlash: number
  overlayMode: string | null
  overlayAlpha: number
}

interface RecoveryStoredSettings {
  audioEnabled: boolean
  masterVolume: number
  autoAdvanceEnabled: boolean
  autoSaveEnabled: boolean
  resumeOnLaunch: boolean
  reducedEffects: boolean
}

interface RecoverySerializedSession {
  version: 1
  savedAtIso: string
  slotLabel: string
  sessionRevision: number
  storyboardIndex: number
  dialogueIndex: number
  frameIndex: number
  storyboardElapsedMs: number
  nextDialogueRemainingMs: number | null
  nextFrameRemainingMs: number | null
  heroReturnCooldownRemainingMs: number | null
  skillCooldownRemainingMs: number | null
  itemCooldownRemainingMs: number | null
  worldmapAutoEnterRemainingMs: number | null
  deployBriefingRemainingMs: number | null
  rewardReviewRemainingMs: number | null
  unlockRevealRemainingMs: number | null
  resultAutoAdvanceRemainingMs: number | null
  lastChannelBeat: number
  panelOverride: RecoveryGameplayState['openPanel']
  heroOverrideMode: RecoveryGameplayState['heroMode'] | null
  battlePaused: boolean
  questRewardClaimed: boolean
  questRewardClaims: number
  selectedDispatchLane: RecoveryHudGhostState['selectedDispatchLane']
  queuedUnitCount: number
  previewManaRatio: number
  previewManaUpgradeProgressRatio: number
  previewOwnTowerHpRatio: number
  previewEnemyTowerHpRatio: number
  alliedManaValue: number
  enemyManaValue: number
  manaCapacityValue: number
  enemyManaCapacityValue: number
  populationCapacity: number
  enemyPopulationCapacity: number
  heroAssignedLane: RecoveryLaneBattleState['laneId'] | null
  laneBattleState: Record<RecoveryLaneBattleState['laneId'], Omit<RecoveryLaneBattleState, 'laneId'>>
  towerUpgradeLevels: RecoveryTowerUpgradeLevels
  currentStageBattleProfile: RecoveryStageBattleProfile
  currentObjectivePhase: RecoveryBattleObjectiveState['phase']
  currentObjectiveLabel: string
  currentWaveIndex: number
  totalWaveCount: number
  enemyWaveCursor: number
  alliedWaveCursor: number
  enemyWavesDispatched: number
  alliedWavesDispatched: number
  objectiveProgressRatio: number
  enemyWaveCountdownBeats: number
  alliedWaveCountdownBeats: number
  enemyWavePlan: RecoveryBattleWaveDirective[]
  alliedWavePlan: RecoveryBattleWaveDirective[]
  battleResolutionOutcome: 'victory' | 'defeat' | null
  battleResolutionReason: string | null
  campaignUnlockedStageCount: number
  campaignLastUnlockedNodeIndex: number | null
  campaignSelectedNodeIndex: number
  campaignSelectedLoadoutIndex: number
  campaignMenuIndex: number
  campaignScenePhase: RecoveryStageSnapshot['campaignState']['scenePhase']
  campaignClearedStoryboardIds: string[]
  campaignLastResolvedStageTitle: string | null
  campaignLastOutcome: 'victory' | 'defeat' | null
  campaignPreferredRouteLabel: string | null
  campaignRouteCommitment: number
  activeDeployLoadoutId: string | null
  lastActionId: RecoveryGameplayActionId | null
  lastActionAccepted: boolean
  lastActionNote: string | null
  lastScriptedBeatNote: string | null
  rosterChainBoosts: Array<[string, number]>
  rosterChainFocusLane: 'upper' | 'lower' | null
  battleStepCount: number
  nextBattleEntityId: number
  nextBattleProjectileId: number
  nextBattleEffectId: number
  laneEntities: Record<RecoveryBattleLaneId, Record<RecoveryBattleSide, RecoveryBattleUnitRuntime[]>>
  battleProjectiles: RecoveryBattleProjectileRuntime[]
  battleEffects: RecoveryBattleEffectRuntime[]
  entityVisuals: Array<[number, RecoveryEntityVisualRuntime]>
  cameraShakeIntensity: number
  cameraShakeAxes: RecoveryStageRenderState['cameraShakeAxes']
  overlayMode: string | null
  overlayColor: number | null
  overlayAlpha: number
  burstPulseIntensity: number
  particleBoostIntensity: number
  hitFlashIntensity: number
  settings: RecoveryStoredSettings
}

export class RecoveryStageSystem {
  private readonly storyboards: RecoveryStageStoryboard[]

  private readonly runtimeBlueprint: RecoveryRuntimeBlueprint | null

  private readonly battleModel: RecoveryBattleModel | null

  private readonly unitTemplatesById = new Map<string, RecoveryBattleUnitTemplate>()

  private readonly projectileTemplatesById = new Map<string, RecoveryBattleProjectileTemplate>()

  private readonly effectTemplatesById = new Map<string, RecoveryBattleEffectTemplate>()

  private readonly skillTemplatesByName = new Map<string, RecoveryBattleSkillTemplate>()

  private readonly itemTemplatesByName = new Map<string, RecoveryBattleItemTemplate>()

  private readonly heroTemplatesByName = new Map<string, RecoveryBattleHeroTemplate>()

  private readonly featuredArchetypesById = new Map<string, RecoveryRuntimeBlueprint['featuredArchetypes'][number]>()

  private readonly opcodeHeuristicsByMnemonic = new Map<string, RecoveryRuntimeBlueprint['opcodeHeuristics'][number]>()

  private storyboardIndex = 0

  private dialogueIndex = 0

  private frameIndex = 0

  private nextDialogueAtMs = Number.POSITIVE_INFINITY

  private nextFrameAtMs = Number.POSITIVE_INFINITY

  private storyboardStartedAtMs = 0

  private lastUpdateNowMs = 0

  private lastChannelBeat = -1

  private version = 0

  private panelOverride: RecoveryGameplayState['openPanel'] = null

  private heroOverrideMode: RecoveryGameplayState['heroMode'] | null = null

  private heroReturnCooldownEndsAtMs = 0

  private battlePaused = false

  private pauseStartedAtMs = 0

  private questRewardClaimed = false

  private questRewardClaims = 0

  private selectedDispatchLane: RecoveryHudGhostState['selectedDispatchLane'] = null

  private queuedUnitCount = 0

  private previewManaRatio = 0.48

  private previewManaUpgradeProgressRatio = 0.22

  private previewOwnTowerHpRatio = 0.74

  private previewEnemyTowerHpRatio = 0.58

  private skillCooldownEndsAtMs = 0

  private itemCooldownEndsAtMs = 0

  private heroAssignedLane: RecoveryLaneBattleState['laneId'] | null = null

  private readonly laneBattleState: Record<RecoveryLaneBattleState['laneId'], Omit<RecoveryLaneBattleState, 'laneId'>> = {
    upper: {
      alliedUnits: 1,
      enemyUnits: 2,
      alliedPressure: 0.28,
      enemyPressure: 0.42,
      frontline: 0.42,
      contested: 0.36,
      momentum: 'enemy-push',
      heroPresent: false,
    },
    lower: {
      alliedUnits: 2,
      enemyUnits: 1,
      alliedPressure: 0.34,
      enemyPressure: 0.26,
      frontline: 0.56,
      contested: 0.28,
      momentum: 'allied-push',
      heroPresent: false,
    },
  }

  private readonly towerUpgradeLevels: RecoveryTowerUpgradeLevels = {
    mana: 1,
    population: 1,
    attack: 1,
  }

  private currentStageBattleProfile: RecoveryStageBattleProfile = {
    label: 'Recovery lane sandbox',
    favoredLane: 'upper',
    tacticalBias: 'neutral-opening',
    stageTier: 10,
    alliedPressureScale: 0.24,
    enemyPressureScale: 0.3,
    alliedWaveCadenceBeats: 5,
    enemyWaveCadenceBeats: 4,
    heroImpact: 0.14,
    effectIntensity: 'medium',
    archetypeLabels: [],
    archetypeSignals: [],
    dispatchBoost: 0.12,
    towerDefenseBias: 0.08,
    recallSwing: 0.1,
    armageddonBurst: 0.12,
    manaSurge: 0.08,
  }

  private currentObjectivePhase: RecoveryBattleObjectiveState['phase'] = 'opening'

  private currentObjectiveLabel = 'stabilize the opening lane'

  private currentWaveIndex = 1

  private totalWaveCount = 4

  private enemyWaveCursor = 1

  private alliedWaveCursor = 1

  private enemyWavesDispatched = 0

  private alliedWavesDispatched = 0

  private objectiveProgressRatio = 0.08

  private enemyWaveCountdownBeats = 4

  private alliedWaveCountdownBeats = 5

  private enemyWavePlan: RecoveryBattleWaveDirective[] = []

  private alliedWavePlan: RecoveryBattleWaveDirective[] = []

  private battleResolutionOutcome: 'victory' | 'defeat' | null = null

  private battleResolutionReason: string | null = null

  private battleResolutionAutoAdvanceAtMs = 0

  private campaignUnlockedStageCount = 1

  private campaignLastUnlockedNodeIndex: number | null = null

  private campaignSelectedNodeIndex = 0

  private campaignSelectedLoadoutIndex = 0

  private campaignMenuIndex = 0

  private campaignScenePhase: RecoveryStageSnapshot['campaignState']['scenePhase'] = 'battle'

  private campaignWorldmapAutoEnterAtMs = 0

  private campaignDeployBriefingEndsAtMs = 0

  private campaignRewardReviewEndsAtMs = 0

  private campaignUnlockRevealEndsAtMs = 0

  private readonly campaignClearedStoryboardIds = new Set<string>()

  private campaignLastResolvedStageTitle: string | null = null

  private campaignLastOutcome: 'victory' | 'defeat' | null = null

  private campaignPreferredRouteLabel: string | null = null

  private campaignRouteCommitment = 0

  private activeDeployLoadout: RecoveryStageSnapshot['campaignState']['loadouts'][number] | null = null

  private lastActionId: RecoveryGameplayActionId | null = null

  private lastActionAccepted = false

  private lastActionNote: string | null = null

  private lastScriptedBeatNote: string | null = null

  private readonly rosterChainBoosts: Partial<Record<string, number>> = {}

  private rosterChainFocusLane: 'upper' | 'lower' | null = null

  private battleStepCount = 0

  private nextBattleEntityId = 1

  private nextBattleProjectileId = 1

  private nextBattleEffectId = 1

  private readonly laneEntities: Record<RecoveryBattleLaneId, Record<RecoveryBattleSide, RecoveryBattleUnitRuntime[]>> = {
    upper: { allied: [], enemy: [] },
    lower: { allied: [], enemy: [] },
  }

  private readonly battleProjectiles: RecoveryBattleProjectileRuntime[] = []

  private readonly battleEffects: RecoveryBattleEffectRuntime[] = []

  private readonly entityVisuals = new Map<number, RecoveryEntityVisualRuntime>()

  private cameraShakeIntensity = 0

  private cameraShakeAxes: RecoveryStageRenderState['cameraShakeAxes'] = 'both'

  private overlayMode: string | null = null

  private overlayColor: number | null = null

  private overlayAlpha = 0

  private burstPulseIntensity = 0

  private particleBoostIntensity = 0

  private hitFlashIntensity = 0

  private alliedManaValue = 0

  private enemyManaValue = 0

  private manaCapacityValue = 100

  private enemyManaCapacityValue = 100

  private populationCapacity = 6

  private enemyPopulationCapacity = 6

  private settingsState: RecoverySettingsState = {
    audioEnabled: true,
    masterVolume: 0.72,
    autoAdvanceEnabled: true,
    autoSaveEnabled: true,
    resumeOnLaunch: true,
    reducedEffects: false,
  }

  private hasQuickSave = false

  private hasResumeSession = false

  private resumedFromSession = false

  private activeSessionSlotLabel: string | null = null

  private lastSavedLabel: string | null = null

  private lastLoadedLabel: string | null = null

  private lastSavedAtIso: string | null = null

  private lastLoadedAtIso: string | null = null

  private sessionRevision = 0

  private lastAutoSaveAtMs = 0

  private audioCueSequence = 0

  private audioCueCategory: RecoveryAudioState['cueCategory'] = 'ui'

  private audioCueLabel: string | null = null

  private audioCueIntensity = 0

  constructor(
    catalog: RecoveryCatalog,
    previewManifest: RecoveryPreviewManifest,
    runtimeBlueprint: RecoveryRuntimeBlueprint | null = null,
    battleModel: RecoveryBattleModel | null = null,
  ) {
    this.runtimeBlueprint = runtimeBlueprint
    this.battleModel = battleModel
    this.loadStoredSettings()
    runtimeBlueprint?.featuredArchetypes.forEach((entry) => {
      this.featuredArchetypesById.set(entry.archetypeId, entry)
    })
    runtimeBlueprint?.opcodeHeuristics.forEach((entry) => {
      this.opcodeHeuristicsByMnemonic.set(entry.mnemonic, entry)
    })
    battleModel?.unitTemplates.forEach((entry) => {
      this.unitTemplatesById.set(entry.id, entry)
    })
    battleModel?.projectileTemplates.forEach((entry) => {
      this.projectileTemplatesById.set(entry.id, entry)
    })
    battleModel?.effectTemplates.forEach((entry) => {
      this.effectTemplatesById.set(entry.id, entry)
    })
    battleModel?.skillTemplates.forEach((entry) => {
      this.skillTemplatesByName.set(entry.name.toLowerCase(), entry)
    })
    battleModel?.itemTemplates.forEach((entry) => {
      this.itemTemplatesByName.set(entry.name.toLowerCase(), entry)
    })
    battleModel?.heroTemplates.forEach((entry) => {
      this.heroTemplatesByName.set(entry.name.toLowerCase(), entry)
    })
    this.storyboards = buildStoryboards(catalog, previewManifest, runtimeBlueprint)
    this.storyboards.forEach((storyboard) => {
      storyboard.sceneScriptSteps = this.buildSceneScript(storyboard)
    })
    if (this.storyboards.length > 0) {
      const restored = this.settingsState.resumeOnLaunch ? this.restoreStoredSession(RESUME_STORAGE_KEY, 'resume-session') : false
      if (!restored) {
        this.campaignPreferredRouteLabel = this.deriveStoryboardRouteBias(this.storyboards[0]).routeLabel
        this.campaignRouteCommitment = 1
        this.seedBattlePreviewState(this.storyboards[0])
        const initialLoadout = this.resolveSelectedDeployLoadout(this.storyboards[0])
        if (initialLoadout) {
          this.applyDeployLoadout(initialLoadout)
        }
        this.enterTitle(0)
      } else {
        this.hasResumeSession = true
      }
    }
  }

  isReady(): boolean {
    return this.storyboards.length > 0
  }

  getVersion(): number {
    return this.version
  }

  getPreviewEntries(): RecoveryPreviewStem[] {
    const seen = new Set<string>()
    return this.storyboards
      .map((storyboard) => storyboard.previewStem)
      .filter((entry) => {
        if (seen.has(entry.stem)) {
          return false
        }
        seen.add(entry.stem)
        return true
      })
  }

  getStoryboards(): RecoveryStageStoryboard[] {
    return this.storyboards
  }

  quickSave(): boolean {
    const saved = this.persistSessionToKey(QUICKSAVE_STORAGE_KEY, 'quick-save')
    if (!saved) {
      return false
    }
    this.lastActionNote = 'quick save written'
    this.emitAudioCue('system', 'save-session', 0.3)
    this.version += 1
    return true
  }

  quickLoad(): boolean {
    const restored = this.restoreStoredSession(QUICKSAVE_STORAGE_KEY, 'quick-save')
    if (!restored) {
      this.lastActionNote = 'quick load unavailable'
      this.version += 1
      return false
    }
    this.lastActionNote = 'quick save restored'
    this.emitAudioCue('system', 'load-session', 0.34)
    this.version += 1
    return true
  }

  retryActiveStage(): boolean {
    if (!this.isReady()) {
      return false
    }
    const index = clamp(
      this.campaignScenePhase === 'worldmap' || this.campaignScenePhase === 'deploy-briefing'
        ? this.campaignSelectedNodeIndex
        : this.storyboardIndex,
      0,
      this.storyboards.length - 1,
    )
    const storyboard = this.storyboards[index]
    if (!storyboard) {
      return false
    }

    if (this.campaignScenePhase === 'title') {
      this.enterMainMenu(this.lastUpdateNowMs)
      this.lastActionNote = 'title attract skipped for retry'
    } else {
      this.campaignSelectedNodeIndex = index
      const selectedLoadout = this.resolveSelectedDeployLoadout(storyboard)
      if (selectedLoadout) {
        this.activeDeployLoadout = selectedLoadout
      }
      this.activateStoryboard(index, this.lastUpdateNowMs, 0)
      this.lastActionNote = `stage retry started: ${this.storyboardLabel(index)}`
    }
    this.emitAudioCue('system', 'retry-stage', 0.36)
    this.persistResumeSessionNow('retry-stage')
    this.version += 1
    return true
  }

  toggleAudioEnabled(): boolean {
    this.settingsState.audioEnabled = !this.settingsState.audioEnabled
    this.persistSettings()
    this.lastActionNote = this.settingsState.audioEnabled ? 'audio enabled' : 'audio muted'
    this.emitAudioCue('system', this.settingsState.audioEnabled ? 'audio-on' : 'audio-off', 0.22)
    this.version += 1
    return true
  }

  adjustMasterVolume(delta: number): boolean {
    const nextVolume = clamp(this.settingsState.masterVolume + delta, 0, 1)
    if (Math.abs(nextVolume - this.settingsState.masterVolume) < 0.001) {
      return false
    }
    this.settingsState.masterVolume = nextVolume
    this.persistSettings()
    this.lastActionNote = `volume ${Math.round(nextVolume * 100)}%`
    this.emitAudioCue('system', 'volume-shift', 0.18 + nextVolume * 0.2)
    this.version += 1
    return true
  }

  toggleAutoAdvanceEnabled(): boolean {
    this.settingsState.autoAdvanceEnabled = !this.settingsState.autoAdvanceEnabled
    this.persistSettings()
    this.lastActionNote = this.settingsState.autoAdvanceEnabled ? 'auto advance enabled' : 'auto advance held for manual confirmation'
    this.emitAudioCue('system', this.settingsState.autoAdvanceEnabled ? 'auto-advance-on' : 'auto-advance-off', 0.22)
    this.version += 1
    return true
  }

  toggleAutoSaveEnabled(): boolean {
    this.settingsState.autoSaveEnabled = !this.settingsState.autoSaveEnabled
    this.persistSettings()
    this.lastActionNote = this.settingsState.autoSaveEnabled ? 'resume autosave enabled' : 'resume autosave paused'
    this.emitAudioCue('system', this.settingsState.autoSaveEnabled ? 'autosave-on' : 'autosave-off', 0.2)
    this.version += 1
    return true
  }

  toggleResumeOnLaunch(): boolean {
    this.settingsState.resumeOnLaunch = !this.settingsState.resumeOnLaunch
    this.persistSettings()
    this.lastActionNote = this.settingsState.resumeOnLaunch ? 'session resume on launch enabled' : 'session resume on launch disabled'
    this.emitAudioCue('system', this.settingsState.resumeOnLaunch ? 'resume-on' : 'resume-off', 0.2)
    this.version += 1
    return true
  }

  toggleReducedEffects(): boolean {
    this.settingsState.reducedEffects = !this.settingsState.reducedEffects
    this.persistSettings()
    this.lastActionNote = this.settingsState.reducedEffects ? 'reduced effects enabled' : 'full effects restored'
    this.emitAudioCue('system', this.settingsState.reducedEffects ? 'effects-low' : 'effects-full', 0.2)
    this.version += 1
    return true
  }

  persistResumeSessionNow(reason: string = 'manual-resume-save'): boolean {
    return this.persistSessionToKey(RESUME_STORAGE_KEY, reason)
  }

  private storage(): Storage | null {
    if (typeof window === 'undefined' || !('localStorage' in window)) {
      return null
    }
    try {
      return window.localStorage
    } catch {
      return null
    }
  }

  private loadStoredSettings(): void {
    const storage = this.storage()
    if (!storage) {
      return
    }
    this.hasQuickSave = storage.getItem(QUICKSAVE_STORAGE_KEY) !== null
    this.hasResumeSession = storage.getItem(RESUME_STORAGE_KEY) !== null
    const raw = storage.getItem(SETTINGS_STORAGE_KEY)
    if (!raw) {
      return
    }
    try {
      const parsed = JSON.parse(raw) as Partial<RecoveryStoredSettings>
      this.settingsState = {
        audioEnabled: parsed.audioEnabled ?? this.settingsState.audioEnabled,
        masterVolume: clamp(typeof parsed.masterVolume === 'number' ? parsed.masterVolume : this.settingsState.masterVolume, 0, 1),
        autoAdvanceEnabled: parsed.autoAdvanceEnabled ?? this.settingsState.autoAdvanceEnabled,
        autoSaveEnabled: parsed.autoSaveEnabled ?? this.settingsState.autoSaveEnabled,
        resumeOnLaunch: parsed.resumeOnLaunch ?? this.settingsState.resumeOnLaunch,
        reducedEffects: parsed.reducedEffects ?? this.settingsState.reducedEffects,
      }
    } catch {
      // Ignore invalid settings payloads.
    }
  }

  private persistSettings(): void {
    const storage = this.storage()
    if (!storage) {
      return
    }
    const payload: RecoveryStoredSettings = {
      audioEnabled: this.settingsState.audioEnabled,
      masterVolume: this.settingsState.masterVolume,
      autoAdvanceEnabled: this.settingsState.autoAdvanceEnabled,
      autoSaveEnabled: this.settingsState.autoSaveEnabled,
      resumeOnLaunch: this.settingsState.resumeOnLaunch,
      reducedEffects: this.settingsState.reducedEffects,
    }
    storage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(payload))
  }

  private persistSessionToKey(storageKey: string, slotLabel: string): boolean {
    const storage = this.storage()
    if (!storage || !this.isReady()) {
      return false
    }
    const savedAtIso = new Date().toISOString()
    this.sessionRevision += 1
    const payload = this.serializeSession(slotLabel, savedAtIso)
    storage.setItem(storageKey, JSON.stringify(payload))
    this.activeSessionSlotLabel = slotLabel
    this.lastSavedLabel = slotLabel
    this.lastSavedAtIso = savedAtIso
    this.lastAutoSaveAtMs = this.lastUpdateNowMs
    if (storageKey === QUICKSAVE_STORAGE_KEY) {
      this.hasQuickSave = true
    }
    if (storageKey === RESUME_STORAGE_KEY) {
      this.hasResumeSession = true
    }
    return true
  }

  private restoreStoredSession(storageKey: string, slotLabel: string): boolean {
    const storage = this.storage()
    if (!storage) {
      return false
    }
    const raw = storage.getItem(storageKey)
    if (!raw) {
      return false
    }
    try {
      const parsed = JSON.parse(raw) as RecoverySerializedSession
      const restored = this.restoreSerializedSession(parsed, slotLabel)
      if (!restored) {
        return false
      }
      this.resumedFromSession = slotLabel === 'resume-session'
      if (storageKey === QUICKSAVE_STORAGE_KEY) {
        this.hasQuickSave = true
      }
      if (storageKey === RESUME_STORAGE_KEY) {
        this.hasResumeSession = true
      }
      return true
    } catch {
      return false
    }
  }

  private serializeSession(slotLabel: string, savedAtIso: string): RecoverySerializedSession {
    return {
      version: 1,
      savedAtIso,
      slotLabel,
      sessionRevision: this.sessionRevision,
      storyboardIndex: this.storyboardIndex,
      dialogueIndex: this.dialogueIndex,
      frameIndex: this.frameIndex,
      storyboardElapsedMs: Math.max(this.lastUpdateNowMs - this.storyboardStartedAtMs, 0),
      nextDialogueRemainingMs: this.remainingMs(this.nextDialogueAtMs),
      nextFrameRemainingMs: this.remainingMs(this.nextFrameAtMs),
      heroReturnCooldownRemainingMs: this.remainingMs(this.heroReturnCooldownEndsAtMs),
      skillCooldownRemainingMs: this.remainingMs(this.skillCooldownEndsAtMs),
      itemCooldownRemainingMs: this.remainingMs(this.itemCooldownEndsAtMs),
      worldmapAutoEnterRemainingMs: this.remainingMs(this.campaignWorldmapAutoEnterAtMs),
      deployBriefingRemainingMs: this.remainingMs(this.campaignDeployBriefingEndsAtMs),
      rewardReviewRemainingMs: this.remainingMs(this.campaignRewardReviewEndsAtMs),
      unlockRevealRemainingMs: this.remainingMs(this.campaignUnlockRevealEndsAtMs),
      resultAutoAdvanceRemainingMs: this.remainingMs(this.battleResolutionAutoAdvanceAtMs),
      lastChannelBeat: this.lastChannelBeat,
      panelOverride: this.panelOverride,
      heroOverrideMode: this.heroOverrideMode,
      battlePaused: this.battlePaused,
      questRewardClaimed: this.questRewardClaimed,
      questRewardClaims: this.questRewardClaims,
      selectedDispatchLane: this.selectedDispatchLane,
      queuedUnitCount: this.queuedUnitCount,
      previewManaRatio: this.previewManaRatio,
      previewManaUpgradeProgressRatio: this.previewManaUpgradeProgressRatio,
      previewOwnTowerHpRatio: this.previewOwnTowerHpRatio,
      previewEnemyTowerHpRatio: this.previewEnemyTowerHpRatio,
      alliedManaValue: this.alliedManaValue,
      enemyManaValue: this.enemyManaValue,
      manaCapacityValue: this.manaCapacityValue,
      enemyManaCapacityValue: this.enemyManaCapacityValue,
      populationCapacity: this.populationCapacity,
      enemyPopulationCapacity: this.enemyPopulationCapacity,
      heroAssignedLane: this.heroAssignedLane,
      laneBattleState: structuredClone(this.laneBattleState),
      towerUpgradeLevels: { ...this.towerUpgradeLevels },
      currentStageBattleProfile: structuredClone(this.currentStageBattleProfile),
      currentObjectivePhase: this.currentObjectivePhase,
      currentObjectiveLabel: this.currentObjectiveLabel,
      currentWaveIndex: this.currentWaveIndex,
      totalWaveCount: this.totalWaveCount,
      enemyWaveCursor: this.enemyWaveCursor,
      alliedWaveCursor: this.alliedWaveCursor,
      enemyWavesDispatched: this.enemyWavesDispatched,
      alliedWavesDispatched: this.alliedWavesDispatched,
      objectiveProgressRatio: this.objectiveProgressRatio,
      enemyWaveCountdownBeats: this.enemyWaveCountdownBeats,
      alliedWaveCountdownBeats: this.alliedWaveCountdownBeats,
      enemyWavePlan: structuredClone(this.enemyWavePlan),
      alliedWavePlan: structuredClone(this.alliedWavePlan),
      battleResolutionOutcome: this.battleResolutionOutcome,
      battleResolutionReason: this.battleResolutionReason,
      campaignUnlockedStageCount: this.campaignUnlockedStageCount,
      campaignLastUnlockedNodeIndex: this.campaignLastUnlockedNodeIndex,
      campaignSelectedNodeIndex: this.campaignSelectedNodeIndex,
      campaignSelectedLoadoutIndex: this.campaignSelectedLoadoutIndex,
      campaignMenuIndex: this.campaignMenuIndex,
      campaignScenePhase: this.campaignScenePhase,
      campaignClearedStoryboardIds: Array.from(this.campaignClearedStoryboardIds),
      campaignLastResolvedStageTitle: this.campaignLastResolvedStageTitle,
      campaignLastOutcome: this.campaignLastOutcome,
      campaignPreferredRouteLabel: this.campaignPreferredRouteLabel,
      campaignRouteCommitment: this.campaignRouteCommitment,
      activeDeployLoadoutId: this.activeDeployLoadout?.id ?? null,
      lastActionId: this.lastActionId,
      lastActionAccepted: this.lastActionAccepted,
      lastActionNote: this.lastActionNote,
      lastScriptedBeatNote: this.lastScriptedBeatNote,
      rosterChainBoosts: Object.entries(this.rosterChainBoosts).filter((entry): entry is [string, number] => typeof entry[1] === 'number'),
      rosterChainFocusLane: this.rosterChainFocusLane,
      battleStepCount: this.battleStepCount,
      nextBattleEntityId: this.nextBattleEntityId,
      nextBattleProjectileId: this.nextBattleProjectileId,
      nextBattleEffectId: this.nextBattleEffectId,
      laneEntities: structuredClone(this.laneEntities),
      battleProjectiles: structuredClone(this.battleProjectiles),
      battleEffects: structuredClone(this.battleEffects),
      entityVisuals: Array.from(this.entityVisuals.entries()).map(([key, value]) => [key, structuredClone(value)]),
      cameraShakeIntensity: this.cameraShakeIntensity,
      cameraShakeAxes: this.cameraShakeAxes,
      overlayMode: this.overlayMode,
      overlayColor: this.overlayColor,
      overlayAlpha: this.overlayAlpha,
      burstPulseIntensity: this.burstPulseIntensity,
      particleBoostIntensity: this.particleBoostIntensity,
      hitFlashIntensity: this.hitFlashIntensity,
      settings: {
        audioEnabled: this.settingsState.audioEnabled,
        masterVolume: this.settingsState.masterVolume,
        autoAdvanceEnabled: this.settingsState.autoAdvanceEnabled,
        autoSaveEnabled: this.settingsState.autoSaveEnabled,
        resumeOnLaunch: this.settingsState.resumeOnLaunch,
        reducedEffects: this.settingsState.reducedEffects,
      },
    }
  }

  private restoreSerializedSession(payload: RecoverySerializedSession, slotLabel: string): boolean {
    if (payload.version !== 1 || !this.storyboards[payload.storyboardIndex]) {
      return false
    }
    const baseNow = this.lastUpdateNowMs
    this.storyboardIndex = clamp(payload.storyboardIndex, 0, this.storyboards.length - 1)
    this.dialogueIndex = clamp(payload.dialogueIndex, 0, Math.max(this.storyboards[this.storyboardIndex].scriptEvents.length - 1, 0))
    this.frameIndex = Math.max(payload.frameIndex, 0)
    this.storyboardStartedAtMs = baseNow - Math.max(payload.storyboardElapsedMs, 0)
    this.nextDialogueAtMs = this.restoreDeadline(payload.nextDialogueRemainingMs, baseNow)
    this.nextFrameAtMs = this.restoreDeadline(payload.nextFrameRemainingMs, baseNow)
    this.heroReturnCooldownEndsAtMs = this.restoreDeadline(payload.heroReturnCooldownRemainingMs, baseNow)
    this.skillCooldownEndsAtMs = this.restoreDeadline(payload.skillCooldownRemainingMs, baseNow)
    this.itemCooldownEndsAtMs = this.restoreDeadline(payload.itemCooldownRemainingMs, baseNow)
    this.campaignWorldmapAutoEnterAtMs = this.restoreDeadline(payload.worldmapAutoEnterRemainingMs, baseNow)
    this.campaignDeployBriefingEndsAtMs = this.restoreDeadline(payload.deployBriefingRemainingMs, baseNow)
    this.campaignRewardReviewEndsAtMs = this.restoreDeadline(payload.rewardReviewRemainingMs, baseNow)
    this.campaignUnlockRevealEndsAtMs = this.restoreDeadline(payload.unlockRevealRemainingMs, baseNow)
    this.battleResolutionAutoAdvanceAtMs = this.restoreDeadline(payload.resultAutoAdvanceRemainingMs, baseNow)
    this.lastChannelBeat = payload.lastChannelBeat
    this.panelOverride = payload.panelOverride
    this.heroOverrideMode = payload.heroOverrideMode
    this.battlePaused = payload.battlePaused
    this.pauseStartedAtMs = payload.battlePaused ? baseNow : 0
    this.questRewardClaimed = payload.questRewardClaimed
    this.questRewardClaims = payload.questRewardClaims
    this.selectedDispatchLane = payload.selectedDispatchLane
    this.queuedUnitCount = payload.queuedUnitCount
    this.previewManaRatio = payload.previewManaRatio
    this.previewManaUpgradeProgressRatio = payload.previewManaUpgradeProgressRatio
    this.previewOwnTowerHpRatio = payload.previewOwnTowerHpRatio
    this.previewEnemyTowerHpRatio = payload.previewEnemyTowerHpRatio
    this.alliedManaValue = payload.alliedManaValue
    this.enemyManaValue = payload.enemyManaValue
    this.manaCapacityValue = payload.manaCapacityValue
    this.enemyManaCapacityValue = payload.enemyManaCapacityValue
    this.populationCapacity = payload.populationCapacity
    this.enemyPopulationCapacity = payload.enemyPopulationCapacity
    this.heroAssignedLane = payload.heroAssignedLane
    this.copyLaneBattleState(payload.laneBattleState)
    this.towerUpgradeLevels.mana = payload.towerUpgradeLevels.mana
    this.towerUpgradeLevels.population = payload.towerUpgradeLevels.population
    this.towerUpgradeLevels.attack = payload.towerUpgradeLevels.attack
    this.currentStageBattleProfile = structuredClone(payload.currentStageBattleProfile)
    this.currentObjectivePhase = payload.currentObjectivePhase
    this.currentObjectiveLabel = payload.currentObjectiveLabel
    this.currentWaveIndex = payload.currentWaveIndex
    this.totalWaveCount = payload.totalWaveCount
    this.enemyWaveCursor = payload.enemyWaveCursor
    this.alliedWaveCursor = payload.alliedWaveCursor
    this.enemyWavesDispatched = payload.enemyWavesDispatched
    this.alliedWavesDispatched = payload.alliedWavesDispatched
    this.objectiveProgressRatio = payload.objectiveProgressRatio
    this.enemyWaveCountdownBeats = payload.enemyWaveCountdownBeats
    this.alliedWaveCountdownBeats = payload.alliedWaveCountdownBeats
    this.enemyWavePlan = structuredClone(payload.enemyWavePlan)
    this.alliedWavePlan = structuredClone(payload.alliedWavePlan)
    this.battleResolutionOutcome = payload.battleResolutionOutcome
    this.battleResolutionReason = payload.battleResolutionReason
    this.campaignUnlockedStageCount = payload.campaignUnlockedStageCount
    this.campaignLastUnlockedNodeIndex = payload.campaignLastUnlockedNodeIndex
    this.campaignSelectedNodeIndex = payload.campaignSelectedNodeIndex
    this.campaignSelectedLoadoutIndex = payload.campaignSelectedLoadoutIndex
    this.campaignMenuIndex = payload.campaignMenuIndex
    this.campaignScenePhase = payload.campaignScenePhase
    this.campaignClearedStoryboardIds.clear()
    payload.campaignClearedStoryboardIds.forEach((id) => {
      this.campaignClearedStoryboardIds.add(id)
    })
    this.campaignLastResolvedStageTitle = payload.campaignLastResolvedStageTitle
    this.campaignLastOutcome = payload.campaignLastOutcome
    this.campaignPreferredRouteLabel = payload.campaignPreferredRouteLabel
    this.campaignRouteCommitment = payload.campaignRouteCommitment
    this.activeDeployLoadout = this.findLoadoutById(payload.activeDeployLoadoutId, this.storyboards[this.storyboardIndex])
    this.lastActionId = payload.lastActionId
    this.lastActionAccepted = payload.lastActionAccepted
    this.lastActionNote = payload.lastActionNote
    this.lastScriptedBeatNote = payload.lastScriptedBeatNote
    for (const key of Object.keys(this.rosterChainBoosts)) {
      delete this.rosterChainBoosts[key]
    }
    payload.rosterChainBoosts.forEach(([key, value]) => {
      this.rosterChainBoosts[key] = value
    })
    this.rosterChainFocusLane = payload.rosterChainFocusLane
    this.battleStepCount = payload.battleStepCount
    this.nextBattleEntityId = payload.nextBattleEntityId
    this.nextBattleProjectileId = payload.nextBattleProjectileId
    this.nextBattleEffectId = payload.nextBattleEffectId
    this.copyLaneEntities(payload.laneEntities)
    this.replaceRuntimeList(this.battleProjectiles, payload.battleProjectiles)
    this.replaceRuntimeList(this.battleEffects, payload.battleEffects)
    this.entityVisuals.clear()
    payload.entityVisuals.forEach(([key, value]) => {
      this.entityVisuals.set(key, structuredClone(value))
    })
    this.cameraShakeIntensity = payload.cameraShakeIntensity
    this.cameraShakeAxes = payload.cameraShakeAxes
    this.overlayMode = payload.overlayMode
    this.overlayColor = payload.overlayColor
    this.overlayAlpha = payload.overlayAlpha
    this.burstPulseIntensity = payload.burstPulseIntensity
    this.particleBoostIntensity = payload.particleBoostIntensity
    this.hitFlashIntensity = payload.hitFlashIntensity
    this.settingsState = {
      audioEnabled: payload.settings.audioEnabled,
      masterVolume: clamp(payload.settings.masterVolume, 0, 1),
      autoAdvanceEnabled: payload.settings.autoAdvanceEnabled,
      autoSaveEnabled: payload.settings.autoSaveEnabled,
      resumeOnLaunch: payload.settings.resumeOnLaunch,
      reducedEffects: payload.settings.reducedEffects,
    }
    this.persistSettings()
    this.rebuildLaneBattleState()
    this.lastSavedLabel = payload.slotLabel
    this.lastSavedAtIso = payload.savedAtIso
    this.lastLoadedLabel = slotLabel
    this.lastLoadedAtIso = new Date().toISOString()
    this.activeSessionSlotLabel = slotLabel
    this.sessionRevision = Math.max(payload.sessionRevision, this.sessionRevision)
    this.lastAutoSaveAtMs = baseNow
    return true
  }

  private remainingMs(deadlineMs: number): number | null {
    if (!Number.isFinite(deadlineMs) || deadlineMs <= 0) {
      return null
    }
    return Math.max(deadlineMs - this.lastUpdateNowMs, 0)
  }

  private restoreDeadline(remainingMs: number | null, baseNow: number): number {
    if (remainingMs === null || !Number.isFinite(remainingMs)) {
      return 0
    }
    return baseNow + Math.max(remainingMs, 0)
  }

  private copyLaneBattleState(
    source: Record<RecoveryLaneBattleState['laneId'], Omit<RecoveryLaneBattleState, 'laneId'>>,
  ): void {
    ;(['upper', 'lower'] as const).forEach((laneId) => {
      const target = this.laneBattleState[laneId]
      const next = source[laneId]
      target.alliedUnits = next.alliedUnits
      target.enemyUnits = next.enemyUnits
      target.alliedPressure = next.alliedPressure
      target.enemyPressure = next.enemyPressure
      target.frontline = next.frontline
      target.contested = next.contested
      target.momentum = next.momentum
      target.heroPresent = next.heroPresent
    })
  }

  private copyLaneEntities(
    source: Record<RecoveryBattleLaneId, Record<RecoveryBattleSide, RecoveryBattleUnitRuntime[]>>,
  ): void {
    ;(['upper', 'lower'] as const).forEach((laneId) => {
      ;(['allied', 'enemy'] as const).forEach((side) => {
        this.replaceRuntimeList(this.laneEntities[laneId][side], source[laneId][side])
      })
    })
  }

  private replaceRuntimeList<T>(target: T[], source: T[]): void {
    target.splice(0, target.length, ...structuredClone(source))
  }

  private findLoadoutById(
    loadoutId: string | null,
    storyboard: RecoveryStageStoryboard | null,
  ): RecoveryStageSnapshot['campaignState']['loadouts'][number] | null {
    if (!loadoutId || !storyboard) {
      return null
    }
    return this.buildDeployLoadouts(storyboard).find((loadout) => loadout.id === loadoutId) ?? null
  }

  private buildSettingsState(): RecoverySettingsState {
    return { ...this.settingsState }
  }

  private buildPersistenceState(): RecoveryPersistenceState {
    return {
      hasQuickSave: this.hasQuickSave,
      hasResumeSession: this.hasResumeSession,
      resumedFromSession: this.resumedFromSession,
      activeSlotLabel: this.activeSessionSlotLabel,
      lastSavedLabel: this.lastSavedLabel,
      lastLoadedLabel: this.lastLoadedLabel,
      lastSavedAtIso: this.lastSavedAtIso,
      lastLoadedAtIso: this.lastLoadedAtIso,
      sessionRevision: this.sessionRevision,
    }
  }

  private buildAudioState(): RecoveryAudioState {
    return {
      enabled: this.settingsState.audioEnabled,
      masterVolume: this.settingsState.masterVolume,
      ambientLayer: this.deriveAmbientLayer(),
      cueSequence: this.audioCueSequence,
      cueCategory: this.audioCueCategory,
      cueLabel: this.audioCueLabel,
      cueIntensity: this.audioCueIntensity,
    }
  }

  private deriveAmbientLayer(): RecoveryAudioState['ambientLayer'] {
    switch (this.campaignScenePhase) {
      case 'title':
        return 'title'
      case 'main-menu':
        return 'menu'
      case 'worldmap':
        return 'worldmap'
      case 'deploy-briefing':
        return 'deploy'
      case 'reward-review':
        return 'reward'
      case 'unlock-reveal':
        return 'unlock'
      case 'result-hold':
        return 'result'
      default:
        return 'battle'
    }
  }

  private emitAudioCue(
    cueCategory: RecoveryAudioState['cueCategory'],
    cueLabel: string,
    cueIntensity: number,
  ): void {
    this.audioCueSequence += 1
    this.audioCueCategory = cueCategory
    this.audioCueLabel = cueLabel
    this.audioCueIntensity = clamp(cueIntensity, 0, 1)
  }

  private maybePersistResumeSession(nowMs: number): void {
    if (!this.settingsState.autoSaveEnabled || nowMs - this.lastAutoSaveAtMs < AUTO_SAVE_INTERVAL_MS) {
      return
    }
    if (this.persistSessionToKey(RESUME_STORAGE_KEY, 'resume-session')) {
      this.lastAutoSaveAtMs = nowMs
    }
  }

  moveCampaignMenu(direction: -1 | 1): boolean {
    if (!this.isReady() || this.campaignScenePhase !== 'main-menu') {
      return false
    }

    const entries = this.campaignMenuEntries()
    const nextIndex = clamp(this.campaignMenuIndex + direction, 0, Math.max(entries.length - 1, 0))
    if (nextIndex === this.campaignMenuIndex) {
      return false
    }

    this.campaignMenuIndex = nextIndex
    this.lastActionNote = `menu focus: ${entries[nextIndex]?.label ?? 'campaign'}`
    this.version += 1
    return true
  }

  moveCampaignSelection(direction: -1 | 1): boolean {
    if (!this.isReady()) {
      return false
    }

    if (
      this.campaignScenePhase === 'title'
      || this.campaignScenePhase === 'main-menu'
      || this.campaignScenePhase === 'reward-review'
      || this.campaignScenePhase === 'unlock-reveal'
    ) {
      return false
    }

    if (!this.battlePaused && this.campaignScenePhase === 'battle') {
      this.lastActionNote = 'campaign route selection is unavailable during active battle'
      this.version += 1
      return false
    }

    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    const nextIndex = clamp(this.campaignSelectedNodeIndex + direction, 0, unlockedCount - 1)
    if (nextIndex === this.campaignSelectedNodeIndex) {
      return false
    }

    this.campaignSelectedNodeIndex = nextIndex
    const targetStoryboard = this.storyboards[nextIndex]
    this.campaignSelectedLoadoutIndex = targetStoryboard
      ? this.deriveRecommendedLoadoutIndexForStoryboard(targetStoryboard).loadoutIndex
      : 0
    if (this.campaignScenePhase === 'worldmap') {
      this.campaignWorldmapAutoEnterAtMs = this.lastUpdateNowMs + WORLDMAP_HOLD_MS
    }
    const target = targetStoryboard
    this.lastActionNote = `campaign route selected: ${target?.stageBlueprint?.title ?? target?.scriptPath ?? `node ${nextIndex + 1}`}`
    this.version += 1
    return true
  }

  moveCampaignLoadout(direction: -1 | 1): boolean {
    if (!this.isReady()) {
      return false
    }

    if (
      this.campaignScenePhase === 'title'
      || this.campaignScenePhase === 'main-menu'
      || this.campaignScenePhase === 'reward-review'
      || this.campaignScenePhase === 'unlock-reveal'
    ) {
      return false
    }

    if (this.campaignScenePhase === 'battle' && !this.battlePaused) {
      this.lastActionNote = 'deploy loadout selection is unavailable during active battle'
      this.version += 1
      return false
    }

    const storyboard = this.storyboards[clamp(this.campaignSelectedNodeIndex, 0, Math.max(this.campaignUnlockedStageCount, 1) - 1)]
    if (!storyboard) {
      return false
    }

    const loadouts = this.buildDeployLoadouts(storyboard)
    const nextIndex = clamp(this.campaignSelectedLoadoutIndex + direction, 0, loadouts.length - 1)
    if (nextIndex === this.campaignSelectedLoadoutIndex) {
      return false
    }

    this.campaignSelectedLoadoutIndex = nextIndex
    if (this.campaignScenePhase === 'deploy-briefing') {
      this.campaignDeployBriefingEndsAtMs = this.lastUpdateNowMs + DEPLOY_BRIEFING_MS
    }
    const target = loadouts[nextIndex]
    this.lastActionNote = `deploy loadout selected: ${target.label}`
    this.version += 1
    return true
  }

  launchSelectedCampaignNode(): boolean {
    if (!this.isReady()) {
      return false
    }

    if (this.campaignScenePhase === 'title') {
      this.enterMainMenu(this.lastUpdateNowMs)
      this.lastActionNote = 'main menu opened'
      this.version += 1
      return true
    }

    if (this.campaignScenePhase === 'main-menu') {
      const entries = this.campaignMenuEntries()
      const selected = entries[clamp(this.campaignMenuIndex, 0, Math.max(entries.length - 1, 0))]
      const currentStoryboard = this.storyboards[this.storyboardIndex] ?? this.storyboards[0]
      const recommendation = currentStoryboard ? this.deriveCampaignRecommendation(currentStoryboard) : null
      if (selected?.action === 'continue-campaign') {
        this.enterWorldmapSelection(this.lastUpdateNowMs)
      } else if (selected?.action === 'direct-deploy') {
        this.enterDeployBriefing(recommendation?.nodeIndex ?? this.campaignSelectedNodeIndex, this.lastUpdateNowMs)
      } else {
        this.enterDeployBriefing(this.storyboardIndex, this.lastUpdateNowMs)
      }
      this.lastActionNote = selected ? `${selected.label} selected` : 'campaign menu accepted'
      this.version += 1
      return true
    }

    if (this.campaignScenePhase === 'result-hold') {
      if (this.battleResolutionOutcome === 'victory') {
        this.enterRewardReview(this.lastUpdateNowMs)
      } else {
        this.enterWorldmapSelection(this.lastUpdateNowMs)
      }
      this.version += 1
      return true
    }

    if (this.campaignScenePhase === 'reward-review') {
      if (this.currentUnlockRevealLabel() !== null) {
        this.enterUnlockReveal(this.lastUpdateNowMs)
      } else {
        this.enterWorldmapSelection(this.lastUpdateNowMs)
      }
      this.version += 1
      return true
    }

    if (this.campaignScenePhase === 'unlock-reveal') {
      this.enterWorldmapSelection(this.lastUpdateNowMs)
      this.version += 1
      return true
    }

    if (!this.battlePaused && this.campaignScenePhase === 'battle') {
      this.lastActionNote = 'campaign route launch locked until pause or result'
      this.version += 1
      return false
    }

    if (this.campaignScenePhase === 'battle' && this.battlePaused) {
      this.enterWorldmapSelection(this.lastUpdateNowMs)
      this.lastActionNote = 'paused battle routed to worldmap'
      this.version += 1
      return true
    }

    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    const nextIndex = clamp(this.campaignSelectedNodeIndex, 0, unlockedCount - 1)
    if (this.campaignScenePhase === 'deploy-briefing') {
      this.launchCampaignNodeNow(nextIndex, this.lastUpdateNowMs)
    } else {
      this.enterDeployBriefing(nextIndex, this.lastUpdateNowMs)
    }
    const target = this.storyboards[nextIndex]
    this.lastActionNote = `campaign node queued: ${target?.stageBlueprint?.title ?? target?.scriptPath ?? `node ${nextIndex + 1}`}`
    this.version += 1
    return true
  }

  dispatchAction(actionId: RecoveryGameplayActionId): boolean {
    const snapshot = this.getSnapshot()
    if (!snapshot) {
      return false
    }

    const gameplayState = snapshot.gameplayState
    const accepted =
      gameplayState.enabledInputs.includes(actionId) && !gameplayState.blockedInputs.includes(actionId)

    this.lastActionId = actionId
    this.lastActionAccepted = accepted
    if (!accepted) {
      this.lastActionNote = `${actionId} blocked in ${gameplayState.objectiveMode}`
      this.version += 1
      return false
    }

    this.applyAction(actionId, snapshot)
    this.version += 1
    return true
  }

  getSnapshot(): RecoveryStageSnapshot | null {
    const currentStoryboard = this.storyboards[this.storyboardIndex]
    if (!currentStoryboard) {
      return null
    }
    const activeDialogueEvent = this.currentDialogueEvent(currentStoryboard)
    const activeTutorialCue = this.resolveTutorialCue(currentStoryboard, activeDialogueEvent)
    const activeSceneCommands = this.resolveSceneCommands(activeDialogueEvent)
    const activeOpcodeCue = this.resolvePrimarySceneCommand(activeSceneCommands)
    const activeSceneStep = currentStoryboard.sceneScriptSteps[this.dialogueIndex] ?? null
    const channelStates = this.buildChannelStates(currentStoryboard)
    const hudState = this.buildHudState(currentStoryboard, activeSceneStep, activeOpcodeCue, channelStates)
    const battlePreviewState = this.buildBattlePreviewState()
    return {
      storyboardIndex: this.storyboardIndex,
      dialogueIndex: this.dialogueIndex,
      frameIndex: this.frameIndex,
      elapsedStoryboardMs: Math.max(this.lastUpdateNowMs - this.storyboardStartedAtMs, 0),
      currentStoryboard,
      campaignState: this.buildCampaignState(currentStoryboard),
      activeDialogueEvent,
      activeTutorialCue,
      activeSceneCommands,
      activeOpcodeCue,
      channelStates,
      renderState: this.buildRenderState(currentStoryboard, channelStates),
      hudState,
      gameplayState: this.buildGameplayState(
        activeSceneStep,
        activeTutorialCue,
        activeOpcodeCue,
        hudState,
      ),
      settingsState: this.buildSettingsState(),
      persistenceState: this.buildPersistenceState(),
      audioState: this.buildAudioState(),
      battlePreviewState,
    }
  }

  advance(nowMs: number): boolean {
    if (!this.isReady()) {
      return false
    }

    if (this.battlePaused) {
      if (this.pauseStartedAtMs <= 0) {
        this.pauseStartedAtMs = nowMs
      }
      return false
    }

    if (this.pauseStartedAtMs > 0) {
      const pausedDurationMs = Math.max(nowMs - this.pauseStartedAtMs, 0)
      if (pausedDurationMs > 0) {
        this.shiftTimelineBy(pausedDurationMs)
      }
      this.pauseStartedAtMs = 0
    }

    this.lastUpdateNowMs = nowMs
    let changed = false
    if (!Number.isFinite(this.nextDialogueAtMs) || !Number.isFinite(this.nextFrameAtMs)) {
      this.resetDeadlines(nowMs)
      changed = true
    }

    while (nowMs >= this.nextFrameAtMs) {
      this.stepFrame()
      this.scheduleNextFrame(this.storyboards[this.storyboardIndex].previewStem, nowMs)
      changed = true
    }

    if (this.campaignScenePhase === 'title' || this.campaignScenePhase === 'main-menu') {
      // Hold on the title/menu phases while keeping sprite playback alive.
    } else if (this.campaignScenePhase === 'result-hold') {
      if (this.settingsState.autoAdvanceEnabled && this.battleResolutionAutoAdvanceAtMs > 0 && nowMs >= this.battleResolutionAutoAdvanceAtMs) {
        if (this.battleResolutionOutcome === 'victory') {
          this.enterRewardReview(nowMs)
        } else {
          this.enterWorldmapSelection(nowMs)
        }
        this.version += 1
        return true
      }
    } else if (this.campaignScenePhase === 'reward-review') {
      if (this.settingsState.autoAdvanceEnabled && this.campaignRewardReviewEndsAtMs > 0 && nowMs >= this.campaignRewardReviewEndsAtMs) {
        if (this.currentUnlockRevealLabel() !== null) {
          this.enterUnlockReveal(nowMs)
        } else {
          this.enterWorldmapSelection(nowMs)
        }
        this.version += 1
        return true
      }
    } else if (this.campaignScenePhase === 'unlock-reveal') {
      if (this.settingsState.autoAdvanceEnabled && this.campaignUnlockRevealEndsAtMs > 0 && nowMs >= this.campaignUnlockRevealEndsAtMs) {
        this.enterWorldmapSelection(nowMs)
        this.version += 1
        return true
      }
    } else if (this.campaignScenePhase === 'worldmap') {
      if (this.settingsState.autoAdvanceEnabled && this.campaignWorldmapAutoEnterAtMs > 0 && nowMs >= this.campaignWorldmapAutoEnterAtMs) {
        this.enterDeployBriefing(this.campaignSelectedNodeIndex, nowMs)
        this.version += 1
        return true
      }
    } else if (this.campaignScenePhase === 'deploy-briefing') {
      if (this.settingsState.autoAdvanceEnabled && this.campaignDeployBriefingEndsAtMs > 0 && nowMs >= this.campaignDeployBriefingEndsAtMs) {
        this.launchCampaignNodeNow(this.campaignSelectedNodeIndex, nowMs)
        this.version += 1
        return true
      }
    } else {
      while (nowMs >= this.nextDialogueAtMs) {
        this.stepDialogue(nowMs)
        changed = true
      }

      const channelBeat = Math.floor(Math.max(nowMs - this.storyboardStartedAtMs, 0) / 120)
      if (channelBeat !== this.lastChannelBeat) {
        this.lastChannelBeat = channelBeat
        this.tickPersistentPreview()
        changed = true
      }
    }

    if (changed) {
      this.version += 1
    }
    this.maybePersistResumeSession(nowMs)
    return changed
  }

  private resetDeadlines(nowMs: number): void {
    this.activateStoryboard(this.storyboardIndex, nowMs)
  }

  private currentDialogueDuration(): number {
    const storyboard = this.storyboards[this.storyboardIndex]
    const event = storyboard ? this.currentDialogueEvent(storyboard) : null
    if (!event) {
      return 1800
    }
    return dialogueDurationMs(event)
  }

  private currentDialogueEvent(storyboard: RecoveryStageStoryboard): RecoveryDialogueEvent | null {
    if (storyboard.scriptEvents.length === 0) {
      return null
    }
    return storyboard.scriptEvents[Math.min(this.dialogueIndex, storyboard.scriptEvents.length - 1)] ?? null
  }

  private scheduleNextFrame(entry: RecoveryPreviewStem, nowMs: number): void {
    const frame = this.currentFrame(entry)
    const delay = Math.max(frame?.playbackDurationMs ?? entry.stemDefaultDurationMs ?? 140, 40)
    this.nextFrameAtMs = nowMs + delay
  }

  private stepDialogue(nowMs: number): void {
    const storyboard = this.storyboards[this.storyboardIndex]
    if (storyboard.scriptEvents.length <= 1) {
      this.nextDialogueAtMs = Number.POSITIVE_INFINITY
      return
    }

    if (this.dialogueIndex >= storyboard.scriptEvents.length - 1) {
      this.nextDialogueAtMs = Number.POSITIVE_INFINITY
      return
    }

    this.dialogueIndex += 1
    this.applyDialogueBeat(storyboard, this.currentDialogueEvent(storyboard))
    this.nextDialogueAtMs = nowMs + this.currentDialogueDuration()
  }

  private activateStoryboard(index: number, nowMs: number, dialogueGapMs: number = 0): void {
    this.storyboardIndex = index
    this.campaignSelectedNodeIndex = index
    this.campaignScenePhase = 'battle'
    this.campaignMenuIndex = 0
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = 0
    this.campaignRewardReviewEndsAtMs = 0
    this.campaignUnlockRevealEndsAtMs = 0
    this.dialogueIndex = 0
    this.frameIndex = 0
    this.storyboardStartedAtMs = nowMs
    this.lastChannelBeat = -1
    this.resetInteractionState()
    const storyboard = this.storyboards[this.storyboardIndex]
    this.seedBattlePreviewState(storyboard)
    this.applyDialogueBeat(storyboard, this.currentDialogueEvent(storyboard))
    this.nextDialogueAtMs = nowMs + this.currentDialogueDuration() + dialogueGapMs
    this.scheduleNextFrame(storyboard.previewStem, nowMs)
    this.emitAudioCue('battle', 'battle-start', 0.42)
  }

  private enterWorldmapSelection(nowMs: number): void {
    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    this.battlePaused = false
    this.pauseStartedAtMs = 0
    if (this.battleResolutionOutcome === 'victory' && !this.questRewardClaimed) {
      this.claimQuestRewardPayout()
    }
    const currentStoryboard = this.storyboards[this.storyboardIndex] ?? this.storyboards[0]
    const recommendation = currentStoryboard ? this.deriveCampaignRecommendation(currentStoryboard) : null
    if (recommendation) {
      this.campaignSelectedNodeIndex = clamp(recommendation.nodeIndex, 0, unlockedCount - 1)
      this.campaignSelectedLoadoutIndex = recommendation.loadoutIndex
    } else if (this.battleResolutionOutcome === 'victory') {
      this.campaignSelectedNodeIndex = clamp(Math.min(this.storyboardIndex + 1, unlockedCount - 1), 0, unlockedCount - 1)
      this.campaignSelectedLoadoutIndex = 0
    } else {
      this.campaignSelectedNodeIndex = clamp(this.storyboardIndex, 0, unlockedCount - 1)
      this.campaignSelectedLoadoutIndex = 0
    }
    this.campaignScenePhase = 'worldmap'
    this.campaignMenuIndex = 0
    this.campaignWorldmapAutoEnterAtMs = nowMs + WORLDMAP_HOLD_MS
    this.campaignDeployBriefingEndsAtMs = 0
    this.campaignRewardReviewEndsAtMs = 0
    this.campaignUnlockRevealEndsAtMs = 0
    this.campaignLastUnlockedNodeIndex = null
    this.lastActionNote = `worldmap opened for ${this.storyboardLabel(this.campaignSelectedNodeIndex)}`
    this.emitAudioCue('ui', 'worldmap-open', 0.26)
  }

  private enterDeployBriefing(index: number, nowMs: number): void {
    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    this.battlePaused = false
    this.pauseStartedAtMs = 0
    this.campaignSelectedNodeIndex = clamp(index, 0, unlockedCount - 1)
    const targetStoryboard = this.storyboards[this.campaignSelectedNodeIndex] ?? this.storyboards[0]
    const recommendedLoadout = targetStoryboard ? this.deriveRecommendedLoadoutIndexForStoryboard(targetStoryboard) : null
    const loadoutCount = this.buildDeployLoadouts(targetStoryboard ?? this.storyboards[0]).length
    this.campaignSelectedLoadoutIndex = clamp(
      recommendedLoadout?.loadoutIndex ?? this.campaignSelectedLoadoutIndex,
      0,
      Math.max(loadoutCount - 1, 0),
    )
    this.campaignScenePhase = 'deploy-briefing'
    this.campaignMenuIndex = 0
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = nowMs + DEPLOY_BRIEFING_MS
    this.campaignRewardReviewEndsAtMs = 0
    this.campaignUnlockRevealEndsAtMs = 0
    this.lastActionNote = `deploy briefing ready for ${this.storyboardLabel(this.campaignSelectedNodeIndex)}`
    this.emitAudioCue('ui', 'deploy-briefing', 0.24)
  }

  private enterTitle(nowMs: number): void {
    this.lastUpdateNowMs = nowMs
    this.campaignScenePhase = 'title'
    this.campaignMenuIndex = 0
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = 0
    this.campaignRewardReviewEndsAtMs = 0
    this.campaignUnlockRevealEndsAtMs = 0
    this.battlePaused = false
    this.pauseStartedAtMs = 0
    this.lastActionNote = 'title screen ready'
    this.emitAudioCue('ui', 'title-ready', 0.18)
  }

  private enterMainMenu(nowMs: number): void {
    this.lastUpdateNowMs = nowMs
    this.campaignScenePhase = 'main-menu'
    this.campaignMenuIndex = 0
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = 0
    this.campaignRewardReviewEndsAtMs = 0
    this.campaignUnlockRevealEndsAtMs = 0
    this.battlePaused = false
    this.pauseStartedAtMs = 0
    this.lastActionNote = 'campaign menu ready'
    this.emitAudioCue('ui', 'main-menu', 0.2)
  }

  private enterRewardReview(nowMs: number): void {
    this.lastUpdateNowMs = nowMs
    this.campaignScenePhase = 'reward-review'
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = 0
    this.campaignRewardReviewEndsAtMs = nowMs + REWARD_REVIEW_MS
    this.campaignUnlockRevealEndsAtMs = 0
    this.battlePaused = false
    this.pauseStartedAtMs = 0
    this.lastActionNote = 'reward review opened'
    this.emitAudioCue('result', 'reward-review', 0.3)
  }

  private enterUnlockReveal(nowMs: number): void {
    this.lastUpdateNowMs = nowMs
    this.campaignScenePhase = 'unlock-reveal'
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = 0
    this.campaignRewardReviewEndsAtMs = 0
    this.campaignUnlockRevealEndsAtMs = nowMs + UNLOCK_REVEAL_MS
    this.battlePaused = false
    this.pauseStartedAtMs = 0
    this.lastActionNote = this.currentUnlockRevealLabel() ?? 'unlock reveal opened'
    this.emitAudioCue('result', 'unlock-reveal', 0.34)
  }

  private currentUnlockRevealLabel(): string | null {
    if (this.battleResolutionOutcome !== 'victory' || this.campaignLastUnlockedNodeIndex === null) {
      return null
    }
    const unlockedStoryboard = this.storyboards[this.campaignLastUnlockedNodeIndex] ?? null
    if (!unlockedStoryboard) {
      return null
    }
    const label = unlockedStoryboard.stageBlueprint?.title ?? unlockedStoryboard.scriptPath
    const route = unlockedStoryboard.stageBlueprint?.mapBinding?.storyBranch ?? 'route-unknown'
    return `Node ${this.campaignLastUnlockedNodeIndex + 1} unlocked · ${label} · ${route}`
  }

  private campaignMenuEntries(): RecoveryCampaignMenuEntry[] {
    const currentStoryboard = this.storyboards[this.storyboardIndex] ?? this.storyboards[0]
    const recommendation = currentStoryboard ? this.deriveCampaignRecommendation(currentStoryboard) : null
    return [
      {
        label: 'Continue Campaign',
        description: recommendation
          ? `Resume the route from node ${recommendation.nodeIndex + 1} with ${recommendation.loadoutLabel ?? 'the recommended loadout'}.`
          : 'Resume the recovered campaign route from the current worldmap position.',
        action: 'continue-campaign',
      },
      {
        label: 'Deploy Next Stage',
        description: 'Skip to deploy briefing for the recommended node and loadout.',
        action: 'direct-deploy',
      },
      {
        label: 'Replay Active Stage',
        description: `Return to ${this.storyboardLabel(this.storyboardIndex)} and redeploy the current stage.`,
        action: 'replay-active-stage',
      },
    ]
  }

  private launchCampaignNodeNow(index: number, nowMs: number): void {
    this.activateStoryboard(index, nowMs, Math.round(STORYBOARD_GAP_MS / 5))
    const storyboard = this.storyboards[index]
    const loadout = storyboard ? this.resolveSelectedDeployLoadout(storyboard) : null
    if (loadout) {
      this.applyDeployLoadout(loadout)
      this.lastActionNote = `campaign node launched: ${this.storyboardLabel(index)} with ${loadout.label}`
      return
    }
    this.activeDeployLoadout = null
    this.lastActionNote = `campaign node launched: ${this.storyboardLabel(index)}`
  }

  private storyboardLabel(index: number): string {
    const storyboard = this.storyboards[index]
    return storyboard?.stageBlueprint?.title ?? storyboard?.scriptPath ?? `node ${index + 1}`
  }

  private buildCampaignState(currentStoryboard: RecoveryStageStoryboard): RecoveryStageSnapshot['campaignState'] {
    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    const recommendation = this.deriveCampaignRecommendation(currentStoryboard)
    const routeGoal = this.deriveCampaignRouteGoal(currentStoryboard)
    const selectedNodeIndex = clamp(this.campaignSelectedNodeIndex, 0, unlockedCount - 1)
    const selectedStoryboard = this.storyboards[selectedNodeIndex] ?? currentStoryboard
    const phaseStoryboard =
      this.campaignScenePhase === 'result-hold'
      || this.campaignScenePhase === 'reward-review'
      || this.campaignScenePhase === 'unlock-reveal'
        ? currentStoryboard
        : selectedStoryboard
    const loadouts = this.buildDeployLoadouts(selectedStoryboard)
    const selectedLoadoutIndex = clamp(this.campaignSelectedLoadoutIndex, 0, Math.max(loadouts.length - 1, 0))
    const selectedLoadout = loadouts[selectedLoadoutIndex] ?? loadouts[0]
    const selectedBriefing = this.buildCampaignBriefing(selectedStoryboard)
    const activeStageTitle = currentStoryboard.stageBlueprint?.title ?? currentStoryboard.scriptPath
    const nextUnlockStoryboard = this.campaignUnlockedStageCount < this.storyboards.length
      ? this.storyboards[this.campaignUnlockedStageCount] ?? null
      : null
    const nextUnlock = nextUnlockStoryboard?.stageBlueprint?.title
      ?? nextUnlockStoryboard?.scriptPath
      ?? null
    const recommendedNodeIndex = clamp(recommendation.nodeIndex, 0, unlockedCount - 1)
    const menuEntries = this.campaignMenuEntries()
    const rewardPreview = [
      phaseStoryboard.stageBlueprint?.rewardText ?? 'Recovered quest payout ready for review.',
      selectedLoadout?.label ? `Loadout: ${selectedLoadout.label}` : null,
      this.battleResolutionReason ? `Resolution: ${this.battleResolutionReason}` : null,
      this.questRewardClaims > 0 ? `Claims: ${this.questRewardClaims}` : null,
    ].filter((value): value is string => value !== null)
    const unlockRevealLabel = this.currentUnlockRevealLabel()
    const selectionMode =
      this.campaignScenePhase === 'title'
        ? 'title-attract'
        : this.campaignScenePhase === 'main-menu'
          ? 'main-menu-selection'
          : this.campaignScenePhase === 'result-hold'
            ? 'result-route-selection'
            : this.campaignScenePhase === 'reward-review'
              ? 'reward-review'
              : this.campaignScenePhase === 'unlock-reveal'
                ? 'unlock-reveal'
                : this.campaignScenePhase === 'worldmap' || this.battlePaused
                  ? 'worldmap-selection'
                  : selectedNodeIndex !== this.storyboardIndex
                    ? 'queued-route-selection'
                    : 'follow-active-stage'
    const autoAdvanceInMs = !this.settingsState.autoAdvanceEnabled
      ? null
      : this.campaignScenePhase === 'result-hold' && this.battleResolutionAutoAdvanceAtMs > 0
        ? Math.max(this.battleResolutionAutoAdvanceAtMs - this.lastUpdateNowMs, 0)
      : this.campaignScenePhase === 'reward-review' && this.campaignRewardReviewEndsAtMs > 0
        ? Math.max(this.campaignRewardReviewEndsAtMs - this.lastUpdateNowMs, 0)
      : this.campaignScenePhase === 'unlock-reveal' && this.campaignUnlockRevealEndsAtMs > 0
        ? Math.max(this.campaignUnlockRevealEndsAtMs - this.lastUpdateNowMs, 0)
      : this.campaignScenePhase === 'worldmap' && this.campaignWorldmapAutoEnterAtMs > 0
        ? Math.max(this.campaignWorldmapAutoEnterAtMs - this.lastUpdateNowMs, 0)
      : this.campaignScenePhase === 'deploy-briefing' && this.campaignDeployBriefingEndsAtMs > 0
        ? Math.max(this.campaignDeployBriefingEndsAtMs - this.lastUpdateNowMs, 0)
      : null
    const phaseTitle =
      this.campaignScenePhase === 'title'
        ? 'Arel Wars 1'
        : this.campaignScenePhase === 'main-menu'
          ? 'Main Menu'
          : this.campaignScenePhase === 'result-hold'
            ? this.battleResolutionOutcome === 'victory' ? 'Stage Clear' : 'Stage Failed'
            : this.campaignScenePhase === 'reward-review'
              ? 'Reward Review'
              : this.campaignScenePhase === 'unlock-reveal'
                ? 'Stage Unlocked'
                : this.campaignScenePhase === 'worldmap'
                  ? 'World Map'
                  : this.campaignScenePhase === 'deploy-briefing'
                    ? 'Deploy Briefing'
                    : selectedStoryboard.stageBlueprint?.title ?? activeStageTitle
    const phaseSubtitle =
      this.campaignScenePhase === 'title'
        ? 'Recovered title attract. Press Enter to open the campaign menu.'
        : this.campaignScenePhase === 'main-menu'
          ? `${unlockedCount} nodes unlocked, ${this.campaignClearedStoryboardIds.size} cleared. Choose a recovery route.`
          : this.campaignScenePhase === 'result-hold'
            ? this.battleResolutionReason ?? 'Battle resolution locked in.'
            : this.campaignScenePhase === 'reward-review'
              ? phaseStoryboard.stageBlueprint?.rewardText ?? 'Recovered quest payout and stage completion review.'
              : this.campaignScenePhase === 'unlock-reveal'
                ? unlockRevealLabel ?? 'Campaign route updated.'
                : this.campaignScenePhase === 'worldmap'
                  ? selectedStoryboard.stageBlueprint?.hintText ?? 'Review unlocked nodes and branch routes.'
                  : this.campaignScenePhase === 'deploy-briefing'
                    ? `${selectedLoadout?.heroRosterLabel ?? 'Core Squad'} / ${selectedLoadout?.skillPresetLabel ?? 'Balanced Kit'} / ${selectedLoadout?.towerPolicyLabel ?? 'Balanced Towers'}`
                    : `${selectedBriefing.objectiveLabel} / ${selectedBriefing.tacticalBias}`
    return {
      currentNodeIndex: this.storyboardIndex + 1,
      selectedNodeIndex: selectedNodeIndex + 1,
      recommendedNodeIndex: recommendedNodeIndex + 1,
      selectedLoadoutIndex: selectedLoadoutIndex + 1,
      unlockedNodeCount: unlockedCount,
      clearedStageCount: this.campaignClearedStoryboardIds.size,
      totalNodeCount: this.storyboards.length,
      activeStageTitle,
      activeFamilyId: currentStoryboard.scriptFamilyId,
      routeLabel: currentStoryboard.stageBlueprint?.mapBinding?.storyBranch ?? 'route-unknown',
      scenePhase: this.campaignScenePhase,
      selectionMode,
      selectionLaunchable: this.battlePaused || this.campaignScenePhase !== 'battle',
      autoAdvanceInMs,
      phaseTitle,
      phaseSubtitle,
      menuItems:
        this.campaignScenePhase === 'title'
          ? [{ menuIndex: 1, label: 'Press Enter', description: 'Open the recovered campaign menu.', selected: true }]
          : this.campaignScenePhase === 'main-menu'
            ? menuEntries.map((entry, index) => ({
              menuIndex: index + 1,
              label: entry.label,
              description: entry.description,
              selected: index === this.campaignMenuIndex,
            }))
            : [],
      rewardPreview,
      unlockRevealLabel,
      nextUnlockLabel: nextUnlock,
      nextUnlockRouteLabel: nextUnlockStoryboard?.stageBlueprint?.mapBinding?.storyBranch ?? null,
      lastResolvedStageTitle: this.campaignLastResolvedStageTitle,
      lastOutcome: this.campaignLastOutcome,
      selectedStageTitle: selectedStoryboard.stageBlueprint?.title ?? selectedStoryboard.scriptPath,
      selectedRouteLabel: selectedStoryboard.stageBlueprint?.mapBinding?.storyBranch ?? 'route-unknown',
      selectedHintText: selectedStoryboard.stageBlueprint?.hintText ?? null,
      selectedRewardText: selectedStoryboard.stageBlueprint?.rewardText ?? null,
      selectedLoadoutLabel: selectedLoadout?.label ?? 'Balanced Vanguard',
      activeLoadoutLabel: this.activeDeployLoadout?.label ?? null,
      preferredRouteLabel: this.campaignPreferredRouteLabel,
      routeCommitment: this.campaignRouteCommitment,
      recommendedRouteLabel: recommendation.routeLabel,
      recommendedLoadoutLabel: recommendation.loadoutLabel,
      recommendedReason: recommendation.reason,
      routeGoalNodeIndex: routeGoal.nodeIndex === null ? null : routeGoal.nodeIndex + 1,
      routeGoalLabel: routeGoal.label,
      routeGoalRouteLabel: routeGoal.routeLabel,
      routeGoalReason: routeGoal.reason,
      briefing: selectedBriefing,
      loadouts,
      nodes: this.storyboards.map((storyboard, index) => ({
        nodeIndex: index + 1,
        label: storyboard.stageBlueprint?.title ?? storyboard.scriptPath.replace('assets/', ''),
        familyId: storyboard.scriptFamilyId,
        routeLabel: storyboard.stageBlueprint?.mapBinding?.storyBranch ?? 'route-unknown',
        preferredRoute:
          this.campaignPreferredRouteLabel !== null
          && (storyboard.stageBlueprint?.mapBinding?.storyBranch ?? 'route-unknown') === this.campaignPreferredRouteLabel,
        unlocked: index < unlockedCount,
        cleared: this.campaignClearedStoryboardIds.has(storyboard.id),
        active: index === this.storyboardIndex,
        selected: index === selectedNodeIndex,
        recommended: index === recommendedNodeIndex && index < unlockedCount,
      })),
    }
  }

  private currentFrame(entry: RecoveryPreviewStem): RecoveryPreviewFrame | null {
    if (entry.eventFrames.length === 0) {
      return null
    }
    return entry.eventFrames[Math.min(this.frameIndex, entry.eventFrames.length - 1)] ?? null
  }

  private stepFrame(): void {
    const entry = this.storyboards[this.storyboardIndex].previewStem
    if (entry.eventFrames.length <= 1) {
      this.frameIndex = 0
      return
    }

    const loopStart = entry.loopSummary?.startEventIndex ?? 0
    const loopEnd = Math.min(entry.loopSummary?.endEventIndex ?? entry.eventFrames.length - 1, entry.eventFrames.length - 1)
    if (this.frameIndex >= loopEnd) {
      this.frameIndex = loopStart
      return
    }

    this.frameIndex += 1
  }

  private resolveTutorialCue(
    storyboard: RecoveryStageStoryboard,
    event: RecoveryDialogueEvent | null,
  ): RecoveryTutorialChainCue | null {
    const prefixHex = event?.prefixHex
    if (!prefixHex || !storyboard.stageBlueprint?.tutorialChainCues?.length) {
      return null
    }

    const matches = storyboard.stageBlueprint.tutorialChainCues.filter((cue) => prefixHex.includes(cue.prefixNeedle))
    if (matches.length === 0) {
      return null
    }
    matches.sort((left, right) => right.prefixNeedle.length - left.prefixNeedle.length)
    return matches[0] ?? null
  }

  private resolveSceneCommands(event: RecoveryDialogueEvent | null): RecoveryResolvedOpcodeCue[] {
    const commands = event?.prefixCommands ?? []
    if (commands.length === 0) {
      return []
    }

    return commands.map((command) => {
      if (command.mnemonic === 'set-left-portrait') {
        return {
          mnemonic: command.mnemonic,
          label: 'left-portrait-assign',
          action: 'assign-left-portrait',
          category: 'presentation',
          confidence: 'high',
          commandId: 'assign-left-portrait',
          commandType: 'portrait',
          target: 'left-portrait',
          args: [...command.args],
          source: 'mnemonic',
        } satisfies RecoveryResolvedOpcodeCue
      }
      if (command.mnemonic === 'set-right-portrait') {
        return {
          mnemonic: command.mnemonic,
          label: 'right-portrait-assign',
          action: 'assign-right-portrait',
          category: 'presentation',
          confidence: 'high',
          commandId: 'assign-right-portrait',
          commandType: 'portrait',
          target: 'right-portrait',
          args: [...command.args],
          source: 'mnemonic',
        } satisfies RecoveryResolvedOpcodeCue
      }
      if (command.mnemonic === 'set-expression') {
        return {
          mnemonic: command.mnemonic,
          label: 'portrait-expression-set',
          action: 'set-portrait-expression',
          category: 'presentation',
          confidence: 'high',
          commandId: 'set-portrait-expression',
          commandType: 'expression',
          target: 'portrait-expression',
          args: [...command.args],
          source: 'mnemonic',
        } satisfies RecoveryResolvedOpcodeCue
      }

      const heuristic = this.opcodeHeuristicsByMnemonic.get(command.mnemonic)
      if (!heuristic) {
        return {
          mnemonic: command.mnemonic,
          label: command.mnemonic,
          action: `apply-scene-transition-preset-${command.mnemonic.replace('cmd-', '').toLowerCase()}`,
          category: 'scene-transition',
          confidence: 'low',
          commandId: `scene-transition-preset-${command.mnemonic.replace('cmd-', '').toLowerCase()}`,
          commandType: 'scene-transition',
          target: 'scene-transition',
          args: [...command.args],
          source: 'mnemonic',
        } satisfies RecoveryResolvedOpcodeCue
      }
      const variantKey = `${command.mnemonic}:${command.args.length > 0 ? command.args.map((value) => value.toString(16).padStart(2, '0')).join(',') : '-'}`
      const variantHint = heuristic.variantHints?.find((hint) => hint.variant === variantKey)
      if (variantHint) {
        return {
          mnemonic: command.mnemonic,
          label: variantHint.label,
          action: variantHint.action,
          category: heuristic.category,
          confidence: variantHint.confidence,
          commandId: variantHint.commandId,
          commandType: variantHint.commandType,
          target: variantHint.target,
          args: [...command.args],
          source: 'variant',
          variant: variantKey,
        } satisfies RecoveryResolvedOpcodeCue
      }
      return {
        mnemonic: command.mnemonic,
        label: heuristic.label,
        action: heuristic.action,
        category: heuristic.category,
        confidence: heuristic.confidence,
        commandId: heuristic.commandId,
        commandType: heuristic.commandType,
        target: heuristic.target,
        args: [...command.args],
        source: 'mnemonic',
      } satisfies RecoveryResolvedOpcodeCue
    })
  }

  private resolvePrimarySceneCommand(commands: RecoveryResolvedOpcodeCue[]): RecoveryResolvedOpcodeCue | null {
    const ranked = commands
      .map((command, commandIndex) => {
        let priority = 0
        if (command.source === 'variant' && !GENERIC_OPCODE_VARIANTS.has(command.variant ?? '')) {
          priority += 12
        } else if (command.source === 'variant') {
          priority += 8
        } else {
          priority += 4
        }
        if (command.commandType === 'ui-focus') {
          priority += 6
        } else if (command.commandType === 'emphasis') {
          priority += 5
        } else if (command.commandType === 'presentation') {
          priority += 4
        } else if (command.commandType === 'scene-layout') {
          priority += 3
        } else if (command.commandType === 'scene-transition') {
          priority += 2
        }
        if (command.commandType === 'portrait' || command.commandType === 'expression') {
          priority -= 20
        }
        return { command, commandIndex, priority }
      })
      .sort((left, right) => right.priority - left.priority || right.commandIndex - left.commandIndex)

    return ranked[0]?.command ?? null
  }

  private buildSceneCommandSignals(commands: RecoveryResolvedOpcodeCue[]): ResolvedSceneCommandSignals {
    const signals: ResolvedSceneCommandSignals = {
      hasFocus: false,
      hasPresentation: false,
      hasEmphasis: false,
      hasSceneLayout: false,
      hasSceneTransition: false,
      hasBattleHudFocus: false,
      hasTowerFocus: false,
      hasManaFocus: false,
      hasPopulationFocus: false,
      hasSkillFocus: false,
      hasItemFocus: false,
      hasSystemFocus: false,
      hasQuestFocus: false,
      hasGuidedFocus: false,
      hasPortraitAssignment: false,
    }

    commands.forEach((command) => {
      if (command.commandType === 'portrait' || command.commandType === 'expression') {
        signals.hasPortraitAssignment = true
        return
      }
      if (command.commandType === 'presentation') {
        signals.hasPresentation = true
      }
      if (command.commandType === 'emphasis') {
        signals.hasEmphasis = true
      }
      if (command.commandType === 'scene-layout') {
        signals.hasSceneLayout = true
      }
      if (command.commandType === 'scene-transition') {
        signals.hasSceneTransition = true
      }
      if (command.commandType === 'ui-focus' || command.commandType === 'tutorial-mode') {
        signals.hasFocus = true
      }

      if (command.target === 'battle-hud') {
        signals.hasBattleHudFocus = true
        signals.hasGuidedFocus = true
      }
      if (command.target === 'tower-panel') {
        signals.hasTowerFocus = true
      }
      if (command.target === 'mana-upgrade') {
        signals.hasTowerFocus = true
        signals.hasManaFocus = true
      }
      if (command.target === 'population-upgrade') {
        signals.hasTowerFocus = true
        signals.hasPopulationFocus = true
      }
      if (command.target === 'skill-menu' || command.target === 'skill-window') {
        signals.hasSkillFocus = true
      }
      if (command.target === 'item-menu') {
        signals.hasItemFocus = true
      }
      if (command.target === 'system-menu') {
        signals.hasSystemFocus = true
      }
      if (command.target === 'quest-panel') {
        signals.hasQuestFocus = true
      }
      if (command.target === 'guided-target' || command.target === 'guided-focus' || command.target === 'tutorial-anchor' || command.target === 'tutorial-subject') {
        signals.hasGuidedFocus = true
      }
    })

    return signals
  }

  private buildSceneScript(storyboard: RecoveryStageStoryboard): RecoverySceneScriptStep[] {
    return storyboard.scriptEvents.map((event, dialogueIndex) => this.compileSceneScriptStep(storyboard, dialogueIndex, event))
  }

  private compileSceneScriptStep(
    storyboard: RecoveryStageStoryboard,
    dialogueIndex: number,
    event: RecoveryDialogueEvent,
  ): RecoverySceneScriptStep {
    const tutorialCue = this.resolveTutorialCue(storyboard, event)
    const sceneCommands = this.resolveSceneCommands(event)
    const primaryCommand = this.resolvePrimarySceneCommand(sceneCommands)
    const sceneSignals = this.buildSceneCommandSignals(sceneCommands)
    const directives: RecoverySceneScriptDirective[] = []
    const tags = new Set<string>()
    const sources = new Set<string>()

    const addDirective = (directive: RecoverySceneScriptDirective): void => {
      directives.push(directive)
    }
    const addSource = (value: string | null | undefined): void => {
      if (value) {
        sources.add(value)
      }
    }
    const addTag = (value: string | null | undefined): void => {
      if (value) {
        tags.add(value)
      }
    }

    sceneCommands.forEach((command) => {
      addSource(`scene:${command.commandId}`)
      addTag(command.commandType)
    })

    if (tutorialCue) {
      addSource(`tutorial:${tutorialCue.chainId}`)
      addTag(tutorialCue.chainId)
    }
    if (sceneSignals.hasBattleHudFocus) addTag('battle-hud-focus')
    if (sceneSignals.hasGuidedFocus) addTag('guided-focus')
    if (sceneSignals.hasTowerFocus) addTag('tower-focus')
    if (sceneSignals.hasManaFocus) addTag('mana-focus')
    if (sceneSignals.hasPopulationFocus) addTag('population-focus')
    if (sceneSignals.hasSkillFocus) addTag('skill-focus')
    if (sceneSignals.hasItemFocus) addTag('item-focus')
    if (sceneSignals.hasSystemFocus) addTag('system-focus')
    if (sceneSignals.hasQuestFocus) addTag('quest-focus')
    if (sceneSignals.hasPresentation) addTag('presentation-pulse')
    if (sceneSignals.hasEmphasis) addTag('emphasis-pulse')
    if (sceneSignals.hasSceneLayout) addTag('layout-preset')
    if (sceneSignals.hasSceneTransition) addTag('transition-preset')

    switch (tutorialCue?.chainId) {
      case 'battle-hud-guard-hp':
        addTag('guard-focus')
        addDirective({ kind: 'set-objective', phase: 'lane-control', label: 'hold the tower line', progressDelta: 0.03 })
        addDirective({ kind: 'trigger-wave', side: 'enemy', label: 'tutorial guard line screen', advanceWave: false })
        addDirective({ kind: 'note', note: 'tutorial fixed own-tower objective and triggered enemy screen' })
        break
      case 'battle-hud-goal-hp':
        addTag('siege-focus')
        addDirective({ kind: 'set-objective', phase: 'siege', label: 'break the enemy tower', progressDelta: 0.05 })
        addDirective({ kind: 'trigger-wave', side: 'enemy', label: 'tutorial revealed siege wave', advanceWave: true })
        addDirective({ kind: 'note', note: 'tutorial fixed siege objective and advanced siege wave' })
        break
      case 'battle-hud-dispatch-arrows':
        addTag('dispatch-focus')
        addDirective({ kind: 'set-objective', phase: 'lane-control', label: 'establish favored lane control', progressDelta: 0.04 })
        addDirective({ kind: 'trigger-wave', side: 'allied', label: 'tutorial triggered favored dispatch wave', advanceWave: false })
        addDirective({ kind: 'set-selected-lane' })
        addDirective({ kind: 'ensure-queue', queueCount: 1 })
        addDirective({ kind: 'commit-dispatch' })
        addDirective({ kind: 'note', note: 'tutorial scripted favored-lane push' })
        break
      case 'battle-hud-unit-card':
        addTag('unit-production')
        addDirective({ kind: 'set-objective', phase: 'lane-control', label: 'build a dispatch reserve', progressDelta: 0.03 })
        addDirective({ kind: 'trigger-wave', side: 'allied', label: 'tutorial primed reserve wave', advanceWave: false })
        addDirective({ kind: 'invoke-action', actionId: 'produce-unit', note: 'tutorial queued unit production' })
        break
      case 'battle-hud-mana-bar':
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'restore mana tempo', progressDelta: 0.02 })
        addDirective({ kind: 'restore-mana', side: 'allied', manaScale: 0.08 })
        addDirective({ kind: 'note', note: 'tutorial restored mana context' })
        break
      case 'battle-hud-hero-sortie':
        addTag('hero-sortie')
        addDirective({ kind: 'set-objective', phase: 'hero-pressure', label: 'deploy the hero strike lane', progressDelta: 0.05 })
        addDirective({ kind: 'trigger-wave', side: 'allied', label: 'tutorial opened hero pressure wave', advanceWave: true })
        addDirective({ kind: 'invoke-action', actionId: 'deploy-hero', note: 'tutorial auto-deployed hero to favored lane' })
        break
      case 'battle-hud-hero-return':
        addTag('hero-return')
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'regroup hero at tower', progressDelta: 0.03 })
        addDirective({ kind: 'invoke-action', actionId: 'return-to-tower', note: 'tutorial recalled hero to tower' })
        break
      case 'tower-menu-highlight':
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'open tower management', progressDelta: 0.02 })
        addDirective({ kind: 'set-panel', panel: 'tower' })
        addDirective({ kind: 'note', note: 'tutorial focused tower panel' })
        break
      case 'mana-upgrade-highlight':
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'advance mana economy', progressDelta: 0.03 })
        addDirective({ kind: 'set-panel', panel: 'tower' })
        addDirective({ kind: 'invoke-action', actionId: 'upgrade-tower-stat', note: 'tutorial advanced mana upgrade' })
        break
      case 'population-upgrade-highlight':
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'raise population ceiling', progressDelta: 0.03 })
        addDirective({ kind: 'set-panel', panel: 'tower' })
        addDirective({ kind: 'invoke-action', actionId: 'upgrade-tower-stat', note: 'tutorial advanced population upgrade' })
        break
      case 'skill-menu-highlight':
        addDirective({ kind: 'set-objective', phase: 'skill-burst', label: 'prepare skill burst window', progressDelta: 0.03 })
        addDirective({ kind: 'set-panel', panel: 'skill' })
        addDirective({ kind: 'note', note: 'tutorial opened skill channel' })
        break
      case 'skill-slot-highlight':
        addDirective({ kind: 'set-objective', phase: 'skill-burst', label: 'fire a burst through the skill window', progressDelta: 0.05 })
        addDirective({ kind: 'trigger-wave', side: 'allied', label: 'tutorial opened skill burst wave', advanceWave: true })
        addDirective({ kind: 'set-panel', panel: 'skill' })
        addDirective({ kind: 'invoke-action', actionId: 'cast-skill', note: 'tutorial fired skill beat' })
        break
      case 'item-menu-highlight':
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'stabilize the line with items', progressDelta: 0.03 })
        addDirective({ kind: 'set-panel', panel: 'item' })
        addDirective({ kind: 'invoke-action', actionId: 'use-item', note: 'tutorial fired item beat' })
        break
      case 'system-menu-highlight':
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'pause and review battle state', progressDelta: 0.01 })
        addDirective({ kind: 'set-panel', panel: 'system' })
        addDirective({ kind: 'note', note: 'tutorial surfaced system panel' })
        break
      case 'quest-panel-highlight':
        addDirective({ kind: 'set-objective', phase: 'quest-resolution', label: 'review quest and bonus objectives', progressDelta: 0.04 })
        addDirective({ kind: 'set-panel', panel: 'system' })
        addDirective({ kind: 'note', note: 'tutorial surfaced quest rewards' })
        break
      default:
        break
    }

    if (directives.length === 0 && primaryCommand) {
      if (sceneSignals.hasTowerFocus || sceneSignals.hasManaFocus || sceneSignals.hasPopulationFocus) {
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'rebalance tower economy', progressDelta: 0.02 })
        addDirective({ kind: 'set-panel', panel: 'tower' })
      } else if (sceneSignals.hasSkillFocus) {
        addDirective({ kind: 'set-objective', phase: 'skill-burst', label: 'open a skill timing window', progressDelta: 0.02 })
        addDirective({ kind: 'set-panel', panel: 'skill' })
      } else if (sceneSignals.hasItemFocus) {
        addDirective({ kind: 'set-objective', phase: 'tower-management', label: 'stabilize with an item route', progressDelta: 0.02 })
        addDirective({ kind: 'set-panel', panel: 'item' })
      } else if (sceneSignals.hasSystemFocus || sceneSignals.hasQuestFocus) {
        addDirective({ kind: 'set-objective', phase: 'quest-resolution', label: 'review auxiliary objectives', progressDelta: 0.02 })
        addDirective({ kind: 'set-panel', panel: 'system' })
      } else if (sceneSignals.hasSceneLayout || sceneSignals.hasSceneTransition) {
        addDirective({ kind: 'set-objective', phase: 'opening', label: 'advance dialogue scene layout', progressDelta: 0.01 })
      }

      if (sceneSignals.hasPresentation || sceneSignals.hasEmphasis) {
        addDirective({ kind: 'set-objective', phase: 'hero-pressure', label: 'capitalize on the pressure swing', progressDelta: 0.03 })
        addDirective({ kind: 'trigger-wave', side: 'enemy', label: `scene command surged ${primaryCommand.commandId}`, advanceWave: false })
        addDirective({ kind: 'spawn-unit', side: 'allied', role: 'push', label: `opcode:${primaryCommand.mnemonic}`, powerScale: 1.08 })
        addDirective({ kind: 'shift-lane', side: 'allied', shiftDelta: 0.02 })
        addDirective({ kind: 'note', note: `scene pulse ${primaryCommand.commandId}` })
      } else if (sceneSignals.hasFocus) {
        addDirective({ kind: 'note', note: `scene focus ${primaryCommand.commandId}` })
      } else if (sceneSignals.hasSceneLayout || sceneSignals.hasSceneTransition) {
        addDirective({ kind: 'note', note: `scene layout ${primaryCommand.commandId}` })
      }
    }

    return {
      dialogueIndex,
      stepId: `${storyboard.id}:dialogue:${dialogueIndex}`,
      label: tutorialCue?.label ?? primaryCommand?.label ?? `dialogue-step-${dialogueIndex + 1}`,
      sources: [...sources],
      tags: [...tags],
      directives,
    }
  }

  private executeSceneScriptStep(
    step: RecoverySceneScriptStep | null,
    favoredLane: 'upper' | 'lower',
  ): boolean {
    if (!step || step.directives.length === 0) {
      return false
    }

    let handled = false
    step.directives.forEach((directive) => {
      switch (directive.kind) {
        case 'set-objective':
          this.setObjectiveState(directive.phase ?? 'opening', directive.label ?? 'advance scene', directive.progressDelta ?? 0)
          handled = true
          break
        case 'set-panel':
          this.panelOverride = directive.panel ?? null
          handled = true
          break
        case 'trigger-wave':
          this.triggerSceneWave(directive.side ?? 'enemy', directive.label ?? step.label, directive.advanceWave ?? false)
          handled = true
          break
        case 'set-selected-lane':
          this.selectedDispatchLane = directive.laneId ?? favoredLane
          handled = true
          break
        case 'ensure-queue':
          this.queuedUnitCount = Math.max(this.queuedUnitCount, directive.queueCount ?? 1)
          handled = true
          break
        case 'commit-dispatch': {
          const dispatchLane = directive.laneId ?? this.selectedDispatchLane ?? favoredLane
          this.selectedDispatchLane = dispatchLane
          const previousActionNote = this.lastActionNote
          this.commitLaneDispatch(dispatchLane)
          this.lastActionNote = previousActionNote
          handled = true
          break
        }
        case 'invoke-action':
          if (directive.actionId) {
            this.applyScriptedAction(directive.actionId, directive.note ?? step.label)
            handled = true
          }
          break
        case 'restore-mana': {
          const side = directive.side ?? 'allied'
          const capacity = side === 'allied' ? this.manaCapacityValue : this.enemyManaCapacityValue
          this.restoreMana(side, capacity * (directive.manaScale ?? 0.08))
          handled = true
          break
        }
        case 'spawn-unit':
          this.spawnBattleUnit(
            directive.side ?? 'allied',
            directive.laneId ?? favoredLane,
            directive.role ?? 'push',
            directive.label ?? step.stepId,
            { powerScale: directive.powerScale ?? 1 },
          )
          handled = true
          break
        case 'shift-lane':
          if (directive.side) {
            this.shiftLaneUnits(directive.laneId ?? favoredLane, directive.side, directive.shiftDelta ?? 0.02)
            handled = true
          }
          break
        case 'note':
          if (directive.note) {
            this.lastScriptedBeatNote = directive.note
            handled = true
          }
          break
        default:
          break
      }
    })

    return handled
  }

  private applyDialogueBeat(
    storyboard: RecoveryStageStoryboard,
    event: RecoveryDialogueEvent | null,
  ): void {
    this.lastScriptedBeatNote = null
    if (!event) {
      return
    }
    const favoredLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
    const step = storyboard.sceneScriptSteps[Math.min(this.dialogueIndex, Math.max(storyboard.sceneScriptSteps.length - 1, 0))] ?? null
    const executedBaseStep = this.executeSceneScriptStep(step, favoredLane)
    const executedLoadoutStep = this.applyLoadoutCuePattern(step, favoredLane)
    if (executedBaseStep || executedLoadoutStep) {
      return
    }
  }

  private setObjectiveState(
    phase: RecoveryBattleObjectiveState['phase'],
    label: string,
    progressDelta: number = 0,
  ): void {
    this.currentObjectivePhase = phase
    this.currentObjectiveLabel = label
    if (progressDelta !== 0) {
      this.objectiveProgressRatio = clamp(
        this.objectiveProgressRatio + this.resolveObjectiveProgressDelta(phase, progressDelta),
        0.02,
        1,
      )
    }
  }

  private resolveObjectiveProgressDelta(
    phase: RecoveryBattleObjectiveState['phase'],
    progressDelta: number,
  ): number {
    if (progressDelta === 0) {
      return 0
    }

    const storyboard = this.storyboards[this.storyboardIndex] ?? null
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)
    let multiplier = 1

    if (routeInfluence.matchesPreferred) {
      if (phase === 'siege' && routeBias.directRoute) {
        multiplier += 0.38 * routeInfluence.commitmentFactor
      } else if (phase === 'hero-pressure' && routeBias.flankingRoute) {
        multiplier += 0.34 * routeInfluence.commitmentFactor
      } else if ((phase === 'lane-control' || phase === 'tower-management' || phase === 'quest-resolution') && routeBias.sustainRoute) {
        multiplier += 0.28 * routeInfluence.commitmentFactor
      } else if ((phase === 'skill-burst' || phase === 'tower-management') && routeBias.manaRoute) {
        multiplier += 0.26 * routeInfluence.commitmentFactor
      } else {
        multiplier += 0.12 * routeInfluence.commitmentFactor
      }
    } else if (routeInfluence.preferredRouteLabel !== null) {
      multiplier -= 0.14 * routeInfluence.commitmentFactor
    }

    return progressDelta * clamp(multiplier, 0.72, 1.55)
  }

  private syncCurrentWaveIndex(): void {
    this.currentWaveIndex = clamp(
      Math.max(this.enemyWaveCursor, this.alliedWaveCursor, this.enemyWavesDispatched, this.alliedWavesDispatched),
      1,
      this.totalWaveCount,
    )
  }

  private markWaveDispatched(side: 'enemy' | 'allied', advanceCycle = true): void {
    if (side === 'enemy') {
      this.enemyWavesDispatched = Math.min(Math.max(this.enemyWavesDispatched, this.enemyWaveCursor), this.totalWaveCount)
      if (advanceCycle && this.enemyWaveCursor < this.totalWaveCount) {
        this.enemyWaveCursor += 1
      }
    } else {
      this.alliedWavesDispatched = Math.min(Math.max(this.alliedWavesDispatched, this.alliedWaveCursor), this.totalWaveCount)
      if (advanceCycle && this.alliedWaveCursor < this.totalWaveCount) {
        this.alliedWaveCursor += 1
      }
    }
    this.syncCurrentWaveIndex()
  }

  private currentWaveDirective(plan: RecoveryBattleWaveDirective[], side: 'enemy' | 'allied'): RecoveryBattleWaveDirective | null {
    if (plan.length === 0) {
      return null
    }
    const cursor = side === 'enemy' ? this.enemyWaveCursor : this.alliedWaveCursor
    return plan[Math.min(Math.max(cursor - 1, 0), plan.length - 1)] ?? null
  }

  private adaptDirectiveForActiveLoadout(
    side: 'enemy' | 'allied',
    directive: RecoveryBattleWaveDirective | null,
    source: 'preview' | 'scene' | 'tick',
  ): RecoveryBattleWaveDirective | null {
    if (!directive || !this.activeDeployLoadout) {
      return directive
    }

    const activeLoadout = this.activeDeployLoadout
    const favoredLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
    const defaultLane = activeLoadout.dispatchLane ?? activeLoadout.heroLane ?? favoredLane
    const alternateLane = defaultLane === 'upper' ? 'lower' : 'upper'
    let laneId = directive.laneId
    let role = directive.role
    let unitBurst = directive.unitBurst
    let pressureBias = directive.pressureBias
    const labelParts: string[] = []

    if (side === 'allied') {
      switch (activeLoadout.heroRosterRole) {
        case 'vanguard':
          laneId = defaultLane
          if (role === 'screen' || role === 'support') {
            role = 'push'
          }
          if (role === 'push' || role === 'siege') {
            unitBurst += 1
          }
          pressureBias += 0.03
          labelParts.push('vanguard')
          break
        case 'raider':
          laneId = activeLoadout.heroLane ?? defaultLane
          if (role === 'push' && (source !== 'preview' || this.currentObjectivePhase === 'siege' || this.currentObjectivePhase === 'hero-pressure')) {
            role = 'skill-window'
          }
          if (source !== 'preview') {
            unitBurst += 1
          }
          pressureBias += 0.04
          labelParts.push('raider')
          break
        case 'defender':
          if (role === 'push') {
            role = source === 'scene' ? 'tower-rally' : 'support'
          }
          laneId = favoredLane
          pressureBias += 0.04
          labelParts.push('defense')
          break
        case 'support':
          if (role === 'push' || role === 'screen') {
            role = 'support'
          }
          laneId = activeLoadout.heroLane ?? alternateLane
          pressureBias += 0.035
          labelParts.push('support')
          break
        default:
          break
      }

      switch (activeLoadout.skillPresetKind) {
        case 'orders':
          laneId = activeLoadout.dispatchLane ?? defaultLane
          if (role === 'screen' || role === 'support') {
            role = 'push'
          }
          if (role === 'push' || role === 'tower-rally') {
            unitBurst += 1
          }
          pressureBias += 0.03
          labelParts.push('orders')
          break
        case 'burst':
          if (role === 'push' && (source !== 'preview' || this.currentObjectivePhase === 'skill-burst' || this.currentObjectivePhase === 'siege')) {
            role = 'skill-window'
          }
          if (role === 'skill-window' || source === 'scene') {
            unitBurst += 1
          }
          pressureBias += 0.04
          labelParts.push('burst')
          break
        case 'support':
          if (role === 'push') {
            role = this.currentObjectivePhase === 'hero-pressure' ? 'tower-rally' : 'support'
          }
          pressureBias += 0.025
          labelParts.push('support-kit')
          break
        case 'utility':
          if (role === 'siege' && source !== 'preview') {
            role = 'tower-rally'
          }
          pressureBias += 0.02
          labelParts.push('utility')
          break
        default:
          break
      }

      switch (activeLoadout.towerPolicyKind) {
        case 'population-first':
          if (role === 'push' || role === 'screen') {
            unitBurst += 1
          }
          labelParts.push('population')
          break
        case 'mana-first':
          if (this.currentObjectivePhase === 'tower-management' && role === 'push') {
            role = 'support'
          }
          pressureBias += 0.02
          labelParts.push('mana')
          break
        case 'attack-first':
          if (role === 'support') {
            role = 'siege'
          }
          laneId = defaultLane
          pressureBias += 0.03
          if (role === 'siege' || source === 'scene') {
            unitBurst += 1
          }
          labelParts.push('attack')
          break
        default:
          break
      }
    } else {
      if (activeLoadout.heroRosterRole === 'defender' || activeLoadout.heroRosterRole === 'support') {
        if ((role === 'siege' || role === 'push') && laneId === favoredLane) {
          unitBurst = Math.max(unitBurst - 1, 1)
          pressureBias -= activeLoadout.heroRosterRole === 'defender' ? 0.03 : 0.02
          labelParts.push(activeLoadout.heroRosterRole === 'defender' ? 'screened' : 'softened')
        }
      }
      if (activeLoadout.heroRosterRole === 'raider' && role === 'hero-bait') {
        laneId = activeLoadout.heroLane ?? defaultLane
        labelParts.push('counter-hero')
      }
      if (activeLoadout.skillPresetKind === 'burst' && source === 'scene' && role === 'screen') {
        role = 'hero-bait'
        pressureBias += 0.02
        labelParts.push('burst-bait')
      }
      if (activeLoadout.towerPolicyKind === 'attack-first' && role === 'screen') {
        role = 'push'
        pressureBias += 0.02
        labelParts.push('counter-push')
      }
      if (activeLoadout.towerPolicyKind === 'mana-first' && role === 'hero-bait') {
        pressureBias -= 0.01
        labelParts.push('delayed')
      }
    }

    return {
      ...directive,
      laneId,
      role,
      unitBurst: clamp(unitBurst, 1, 5),
      pressureBias: clamp(pressureBias, 0.02, 0.4),
      label: labelParts.length > 0 ? `${directive.label} · ${labelParts.join('+')}` : directive.label,
    }
  }

  private currentLoadoutDirective(
    plan: RecoveryBattleWaveDirective[],
    side: 'enemy' | 'allied',
    source: 'preview' | 'scene' | 'tick',
  ): RecoveryBattleWaveDirective | null {
    return this.adaptDirectiveForActiveLoadout(side, this.currentWaveDirective(plan, side), source)
  }

  private adjustSceneDirectiveForRoute(
    side: 'enemy' | 'allied',
    directive: RecoveryBattleWaveDirective | null,
  ): RecoveryBattleWaveDirective | null {
    if (!directive) {
      return null
    }

    const storyboard = this.storyboards[this.storyboardIndex] ?? null
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)
    let laneId = directive.laneId
    let role = directive.role
    let unitBurst = directive.unitBurst
    let pressureBias = directive.pressureBias
    const labelParts: string[] = []

    if (side === 'allied') {
      if (routeInfluence.matchesPreferred && routeBias.directRoute && (role === 'push' || role === 'siege' || role === 'skill-window')) {
        unitBurst += 1
        pressureBias += 0.03 + routeInfluence.pressureDelta * 0.3
        labelParts.push('branch-commit')
      } else if (routeInfluence.matchesPreferred && routeBias.flankingRoute && (role === 'push' || role === 'tower-rally')) {
        laneId = routeInfluence.preferredLane ?? laneId
        unitBurst += 1
        pressureBias += 0.025
        labelParts.push('route-flank')
      } else if (routeInfluence.matchesPreferred && routeBias.sustainRoute && (role === 'support' || role === 'tower-rally')) {
        pressureBias += 0.03 + routeInfluence.defenseDelta * 0.25
        labelParts.push('route-hold')
      } else if (routeInfluence.matchesPreferred && routeBias.manaRoute && (role === 'skill-window' || role === 'support')) {
        pressureBias += 0.028 + routeInfluence.manaDelta * 0.15
        labelParts.push('route-mana')
      } else if (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null) {
        pressureBias -= 0.014 * Math.max(routeInfluence.commitmentFactor, 0.4)
        labelParts.push('branch-drift')
      }
    } else {
      if (routeInfluence.matchesPreferred && routeBias.sustainRoute && (role === 'siege' || role === 'push')) {
        unitBurst = Math.max(unitBurst - 1, 1)
        pressureBias -= 0.03 + routeInfluence.defenseDelta * 0.2
        labelParts.push('screened')
      } else if (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null && (role === 'push' || role === 'siege' || role === 'hero-bait')) {
        unitBurst += 1
        pressureBias += 0.02 + routeInfluence.commitmentFactor * 0.02
        labelParts.push('counter-route')
      }
    }

    return {
      ...directive,
      laneId,
      role,
      unitBurst: clamp(unitBurst, 1, 5),
      pressureBias: clamp(pressureBias, 0.02, 0.42),
      label: labelParts.length > 0 ? `${directive.label} · ${labelParts.join('+')}` : directive.label,
    }
  }

  private resetWaveCountdown(
    side: 'enemy' | 'allied',
    directive: RecoveryBattleWaveDirective | null,
  ): void {
    if (side === 'enemy') {
      this.enemyWaveCountdownBeats = Math.max(
        1,
        this.currentStageBattleProfile.enemyWaveCadenceBeats
        - (directive?.role === 'siege' ? 1 : 0)
        - Math.min(Math.floor(this.currentWaveIndex / 3), 2),
      )
      return
    }
    this.alliedWaveCountdownBeats = Math.max(
      1,
      this.currentStageBattleProfile.alliedWaveCadenceBeats
      - (directive?.role === 'push' ? 1 : 0)
      - (this.heroAssignedLane === directive?.laneId ? 1 : 0),
    )
  }

  private applyWaveDirective(
    side: 'enemy' | 'allied',
    directive: RecoveryBattleWaveDirective | null,
  ): void {
    if (!directive) {
      return
    }

    this.spawnUnitsFromDirective(side, directive, `${side}-wave-${directive.waveNumber}`)
    if (side === 'enemy' && directive.role === 'siege') {
      this.damageTower('allied', 0.018)
      return
    }
    if (side === 'allied' && (directive.role === 'push' || directive.role === 'siege' || directive.role === 'skill-window')) {
      this.selectedDispatchLane = directive.laneId
    }
    if (side === 'allied' && (directive.role === 'tower-rally' || directive.role === 'support')) {
      this.supportLaneUnits(directive.laneId, 'allied', 0.16)
      this.repairTower('allied', 0.012 + this.currentStageBattleProfile.towerDefenseBias * 0.05)
    }
  }

  private applyLoadoutWaveBeat(
    side: 'enemy' | 'allied',
    directive: RecoveryBattleWaveDirective | null,
    source: 'scene' | 'tick',
  ): string | null {
    const activeLoadout = this.activeDeployLoadout
    if (!directive || !activeLoadout) {
      return null
    }

    if (side === 'allied') {
      const queueCapacity = this.battleModel?.resourceRules.queueCapacity ?? 6
      if (activeLoadout.skillPresetKind === 'orders' && (directive.role === 'push' || directive.role === 'siege')) {
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, queueCapacity)
        this.selectedDispatchLane = directive.laneId
      }
      if (activeLoadout.skillPresetKind === 'burst' && directive.role === 'skill-window') {
        this.damageTower('enemy', source === 'scene' ? 0.028 : 0.018)
        this.skillCooldownEndsAtMs = Math.max(this.skillCooldownEndsAtMs - 700, this.lastUpdateNowMs)
      }
      if (activeLoadout.skillPresetKind === 'support' && (directive.role === 'support' || directive.role === 'tower-rally')) {
        this.repairTower('allied', 0.025)
      }
      if (activeLoadout.towerPolicyKind === 'mana-first') {
        this.restoreMana('allied', this.manaCapacityValue * (source === 'scene' ? 0.05 : 0.03))
      } else if (activeLoadout.towerPolicyKind === 'attack-first' && (directive.role === 'push' || directive.role === 'siege')) {
        this.damageTower('enemy', 0.016)
      } else if (activeLoadout.towerPolicyKind === 'population-first') {
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, queueCapacity)
      }

      if (activeLoadout.heroRosterRole === 'support' || activeLoadout.heroRosterRole === 'defender') {
        this.repairTower('allied', 0.015)
      }
      return `${activeLoadout.label} script`
    }

    if ((activeLoadout.heroRosterRole === 'defender' || activeLoadout.heroRosterRole === 'support') && directive.role === 'siege') {
      this.repairTower('allied', 0.01)
    }
    if (activeLoadout.skillPresetKind === 'orders' && directive.role === 'push' && this.selectedDispatchLane) {
      this.spawnBattleUnit('allied', this.selectedDispatchLane, 'push', `${activeLoadout.label} counter-script`, {
        powerScale: 1.06,
      })
    }
    return `${activeLoadout.label} counter-script`
  }

  private loadoutHasMember(
    loadout: RecoveryStageSnapshot['campaignState']['loadouts'][number] | null,
    memberName: string,
  ): boolean {
    if (!loadout) {
      return false
    }
    return loadout.heroRosterMembers.some((member) => member.toLowerCase() === memberName.toLowerCase())
  }

  private deriveStoryboardRouteBias(
    storyboard: RecoveryStageStoryboard | null,
  ): {
    routeLabel: string
    directRoute: boolean
    flankingRoute: boolean
    sustainRoute: boolean
    manaRoute: boolean
    preferredLane: 'upper' | 'lower' | null
    pressureShift: number
    cadenceShift: number
    heroShift: number
  } {
    const stage = storyboard?.stageBlueprint ?? null
    const routeLabel = stage?.mapBinding?.storyBranch ?? 'route-unknown'
    const title = (stage?.title ?? '').toLowerCase()
    const hint = (stage?.hintText ?? '').toLowerCase()
    const reward = (stage?.rewardText ?? '').toLowerCase()
    const joined = `${routeLabel} ${title} ${hint} ${reward}`
    const favoredLane = this.currentStageBattleProfile.favoredLane
    const alternateLane = favoredLane === 'upper' ? 'lower' : 'upper'

    const flankingRoute =
      routeLabel === 'secondary'
      || includesAny(joined, ['secondary', 'flank', 'side', 'alternate', 'detour', 'ambush'])
    const directRoute =
      routeLabel === 'primary'
      || includesAny(joined, ['primary', 'front', 'main', 'direct', 'charge'])
    const sustainRoute = includesAny(joined, ['defend', 'hold', 'guard', 'supply', 'reward', 'bonus'])
    const manaRoute = includesAny(joined, ['mana', 'skill', 'arcane', 'magic'])

    return {
      routeLabel,
      directRoute,
      flankingRoute,
      sustainRoute,
      manaRoute,
      preferredLane:
        favoredLane === null
          ? null
          : flankingRoute
            ? alternateLane
            : favoredLane,
      pressureShift: directRoute ? 0.03 : flankingRoute ? 0.02 : sustainRoute ? -0.01 : 0,
      cadenceShift: flankingRoute ? -1 : sustainRoute ? 1 : 0,
      heroShift: flankingRoute || manaRoute ? 0.03 : directRoute ? 0.02 : 0,
    }
  }

  private deriveCampaignRouteInfluence(
    storyboard: RecoveryStageStoryboard | null,
  ): {
    preferredRouteLabel: string | null
    matchesPreferred: boolean
    commitmentFactor: number
    queueDelta: number
    manaDelta: number
    defenseDelta: number
    pressureDelta: number
    cadenceDelta: number
    heroDelta: number
    preferredLane: 'upper' | 'lower' | null
    stanceLabel: string
  } {
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const preferredRouteLabel = this.campaignPreferredRouteLabel
    const matchesPreferred = preferredRouteLabel !== null && preferredRouteLabel === routeBias.routeLabel
    const commitmentFactor = clamp(this.campaignRouteCommitment / 5, 0, 1)
    const mismatchPenalty = preferredRouteLabel !== null && !matchesPreferred ? commitmentFactor * 0.6 : 0

    const queueDelta =
      (routeBias.flankingRoute ? 2 : routeBias.directRoute ? 1 : 0) * commitmentFactor
      - (routeBias.sustainRoute ? 1 : 0) * mismatchPenalty
    const manaDelta =
      (routeBias.manaRoute ? 0.12 : routeBias.sustainRoute ? 0.05 : 0) * commitmentFactor
      - (routeBias.directRoute ? 0.03 : 0) * mismatchPenalty
    const defenseDelta =
      (routeBias.sustainRoute ? 0.08 : 0) * commitmentFactor
      - (routeBias.directRoute ? 0.03 : routeBias.flankingRoute ? 0.02 : 0) * mismatchPenalty
    const pressureDelta =
      routeBias.pressureShift * (matchesPreferred ? 1 + commitmentFactor * 0.85 : 1 - mismatchPenalty * 0.5)
    const cadenceDelta =
      routeBias.cadenceShift === 0
        ? 0
        : routeBias.cadenceShift > 0
          ? Math.round(routeBias.cadenceShift * (matchesPreferred ? 1 + commitmentFactor : 1 - mismatchPenalty * 0.5))
          : Math.round(routeBias.cadenceShift * (matchesPreferred ? 1 + commitmentFactor : 1 - mismatchPenalty * 0.5))
    const heroDelta =
      routeBias.heroShift * (matchesPreferred ? 1 + commitmentFactor * 0.8 : 1 - mismatchPenalty * 0.45)
    const preferredLane =
      matchesPreferred
        ? routeBias.preferredLane
        : routeBias.preferredLane === null
          ? null
          : routeBias.preferredLane === 'upper'
            ? 'lower'
            : 'upper'
    const stanceLabel =
      matchesPreferred
        ? `branch-hold:${preferredRouteLabel ?? 'route-unknown'}`
        : preferredRouteLabel === null
          ? `branch-open:${routeBias.routeLabel}`
          : `branch-contest:${preferredRouteLabel}->${routeBias.routeLabel}`

    return {
      preferredRouteLabel,
      matchesPreferred,
      commitmentFactor,
      queueDelta,
      manaDelta,
      defenseDelta,
      pressureDelta,
      cadenceDelta,
      heroDelta,
      preferredLane,
      stanceLabel,
    }
  }

  private scoreLoadoutForRoute(
    storyboard: RecoveryStageStoryboard,
    loadout: RecoveryStageSnapshot['campaignState']['loadouts'][number],
  ): number {
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    let score = loadout.recommended ? 0.08 : 0

    if (routeBias.flankingRoute) {
      if (loadout.heroRosterRole === 'vanguard') {
        score += 0.2
      }
      if (loadout.skillPresetKind === 'orders') {
        score += 0.22
      }
      if (loadout.towerPolicyKind === 'population-first') {
        score += 0.16
      }
    }

    if (routeBias.directRoute) {
      if (loadout.heroRosterRole === 'raider' || loadout.heroRosterRole === 'vanguard') {
        score += 0.18
      }
      if (loadout.skillPresetKind === 'burst') {
        score += 0.22
      }
      if (loadout.towerPolicyKind === 'attack-first') {
        score += 0.18
      }
    }

    if (routeBias.sustainRoute) {
      if (loadout.heroRosterRole === 'defender' || loadout.heroRosterRole === 'support') {
        score += 0.22
      }
      if (loadout.skillPresetKind === 'support') {
        score += 0.18
      }
      if (loadout.towerPolicyKind === 'balanced' || loadout.towerPolicyKind === 'mana-first') {
        score += 0.1
      }
    }

    if (routeBias.manaRoute) {
      if (loadout.skillPresetKind === 'utility' || loadout.skillPresetKind === 'burst') {
        score += 0.18
      }
      if (loadout.towerPolicyKind === 'mana-first') {
        score += 0.22
      }
      if (this.loadoutHasMember(loadout, 'Juno')) {
        score += 0.1
      }
    }

    if (this.activeDeployLoadout && this.activeDeployLoadout.id === loadout.id) {
      score += 0.04
    }

    return score
  }

  private updateCampaignRouteCommitment(
    storyboard: RecoveryStageStoryboard | null,
    outcome: 'victory' | 'defeat',
  ): void {
    if (!storyboard) {
      return
    }
    const routeLabel = this.deriveStoryboardRouteBias(storyboard).routeLabel
    if (!routeLabel) {
      return
    }
    if (outcome === 'victory') {
      if (this.campaignPreferredRouteLabel === routeLabel) {
        this.campaignRouteCommitment = clamp(this.campaignRouteCommitment + 1, 1, 5)
      } else {
        this.campaignPreferredRouteLabel = routeLabel
        this.campaignRouteCommitment = Math.max(2, this.campaignRouteCommitment)
      }
      return
    }

    if (this.campaignPreferredRouteLabel === routeLabel) {
      this.campaignRouteCommitment = Math.max(this.campaignRouteCommitment - 1, 0)
      if (this.campaignRouteCommitment === 0) {
        this.campaignPreferredRouteLabel = null
      }
    }
  }

  private deriveRecommendedLoadoutIndexForStoryboard(
    storyboard: RecoveryStageStoryboard,
  ): {
    loadoutIndex: number
    loadoutLabel: string | null
  } {
    const loadouts = this.buildDeployLoadouts(storyboard)
    if (loadouts.length === 0) {
      return { loadoutIndex: 0, loadoutLabel: null }
    }

    let bestIndex = 0
    let bestScore = Number.NEGATIVE_INFINITY
    loadouts.forEach((loadout, index) => {
      const score = this.scoreLoadoutForRoute(storyboard, loadout)
      if (score > bestScore) {
        bestScore = score
        bestIndex = index
      }
    })

    return {
      loadoutIndex: bestIndex,
      loadoutLabel: loadouts[bestIndex]?.label ?? null,
    }
  }

  private deriveCampaignRecommendation(
    currentStoryboard: RecoveryStageStoryboard,
  ): {
    nodeIndex: number
    routeLabel: string | null
    loadoutIndex: number
    loadoutLabel: string | null
    reason: string
  } {
    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    const currentRouteBias = this.deriveStoryboardRouteBias(currentStoryboard)
    const preferredRouteLabel = this.campaignPreferredRouteLabel ?? currentRouteBias.routeLabel
    let bestIndex = clamp(
      this.campaignLastOutcome === 'victory' ? this.storyboardIndex + 1 : this.storyboardIndex,
      0,
      unlockedCount - 1,
    )
    let bestScore = Number.NEGATIVE_INFINITY

    for (let index = 0; index < unlockedCount; index += 1) {
      const candidate = this.storyboards[index]
      if (!candidate) {
        continue
      }
      const candidateRouteBias = this.deriveStoryboardRouteBias(candidate)
      let score = 0
      score += this.campaignLastOutcome === 'victory'
        ? index === Math.min(this.storyboardIndex + 1, unlockedCount - 1) ? 0.36 : 0
        : index === this.storyboardIndex ? 0.28 : 0
      score += Math.max(0, 0.14 - Math.abs(index - this.storyboardIndex) * 0.04)
      if (candidateRouteBias.routeLabel === currentRouteBias.routeLabel) {
        score += 0.12
      }
      if (candidateRouteBias.routeLabel === preferredRouteLabel) {
        score += 0.08 + this.campaignRouteCommitment * 0.04
      } else if (preferredRouteLabel !== null && this.campaignRouteCommitment >= 2) {
        score -= Math.min(this.campaignRouteCommitment * 0.03, 0.12)
      }
      if (candidateRouteBias.flankingRoute && currentRouteBias.flankingRoute) {
        score += 0.14
      }
      if (candidateRouteBias.directRoute && currentRouteBias.directRoute) {
        score += 0.14
      }
      if (candidateRouteBias.sustainRoute && currentRouteBias.sustainRoute) {
        score += 0.12
      }
      if (candidateRouteBias.manaRoute && currentRouteBias.manaRoute) {
        score += 0.1
      }

      if (this.activeDeployLoadout) {
        if (candidateRouteBias.flankingRoute && (this.activeDeployLoadout.skillPresetKind === 'orders' || this.activeDeployLoadout.heroRosterRole === 'vanguard')) {
          score += 0.16
        }
        if (candidateRouteBias.directRoute && (this.activeDeployLoadout.skillPresetKind === 'burst' || this.activeDeployLoadout.heroRosterRole === 'raider')) {
          score += 0.16
        }
        if (candidateRouteBias.sustainRoute && (this.activeDeployLoadout.heroRosterRole === 'defender' || this.activeDeployLoadout.heroRosterRole === 'support')) {
          score += 0.14
        }
        if (candidateRouteBias.manaRoute && (this.activeDeployLoadout.towerPolicyKind === 'mana-first' || this.activeDeployLoadout.skillPresetKind === 'utility')) {
          score += 0.14
        }
      }

      if (preferredRouteLabel !== null && candidateRouteBias.routeLabel === preferredRouteLabel && index >= this.storyboardIndex) {
        score += 0.06
      }

      if (score > bestScore) {
        bestScore = score
        bestIndex = index
      }
    }

    const recommendedStoryboard = this.storyboards[bestIndex] ?? currentStoryboard
    const recommendedRouteBias = this.deriveStoryboardRouteBias(recommendedStoryboard)
    const recommendedLoadout = this.deriveRecommendedLoadoutIndexForStoryboard(recommendedStoryboard)
    const routeReason =
      recommendedRouteBias.flankingRoute
        ? 'route-flank-dispatch'
        : recommendedRouteBias.directRoute
          ? 'route-main-siege'
          : recommendedRouteBias.sustainRoute
            ? 'route-hold-defense'
          : recommendedRouteBias.manaRoute
              ? 'route-mana-cycle'
              : 'route-continuity'
    const commitmentReason =
      preferredRouteLabel !== null && recommendedRouteBias.routeLabel === preferredRouteLabel
        ? `branch-lock-${preferredRouteLabel}`
        : `branch-shift-${recommendedRouteBias.routeLabel ?? 'route-unknown'}`

    return {
      nodeIndex: bestIndex,
      routeLabel: recommendedRouteBias.routeLabel,
      loadoutIndex: recommendedLoadout.loadoutIndex,
      loadoutLabel: recommendedLoadout.loadoutLabel,
      reason: this.campaignRouteCommitment > 1 ? `${commitmentReason}/${routeReason}` : routeReason,
    }
  }

  private deriveCampaignRouteGoal(
    currentStoryboard: RecoveryStageStoryboard,
  ): {
    nodeIndex: number | null
    label: string | null
    routeLabel: string | null
    reason: string | null
  } {
    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    if (unlockedCount >= this.storyboards.length) {
      return {
        nodeIndex: null,
        label: null,
        routeLabel: null,
        reason: null,
      }
    }

    const currentRouteBias = this.deriveStoryboardRouteBias(currentStoryboard)
    const preferredRouteLabel = this.campaignPreferredRouteLabel ?? currentRouteBias.routeLabel
    let bestIndex: number | null = null
    let bestScore = Number.NEGATIVE_INFINITY

    for (let index = unlockedCount; index < this.storyboards.length; index += 1) {
      const candidate = this.storyboards[index]
      if (!candidate) {
        continue
      }
      const candidateRouteBias = this.deriveStoryboardRouteBias(candidate)
      let score = Math.max(0, 0.22 - (index - unlockedCount) * 0.03)
      if (preferredRouteLabel !== null && candidateRouteBias.routeLabel === preferredRouteLabel) {
        score += 0.38 + this.campaignRouteCommitment * 0.04
      }
      if (candidateRouteBias.routeLabel === currentRouteBias.routeLabel) {
        score += 0.16
      }
      if (candidateRouteBias.flankingRoute && currentRouteBias.flankingRoute) {
        score += 0.1
      }
      if (candidateRouteBias.directRoute && currentRouteBias.directRoute) {
        score += 0.1
      }
      if (candidateRouteBias.sustainRoute && currentRouteBias.sustainRoute) {
        score += 0.08
      }
      if (candidateRouteBias.manaRoute && currentRouteBias.manaRoute) {
        score += 0.08
      }

      if (score > bestScore) {
        bestScore = score
        bestIndex = index
      }
    }

    if (bestIndex === null) {
      return {
        nodeIndex: null,
        label: null,
        routeLabel: null,
        reason: null,
      }
    }

    const target = this.storyboards[bestIndex] ?? null
    const targetRouteLabel = target?.stageBlueprint?.mapBinding?.storyBranch ?? null
    const reason = bestIndex === unlockedCount
      ? 'next-unlock-aligned'
      : targetRouteLabel === preferredRouteLabel
        ? 'branch-hold-for-future'
        : 'future-route-fallback'
    return {
      nodeIndex: bestIndex,
      label: target?.stageBlueprint?.title ?? target?.scriptPath ?? null,
      routeLabel: targetRouteLabel,
      reason,
    }
  }

  private deriveCurrentStageScriptBias(): {
    label: string
    siegeBias: boolean
    sustainBias: boolean
    dispatchBias: boolean
    heroBias: boolean
    manaBias: boolean
    rewardBias: boolean
    preferredLane: 'upper' | 'lower' | null
  } {
    const storyboard = this.storyboards[this.storyboardIndex] ?? null
    const stage = storyboard?.stageBlueprint ?? null
    const title = (stage?.title ?? '').toLowerCase()
    const hint = (stage?.hintText ?? '').toLowerCase()
    const reward = (stage?.rewardText ?? '').toLowerCase()
    const familyId = stage?.familyId ?? storyboard?.scriptFamilyId ?? '000'
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const favoredLane = routeBias.preferredLane ?? this.currentStageBattleProfile.favoredLane
    const alternateLane = favoredLane === 'upper' ? 'lower' : 'upper'
    const joined = `${title} ${hint} ${reward}`

    const siegeBias =
      this.currentObjectivePhase === 'siege'
      || routeBias.directRoute
      || includesAny(joined, ['seize', 'siege', 'defeat', 'enemy camp', 'proxy', 'hunt', 'break'])
    const sustainBias =
      this.currentObjectivePhase === 'tower-management'
      || this.currentObjectivePhase === 'lane-control'
      || routeBias.sustainRoute
      || includesAny(joined, ['defend', 'hold', 'protect', 'guard', 'survive', 'wall'])
    const dispatchBias =
      this.currentObjectivePhase === 'lane-control'
      || routeBias.flankingRoute
      || includesAny(joined, ['advance', 'dispatch', 'lane', 'escort', 'forward', 'charge', 'proxies'])
    const heroBias =
      this.currentObjectivePhase === 'hero-pressure'
      || routeBias.flankingRoute
      || includesAny(joined, ['hero', 'champion', 'captain', 'leader', 'boss', 'elite'])
    const manaBias =
      this.currentObjectivePhase === 'skill-burst'
      || routeBias.manaRoute
      || includesAny(joined, ['mana', 'skill', 'arcane', 'magic', 'burst', 'spell'])
    const rewardBias =
      this.currentObjectivePhase === 'quest-resolution'
      || routeBias.sustainRoute
      || includesAny(joined, ['reward', 'bonus', 'quest', 'treasure', 'bounty'])

    const familyNumber = Number.parseInt(familyId, 10)
    const preferredLane =
      favoredLane === null
        ? null
        : Number.isFinite(familyNumber) && familyNumber % 2 === 1
          ? alternateLane
          : favoredLane

    const labels = [
      siegeBias ? 'siege' : null,
      sustainBias ? 'hold' : null,
      dispatchBias ? 'dispatch' : null,
      heroBias ? 'hero' : null,
      manaBias ? 'mana' : null,
      rewardBias ? 'reward' : null,
      routeBias.flankingRoute ? 'route-flank' : routeBias.directRoute ? 'route-main' : null,
    ].filter((value): value is string => value !== null)

    return {
      label: labels.join('/') || 'neutral',
      siegeBias,
      sustainBias,
      dispatchBias,
      heroBias,
      manaBias,
      rewardBias,
      preferredLane,
    }
  }

  private applyLoadoutCuePattern(
    step: RecoverySceneScriptStep | null,
    favoredLane: 'upper' | 'lower',
  ): boolean {
    const activeLoadout = this.activeDeployLoadout
    if (!activeLoadout) {
      return false
    }

    const stepTags = new Set(step?.tags ?? [])
    const hasTag = (value: string): boolean => stepTags.has(value)
    const rosterRole = activeLoadout.heroRosterRole
    const skillPresetKind = activeLoadout.skillPresetKind
    const towerPolicyKind = activeLoadout.towerPolicyKind
    const stageBias = this.deriveCurrentStageScriptBias()
    const hasVincent = this.loadoutHasMember(activeLoadout, 'Vincent')
    const hasRogan = this.loadoutHasMember(activeLoadout, 'Rogan')
    const hasHelba = this.loadoutHasMember(activeLoadout, 'Helba')
    const hasJuno = this.loadoutHasMember(activeLoadout, 'Juno')
    const hasManos = this.loadoutHasMember(activeLoadout, 'Manos')
    const hasCaesar = this.loadoutHasMember(activeLoadout, 'Caesar')
    const preferredLane = stageBias.preferredLane ?? activeLoadout.dispatchLane ?? activeLoadout.heroLane ?? favoredLane
    const routeInfluence = this.deriveCampaignRouteInfluence(this.storyboards[this.storyboardIndex] ?? null)

    if (routeInfluence.matchesPreferred && routeInfluence.commitmentFactor >= 0.4) {
      if (
        routeInfluence.stanceLabel.includes('branch-hold')
        && hasVincent
        && hasManos
        && (
          hasTag('siege-focus')
          || hasTag('skill-focus')
          || stageBias.siegeBias
          || hasTag('emphasis-pulse')
          || hasTag('presentation-pulse')
        )
      ) {
        this.selectedDispatchLane = preferredLane
        this.panelOverride = 'skill'
        this.queuedUnitCount = Math.max(this.queuedUnitCount, 1)
      if (
          this.triggerRosterActionChain(
            ['Vincent', 'Manos'],
            preferredLane,
            ['deploy-hero', 'cast-skill'],
            `committed strike route chained Vincent and Manos (${routeInfluence.stanceLabel})`,
            'assault',
          )
        ) {
          return true
        }
      }

      if (
        routeInfluence.stanceLabel.includes('branch-hold')
        && hasRogan
        && hasVincent
        && (
          hasTag('dispatch-focus')
          || hasTag('unit-production')
          || stageBias.dispatchBias
          || hasTag('guided-focus')
          || hasTag('battle-hud-focus')
        )
      ) {
        this.selectedDispatchLane = preferredLane
        this.queuedUnitCount = Math.max(this.queuedUnitCount, 2)
      if (
          this.triggerRosterActionChain(
            ['Rogan', 'Vincent'],
            preferredLane,
            ['produce-unit', 'deploy-hero'],
            `committed flank route chained Rogan and Vincent (${routeInfluence.stanceLabel})`,
            'flank',
          )
        ) {
          return true
        }
      }

      if (
        routeInfluence.stanceLabel.includes('branch-hold')
        && hasHelba
        && hasCaesar
        && (
          hasTag('guard-focus')
          || hasTag('tower-focus')
          || hasTag('quest-focus')
          || stageBias.sustainBias
          || stageBias.rewardBias
          || hasTag('population-focus')
        )
      ) {
        this.panelOverride = hasTag('quest-focus') ? 'item' : 'tower'
      if (
          this.triggerRosterActionChain(
            ['Helba', 'Caesar'],
            preferredLane,
            ['upgrade-tower-stat', 'use-item'],
            `committed hold route chained Helba and Caesar (${routeInfluence.stanceLabel})`,
            'hold',
          )
        ) {
          return true
        }
      }

      if (
        routeInfluence.stanceLabel.includes('branch-hold')
        && hasJuno
        && (
          hasTag('mana-focus')
          || hasTag('skill-focus')
          || stageBias.manaBias
          || hasTag('system-focus')
          || hasTag('emphasis-pulse')
        )
      ) {
        this.panelOverride = 'skill'
      if (
          this.triggerRosterActionChain(
            ['Juno'],
            preferredLane,
            ['upgrade-tower-stat', 'cast-skill'],
            `committed mana route chained Juno channels (${routeInfluence.stanceLabel})`,
            'mana',
          )
        ) {
          return true
        }
      }
    }

    if (
      hasVincent
      && (
        hasTag('dispatch-focus')
        || hasTag('hero-sortie')
        || hasTag('siege-focus')
        || stageBias.siegeBias
        || stageBias.heroBias
        || hasTag('battle-hud-focus')
        || hasTag('emphasis-pulse')
      )
    ) {
      this.selectedDispatchLane = preferredLane
      this.queuedUnitCount = Math.max(this.queuedUnitCount, stageBias.dispatchBias ? 2 : 1)
      if (this.applyScriptedAction('deploy-hero', `Vincent auto-led the assault lane (${stageBias.label})`)) {
        return true
      }
    }

    if (
      hasRogan
      && (
        hasTag('unit-production')
        || hasTag('dispatch-focus')
        || stageBias.dispatchBias
        || hasTag('guided-focus')
        || hasTag('battle-hud-focus')
      )
    ) {
      this.selectedDispatchLane = preferredLane
      if (this.applyScriptedAction('produce-unit', `Rogan auto-queued reinforcements (${stageBias.label})`)) {
        return true
      }
    }

    if (
      hasHelba
      && (
        hasTag('mana-focus')
        || hasTag('tower-focus')
        || hasTag('item-focus')
        || stageBias.sustainBias
        || stageBias.rewardBias
        || hasTag('quest-focus')
      )
    ) {
      this.panelOverride = hasTag('item-focus') ? 'item' : 'tower'
      if (
        this.applyScriptedAction(
          hasTag('item-focus') ? 'use-item' : 'upgrade-tower-stat',
          hasTag('item-focus')
            ? `Helba auto-secured the defense item (${stageBias.label})`
            : `Helba auto-fortified the tower line (${stageBias.label})`,
        )
      ) {
        return true
      }
    }

    if (
      hasJuno
      && (
        hasTag('skill-focus')
        || hasTag('mana-focus')
        || hasTag('siege-focus')
        || stageBias.manaBias
        || stageBias.heroBias
        || hasTag('emphasis-pulse')
      )
    ) {
      this.panelOverride = 'skill'
      if (this.applyScriptedAction('cast-skill', `Juno auto-threaded an arcane strike window (${stageBias.label})`)) {
        return true
      }
    }

    if (
      hasManos
      && (
        hasTag('siege-focus')
        || hasTag('skill-focus')
        || stageBias.siegeBias
        || hasTag('emphasis-pulse')
        || hasTag('presentation-pulse')
      )
    ) {
      this.panelOverride = 'skill'
      if (this.applyScriptedAction('cast-skill', `Manos auto-pressed the siege burst (${stageBias.label})`)) {
        return true
      }
    }

    if (
      hasCaesar
      && (
        hasTag('guard-focus')
        || hasTag('population-focus')
        || hasTag('quest-focus')
        || stageBias.sustainBias
        || stageBias.rewardBias
      )
    ) {
      this.panelOverride = 'tower'
      if (this.applyScriptedAction('upgrade-tower-stat', `Caesar auto-shored up the guard line (${stageBias.label})`)) {
        return true
      }
    }

    if (
      (rosterRole === 'vanguard' || rosterRole === 'raider')
      && (hasTag('dispatch-focus') || hasTag('battle-hud-focus') || hasTag('emphasis-pulse'))
    ) {
      this.selectedDispatchLane = activeLoadout.dispatchLane ?? activeLoadout.heroLane ?? favoredLane
      this.queuedUnitCount = Math.max(this.queuedUnitCount, rosterRole === 'raider' ? 2 : 1)
      if (this.applyScriptedAction('deploy-hero', `${activeLoadout.heroRosterLabel} auto-committed hero pressure`)) {
        return true
      }
    }

    if (
      (rosterRole === 'defender' || rosterRole === 'support')
      && (
        hasTag('mana-focus')
        || hasTag('population-focus')
        || hasTag('tower-focus')
        || hasTag('quest-focus')
      )
    ) {
      this.panelOverride = 'tower'
      if (this.applyScriptedAction('upgrade-tower-stat', `${activeLoadout.heroRosterLabel} reinforced tower policy`)) {
        return true
      }
    }

    if (
      (skillPresetKind === 'support' || skillPresetKind === 'utility')
      && (
        hasTag('mana-focus')
        || hasTag('item-focus')
        || hasTag('quest-focus')
        || hasTag('system-focus')
      )
    ) {
      if (this.applyScriptedAction('use-item', `${activeLoadout.skillPresetLabel} auto-stabilized the lane`)) {
        return true
      }
    }

    if (
      (skillPresetKind === 'burst' || skillPresetKind === 'orders')
      && (
        hasTag('skill-focus')
        || hasTag('siege-focus')
        || hasTag('presentation-pulse')
        || hasTag('emphasis-pulse')
      )
    ) {
      this.panelOverride = 'skill'
      if (this.applyScriptedAction('cast-skill', `${activeLoadout.skillPresetLabel} auto-opened a channel spike`)) {
        return true
      }
    }

    if (
      towerPolicyKind === 'population-first'
      && (hasTag('unit-production') || hasTag('guided-focus') || hasTag('battle-hud-focus'))
    ) {
      if (this.applyScriptedAction('produce-unit', `${activeLoadout.towerPolicyLabel} auto-queued reinforcements`)) {
        return true
      }
    }

    return false
  }

  private deriveChannelLoadoutModulation(
    archetype: RecoveryRuntimeBlueprint['featuredArchetypes'][number],
    baseIntensity: number,
    phaseLabel: string,
  ): Pick<RecoveryBattleChannelState, 'intensity' | 'phaseLabel' | 'loadoutMode' | 'focusLane' | 'focusSource'> {
    const activeLoadout = this.activeDeployLoadout
    if (!activeLoadout) {
      return {
        intensity: baseIntensity,
        phaseLabel,
        loadoutMode: null,
        focusLane: null,
        focusSource: null,
      }
    }

    const signals = this.deriveArchetypeSignals(archetype)
    const stageBias = this.deriveCurrentStageScriptBias()
    const favoredLane = activeLoadout.dispatchLane ?? activeLoadout.heroLane ?? this.currentStageBattleProfile.favoredLane ?? null
    let intensity = baseIntensity
    let resolvedPhaseLabel = phaseLabel
    let loadoutMode: string | null = null
    let focusLane: 'upper' | 'lower' | null = stageBias.preferredLane ?? null
    let focusSource: 'roster' | 'skill' | 'policy' | null = null
    const hasVincent = this.loadoutHasMember(activeLoadout, 'Vincent')
    const hasRogan = this.loadoutHasMember(activeLoadout, 'Rogan')
    const hasHelba = this.loadoutHasMember(activeLoadout, 'Helba')
    const hasJuno = this.loadoutHasMember(activeLoadout, 'Juno')
    const hasManos = this.loadoutHasMember(activeLoadout, 'Manos')
    const hasCaesar = this.loadoutHasMember(activeLoadout, 'Caesar')

    if (
      activeLoadout.heroRosterRole === 'vanguard'
      && (signals.has('dispatch') || signals.has('tower-defense'))
    ) {
      intensity += 0.14
      resolvedPhaseLabel = intensity > 0.82 ? 'vanguard-pulse' : 'lane-orders'
      loadoutMode = activeLoadout.heroRosterLabel
      focusLane = favoredLane
      focusSource = 'roster'
    } else if (
      activeLoadout.heroRosterRole === 'raider'
      && (signals.has('armageddon') || signals.has('dispatch'))
    ) {
      intensity += 0.18
      resolvedPhaseLabel = this.currentObjectivePhase === 'siege' || this.currentObjectivePhase === 'hero-pressure' ? 'raid-window' : 'raid-ready'
      loadoutMode = activeLoadout.heroRosterLabel
      focusLane = activeLoadout.heroLane ?? favoredLane
      focusSource = 'roster'
    } else if (
      (activeLoadout.heroRosterRole === 'defender' || activeLoadout.heroRosterRole === 'support')
      && (signals.has('tower-defense') || archetype.buffRows.length > 0)
    ) {
      intensity += 0.12
      resolvedPhaseLabel = activeLoadout.heroRosterRole === 'defender' ? 'guard-loop' : 'support-loop'
      loadoutMode = activeLoadout.heroRosterLabel
      focusLane = this.currentStageBattleProfile.favoredLane ?? favoredLane
      focusSource = 'roster'
    }

    if (activeLoadout.skillPresetKind === 'orders' && (signals.has('dispatch') || signals.has('tower-defense'))) {
      intensity += 0.1
      resolvedPhaseLabel = 'orders-window'
      loadoutMode = activeLoadout.skillPresetLabel
      focusLane = activeLoadout.dispatchLane ?? favoredLane
      focusSource = 'skill'
    } else if (
      activeLoadout.skillPresetKind === 'burst'
      && (signals.has('armageddon') || archetype.evidence.some((entry) => entry.includes('exact projectile or effect hits')))
    ) {
      intensity += 0.14
      resolvedPhaseLabel = this.currentObjectivePhase === 'skill-burst' || this.currentObjectivePhase === 'siege' ? 'burst-window' : 'burst-arming'
      loadoutMode = activeLoadout.skillPresetLabel
      focusSource = 'skill'
    } else if (activeLoadout.skillPresetKind === 'support' && archetype.buffRows.length > 0) {
      intensity += 0.1
      resolvedPhaseLabel = 'support-net'
      loadoutMode = activeLoadout.skillPresetLabel
      focusLane = activeLoadout.heroLane ?? this.currentStageBattleProfile.favoredLane ?? null
      focusSource = 'skill'
    } else if (activeLoadout.skillPresetKind === 'utility' && (signals.has('mana-surge') || archetype.buffRows.length > 0)) {
      intensity += 0.08
      resolvedPhaseLabel = 'utility-cycle'
      loadoutMode = activeLoadout.skillPresetLabel
      focusSource = 'skill'
    }

    if (activeLoadout.towerPolicyKind === 'mana-first' && signals.has('mana-surge')) {
      intensity += 0.08
      resolvedPhaseLabel = 'mana-route'
      loadoutMode = activeLoadout.towerPolicyLabel
      focusSource = 'policy'
    } else if (activeLoadout.towerPolicyKind === 'population-first' && signals.has('dispatch')) {
      intensity += 0.08
      resolvedPhaseLabel = 'population-surge'
      loadoutMode = activeLoadout.towerPolicyLabel
      focusLane = activeLoadout.dispatchLane ?? favoredLane
      focusSource = 'policy'
    } else if (activeLoadout.towerPolicyKind === 'attack-first' && (signals.has('dispatch') || signals.has('armageddon'))) {
      intensity += 0.09
      resolvedPhaseLabel = 'siege-route'
      loadoutMode = activeLoadout.towerPolicyLabel
      focusLane = activeLoadout.dispatchLane ?? favoredLane
      focusSource = 'policy'
    }

    if (hasVincent && signals.has('dispatch')) {
      intensity += stageBias.siegeBias || stageBias.heroBias ? 0.09 : 0.06
      resolvedPhaseLabel =
        this.currentObjectivePhase === 'hero-pressure' || stageBias.heroBias
          ? 'vincent-sortie'
          : stageBias.siegeBias
            ? 'vincent-break'
            : 'vincent-drive'
      loadoutMode = `Vincent spearhead/${stageBias.label}`
      focusLane = stageBias.preferredLane ?? activeLoadout.heroLane ?? favoredLane
      focusSource = 'roster'
    } else if (hasRogan && signals.has('dispatch')) {
      intensity += stageBias.dispatchBias ? 0.08 : 0.05
      resolvedPhaseLabel = stageBias.dispatchBias ? 'rogan-flood' : 'rogan-rally'
      loadoutMode = `Rogan reserves/${stageBias.label}`
      focusLane = stageBias.preferredLane ?? activeLoadout.dispatchLane ?? favoredLane
      focusSource = 'roster'
    } else if (hasHelba && (signals.has('tower-defense') || signals.has('healing'))) {
      intensity += stageBias.sustainBias || stageBias.rewardBias ? 0.09 : 0.06
      resolvedPhaseLabel = stageBias.rewardBias ? 'helba-claim' : 'helba-ward'
      loadoutMode = `Helba ward/${stageBias.label}`
      focusLane = stageBias.preferredLane ?? this.currentStageBattleProfile.favoredLane ?? favoredLane
      focusSource = 'roster'
    } else if (hasJuno && (signals.has('armageddon') || signals.has('mana-surge'))) {
      intensity += stageBias.manaBias ? 0.1 : 0.07
      resolvedPhaseLabel = stageBias.manaBias ? 'juno-focus' : 'juno-arc'
      loadoutMode = `Juno arc/${stageBias.label}`
      focusSource = 'roster'
    } else if (hasManos && signals.has('armageddon')) {
      intensity += stageBias.siegeBias ? 0.11 : 0.08
      resolvedPhaseLabel = this.currentObjectivePhase === 'siege' || stageBias.siegeBias ? 'manos-break' : 'manos-charge'
      loadoutMode = `Manos break/${stageBias.label}`
      focusLane = stageBias.preferredLane ?? activeLoadout.heroLane ?? favoredLane
      focusSource = 'roster'
    } else if (hasCaesar && signals.has('tower-defense')) {
      intensity += stageBias.sustainBias ? 0.09 : 0.06
      resolvedPhaseLabel = stageBias.rewardBias ? 'caesar-hold' : 'caesar-guard'
      loadoutMode = `Caesar guard/${stageBias.label}`
      focusLane = stageBias.preferredLane ?? this.currentStageBattleProfile.favoredLane ?? favoredLane
      focusSource = 'roster'
    }

    if (Object.keys(this.rosterChainBoosts).length > 0) {
      const memberBoosts = [
        hasVincent ? this.rosterChainBoosts.Vincent ?? 0 : 0,
        hasRogan ? this.rosterChainBoosts.Rogan ?? 0 : 0,
        hasHelba ? this.rosterChainBoosts.Helba ?? 0 : 0,
        hasJuno ? this.rosterChainBoosts.Juno ?? 0 : 0,
        hasManos ? this.rosterChainBoosts.Manos ?? 0 : 0,
        hasCaesar ? this.rosterChainBoosts.Caesar ?? 0 : 0,
      ].filter((value) => value > 0)
      const chainBoost = memberBoosts.length > 0 ? Math.max(...memberBoosts) : 0
      if (chainBoost > 0) {
        intensity += chainBoost * 0.22
        if (this.rosterChainFocusLane) {
          focusLane = this.rosterChainFocusLane
          focusSource = 'roster'
        }
        if (chainBoost >= 0.22) {
          resolvedPhaseLabel = `${resolvedPhaseLabel}-chain`
          loadoutMode = loadoutMode ? `${loadoutMode} / chain` : 'route-chain'
        }
      }
    }

    return {
      intensity: clamp(intensity, 0.18, 1),
      phaseLabel: resolvedPhaseLabel,
      loadoutMode,
      focusLane,
      focusSource,
    }
  }

  private triggerSceneWave(
    side: 'enemy' | 'allied',
    note: string,
    advanceWave: boolean,
  ): void {
    const storyboard = this.storyboards[this.storyboardIndex] ?? null
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)

    const plan = side === 'enemy' ? this.enemyWavePlan : this.alliedWavePlan
    const directive = this.adjustSceneDirectiveForRoute(side, this.currentLoadoutDirective(plan, side, 'scene'))
    this.applyWaveDirective(side, directive)
    if (directive) {
      this.markWaveDispatched(side, advanceWave)
    }
    const loadoutBeat = this.applyLoadoutWaveBeat(side, directive, 'scene')
    if (directive && side === 'allied' && routeInfluence.matchesPreferred) {
      if ((directive.role === 'push' || directive.role === 'siege') && routeBias.directRoute) {
        this.objectiveProgressRatio = clamp(
          Math.max(
            this.objectiveProgressRatio,
            this.alliedWavesDispatched / Math.max(this.totalWaveCount, 1) * 0.72 + 0.14 + routeInfluence.commitmentFactor * 0.04,
          ),
          0.04,
          1,
        )
      } else if (directive.role === 'tower-rally' && routeBias.sustainRoute) {
        this.repairTower('allied', 0.02 + routeInfluence.defenseDelta * 0.25)
      } else if (directive.role === 'skill-window' && routeBias.manaRoute) {
        this.restoreMana('allied', this.manaCapacityValue * (0.04 + routeInfluence.manaDelta * 0.3))
      }
    }
    this.resetWaveCountdown(side, directive)
    this.evaluateBattleResolution()
    this.lastScriptedBeatNote = directive ? `${note} (${directive.label}${loadoutBeat ? ` / ${loadoutBeat}` : ''})` : note
  }

  private resolveBattleOutcome(outcome: 'victory' | 'defeat', reason: string): void {
    if (this.battleResolutionOutcome) {
      return
    }
    const currentStoryboard = this.storyboards[this.storyboardIndex]
    const previousUnlockedStageCount = this.campaignUnlockedStageCount
    this.battleResolutionOutcome = outcome
    this.battleResolutionReason = reason
    this.campaignScenePhase = 'result-hold'
    this.battleResolutionAutoAdvanceAtMs = this.lastUpdateNowMs + RESULT_HOLD_MS
    this.campaignLastResolvedStageTitle = currentStoryboard?.stageBlueprint?.title ?? currentStoryboard?.scriptPath ?? null
    this.campaignLastOutcome = outcome
    if (outcome === 'victory' && currentStoryboard && !this.campaignClearedStoryboardIds.has(currentStoryboard.id)) {
      this.campaignClearedStoryboardIds.add(currentStoryboard.id)
      this.campaignUnlockedStageCount = Math.min(
        Math.max(this.campaignUnlockedStageCount, this.campaignClearedStoryboardIds.size + 1),
        this.storyboards.length,
      )
      if (this.campaignUnlockedStageCount > previousUnlockedStageCount) {
        this.campaignLastUnlockedNodeIndex = this.campaignUnlockedStageCount - 1
      }
    } else {
      this.campaignLastUnlockedNodeIndex = null
    }
    this.updateCampaignRouteCommitment(currentStoryboard ?? null, outcome)
    const recommendation = currentStoryboard ? this.deriveCampaignRecommendation(currentStoryboard) : null
    if (recommendation) {
      this.campaignSelectedNodeIndex = clamp(
        recommendation.nodeIndex,
        0,
        Math.max(this.campaignUnlockedStageCount, 1) - 1,
      )
      this.campaignSelectedLoadoutIndex = recommendation.loadoutIndex
    } else if (outcome === 'victory') {
      this.campaignSelectedNodeIndex = clamp(
        Math.min(this.storyboardIndex + 1, Math.max(this.campaignUnlockedStageCount, 1) - 1),
        0,
        Math.max(this.campaignUnlockedStageCount, 1) - 1,
      )
      this.campaignSelectedLoadoutIndex = 0
    } else {
      this.campaignSelectedNodeIndex = this.storyboardIndex
      this.campaignSelectedLoadoutIndex = 0
    }
    if (outcome === 'victory') {
      this.currentObjectivePhase = 'quest-resolution'
      this.currentObjectiveLabel = 'stage clear, collect rewards, advance'
      this.panelOverride = 'system'
      this.questRewardClaimed = false
    } else {
      this.currentObjectivePhase = 'tower-management'
      this.currentObjectiveLabel = 'tower breached, regroup for the next attempt'
      this.panelOverride = 'system'
    }
    this.lastScriptedBeatNote = `${outcome === 'victory' ? 'stage clear' : 'stage failed'}: ${reason}`
    this.emitAudioCue(outcome === 'victory' ? 'result' : 'battle', outcome === 'victory' ? 'stage-victory' : 'stage-defeat', outcome === 'victory' ? 0.48 : 0.4)
  }

  private totalUnits(side: RecoveryBattleSide): number {
    return (['upper', 'lower'] as const).reduce((sum, laneId) => sum + this.laneEntities[laneId][side].length, 0)
  }

  private totalProjectiles(side: RecoveryBattleSide): number {
    return this.battleProjectiles.filter((projectile) => projectile.side === side).length
  }

  private laneControlScore(side: RecoveryBattleSide, laneId: RecoveryBattleLaneId): number {
    const lane = this.laneBattleState[laneId]
    const unitAdvantage = side === 'allied'
      ? lane.alliedUnits - lane.enemyUnits
      : lane.enemyUnits - lane.alliedUnits
    const frontlineBias = side === 'allied'
      ? lane.frontline - 0.5
      : 0.5 - lane.frontline
    return unitAdvantage * 0.22 + frontlineBias + (lane.heroPresent && side === 'allied' ? 0.18 : 0)
  }

  private securedLaneCount(side: RecoveryBattleSide): number {
    return (['upper', 'lower'] as const).filter((laneId) => this.laneControlScore(side, laneId) > 0.12).length
  }

  private threatenedLaneCount(side: RecoveryBattleSide): number {
    return (['upper', 'lower'] as const).filter((laneId) => this.laneControlScore(side, laneId) < -0.12).length
  }

  private evaluateBattleResolution(): void {
    if (this.battleResolutionOutcome) {
      return
    }

    const storyboard = this.storyboards[this.storyboardIndex] ?? null
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)
    const alliedUnits = this.totalUnits('allied')
    const enemyUnits = this.totalUnits('enemy')
    const alliedProjectiles = this.totalProjectiles('allied')
    const enemyProjectiles = this.totalProjectiles('enemy')
    const alliedSecuredLanes = this.securedLaneCount('allied')
    const enemySecuredLanes = this.securedLaneCount('enemy')
    const alliedThreatenedLanes = this.threatenedLaneCount('allied')
    const enemyWavesExhausted = this.enemyWavesDispatched >= this.totalWaveCount
    const alliedWavesExhausted = this.alliedWavesDispatched >= this.totalWaveCount
    const enemyFieldCleared = enemyUnits === 0 && enemyProjectiles === 0
    const alliedFieldCollapsed = alliedUnits === 0 && alliedProjectiles === 0 && !this.heroAssignedLane
    const siegeTowerThreshold = clamp(
      0.18
      + (routeInfluence.matchesPreferred && routeBias.directRoute ? 0.03 + routeInfluence.commitmentFactor * 0.03 : 0)
      - (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null ? 0.015 : 0),
      0.12,
      0.24,
    )
    const alliedExhaustedThreshold = clamp(
      0.14
      - (routeInfluence.matchesPreferred && routeBias.sustainRoute ? 0.02 + routeInfluence.commitmentFactor * 0.02 : 0)
      + (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null ? 0.012 : 0),
      0.08,
      0.16,
    )

    if (
      this.previewEnemyTowerHpRatio <= 0.08
      || (
        enemyWavesExhausted
        && enemyFieldCleared
        && alliedSecuredLanes >= (this.currentObjectivePhase === 'lane-control' ? 1 : 0)
      )
      || (
        this.currentObjectivePhase === 'siege'
        && enemyWavesExhausted
        && this.previewEnemyTowerHpRatio <= siegeTowerThreshold
        && alliedUnits + alliedProjectiles > 0
      )
      || (
        this.currentObjectivePhase === 'skill-burst'
        && routeInfluence.matchesPreferred
        && routeBias.manaRoute
        && enemyWavesExhausted
        && enemyFieldCleared
        && this.alliedManaValue >= this.manaCapacityValue * 0.44
      )
    ) {
      this.resolveBattleOutcome(
        'victory',
        enemyWavesExhausted && enemyFieldCleared
          ? `enemy waves exhausted under ${routeInfluence.stanceLabel}`
          : 'enemy tower destroyed',
      )
      return
    }

    if (
      this.previewOwnTowerHpRatio <= 0.08
      || (
        alliedFieldCollapsed
        && this.queuedUnitCount === 0
        && this.alliedManaValue < this.manaCapacityValue * 0.18
        && enemyUnits + enemyProjectiles > 0
        && enemySecuredLanes >= 1
      )
      || (
        alliedWavesExhausted
        && this.previewOwnTowerHpRatio <= alliedExhaustedThreshold
        && enemySecuredLanes >= 1
        && this.queuedUnitCount === 0
      )
      || (
        this.currentObjectivePhase === 'lane-control'
        && enemySecuredLanes === 2
        && alliedThreatenedLanes >= 2
        && this.previewOwnTowerHpRatio <= 0.18
      )
    ) {
      this.resolveBattleOutcome(
        'defeat',
        routeInfluence.preferredRouteLabel !== null && !routeInfluence.matchesPreferred
          ? `branch counter-force held the field (${routeInfluence.stanceLabel})`
          : 'allied field collapsed before the tower line recovered',
      )
    }
  }

  private buildCampaignBriefing(storyboard: RecoveryStageStoryboard): RecoveryStageSnapshot['campaignState']['briefing'] {
    const profile = this.deriveStageBattleProfile(storyboard)
    const objectiveSeed = this.deriveObjectiveSeed(storyboard, profile)
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const recommendedArchetypes = profile.archetypeLabels.length > 0
      ? profile.archetypeLabels
      : (storyboard.stageBlueprint?.recommendedArchetypeIds ?? []).slice(0, 3)
    const alliedForecast = objectiveSeed.alliedWavePlan
      .slice(0, 3)
      .map((directive) => `W${directive.waveNumber} ${directive.role} ${directive.laneId} x${directive.unitBurst}`)
    const enemyForecast = objectiveSeed.enemyWavePlan
      .slice(0, 3)
      .map((directive) => `W${directive.waveNumber} ${directive.role} ${directive.laneId} x${directive.unitBurst}`)
    return {
      objectivePhase: objectiveSeed.phase,
      objectiveLabel: `${objectiveSeed.label} [${routeBias.routeLabel}${routeBias.flankingRoute ? ' flank' : routeBias.directRoute ? ' main' : routeBias.sustainRoute ? ' hold' : ''}]`,
      favoredLane: profile.favoredLane,
      tacticalBias: `${profile.tacticalBias} / ${routeBias.routeLabel}`,
      totalWaves: objectiveSeed.totalWaveCount,
      stageTier: profile.stageTier,
      effectIntensity: profile.effectIntensity,
      recommendedArchetypes,
      alliedForecast,
      enemyForecast,
    }
  }

  private buildWavePlanForProfile(
    storyboard: RecoveryStageStoryboard,
    side: 'enemy' | 'allied',
    profile: RecoveryStageBattleProfile,
    totalWaveCount: number,
  ): RecoveryBattleWaveDirective[] {
    const stage = storyboard.stageBlueprint
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)
    const favoredLane = routeInfluence.preferredLane ?? routeBias.preferredLane ?? profile.favoredLane ?? 'upper'
    const supportLane = favoredLane === 'upper' ? 'lower' : 'upper'
    const stageTier = stage?.runtimeFields?.tierCandidate ?? 10
    const storyBranch = routeBias.routeLabel
    const title = (stage?.title ?? '').toLowerCase()
    const hintText = (stage?.hintText ?? '').toLowerCase()
    const signals = new Set(profile.archetypeSignals)
    const highIntensity = (stage?.renderIntent?.effectIntensity ?? 'medium') === 'high'

    return Array.from({ length: totalWaveCount }, (_, index) => {
      const waveNumber = index + 1
      if (side === 'enemy') {
        const role: RecoveryBattleWaveDirective['role'] =
          waveNumber === totalWaveCount || includesAny(title, ['seize', 'siege', 'enemy camp', 'defeat'])
            ? 'siege'
            : includesAny(hintText, ['hero', 'eliminate']) && waveNumber % 3 === 0
              ? 'hero-bait'
              : storyBranch === 'secondary' && waveNumber === 1
                ? 'screen'
                : waveNumber % 2 === 0
                  ? 'push'
                  : 'screen'
        const laneId =
          role === 'siege'
            ? favoredLane
            : role === 'hero-bait'
              ? supportLane
              : routeBias.flankingRoute
                ? (waveNumber % 2 === 0 ? favoredLane : supportLane)
                : (waveNumber % 2 === 0 ? supportLane : favoredLane)
        const unitBurst = clamp(
          1
          + Math.floor(stageTier / 20)
          + (highIntensity ? 1 : 0)
          + (role === 'siege' ? 1 : 0)
          + (routeBias.directRoute ? 1 : 0)
          + (routeInfluence.matchesPreferred && role !== 'screen' ? Math.round(routeInfluence.commitmentFactor) : 0)
          - (routeBias.sustainRoute && role === 'screen' ? 0 : 0),
          1,
          5,
        )
        const pressureBias = clamp(
          0.04
          + stageTier * 0.002
          + routeBias.pressureShift
          - routeInfluence.pressureDelta * 0.35
          + (role === 'siege' ? 0.12 : role === 'push' ? 0.08 : role === 'hero-bait' ? 0.06 : 0.04),
          0.04,
          0.36,
        )
        return {
          waveNumber,
          laneId,
          role,
          unitBurst,
          pressureBias,
          label: `enemy ${role} ${laneId}`,
        }
      }

      const role: RecoveryBattleWaveDirective['role'] =
        signals.has('armageddon') && waveNumber >= Math.max(totalWaveCount - 1, 2)
          ? 'skill-window'
          : signals.has('dispatch') && waveNumber <= Math.ceil(totalWaveCount / 2)
            ? 'push'
            : signals.has('tower-defense') && waveNumber === 1
              ? 'support'
              : signals.has('recall') && waveNumber % 3 === 0
                ? 'tower-rally'
                : waveNumber === this.totalWaveCount
                  ? 'siege'
                  : 'push'
      const laneId =
        role === 'support' || role === 'tower-rally'
          ? supportLane
          : role === 'skill-window'
            ? favoredLane
            : waveNumber % 2 === 0 && (signals.has('dispatch') || routeBias.flankingRoute)
              ? supportLane
              : favoredLane
      const unitBurst = clamp(
        1
        + (signals.has('dispatch') ? 1 : 0)
        + (routeBias.directRoute ? 1 : 0)
        + Math.max(0, Math.round(routeInfluence.queueDelta))
        + (role === 'skill-window' ? 1 : 0)
        + (role === 'siege' ? 1 : 0),
        1,
        5,
      )
      const pressureBias = clamp(
        0.03
        + profile.dispatchBoost * 0.3
        + routeBias.pressureShift
        + routeInfluence.pressureDelta
        + profile.heroImpact * 0.1
        + (role === 'support' ? 0.03 : role === 'tower-rally' ? 0.04 : role === 'skill-window' ? 0.06 : 0.05),
        0.03,
        0.32,
      )
      return {
        waveNumber,
        laneId,
        role,
        unitBurst,
        pressureBias,
        label: `ally ${role} ${laneId}`,
      }
    })
  }

  private buildChannelStates(storyboard: RecoveryStageStoryboard): RecoveryBattleChannelState[] {
    const archetypeIds = storyboard.stageBlueprint?.recommendedArchetypeIds ?? []
    const elapsed = Math.max(this.lastUpdateNowMs - this.storyboardStartedAtMs, 0)
    return archetypeIds
      .map((archetypeId, index) => {
        const archetype = this.featuredArchetypesById.get(archetypeId)
        if (!archetype) {
          return null
        }
        const cycleMs = archetypeCycleMs(archetype)
        const offsetMs = index * 180 + this.storyboardIndex * 75
        const markerCount =
          archetype.activeRows.reduce(
            (count, row) => count + row.timingWindowACompact.length + row.timingWindowBCompact.length,
            0,
          ) + archetype.buffRows.length
        const phaseProgress = cycleMs > 0 ? ((elapsed + offsetMs) % cycleMs) / cycleMs : 0
        const pulse = Math.sin(phaseProgress * Math.PI * 2)
        const baseIntensity = 0.25 + Math.max(pulse, 0) * 0.75
        const basePhaseLabel =
          baseIntensity > 0.82 ? 'burst' : baseIntensity > 0.52 ? 'arming' : markerCount > 0 ? 'ready' : 'idle'
        const hasExactTailHit = archetype.evidence.some((entry) => entry.includes('exact projectile or effect hits'))
        const { intensity, phaseLabel, loadoutMode, focusLane, focusSource } = this.deriveChannelLoadoutModulation(
          archetype,
          baseIntensity,
          basePhaseLabel,
        )

        return {
          archetypeId: archetype.archetypeId,
          label: archetype.label,
          archetypeKind: archetype.archetypeKind,
          confidence: archetype.confidence,
          intensity,
          phaseLabel,
          cycleMs,
          markerCount,
          hasBuffLayer: archetype.buffRows.length > 0,
          hasExactTailHit,
          loadoutMode,
          focusLane,
          focusSource,
        }
      })
      .filter((entry): entry is RecoveryBattleChannelState => entry !== null)
  }

  private buildRenderState(
    storyboard: RecoveryStageStoryboard,
    channelStates: RecoveryBattleChannelState[],
  ): RecoveryStageRenderState {
    const currentFrame = this.currentFrame(storyboard.previewStem)
    const specialRule = this.runtimeBlueprint?.renderProfile.specialPackedPixelStems.find(
      (entry) => entry.stem === storyboard.previewStem.stem,
    )
    const familyRepresentatives = this.runtimeBlueprint?.renderProfile.ptcBridgeSummary.familyRepresentativeEmitters ?? {}
    const bankOverlayWeight = Math.max(0, Number(currentFrame?.bankOverlayWeight ?? 0))
    const effectsScale = this.settingsState.reducedEffects ? 0.52 : 1
    return {
      bankRuleLabel: storyboard.stageBlueprint?.renderIntent?.bankRule ?? this.runtimeBlueprint?.renderProfile.defaultMplBankRule.label ?? 'flag-driven-bank-switch',
      bankOverlayActive: bankOverlayWeight * effectsScale > 0.01,
      bankStateId: currentFrame?.bankStateId ?? 'bank-b-only',
      bankTransition: currentFrame?.bankTransition ?? null,
      bankBlendMode: currentFrame?.bankBlendMode ?? 'opaque-b',
      bankOverlayWeight: bankOverlayWeight * effectsScale,
      baseFlaggedCount: Number(currentFrame?.baseFlaggedCount ?? 0),
      tailFlaggedCount: Number(currentFrame?.tailFlaggedCount ?? 0),
      packedPixelStemRule: specialRule?.heuristic ?? null,
      packedPixelBlendMode: specialRule?.highlightBlendMode ?? null,
      effectPulseCount: Math.max(
        channelStates.filter((entry) => entry.intensity > 0.62 && entry.hasBuffLayer).length,
        Math.round(this.burstPulseIntensity * effectsScale * 4),
      ),
      effectIntensity: storyboard.stageBlueprint?.renderIntent?.effectIntensity ?? 'medium',
      ptcEmitterHint: typeof familyRepresentatives.support === 'string' ? familyRepresentatives.support : null,
      cameraShakeIntensity: this.cameraShakeIntensity * effectsScale,
      cameraShakeAxes: this.cameraShakeAxes,
      overlayMode: this.overlayMode,
      overlayColor: this.overlayColor,
      overlayAlpha: this.overlayAlpha * effectsScale,
      burstPulseIntensity: this.burstPulseIntensity * effectsScale,
      particleBoostIntensity: this.particleBoostIntensity * effectsScale,
      hitFlashIntensity: this.hitFlashIntensity * effectsScale,
    }
  }

  private buildHudState(
    storyboard: RecoveryStageStoryboard,
    activeSceneStep: RecoverySceneScriptStep | null,
    _activeOpcodeCue: RecoveryResolvedOpcodeCue | null,
    channelStates: RecoveryBattleChannelState[],
  ): RecoveryHudGhostState {
    const elapsed = Math.max(this.lastUpdateNowMs - this.storyboardStartedAtMs, 0)
    const runtimeFields = storyboard.stageBlueprint?.runtimeFields
    const channelEnergy =
      channelStates.length > 0
        ? channelStates.reduce((sum, channel) => sum + channel.intensity, 0) / channelStates.length
        : 0.5
    let ownTowerHpRatio = clamp(this.previewOwnTowerHpRatio + oscillate(elapsed, 5800, 0) * 0.08 - channelEnergy * 0.03, 0.1, 1)
    let enemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio + oscillate(elapsed, 5300, 900) * 0.1, 0.08, 1)
    let manaRatio = clamp(this.previewManaRatio + oscillate(elapsed, 3600, 1400) * 0.12, 0.06, 1)
    let manaUpgradeProgressRatio = clamp(this.previewManaUpgradeProgressRatio + oscillate(elapsed, 4200, 600) * 0.12, 0.04, 1)
    let activePanel: RecoveryHudGhostState['activePanel'] = this.panelOverride
    let highlightedMenuId: RecoveryHudGhostState['highlightedMenuId'] = null
    let highlightedTowerUpgradeId: RecoveryHudGhostState['highlightedTowerUpgradeId'] = null
    let highlightedUnitCardIndex: number | null = null
    let questVisible = (runtimeFields?.storyFlagCandidate ?? 0) === 1
    let questRewardReady = false
    let skillWindowVisible = false
    let itemWindowVisible = false
    let skillSlotHighlighted = false
    let itemSlotHighlighted = false
    let heroDeployed = oscillate(elapsed, 4400, 200) > 0.55
    let heroPortraitHighlighted = false
    let returnCooldownRatio = heroDeployed ? clamp(oscillate(elapsed, 2600, 1200), 0, 1) : 0
    let dispatchArrowsHighlighted = false
    let leftDispatchCueVisible = false
    const skillCooldownRatio = this.cooldownRatio(this.skillCooldownEndsAtMs, SKILL_COOLDOWN_MS)
    const itemCooldownRatio = this.cooldownRatio(this.itemCooldownEndsAtMs, ITEM_COOLDOWN_MS)
    const stepTags = new Set(activeSceneStep?.tags ?? [])
    const stepDirectives = activeSceneStep?.directives ?? []
    const hasTag = (value: string): boolean => stepTags.has(value)
    const hasDirective = (kind: RecoverySceneScriptDirective['kind']): boolean =>
      stepDirectives.some((directive) => directive.kind === kind)
    const invokedActionIds = new Set(
      stepDirectives
        .filter((directive) => directive.kind === 'invoke-action')
        .map((directive) => directive.actionId)
        .filter((value): value is RecoveryGameplayActionId => value !== undefined),
    )
    const panelDirective = stepDirectives.find((directive) => directive.kind === 'set-panel') ?? null

    if (hasTag('guard-focus')) {
      ownTowerHpRatio = 0.16
    }
    if (hasTag('siege-focus')) {
      enemyTowerHpRatio = 0.14
    }
    if (hasTag('dispatch-focus') || hasDirective('set-selected-lane') || hasDirective('commit-dispatch')) {
      dispatchArrowsHighlighted = true
      leftDispatchCueVisible = true
    }
    if (hasTag('unit-production') || invokedActionIds.has('produce-unit')) {
      highlightedUnitCardIndex = 0
      manaRatio = Math.max(manaRatio, 0.62)
    }
    if (hasTag('mana-focus') || hasDirective('restore-mana')) {
      manaRatio = 0.34
      manaUpgradeProgressRatio = 0.12
    }
    if (hasTag('hero-sortie') || invokedActionIds.has('deploy-hero')) {
      heroDeployed = false
      heroPortraitHighlighted = true
      returnCooldownRatio = 0
    }
    if (hasTag('hero-return') || invokedActionIds.has('return-to-tower')) {
      heroDeployed = true
      heroPortraitHighlighted = true
      returnCooldownRatio = 0.78
    }

    if (panelDirective?.panel) {
      activePanel = panelDirective.panel
      highlightedMenuId = panelDirective.panel
    }
    if (hasTag('tower-focus') || hasTag('tower-menu-highlight')) {
      activePanel = 'tower'
      highlightedMenuId = 'tower'
    }
    if (hasTag('mana-focus') || hasTag('mana-upgrade-highlight')) {
      activePanel = 'tower'
      highlightedMenuId = 'tower'
      highlightedTowerUpgradeId = 'mana'
      manaRatio = 1
      manaUpgradeProgressRatio = 0.82
    }
    if (hasTag('population-focus') || hasTag('population-upgrade-highlight')) {
      activePanel = 'tower'
      highlightedMenuId = 'tower'
      highlightedTowerUpgradeId = 'population'
    }
    if (hasTag('skill-focus') || hasTag('skill-menu-highlight') || hasTag('skill-slot-highlight')) {
      activePanel = 'skill'
      highlightedMenuId = 'skill'
      skillWindowVisible = true
      skillSlotHighlighted = hasTag('skill-slot-highlight') || invokedActionIds.has('cast-skill')
    }
    if (hasTag('item-focus') || hasTag('item-menu-highlight') || invokedActionIds.has('use-item')) {
      activePanel = 'item'
      highlightedMenuId = 'item'
      itemWindowVisible = true
      itemSlotHighlighted = true
    }
    if (hasTag('system-focus') || hasTag('system-menu-highlight')) {
      activePanel = 'system'
      highlightedMenuId = 'system'
    }
    if (hasTag('quest-focus') || hasTag('quest-panel-highlight')) {
      questVisible = true
      questRewardReady = true
      highlightedMenuId = 'system'
    }

    if (activePanel === null && questVisible) {
      highlightedMenuId = highlightedMenuId ?? 'system'
    }

    if (this.heroOverrideMode === 'field') {
      heroDeployed = true
      heroPortraitHighlighted = true
      returnCooldownRatio = 0
    } else if (this.heroOverrideMode === 'return-cooldown') {
      const remaining = Math.max(this.heroReturnCooldownEndsAtMs - this.lastUpdateNowMs, 0)
      if (remaining <= 0) {
        this.heroOverrideMode = null
        returnCooldownRatio = 0
      } else {
        heroDeployed = false
        heroPortraitHighlighted = true
        returnCooldownRatio = clamp(remaining / HERO_RETURN_COOLDOWN_MS, 0, 1)
      }
    }

    if (this.questRewardClaimed) {
      questRewardReady = false
    }

    if (this.battleResolutionOutcome === 'victory') {
      activePanel = 'system'
      questVisible = true
      questRewardReady = !this.questRewardClaimed
      ownTowerHpRatio = Math.max(ownTowerHpRatio, 0.34)
      enemyTowerHpRatio = Math.min(enemyTowerHpRatio, 0.1)
    } else if (this.battleResolutionOutcome === 'defeat') {
      activePanel = 'system'
      questRewardReady = false
      ownTowerHpRatio = Math.min(ownTowerHpRatio, 0.12)
    }

    return {
      ownTowerHpRatio,
      enemyTowerHpRatio,
      manaRatio,
      manaUpgradeProgressRatio,
      activePanel,
      highlightedMenuId,
      highlightedTowerUpgradeId,
      highlightedUnitCardIndex,
      questVisible,
      questRewardReady,
      skillWindowVisible,
      itemWindowVisible,
      skillSlotHighlighted,
      itemSlotHighlighted,
      heroDeployed,
      heroPortraitHighlighted,
      returnCooldownRatio,
      dispatchArrowsHighlighted,
      leftDispatchCueVisible,
      selectedDispatchLane: this.selectedDispatchLane,
      queuedUnitCount: this.queuedUnitCount,
      towerUpgradeLevels: { ...this.towerUpgradeLevels },
      skillCooldownRatio,
      itemCooldownRatio,
      battlePaused: this.battlePaused,
      questRewardClaims: this.questRewardClaims,
    }
  }

  private buildGameplayState(
    activeSceneStep: RecoverySceneScriptStep | null,
    activeTutorialCue: RecoveryTutorialChainCue | null,
    activeOpcodeCue: RecoveryResolvedOpcodeCue | null,
    hudState: RecoveryHudGhostState,
  ): RecoveryGameplayState {
    const stepTags = new Set(activeSceneStep?.tags ?? [])
    const stepDirectives = activeSceneStep?.directives ?? []
    const stepSources = activeSceneStep?.sources ?? []
    const hasTag = (value: string): boolean => stepTags.has(value)
    const hasDirective = (kind: RecoverySceneScriptDirective['kind']): boolean =>
      stepDirectives.some((directive) => directive.kind === kind)
    const firstDirective = (kind: RecoverySceneScriptDirective['kind']): RecoverySceneScriptDirective | null =>
      stepDirectives.find((directive) => directive.kind === kind) ?? null
    const invokedActionIds = new Set(
      stepDirectives
        .filter((directive) => directive.kind === 'invoke-action')
        .map((directive) => directive.actionId)
        .filter((value): value is RecoveryGameplayActionId => value !== undefined),
    )
    const panelDirective = firstDirective('set-panel')
    const objectiveDirective = firstDirective('set-objective')
    const hasTutorialSource = stepSources.some((value) => value.startsWith('tutorial:'))
    let mode: RecoveryGameplayState['mode'] = hasTutorialSource
      ? 'tutorial-lock'
      : activeSceneStep && stepDirectives.length > 0
        ? 'guided-preview'
        : activeOpcodeCue
          ? 'guided-preview'
          : 'free-preview'
    let openPanel: RecoveryGameplayState['openPanel'] = hudState.activePanel
    let heroMode: RecoveryGameplayState['heroMode'] = hudState.heroDeployed
      ? (hudState.returnCooldownRatio > 0.05 ? 'return-cooldown' : 'field')
      : 'tower'
    let objectiveMode: RecoveryGameplayState['objectiveMode'] = 'generic-preview'
    let questState: RecoveryGameplayState['questState'] = hudState.questRewardReady
      ? 'reward-ready'
      : hudState.questVisible
        ? 'available'
        : 'hidden'
    const enabledInputs = new Set<RecoveryGameplayActionId>()
    const blockedInputs = new Set<RecoveryGameplayActionId>()
    let primaryHint = activeSceneStep?.label ?? activeTutorialCue?.label ?? activeOpcodeCue?.label ?? 'free-preview'

    const blockCommonBattleInputs = (): void => {
      blockedInputs.add('open-skill-menu')
      blockedInputs.add('open-item-menu')
      blockedInputs.add('open-system-menu')
    }

    if (panelDirective?.panel) {
      openPanel = panelDirective.panel
    }

    if (hasTag('guard-focus')) {
      objectiveMode = 'defend-own-tower'
      enabledInputs.add('inspect-own-tower-hp')
      enabledInputs.add('read-loss-condition')
      blockCommonBattleInputs()
      primaryHint = 'Protect your tower HP'
    } else if (hasTag('siege-focus') || objectiveDirective?.phase === 'siege') {
      objectiveMode = 'attack-enemy-tower'
      enabledInputs.add('inspect-enemy-tower-hp')
      enabledInputs.add('read-win-condition')
      blockCommonBattleInputs()
      primaryHint = 'Reduce enemy tower HP to zero'
    } else if (
      hasTag('dispatch-focus')
      || hasDirective('commit-dispatch')
      || hasDirective('set-selected-lane')
    ) {
      objectiveMode = 'dispatch-lanes'
      enabledInputs.add('dispatch-up-lane')
      enabledInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('toggle-hero-sortie')
      primaryHint = 'Choose a lane for unit dispatch'
    } else if (hasTag('unit-production') || invokedActionIds.has('produce-unit')) {
      objectiveMode = 'produce-units'
      enabledInputs.add('produce-unit')
      enabledInputs.add('inspect-unit-card')
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      primaryHint = 'Produce a unit from the left card tray'
    } else if (hasTag('mana-focus') || hasDirective('restore-mana')) {
      objectiveMode = 'produce-units'
      enabledInputs.add('inspect-mana-bar')
      blockedInputs.add('open-skill-menu')
      blockedInputs.add('open-item-menu')
      primaryHint = 'Mana is spent on unit production'
    } else if (hasTag('hero-sortie') || invokedActionIds.has('deploy-hero')) {
      objectiveMode = 'dispatch-lanes'
      enabledInputs.add('toggle-hero-sortie')
      enabledInputs.add('deploy-hero')
      blockedInputs.add('return-to-tower')
      primaryHint = 'Deploy the hero from the portrait button'
    } else if (hasTag('hero-return') || invokedActionIds.has('return-to-tower')) {
      objectiveMode = 'dispatch-lanes'
      enabledInputs.add('return-to-tower')
      blockedInputs.add('deploy-hero')
      primaryHint = 'Return to the tower and wait out cooldown'
    } else if (
      openPanel === 'tower'
      || hasTag('tower-focus')
      || hasTag('population-focus')
      || invokedActionIds.has('upgrade-tower-stat')
      || objectiveDirective?.phase === 'tower-management'
    ) {
      objectiveMode = 'manage-tower'
      openPanel = 'tower'
      enabledInputs.add('open-tower-menu')
      enabledInputs.add('upgrade-tower-stat')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      primaryHint = hasTag('mana-focus')
        ? 'Upgrade mana when the bar is full'
        : hasTag('population-focus')
          ? 'Increase population before unit cap blocks production'
          : 'Open the tower panel'
    } else if (
      openPanel === 'skill'
      || hasTag('skill-focus')
      || invokedActionIds.has('cast-skill')
      || objectiveDirective?.phase === 'skill-burst'
    ) {
      objectiveMode = 'cast-skills'
      openPanel = 'skill'
      enabledInputs.add('open-skill-menu')
      enabledInputs.add('cast-skill')
      blockedInputs.add('use-item')
      primaryHint = invokedActionIds.has('cast-skill')
        ? 'Use a skill from the visible skill window'
        : 'Open the skill panel'
    } else if (
      openPanel === 'item'
      || hasTag('item-focus')
      || invokedActionIds.has('use-item')
    ) {
      objectiveMode = 'use-items'
      openPanel = 'item'
      enabledInputs.add('open-item-menu')
      enabledInputs.add('use-item')
      blockedInputs.add('cast-skill')
      primaryHint = 'Use an equipped item from the item panel'
    } else if (
      hasTag('quest-focus')
      || objectiveDirective?.phase === 'quest-resolution'
      || questState !== 'hidden'
    ) {
      objectiveMode = 'review-quests'
      openPanel = 'system'
      enabledInputs.add('open-system-menu')
      enabledInputs.add('review-quest-rewards')
      primaryHint = 'Review quest rewards from the quest panel'
    } else if (
      openPanel === 'system'
      || hasTag('system-focus')
      || hasTag('transition-preset')
      || hasTag('layout-preset')
    ) {
      objectiveMode = 'system-navigation'
      openPanel = 'system'
      enabledInputs.add('open-system-menu')
      enabledInputs.add('resume-battle')
      enabledInputs.add('open-settings')
      primaryHint = 'Use the system menu for pause, resume, and settings'
    } else if (hudState.highlightedUnitCardIndex !== null) {
      objectiveMode = 'produce-units'
    } else if (hudState.dispatchArrowsHighlighted) {
      objectiveMode = 'dispatch-lanes'
    }

    if (objectiveMode === 'dispatch-lanes' && hudState.selectedDispatchLane) {
      primaryHint = `${hudState.selectedDispatchLane} lane armed${hudState.queuedUnitCount > 0 ? ` with ${hudState.queuedUnitCount} queued unit${hudState.queuedUnitCount > 1 ? 's' : ''}` : ''}`
    } else if (objectiveMode === 'produce-units' && hudState.queuedUnitCount > 0) {
      primaryHint = `${hudState.queuedUnitCount} queued unit${hudState.queuedUnitCount > 1 ? 's' : ''} ready for dispatch`
    } else if (objectiveMode === 'cast-skills' && hudState.skillCooldownRatio > 0.02) {
      primaryHint = 'Skill channel is cooling down'
    } else if (objectiveMode === 'use-items' && hudState.itemCooldownRatio > 0.02) {
      primaryHint = 'Item slot is cooling down'
    }

    if (this.battlePaused) {
      mode = hasTutorialSource || stepDirectives.length > 0 ? 'guided-preview' : 'free-preview'
      openPanel = 'system'
      objectiveMode = 'worldmap-selection'
      primaryHint = 'Battle paused; choose an unlocked campaign node or resume the battle'
      enabledInputs.clear()
      enabledInputs.add('resume-battle')
      enabledInputs.add('open-settings')
      enabledInputs.add('open-system-menu')
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('deploy-hero')
      blockedInputs.add('toggle-hero-sortie')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      blockedInputs.add('upgrade-tower-stat')
    }

    if (!this.battlePaused) {
      if (heroMode === 'field') {
        enabledInputs.add('hero-combat-active')
      }
      if (heroMode === 'return-cooldown') {
        blockedInputs.add('deploy-hero')
      }
      if (hudState.skillCooldownRatio > 0.02) {
        blockedInputs.add('cast-skill')
      } else if (objectiveMode === 'cast-skills' || openPanel === 'skill') {
        enabledInputs.add('cast-skill')
      }
      if (hudState.itemCooldownRatio > 0.02) {
        blockedInputs.add('use-item')
      } else if (objectiveMode === 'use-items' || openPanel === 'item') {
        enabledInputs.add('use-item')
      }
      if (questState === 'reward-ready') {
        enabledInputs.add('claim-quest-reward')
      }
      if (mode === 'free-preview' && enabledInputs.size === 0) {
        enabledInputs.add('observe-stage-preview')
      }
    }

    if (this.campaignScenePhase === 'title') {
      mode = 'guided-preview'
      openPanel = 'system'
      objectiveMode = 'title-screen'
      primaryHint = 'Press Enter to open the recovered main menu.'
      enabledInputs.clear()
      blockedInputs.clear()
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('deploy-hero')
      blockedInputs.add('toggle-hero-sortie')
      blockedInputs.add('return-to-tower')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      blockedInputs.add('upgrade-tower-stat')
      enabledInputs.add('observe-stage-preview')
    } else if (this.campaignScenePhase === 'main-menu') {
      const selectedMenu = this.campaignMenuEntries()[clamp(this.campaignMenuIndex, 0, Math.max(this.campaignMenuEntries().length - 1, 0))]
      mode = 'guided-preview'
      openPanel = 'system'
      objectiveMode = 'main-menu'
      primaryHint = selectedMenu
        ? `${selectedMenu.label}. ${selectedMenu.description}`
        : 'Choose a campaign route from the recovered main menu.'
      enabledInputs.clear()
      blockedInputs.clear()
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('deploy-hero')
      blockedInputs.add('toggle-hero-sortie')
      blockedInputs.add('return-to-tower')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      blockedInputs.add('upgrade-tower-stat')
      enabledInputs.add('observe-stage-preview')
      enabledInputs.add('open-system-menu')
    } else if (this.campaignScenePhase === 'worldmap') {
      const selectedLoadout = this.resolveSelectedDeployLoadout(this.storyboards[clamp(this.campaignSelectedNodeIndex, 0, Math.max(this.campaignUnlockedStageCount, 1) - 1)] ?? this.storyboards[0])
      mode = 'guided-preview'
      openPanel = 'system'
      objectiveMode = 'worldmap-selection'
      primaryHint = `Worldmap open. Select a node and loadout${selectedLoadout ? ` (${selectedLoadout.label})` : ''}, or wait for deploy briefing.`
      enabledInputs.clear()
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('deploy-hero')
      blockedInputs.add('toggle-hero-sortie')
      blockedInputs.add('return-to-tower')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      blockedInputs.add('upgrade-tower-stat')
      enabledInputs.add('observe-stage-preview')
      enabledInputs.add('open-system-menu')
    } else if (this.campaignScenePhase === 'deploy-briefing') {
      const selectedLoadout = this.resolveSelectedDeployLoadout(this.storyboards[clamp(this.campaignSelectedNodeIndex, 0, Math.max(this.campaignUnlockedStageCount, 1) - 1)] ?? this.storyboards[0])
      mode = 'guided-preview'
      openPanel = 'system'
      objectiveMode = 'deploy-briefing'
      primaryHint = `Deploy briefing active. ${selectedLoadout?.heroRosterLabel ?? 'Core Squad'} with ${selectedLoadout?.skillPresetLabel ?? 'Balanced Kit'} and ${selectedLoadout?.towerPolicyLabel ?? 'Balanced Towers'} is queued.`
      enabledInputs.clear()
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('deploy-hero')
      blockedInputs.add('toggle-hero-sortie')
      blockedInputs.add('return-to-tower')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      blockedInputs.add('upgrade-tower-stat')
      enabledInputs.add('observe-stage-preview')
      enabledInputs.add('open-system-menu')
    } else if (this.campaignScenePhase === 'reward-review') {
      mode = 'guided-preview'
      openPanel = 'system'
      objectiveMode = 'reward-review'
      questState = this.questRewardClaimed ? 'available' : 'reward-ready'
      primaryHint = this.questRewardClaimed
        ? 'Reward reviewed. Press Enter to continue to the next unlock reveal.'
        : 'Reward review active. Claim the payout or press Enter to continue.'
      enabledInputs.clear()
      blockedInputs.clear()
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('deploy-hero')
      blockedInputs.add('toggle-hero-sortie')
      blockedInputs.add('return-to-tower')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      blockedInputs.add('upgrade-tower-stat')
      enabledInputs.add('open-system-menu')
      enabledInputs.add('review-quest-rewards')
      if (!this.questRewardClaimed) {
        enabledInputs.add('claim-quest-reward')
      }
    } else if (this.campaignScenePhase === 'unlock-reveal') {
      mode = 'guided-preview'
      openPanel = 'system'
      objectiveMode = 'unlock-reveal'
      primaryHint = this.currentUnlockRevealLabel() ?? 'Next campaign node unlocked. Press Enter to open the world map.'
      enabledInputs.clear()
      blockedInputs.clear()
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('deploy-hero')
      blockedInputs.add('toggle-hero-sortie')
      blockedInputs.add('return-to-tower')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      blockedInputs.add('upgrade-tower-stat')
      enabledInputs.add('observe-stage-preview')
      enabledInputs.add('open-system-menu')
    } else if (this.battleResolutionOutcome) {
      mode = 'guided-preview'
      openPanel = 'system'
      enabledInputs.clear()
      blockedInputs.add('dispatch-up-lane')
      blockedInputs.add('dispatch-down-lane')
      blockedInputs.add('produce-unit')
      blockedInputs.add('deploy-hero')
      blockedInputs.add('toggle-hero-sortie')
      blockedInputs.add('return-to-tower')
      blockedInputs.add('cast-skill')
      blockedInputs.add('use-item')
      blockedInputs.add('upgrade-tower-stat')
      if (this.battleResolutionOutcome === 'victory') {
        objectiveMode = 'review-quests'
        questState = this.questRewardClaimed ? 'available' : 'reward-ready'
        primaryHint = 'Stage clear. Claim the reward or wait for the worldmap transition.'
        enabledInputs.add('open-system-menu')
        enabledInputs.add('review-quest-rewards')
        if (!this.questRewardClaimed) {
          enabledInputs.add('claim-quest-reward')
        }
      } else {
        objectiveMode = 'system-navigation'
        questState = 'hidden'
        primaryHint = 'Tower breached. Result hold will return you to the current node route.'
        enabledInputs.add('open-system-menu')
        enabledInputs.add('observe-stage-preview')
      }
    }

    return {
      mode,
      openPanel,
      heroMode,
      objectiveMode,
      questState,
      selectedDispatchLane: hudState.selectedDispatchLane,
      queuedUnitCount: hudState.queuedUnitCount,
      battlePaused: hudState.battlePaused,
      towerUpgradeLevels: { ...hudState.towerUpgradeLevels },
      skillReady: hudState.skillCooldownRatio <= 0.02,
      itemReady: hudState.itemCooldownRatio <= 0.02,
      questRewardClaims: hudState.questRewardClaims,
      enabledInputs: Array.from(enabledInputs),
      blockedInputs: Array.from(blockedInputs),
      primaryHint,
      scriptedBeatNote: this.lastScriptedBeatNote,
      lastActionId: this.lastActionId,
      lastActionAccepted: this.lastActionAccepted,
      lastActionNote: this.lastActionNote,
    }
  }

  private resetInteractionState(): void {
    this.panelOverride = null
    this.heroOverrideMode = null
    this.heroReturnCooldownEndsAtMs = 0
    this.battlePaused = false
    this.pauseStartedAtMs = 0
    this.questRewardClaimed = false
    this.questRewardClaims = 0
    this.selectedDispatchLane = null
    this.queuedUnitCount = 0
    this.previewManaRatio = 0.48
    this.previewManaUpgradeProgressRatio = 0.22
    this.alliedManaValue = 0
    this.enemyManaValue = 0
    this.manaCapacityValue = this.battleModel?.resourceRules.manaCapacity ?? 100
    this.enemyManaCapacityValue = this.battleModel?.resourceRules.enemyManaCapacity ?? 110
    this.populationCapacity = this.battleModel?.resourceRules.populationBase ?? 7
    this.enemyPopulationCapacity = this.battleModel?.resourceRules.enemyPopulationBase ?? 8
    this.previewOwnTowerHpRatio = 0.74
    this.previewEnemyTowerHpRatio = 0.58
    this.skillCooldownEndsAtMs = 0
    this.itemCooldownEndsAtMs = 0
    this.heroAssignedLane = null
    this.currentObjectivePhase = 'opening'
    this.currentObjectiveLabel = 'stabilize the opening lane'
    this.currentWaveIndex = 1
    this.enemyWaveCursor = 1
    this.alliedWaveCursor = 1
    this.enemyWavesDispatched = 0
    this.alliedWavesDispatched = 0
    this.totalWaveCount = 4
    this.objectiveProgressRatio = 0.08
    this.enemyWaveCountdownBeats = 4
    this.alliedWaveCountdownBeats = 5
    this.enemyWavePlan = []
    this.alliedWavePlan = []
    this.battleResolutionOutcome = null
    this.battleResolutionReason = null
    this.battleResolutionAutoAdvanceAtMs = 0
    this.towerUpgradeLevels.mana = 1
    this.towerUpgradeLevels.population = 1
    this.towerUpgradeLevels.attack = 1
    this.lastScriptedBeatNote = null
    this.lastActionId = null
    this.lastActionAccepted = false
    this.lastActionNote = null
    this.campaignScenePhase = 'battle'
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = 0
  }

  private pickLeadHeroTemplate(): RecoveryBattleHeroTemplate | null {
    const members = this.activeDeployLoadout?.heroRosterMembers ?? []
    for (const member of members) {
      const heroTemplate = this.heroTemplateForMember(member)
      if (heroTemplate) {
        return heroTemplate
      }
    }
    return null
  }

  private pickSkillTemplate(): RecoveryBattleSkillTemplate | null {
    const heroTemplate = this.pickLeadHeroTemplate()
    const preferredKinds = [
      this.activeDeployLoadout?.skillPresetKind ?? 'balanced',
      heroTemplate?.memberRole === 'caster' ? 'burst' : null,
      heroTemplate?.memberRole === 'support' ? 'support' : null,
      'balanced',
    ].filter((value): value is RecoveryBattleSkillTemplate['kind'] => Boolean(value))

    for (const kind of preferredKinds) {
      for (const skillName of heroTemplate?.preferredSkillNames ?? []) {
        const template = this.skillTemplatesByName.get(skillName.toLowerCase())
        if (template && template.kind === kind) {
          return template
        }
      }
    }

    for (const skillName of heroTemplate?.preferredSkillNames ?? []) {
      const template = this.skillTemplatesByName.get(skillName.toLowerCase())
      if (template) {
        return template
      }
    }

    return this.battleModel?.skillTemplates[0] ?? null
  }

  private pickItemTemplate(): RecoveryBattleItemTemplate | null {
    const heroTemplate = this.pickLeadHeroTemplate()
    const preferredKinds = [
      this.activeDeployLoadout?.towerPolicyKind === 'mana-first' ? 'mana' : null,
      this.activeDeployLoadout?.towerPolicyKind === 'attack-first' ? 'burst' : null,
      this.activeDeployLoadout?.heroRosterRole === 'support' ? 'heal' : null,
      'support',
      'utility',
    ].filter((value): value is RecoveryBattleItemTemplate['kind'] => Boolean(value))

    for (const kind of preferredKinds) {
      for (const itemName of heroTemplate?.preferredItemNames ?? []) {
        const template = this.itemTemplatesByName.get(itemName.toLowerCase())
        if (template && template.kind === kind) {
          return template
        }
      }
    }

    for (const itemName of heroTemplate?.preferredItemNames ?? []) {
      const template = this.itemTemplatesByName.get(itemName.toLowerCase())
      if (template) {
        return template
      }
    }

    return this.battleModel?.itemTemplates[0] ?? null
  }

  private applySkillAction(nowMs: number): void {
    const skillTemplate = this.pickSkillTemplate()
    const activeLoadout = this.activeDeployLoadout
    if (!skillTemplate) {
      this.lastActionNote = 'no runtime skill template available'
      return
    }
    if (!this.spendMana('allied', skillTemplate.manaCost)) {
      this.lastActionNote = `${skillTemplate.name} blocked by mana`
      return
    }

    const skillCooldownBase = this.battleModel?.resourceRules.skillCooldownBaseBeats ?? 5
    this.skillCooldownEndsAtMs = nowMs + Math.max(skillTemplate.cooldownBeats, skillCooldownBase) * 120
    const targetLane = this.heroAssignedLane ?? this.selectedDispatchLane ?? this.currentStageBattleProfile.favoredLane ?? 'upper'
    const oppositeLane = targetLane === 'upper' ? 'lower' : 'upper'
    this.createEffect('allied', targetLane, 0.54, skillTemplate.effectTemplateId, skillTemplate.kind, 1)

    switch (skillTemplate.kind) {
      case 'burst':
        this.strikeLaneUnits(targetLane, 'enemy', 0.24 * skillTemplate.powerScale + this.currentStageBattleProfile.armageddonBurst * 0.32, 2)
        this.damageTower('enemy', 0.018 * skillTemplate.powerScale)
        this.spawnBattleUnit('allied', targetLane, 'skill-window', `skill:${skillTemplate.name}`, {
          powerScale: skillTemplate.powerScale,
        })
        break
      case 'support':
        this.supportLaneUnits(targetLane, 'allied', 0.2 * skillTemplate.powerScale)
        this.repairTower('allied', 0.04 * skillTemplate.powerScale)
        break
      case 'orders':
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 2, this.battleModel?.resourceRules.queueCapacity ?? 6)
        this.spawnBattleUnit('allied', targetLane, 'push', `skill:${skillTemplate.name}`, {
          powerScale: 1 + this.currentStageBattleProfile.dispatchBoost,
        })
        break
      case 'utility':
        this.strikeLaneUnits(oppositeLane, 'enemy', 0.12 * skillTemplate.powerScale, 1)
        this.shiftLaneUnits(targetLane, 'allied', 0.03)
        this.restoreMana('allied', this.manaCapacityValue * 0.05)
        break
      default:
        this.spawnBattleUnit('allied', targetLane, 'support', `skill:${skillTemplate.name}`, {
          powerScale: 1.02,
        })
        break
    }

    if (this.loadoutHasMember(activeLoadout, 'Juno')) {
      this.restoreMana('allied', this.manaCapacityValue * 0.06)
      this.skillCooldownEndsAtMs = Math.max(this.skillCooldownEndsAtMs - 240, nowMs)
    }
    if (this.loadoutHasMember(activeLoadout, 'Manos')) {
      this.strikeLaneUnits(targetLane, 'enemy', 0.14, 1)
    }
    if (this.loadoutHasMember(activeLoadout, 'Helba')) {
      this.supportLaneUnits(targetLane, 'allied', 0.12)
    }
    this.lastActionNote = `skill cast ${skillTemplate.name}`
    this.emitAudioCue('battle', 'cast-skill', 0.36)
  }

  private applyItemAction(nowMs: number): void {
    const itemTemplate = this.pickItemTemplate()
    const activeLoadout = this.activeDeployLoadout
    if (!itemTemplate) {
      this.lastActionNote = 'no runtime item template available'
      return
    }
    const resourceCost = Math.min(itemTemplate.cost / 12, this.manaCapacityValue * 0.3)
    if (!this.spendMana('allied', resourceCost)) {
      this.lastActionNote = `${itemTemplate.name} blocked by resource cost`
      return
    }

    const itemCooldownBase = this.battleModel?.resourceRules.itemCooldownBaseBeats ?? 6
    this.itemCooldownEndsAtMs = nowMs + Math.max(itemTemplate.cooldownBeats, itemCooldownBase) * 120
    const targetLane = this.currentStageBattleProfile.favoredLane ?? this.selectedDispatchLane ?? 'upper'
    this.createEffect('allied', targetLane, 0.34, itemTemplate.effectTemplateId, itemTemplate.kind, 1)

    switch (itemTemplate.kind) {
      case 'heal':
      case 'support':
        this.supportLaneUnits(targetLane, 'allied', 0.22 * itemTemplate.powerScale)
        this.repairTower('allied', 0.06 * itemTemplate.powerScale)
        break
      case 'burst':
        this.strikeLaneUnits(targetLane, 'enemy', 0.26 * itemTemplate.powerScale, 2)
        this.damageTower('enemy', 0.012 * itemTemplate.powerScale)
        break
      case 'mana':
        this.restoreMana('allied', this.manaCapacityValue * 0.16)
        break
      case 'orders':
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 2, this.battleModel?.resourceRules.queueCapacity ?? 6)
        this.spawnBattleUnit('allied', targetLane, 'tower-rally', `item:${itemTemplate.name}`, {
          powerScale: 1.06,
        })
        break
      default:
        this.shiftLaneUnits(targetLane, 'allied', 0.024)
        this.strikeLaneUnits(targetLane, 'enemy', 0.1 * itemTemplate.powerScale, 1)
        break
    }

    if (this.loadoutHasMember(activeLoadout, 'Rogan')) {
      this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, this.battleModel?.resourceRules.queueCapacity ?? 6)
    }
    if (this.loadoutHasMember(activeLoadout, 'Caesar')) {
      this.supportLaneUnits(targetLane, 'allied', 0.12)
    }
    this.lastActionNote = `item used ${itemTemplate.name}`
    this.emitAudioCue('battle', 'use-item', 0.28)
  }

  private applyAction(actionId: RecoveryGameplayActionId, snapshot: RecoveryStageSnapshot): void {
    const gameplayState = snapshot.gameplayState
    const nowMs = this.lastUpdateNowMs
    switch (actionId) {
      case 'open-tower-menu':
        this.panelOverride = 'tower'
        this.lastActionNote = 'tower panel opened'
        this.emitAudioCue('ui', 'panel-tower', 0.18)
        break
      case 'open-skill-menu':
        this.panelOverride = 'skill'
        this.lastActionNote = 'skill panel opened'
        this.emitAudioCue('ui', 'panel-skill', 0.18)
        break
      case 'open-item-menu':
        this.panelOverride = 'item'
        this.lastActionNote = 'item panel opened'
        this.emitAudioCue('ui', 'panel-item', 0.18)
        break
      case 'open-system-menu':
      case 'open-settings':
        this.panelOverride = 'system'
        this.setBattlePaused(nowMs, true)
        this.lastActionNote = actionId === 'open-settings' ? 'settings route selected' : 'system panel opened'
        this.emitAudioCue('ui', actionId === 'open-settings' ? 'panel-settings' : 'panel-system', 0.2)
        break
      case 'resume-battle':
        this.panelOverride = null
        this.setBattlePaused(nowMs, false)
        this.lastActionNote = 'panel closed, battle resumed'
        this.emitAudioCue('ui', 'resume-battle', 0.16)
        break
      case 'upgrade-tower-stat':
        this.panelOverride = 'tower'
        this.applyTowerUpgrade(snapshot)
        break
      case 'cast-skill':
        this.panelOverride = 'skill'
        this.applySkillAction(nowMs)
        break
      case 'use-item':
        this.panelOverride = 'item'
        this.applyItemAction(nowMs)
        break
      case 'dispatch-up-lane':
        this.commitLaneDispatch('upper')
        break
      case 'dispatch-down-lane':
        this.commitLaneDispatch('lower')
        break
      case 'produce-unit':
        {
        const activeLoadout = this.activeDeployLoadout
        const hasRogan = this.loadoutHasMember(activeLoadout, 'Rogan')
        const hasVincent = this.loadoutHasMember(activeLoadout, 'Vincent')
        const pushTemplate = this.resolveUnitTemplate('allied', 'push')
        const queueCapacity = this.battleModel?.resourceRules.queueCapacity ?? 6
        const canQueue =
          this.queuedUnitCount < queueCapacity
          && (!!pushTemplate ? this.remainingPopulation('allied') >= pushTemplate.populationCost : true)
          && (!!pushTemplate ? this.spendMana('allied', pushTemplate.manaCost) : this.consumeManaRatio(0.16))
        if (!canQueue) {
          this.lastActionNote = 'unit production blocked by mana or population'
          break
        }
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, queueCapacity)
        this.applyUpgradeProgressDelta(0.08)
        if (hasRogan) {
          this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, queueCapacity)
        }
        if (hasVincent && this.selectedDispatchLane) {
          this.spawnBattleUnit('allied', this.selectedDispatchLane, 'screen', 'vincent-production', {
            powerScale: 1.08,
            initialPositionRatio: 0.1,
          })
        }
        this.lastActionNote = `unit production preview accepted${activeLoadout ? ` (${activeLoadout.heroRosterLabel})` : ''}`
        this.emitAudioCue('battle', 'produce-unit', 0.22)
        }
        break
      case 'deploy-hero':
      case 'toggle-hero-sortie':
        {
          const activeLoadout = this.activeDeployLoadout
          const hasVincent = this.loadoutHasMember(activeLoadout, 'Vincent')
          const hasJuno = this.loadoutHasMember(activeLoadout, 'Juno')
          const hasManos = this.loadoutHasMember(activeLoadout, 'Manos')
          const hasCaesar = this.loadoutHasMember(activeLoadout, 'Caesar')
        if (gameplayState.heroMode === 'field') {
          this.heroOverrideMode = 'return-cooldown'
          this.heroReturnCooldownEndsAtMs = nowMs + HERO_RETURN_COOLDOWN_MS
          this.clearHeroUnits()
          this.heroAssignedLane = null
          this.repairTower('allied', 0.04 + (activeLoadout?.heroRosterRole === 'support' ? 0.03 : 0))
          this.lastActionNote = `hero returned to tower (${activeLoadout?.heroRosterLabel ?? 'core squad'})`
        } else {
          this.heroOverrideMode = 'field'
          this.heroReturnCooldownEndsAtMs = 0
          this.heroAssignedLane = activeLoadout?.heroLane ?? this.selectedDispatchLane ?? 'upper'
          this.ensureHeroUnit(this.heroAssignedLane, activeLoadout?.heroRosterMembers[0] ?? null, 'hero-deploy')
          this.damageTower(
            'enemy',
            0.04
            + (activeLoadout?.heroRosterRole === 'raider' ? 0.03 : activeLoadout?.heroRosterRole === 'vanguard' ? 0.02 : 0),
          )
          if ((activeLoadout?.heroRosterRole === 'defender' || activeLoadout?.heroRosterRole === 'support') && this.heroAssignedLane) {
            this.supportLaneUnits(this.heroAssignedLane, 'allied', 0.2)
          }
          if (hasVincent && this.heroAssignedLane) {
            this.shiftLaneUnits(this.heroAssignedLane, 'allied', 0.04)
          }
          if (hasJuno) {
            this.skillCooldownEndsAtMs = Math.max(this.skillCooldownEndsAtMs - 240, nowMs)
          }
          if (hasManos) {
            this.damageTower('enemy', 0.02)
          }
          if (hasCaesar && this.heroAssignedLane) {
            this.spawnBattleUnit('allied', this.heroAssignedLane, 'screen', 'caesar-escort', {
              powerScale: 1.06,
            })
          }
          this.lastActionNote = `hero deployed to ${this.heroAssignedLane} lane (${activeLoadout?.heroRosterLabel ?? 'core squad'})`
          this.emitAudioCue('battle', 'hero-deploy', 0.34)
        }
        }
        break
      case 'return-to-tower':
        {
          const activeLoadout = this.activeDeployLoadout
          const hasHelba = this.loadoutHasMember(activeLoadout, 'Helba')
          const hasCaesar = this.loadoutHasMember(activeLoadout, 'Caesar')
        this.heroOverrideMode = 'return-cooldown'
        this.heroReturnCooldownEndsAtMs = nowMs + HERO_RETURN_COOLDOWN_MS
        if (this.heroAssignedLane) {
          if (this.currentStageBattleProfile.recallSwing > 0.1) {
            this.spawnBattleUnit('allied', this.heroAssignedLane, 'support', 'recall-swing', {
              powerScale: 1 + this.currentStageBattleProfile.recallSwing,
            })
            this.shiftLaneUnits(this.heroAssignedLane, 'allied', -this.currentStageBattleProfile.recallSwing * 0.09)
          }
        }
        this.clearHeroUnits()
        this.heroAssignedLane = null
        this.repairTower('allied', 0.04 + (activeLoadout?.heroRosterRole === 'support' ? 0.04 : 0) + (hasHelba ? 0.02 : 0))
        if (hasCaesar) {
          const guardLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
          this.supportLaneUnits(guardLane, 'allied', 0.12)
        }
        this.lastActionNote = `hero return cooldown started (${activeLoadout?.heroRosterLabel ?? 'core squad'})`
        this.emitAudioCue('battle', 'hero-return', 0.24)
        }
        break
      case 'review-quest-rewards':
        this.panelOverride = 'system'
        this.setBattlePaused(nowMs, true)
        this.lastActionNote = 'quest reward panel reviewed'
        break
      case 'claim-quest-reward':
        this.panelOverride = 'system'
        this.claimQuestRewardPayout()
        this.lastActionNote = 'quest reward claimed'
        this.emitAudioCue('result', 'reward-claim', 0.28)
        break
      default:
        this.lastActionNote = `${actionId} accepted`
        break
    }

    this.rebuildLaneBattleState()
  }

  private claimQuestRewardPayout(): void {
    if (this.questRewardClaimed) {
      return
    }
    this.questRewardClaimed = true
    this.questRewardClaims += 1
    this.restoreMana('allied', this.manaCapacityValue * 0.18)
    this.applyUpgradeProgressDelta(0.16)
  }

  private applyScriptedAction(actionId: RecoveryGameplayActionId, note: string): boolean {
    const snapshot = this.getSnapshot()
    if (!snapshot) {
      return false
    }
    const accepted =
      snapshot.gameplayState.enabledInputs.includes(actionId)
      && !snapshot.gameplayState.blockedInputs.includes(actionId)
    if (!accepted) {
      return false
    }

    const previousActionNote = this.lastActionNote
    this.applyAction(actionId, snapshot)
    this.lastActionNote = previousActionNote
    this.lastScriptedBeatNote = note
    return true
  }

  private applyScriptedActionChain(
    actionIds: RecoveryGameplayActionId[],
    note: string,
  ): boolean {
    const applied: RecoveryGameplayActionId[] = []

    actionIds.forEach((actionId) => {
      if (this.applyScriptedAction(actionId, note)) {
        applied.push(actionId)
      }
    })

    if (applied.length === 0) {
      return false
    }

    this.lastScriptedBeatNote = `${note} [${applied.join(' -> ')}]`
    return true
  }

  private triggerRosterActionChain(
    members: string[],
    lane: 'upper' | 'lower' | null,
    actionIds: RecoveryGameplayActionId[],
    note: string,
    emphasis: 'assault' | 'flank' | 'hold' | 'mana',
  ): boolean {
    if (!this.applyScriptedActionChain(actionIds, note)) {
      return false
    }

    this.rosterChainFocusLane = lane
    members.forEach((member) => {
      const current = this.rosterChainBoosts[member] ?? 0
      this.rosterChainBoosts[member] = clamp(current + 0.32, 0, 1)
    })

    const targetLane = lane ?? this.currentStageBattleProfile.favoredLane ?? 'upper'
    const oppositeLane = targetLane === 'upper' ? 'lower' : 'upper'
    switch (emphasis) {
      case 'assault':
        this.spawnBattleUnit('allied', targetLane, 'push', `chain:${members.join('+')}:assault`, {
          powerScale: 1.18,
          durabilityScale: 1.08,
        })
        this.shiftLaneUnits(targetLane, 'allied', 0.05)
        this.damageTower('enemy', 0.035)
        this.heroAssignedLane = targetLane
        this.ensureHeroUnit(targetLane, members[0] ?? null, `chain:${members.join('+')}:hero`)
        break
      case 'flank':
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, 5)
        this.spawnBattleUnit('allied', targetLane, 'push', `chain:${members.join('+')}:flank`, {
          powerScale: 1.12,
        })
        this.spawnBattleUnit('allied', targetLane, 'screen', `chain:${members.join('+')}:flank-screen`, {
          powerScale: 1.04,
        })
        this.strikeLaneUnits(oppositeLane, 'enemy', 0.12, 1)
        break
      case 'hold':
        this.repairTower('allied', 0.04)
        this.strikeLaneUnits(targetLane, 'enemy', 0.14, 2)
        this.supportLaneUnits(targetLane, 'allied', 0.16)
        break
      case 'mana':
        this.restoreMana('allied', this.manaCapacityValue * 0.08)
        this.applyUpgradeProgressDelta(0.06)
        this.spawnBattleUnit('allied', targetLane, 'skill-window', `chain:${members.join('+')}:mana`, {
          powerScale: 1.1,
        })
        break
    }

    this.rebuildLaneBattleState()
    this.lastScriptedBeatNote = `${note} [${members.join('+')} ${emphasis}]`
    return true
  }

  private cooldownRatio(endsAtMs: number, totalMs: number): number {
    if (totalMs <= 0 || endsAtMs <= 0) {
      return 0
    }
    return clamp((endsAtMs - this.lastUpdateNowMs) / totalMs, 0, 1)
  }

  private shiftTimelineBy(deltaMs: number): void {
    this.storyboardStartedAtMs += deltaMs
    this.nextDialogueAtMs += deltaMs
    this.nextFrameAtMs += deltaMs
    if (this.heroReturnCooldownEndsAtMs > 0) {
      this.heroReturnCooldownEndsAtMs += deltaMs
    }
    if (this.skillCooldownEndsAtMs > 0) {
      this.skillCooldownEndsAtMs += deltaMs
    }
    if (this.itemCooldownEndsAtMs > 0) {
      this.itemCooldownEndsAtMs += deltaMs
    }
  }

  private setBattlePaused(nowMs: number, paused: boolean): void {
    if (paused) {
      if (!this.battlePaused) {
        this.battlePaused = true
        this.pauseStartedAtMs = nowMs
      }
      return
    }

    if (!this.battlePaused) {
      return
    }

    const pausedDurationMs = this.pauseStartedAtMs > 0 ? Math.max(nowMs - this.pauseStartedAtMs, 0) : 0
    if (pausedDurationMs > 0) {
      this.shiftTimelineBy(pausedDurationMs)
    }
    this.battlePaused = false
    this.pauseStartedAtMs = 0
  }

  private applyAiAction(actionId: RecoveryGameplayActionId, note: string): boolean {
    const snapshot = this.getSnapshot()
    if (!snapshot) {
      return false
    }
    const previousActionNote = this.lastActionNote
    this.applyAction(actionId, snapshot)
    this.lastActionNote = previousActionNote
    this.lastScriptedBeatNote = note
    return true
  }

  private tickBattleAi(): void {
    const beat = Math.max(this.lastChannelBeat, 0)
    const loadout = this.activeDeployLoadout
    const alliedMomentum = (this.laneBattleState.upper.alliedPressure + this.laneBattleState.lower.alliedPressure) / 2
    const enemyMomentum = (this.laneBattleState.upper.enemyPressure + this.laneBattleState.lower.enemyPressure) / 2

    for (const member of loadout?.heroRosterMembers ?? []) {
      const heroTemplate = this.heroTemplateForMember(member)
      if (!heroTemplate) {
        continue
      }
      const lane = this.heroAssignedLane ?? this.selectedDispatchLane ?? this.currentStageBattleProfile.favoredLane ?? 'upper'
      if (beat % heroTemplate.ai.spawnCadenceBeats === heroTemplate.heroId % heroTemplate.ai.spawnCadenceBeats) {
        const pushTemplate = this.resolveUnitTemplate('allied', heroTemplate.memberRole === 'support' ? 'support' : heroTemplate.memberRole === 'guardian' ? 'screen' : 'push')
        if (
          pushTemplate
          && this.queuedUnitCount < (this.battleModel?.resourceRules.queueCapacity ?? 6)
          && this.remainingPopulation('allied') >= pushTemplate.populationCost
          && this.alliedManaValue >= pushTemplate.manaCost
        ) {
          this.applyAiAction('produce-unit', `${member} queued reinforcements`)
        }
      }

      if (
        beat % heroTemplate.ai.skillCadenceBeats === heroTemplate.heroId % heroTemplate.ai.skillCadenceBeats
        && this.lastUpdateNowMs >= this.skillCooldownEndsAtMs
        && enemyMomentum >= 0.2 + heroTemplate.ai.burst * 0.25
      ) {
        this.applyAiAction('cast-skill', `${member} triggered AI skill timing`)
      }

      if (
        beat % heroTemplate.ai.itemCadenceBeats === heroTemplate.heroId % heroTemplate.ai.itemCadenceBeats
        && this.lastUpdateNowMs >= this.itemCooldownEndsAtMs
        && (this.previewOwnTowerHpRatio <= 0.74 || heroTemplate.ai.support >= 0.5)
      ) {
        this.applyAiAction('use-item', `${member} triggered AI support item`)
      }

      if (
        beat % heroTemplate.ai.heroCadenceBeats === heroTemplate.heroId % heroTemplate.ai.heroCadenceBeats
        && this.heroOverrideMode !== 'field'
        && (this.currentObjectivePhase === 'hero-pressure' || this.currentObjectivePhase === 'siege' || heroTemplate.ai.aggression >= 0.6)
      ) {
        this.applyAiAction('deploy-hero', `${member} forced hero sortie`)
      } else if (
        this.heroOverrideMode === 'field'
        && this.heroAssignedLane === lane
        && this.previewOwnTowerHpRatio <= 0.42
        && heroTemplate.ai.support >= 0.4
      ) {
        this.applyAiAction('return-to-tower', `${member} recalled hero under tower threat`)
      }
    }

    if (this.enemyManaValue >= 14 && beat % Math.max(this.currentStageBattleProfile.enemyWaveCadenceBeats - 1, 3) === 1) {
      const enemyLane = this.currentWaveDirective(this.enemyWavePlan, 'enemy')?.laneId ?? this.currentStageBattleProfile.favoredLane ?? 'upper'
      const role: RecoveryBattleWaveDirective['role'] =
        this.currentObjectivePhase === 'siege'
          ? 'siege'
          : this.currentObjectivePhase === 'skill-burst'
            ? 'skill-window'
            : enemyMomentum < alliedMomentum
              ? 'push'
              : 'screen'
      const enemyTemplate = this.resolveUnitTemplate('enemy', role)
      if (enemyTemplate && this.remainingPopulation('enemy') >= enemyTemplate.populationCost && this.spendMana('enemy', enemyTemplate.manaCost)) {
        this.spawnBattleUnit('enemy', enemyLane, role, `enemy-ai:${role}`, {
          powerScale: 1 + this.currentStageBattleProfile.enemyPressureScale * 0.4,
        })
        this.createEffect('enemy', enemyLane, 0.7, enemyTemplate.effectTemplateId, `enemy-${role}`, 0.9)
      }
    }

    if (this.enemyManaValue >= 18 && beat % 6 === 3 && this.previewOwnTowerHpRatio > 0.18) {
      const lane = this.currentStageBattleProfile.favoredLane ?? 'upper'
      if (this.spendMana('enemy', 18)) {
        this.strikeLaneUnits(lane, 'allied', 0.18 + this.currentStageBattleProfile.enemyPressureScale * 0.2, 2)
        this.createEffect('enemy', lane, 0.4, null, 'enemy-burst', 1)
      }
    }
  }

  private tickPersistentPreview(): void {
    Object.keys(this.rosterChainBoosts).forEach((member) => {
      const nextValue = Math.max((this.rosterChainBoosts[member] ?? 0) - 0.06, 0)
      if (nextValue <= 0) {
        delete this.rosterChainBoosts[member]
      } else {
        this.rosterChainBoosts[member] = nextValue
      }
    })
    if (Object.keys(this.rosterChainBoosts).length === 0) {
      this.rosterChainFocusLane = null
    }

    const activeLoadout = this.activeDeployLoadout
    const stageBias = this.deriveCurrentStageScriptBias()
    const hasVincent = this.loadoutHasMember(activeLoadout, 'Vincent')
    const hasRogan = this.loadoutHasMember(activeLoadout, 'Rogan')
    const hasHelba = this.loadoutHasMember(activeLoadout, 'Helba')
    const hasJuno = this.loadoutHasMember(activeLoadout, 'Juno')
    const hasManos = this.loadoutHasMember(activeLoadout, 'Manos')
    const hasCaesar = this.loadoutHasMember(activeLoadout, 'Caesar')
    const manaBonus =
      activeLoadout?.towerPolicyKind === 'mana-first'
        ? 0.01
        : activeLoadout?.skillPresetKind === 'utility'
          ? 0.006
          : 0
    const upgradeBonus =
      activeLoadout?.towerPolicyKind === 'population-first'
        ? 0.01
        : activeLoadout?.heroRosterRole === 'support'
          ? 0.004
          : 0
    const alliedManaRegen =
      (this.battleModel?.resourceRules.manaRegenPerBeat ?? 6)
      + this.manaCapacityValue * manaBonus
      + (hasJuno ? this.manaCapacityValue * (stageBias.manaBias ? 0.007 : 0.004) : 0)
    this.applyUpgradeProgressDelta(
      UPGRADE_PROGRESS_RECOVERY_PER_BEAT
      + upgradeBonus
      + (hasRogan ? (stageBias.dispatchBias ? 0.007 : 0.004) : 0),
    )

    if (this.heroOverrideMode === 'field') {
      this.damageTower(
        'enemy',
        0.004
        + (activeLoadout?.heroRosterRole === 'raider' ? 0.002 : activeLoadout?.heroRosterRole === 'vanguard' ? 0.001 : 0)
        + (hasVincent ? (stageBias.siegeBias || stageBias.heroBias ? 0.0025 : 0.0015) : 0)
        + (hasManos ? (stageBias.siegeBias ? 0.0025 : 0.0015) : 0),
      )
    }

    if (activeLoadout?.heroRosterRole === 'defender' || activeLoadout?.heroRosterRole === 'support') {
      this.repairTower(
        'allied',
        0.002
        + (hasHelba ? (stageBias.sustainBias || stageBias.rewardBias ? 0.0035 : 0.002) : 0)
        + (hasCaesar ? (stageBias.sustainBias ? 0.0025 : 0.0015) : 0),
      )
    }

    if (this.selectedDispatchLane && this.queuedUnitCount > 0 && this.alliedManaValue > this.manaCapacityValue * 0.18) {
      this.damageTower(
        'enemy',
        0.006 + (activeLoadout?.skillPresetKind === 'orders' ? 0.002 : 0),
      )
      if (hasRogan) {
        this.spawnBattleUnit('allied', this.selectedDispatchLane, 'push', 'rogan-tempo', {
          powerScale: 1.04,
        })
      }
      if (hasVincent && stageBias.dispatchBias) {
        this.shiftLaneUnits(this.selectedDispatchLane, 'allied', 0.018)
      }
    }

    this.restoreMana('allied', alliedManaRegen)
    this.restoreMana('enemy', this.battleModel?.resourceRules.enemyManaRegenPerBeat ?? 5)
    this.recalculatePopulationCaps()
    this.tickBattleAi()
    this.tickLaneBattlePreview()
  }

  private applyTowerUpgrade(snapshot: RecoveryStageSnapshot): void {
    const gameplayState = snapshot.gameplayState
    const focusedUpgrade = snapshot.hudState.highlightedTowerUpgradeId
    const towerPolicyKind = this.activeDeployLoadout?.towerPolicyKind ?? 'balanced'
    const upgradeId =
      focusedUpgrade
      ?? (gameplayState.primaryHint.includes('population')
        ? 'population'
        : gameplayState.primaryHint.includes('mana')
          ? 'mana'
          : towerPolicyKind === 'population-first'
            ? (this.towerUpgradeLevels.population <= this.towerUpgradeLevels.mana ? 'population' : 'mana')
            : towerPolicyKind === 'attack-first'
              ? (this.towerUpgradeLevels.attack <= this.towerUpgradeLevels.population ? 'attack' : 'population')
              : towerPolicyKind === 'mana-first'
                ? (this.towerUpgradeLevels.mana <= this.towerUpgradeLevels.population ? 'mana' : 'population')
              : gameplayState.openPanel === 'tower' && this.towerUpgradeLevels.attack < this.towerUpgradeLevels.mana
                  ? 'attack'
                  : 'mana')
    if (!this.spendMana('allied', this.manaCapacityValue * (0.22 - (towerPolicyKind === 'mana-first' ? 0.06 : 0)))) {
      this.lastActionNote = `${upgradeId} upgrade blocked by mana`
      return
    }
    this.towerUpgradeLevels[upgradeId] = Math.min(this.towerUpgradeLevels[upgradeId] + 1, 5)
    this.applyUpgradeProgressDelta(-0.3)
    this.recalculatePopulationCaps()
    this.lastActionNote = `${upgradeId} upgrade advanced to tier ${this.towerUpgradeLevels[upgradeId]} (${this.activeDeployLoadout?.towerPolicyLabel ?? 'balanced towers'})`
    this.emitAudioCue('system', `upgrade-${upgradeId}`, 0.22)
  }

  private commitLaneDispatch(lane: 'upper' | 'lower'): void {
    this.selectedDispatchLane = lane
    if (this.queuedUnitCount > 0) {
      const commitCount = Math.min(
        this.queuedUnitCount,
        this.currentStageBattleProfile.dispatchBoost >= 0.16 ? 3 : 2,
      )
      const pushTemplate = this.resolveUnitTemplate('allied', 'push')
      const allowedCount = pushTemplate
        ? Math.min(commitCount, Math.floor(this.remainingPopulation('allied') / Math.max(pushTemplate.populationCost, 1)))
        : commitCount
      const queueDamage = Math.min(allowedCount * 0.04, 0.16)
      this.damageTower('enemy', queueDamage)
      for (let index = 0; index < allowedCount; index += 1) {
        this.spawnBattleUnit('allied', lane, 'push', 'dispatch-commit', {
          powerScale: 1 + this.currentStageBattleProfile.dispatchBoost * 1.2,
          speedScale: 1.08,
          initialPositionRatio: 0.12 + index * 0.026,
        })
      }
      this.queuedUnitCount = Math.max(this.queuedUnitCount - allowedCount, 0)
      this.recalculatePopulationCaps()
      this.rebuildLaneBattleState()
      this.lastActionNote = `${lane} lane selected with ${allowedCount} unit push`
      this.emitAudioCue('battle', `dispatch-${lane}`, 0.24)
      return
    }
    this.lastActionNote = `${lane} lane primed`
    this.emitAudioCue('battle', `prime-${lane}`, 0.18)
  }

  private seedBattlePreviewState(storyboard: RecoveryStageStoryboard): void {
    Object.keys(this.rosterChainBoosts).forEach((member) => {
      delete this.rosterChainBoosts[member]
    })
    this.rosterChainFocusLane = null
    this.currentStageBattleProfile = this.deriveStageBattleProfile(storyboard)
    this.seedBattleObjectiveState(storyboard)
    this.clearBattleEntities()
    const favoredLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
    const supportLane = favoredLane === 'upper' ? 'lower' : 'upper'

    this.selectedDispatchLane = favoredLane
    this.heroAssignedLane = null
    this.queuedUnitCount = 0

    const favoredAllies = clamp(Math.round(1 + this.currentStageBattleProfile.alliedPressureScale * 8), 1, 4)
    const favoredEnemies = clamp(Math.round(1 + this.currentStageBattleProfile.enemyPressureScale * 8), 1, 5)
    const supportAllies = clamp(Math.round(1 + this.currentStageBattleProfile.alliedPressureScale * 5), 1, 3)
    const supportEnemies = clamp(Math.round(1 + this.currentStageBattleProfile.enemyPressureScale * 5), 1, 4)
    const favoredFrontline = clamp(
      0.48
      + (this.currentStageBattleProfile.alliedPressureScale - this.currentStageBattleProfile.enemyPressureScale) * 0.25
      + (favoredLane === 'upper' ? -0.04 : 0.04),
      0.18,
      0.82,
    )
    const supportFrontline = clamp(1 - favoredFrontline + 0.08, 0.18, 0.82)

    for (let index = 0; index < favoredAllies; index += 1) {
      this.spawnBattleUnit('allied', favoredLane, 'push', 'seed-favored-allied', {
        powerScale: 1 + this.currentStageBattleProfile.alliedPressureScale * 0.8,
        initialPositionRatio: clamp(favoredFrontline - 0.18 - index * 0.035, 0.08, 0.54),
      })
    }
    for (let index = 0; index < favoredEnemies; index += 1) {
      this.spawnBattleUnit('enemy', favoredLane, 'push', 'seed-favored-enemy', {
        powerScale: 1 + this.currentStageBattleProfile.enemyPressureScale * 0.8,
        initialPositionRatio: clamp(favoredFrontline + 0.18 + index * 0.035, 0.46, 0.92),
      })
    }
    for (let index = 0; index < supportAllies; index += 1) {
      this.spawnBattleUnit('allied', supportLane, index === 0 ? 'support' : 'screen', 'seed-support-allied', {
        powerScale: 1 + this.currentStageBattleProfile.alliedPressureScale * 0.55,
        initialPositionRatio: clamp(supportFrontline - 0.16 - index * 0.034, 0.08, 0.54),
      })
    }
    for (let index = 0; index < supportEnemies; index += 1) {
      this.spawnBattleUnit('enemy', supportLane, index === 0 ? 'siege' : 'screen', 'seed-support-enemy', {
        powerScale: 1 + this.currentStageBattleProfile.enemyPressureScale * 0.55,
        initialPositionRatio: clamp(supportFrontline + 0.16 + index * 0.034, 0.46, 0.92),
      })
    }
    this.rebuildLaneBattleState()

    this.manaCapacityValue = this.battleModel?.resourceRules.manaCapacity ?? 100
    this.enemyManaCapacityValue = this.battleModel?.resourceRules.enemyManaCapacity ?? 110
    this.alliedManaValue = clamp(
      (0.32 + this.currentStageBattleProfile.alliedPressureScale * 0.55 - this.currentStageBattleProfile.enemyPressureScale * 0.14)
      * this.manaCapacityValue,
      this.manaCapacityValue * 0.2,
      this.manaCapacityValue * 0.9,
    )
    this.enemyManaValue = clamp(
      (0.34 + this.currentStageBattleProfile.enemyPressureScale * 0.5)
      * this.enemyManaCapacityValue,
      this.enemyManaCapacityValue * 0.24,
      this.enemyManaCapacityValue * 0.92,
    )
    this.setUpgradeProgressRatio(
      clamp(
        0.16 + this.currentStageBattleProfile.alliedPressureScale * 0.34,
        0.08,
        0.92,
      ),
    )
    this.previewOwnTowerHpRatio = clamp(
      0.78 - this.currentStageBattleProfile.enemyPressureScale * 0.22,
      0.28,
      0.95,
    )
    this.previewEnemyTowerHpRatio = clamp(
      0.74 - this.currentStageBattleProfile.alliedPressureScale * 0.2,
      0.22,
      0.92,
    )
    this.recalculatePopulationCaps()
    this.syncResourcePreviewState()
  }

  private seedBattleObjectiveState(storyboard: RecoveryStageStoryboard): void {
    const seed = this.deriveObjectiveSeed(storyboard, this.currentStageBattleProfile)
    this.totalWaveCount = seed.totalWaveCount
    this.currentWaveIndex = 1
    this.enemyWaveCursor = 1
    this.alliedWaveCursor = 1
    this.enemyWavesDispatched = 0
    this.alliedWavesDispatched = 0
    this.objectiveProgressRatio = seed.objectiveProgressRatio
    this.enemyWaveCountdownBeats = seed.enemyWaveCountdownBeats
    this.alliedWaveCountdownBeats = seed.alliedWaveCountdownBeats
    this.enemyWavePlan = seed.enemyWavePlan
    this.alliedWavePlan = seed.alliedWavePlan
    this.currentObjectivePhase = seed.phase
    this.currentObjectiveLabel = seed.label
  }

  private deriveObjectiveSeed(
    storyboard: RecoveryStageStoryboard,
    profile: RecoveryStageBattleProfile,
  ): {
    totalWaveCount: number
    objectiveProgressRatio: number
    enemyWaveCountdownBeats: number
    alliedWaveCountdownBeats: number
    enemyWavePlan: RecoveryBattleWaveDirective[]
    alliedWavePlan: RecoveryBattleWaveDirective[]
    phase: RecoveryBattleObjectiveState['phase']
    label: string
  } {
    const stage = storyboard.stageBlueprint
    const stageTier = stage?.runtimeFields?.tierCandidate ?? 10
    const archetypeCount = stage?.recommendedArchetypeIds.length ?? 0
    const eventCount = Math.max(storyboard.scriptEventCount, storyboard.scriptEvents.length, 1)
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)
    const title = stage?.title ?? storyboard.scriptFamilyId
    const hintText = stage?.hintText ?? ''
    const effectIntensity = stage?.renderIntent?.effectIntensity ?? 'medium'

    const totalWaveCount = clamp(
      Math.round(eventCount / 24)
      + Math.max(Math.round(stageTier / 20), 1)
      + Math.min(archetypeCount, 2)
      + (routeInfluence.matchesPreferred && routeBias.directRoute ? 1 : 0)
      + (routeInfluence.matchesPreferred && routeBias.sustainRoute ? 1 : 0),
      3,
      9,
    )
    const objectiveProgressRatio = clamp(
      0.06
      + (routeBias.flankingRoute ? 0.03 : routeBias.directRoute ? 0.02 : 0.01)
      + Math.max(routeInfluence.pressureDelta, 0) * 0.35
      + (effectIntensity === 'high' ? 0.03 : effectIntensity === 'medium' ? 0.015 : 0),
      0.04,
      0.24,
    )
    const enemyWaveCountdownBeats = Math.max(
      1,
      profile.enemyWaveCadenceBeats
      - (effectIntensity === 'high' ? 1 : 0)
      + Math.max(routeBias.cadenceShift, 0)
      - Math.max(routeInfluence.cadenceDelta, 0),
    )
    const alliedWaveCountdownBeats = Math.max(
      1,
      profile.alliedWaveCadenceBeats + Math.min(routeBias.cadenceShift, 0) + Math.min(routeInfluence.cadenceDelta, 0),
    )
    const enemyWavePlan = this.buildWavePlanForProfile(storyboard, 'enemy', profile, totalWaveCount)
    const alliedWavePlan = this.buildWavePlanForProfile(storyboard, 'allied', profile, totalWaveCount)
    const routeLabel = routeInfluence.matchesPreferred
      ? `${routeBias.routeLabel} committed`
      : routeBias.routeLabel

    if (routeBias.directRoute || includesAny(title, ['defeat', 'siege', 'seize', 'enemy camp'])) {
      return {
        totalWaveCount,
        objectiveProgressRatio,
        enemyWaveCountdownBeats,
        alliedWaveCountdownBeats,
        enemyWavePlan,
        alliedWavePlan,
        phase: 'siege',
        label: `break the enemy defensive line via ${routeLabel}`,
      }
    }
    if (routeBias.flankingRoute || includesAny(hintText, ['hero', 'eliminate'])) {
      return {
        totalWaveCount,
        objectiveProgressRatio,
        enemyWaveCountdownBeats,
        alliedWaveCountdownBeats,
        enemyWavePlan,
        alliedWavePlan,
        phase: 'hero-pressure',
        label: `use the hero to disrupt clustered enemies on the ${routeLabel} route`,
      }
    }
    if (routeBias.sustainRoute || includesAny(hintText, ['bonus', 'reward', 'clear the stage'])) {
      return {
        totalWaveCount,
        objectiveProgressRatio,
        enemyWaveCountdownBeats,
        alliedWaveCountdownBeats,
        enemyWavePlan,
        alliedWavePlan,
        phase: 'lane-control',
        label: `secure lanes before the ${routeLabel} bonus window closes`,
      }
    }

    return {
      totalWaveCount,
      objectiveProgressRatio,
      enemyWaveCountdownBeats,
      alliedWaveCountdownBeats,
      enemyWavePlan,
      alliedWavePlan,
      phase: 'opening',
      label: `stabilize the opening lane on the ${routeLabel} route`,
    }
  }

  private deriveArchetypeSignals(
    archetype: RecoveryRuntimeBlueprint['featuredArchetypes'][number],
  ): Set<string> {
    const signalSet = new Set<string>()
    const haystacks = [
      archetype.label,
      archetype.archetypeKind,
      archetype.familyType,
      ...archetype.mechanicHints,
    ]
    const joined = haystacks.join(' ').toLowerCase()

    if (includesAny(joined, ['dispatch', 'redeploy', 'respawn'])) {
      signalSet.add('dispatch')
    }
    if (includesAny(joined, ['tower defense', 'defend tower', 'barrier'])) {
      signalSet.add('tower-defense')
    }
    if (includesAny(joined, ['recall', 'relocation'])) {
      signalSet.add('recall')
    }
    if (includesAny(joined, ['armageddon', 'meteor'])) {
      signalSet.add('armageddon')
    }
    if (includesAny(joined, ['mana', 'resource-conversion', 'mana gain', 'reactive-mana-proc'])) {
      signalSet.add('mana-surge')
    }
    if (includesAny(joined, ['heal', 'healing'])) {
      signalSet.add('healing')
    }

    return signalSet
  }

  private buildDeployLoadouts(
    storyboard: RecoveryStageStoryboard,
  ): RecoveryStageSnapshot['campaignState']['loadouts'] {
    const profile = this.deriveStageBattleProfile(storyboard)
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)
    const favoredLane = profile.favoredLane ?? 'upper'
    const supportLane = favoredLane === 'upper' ? 'lower' : 'upper'
    const defaultRoster = ['Vincent', 'Helba', 'Juno']
    const archetypes = (storyboard.stageBlueprint?.recommendedArchetypeIds ?? [])
      .map((archetypeId) => this.featuredArchetypesById.get(archetypeId))
      .filter((entry): entry is NonNullable<typeof entry> => entry !== undefined)

    const loadouts: RecoveryStageSnapshot['campaignState']['loadouts'] = [
      {
        loadoutIndex: 1,
        id: 'balanced-vanguard',
        label: 'Balanced Vanguard',
        summary: `${favoredLane} lane stability with one queued unit and neutral tower stance on ${routeBias.routeLabel} / ${routeInfluence.stanceLabel}`,
        recommended: archetypes.length === 0,
        heroRosterLabel:
          routeInfluence.matchesPreferred && routeBias.sustainRoute
            ? 'Committed Hold Squad'
            : routeInfluence.matchesPreferred && routeBias.directRoute
              ? 'Committed Strike Squad'
              : 'Core Squad',
        heroRosterRole:
          routeInfluence.matchesPreferred && routeBias.sustainRoute
            ? 'defender'
            : routeInfluence.matchesPreferred && routeBias.directRoute
              ? 'raider'
              : 'balanced',
        heroRosterMembers:
          routeInfluence.matchesPreferred && routeBias.sustainRoute
            ? ['Helba', 'Caesar', 'Juno']
            : routeInfluence.matchesPreferred && routeBias.directRoute
              ? ['Vincent', 'Manos', 'Rogan']
              : defaultRoster,
        skillPresetLabel:
          routeInfluence.matchesPreferred && routeBias.manaRoute
            ? 'Committed Arcane Kit'
            : routeInfluence.matchesPreferred && routeBias.flankingRoute
              ? 'Committed Orders'
              : 'Balanced Kit',
        skillPresetKind:
          routeInfluence.matchesPreferred && routeBias.manaRoute
            ? 'utility'
            : routeInfluence.matchesPreferred && routeBias.flankingRoute
              ? 'orders'
              : 'balanced',
        towerPolicyLabel:
          routeInfluence.matchesPreferred && routeBias.manaRoute
            ? 'Committed Mana Towers'
            : routeInfluence.matchesPreferred && routeBias.sustainRoute
              ? 'Committed Guard Towers'
              : 'Balanced Towers',
        towerPolicyKind:
          routeInfluence.matchesPreferred && routeBias.manaRoute
            ? 'mana-first'
            : routeInfluence.matchesPreferred && routeBias.sustainRoute
              ? 'attack-first'
              : 'balanced',
        heroStartMode: 'tower',
        heroLane: null,
        dispatchLane: routeInfluence.preferredLane ?? favoredLane,
        openingPanel: null,
        startingQueue: clamp(1 + Math.max(0, Math.round(routeInfluence.queueDelta)), 1, 4),
        startingManaRatio: clamp(0.38 + profile.manaSurge * 0.2 + routeInfluence.manaDelta, 0.24, 0.82),
        startingManaUpgradeProgressRatio: clamp(
          0.18 + profile.dispatchBoost * 0.08 + Math.max(routeInfluence.queueDelta, 0) * 0.03,
          0.08,
          0.62,
        ),
        towerUpgrades: {
          mana: routeInfluence.matchesPreferred && routeBias.manaRoute ? 2 : 1,
          population: routeInfluence.matchesPreferred && routeBias.flankingRoute ? 2 : 1,
          attack: routeInfluence.matchesPreferred && routeBias.sustainRoute ? 2 : 1,
        },
      },
    ]

    archetypes.forEach((archetype) => {
      const signals = this.deriveArchetypeSignals(archetype)
      const towerUpgrades = { mana: 1, population: 1, attack: 1 }
      let heroStartMode: 'tower' | 'field' = 'tower'
      let heroLane: 'upper' | 'lower' | null = null
      let dispatchLane: 'upper' | 'lower' | null = favoredLane
      let openingPanel: 'tower' | 'skill' | 'item' | null = null
      let startingQueue = 1
      let startingManaRatio = 0.34
      let startingManaUpgradeProgressRatio = 0.16
      let heroRosterLabel = 'Core Squad'
      let heroRosterRole: RecoveryStageSnapshot['campaignState']['loadouts'][number]['heroRosterRole'] = 'balanced'
      let heroRosterMembers = defaultRoster
      let skillPresetLabel = 'Balanced Kit'
      let skillPresetKind: RecoveryStageSnapshot['campaignState']['loadouts'][number]['skillPresetKind'] = 'balanced'
      let towerPolicyLabel = 'Balanced Towers'
      let towerPolicyKind: RecoveryStageSnapshot['campaignState']['loadouts'][number]['towerPolicyKind'] = 'balanced'
      const summaryParts: string[] = []

      if (signals.has('dispatch')) {
        startingQueue += routeBias.flankingRoute ? 3 : 2
        dispatchLane = routeBias.preferredLane ?? favoredLane
        heroRosterLabel = 'Forward Vanguard'
        heroRosterRole = 'vanguard'
        heroRosterMembers = ['Vincent', 'Rogan']
        skillPresetLabel = 'Lane Orders'
        skillPresetKind = 'orders'
        towerPolicyLabel = 'Population First'
        towerPolicyKind = 'population-first'
        summaryParts.push(`${dispatchLane ?? favoredLane} lane opening push on ${routeBias.routeLabel}`)
      }
      if (signals.has('tower-defense')) {
        towerUpgrades.attack = 2
        towerUpgrades.population = 2
        openingPanel = 'tower'
        heroRosterLabel = 'Ward Defenders'
        heroRosterRole = 'defender'
        heroRosterMembers = ['Helba', 'Caesar']
        if (skillPresetKind === 'balanced') {
          skillPresetLabel = 'Guard Pulse'
          skillPresetKind = 'support'
        }
        towerPolicyLabel = 'Attack First'
        towerPolicyKind = 'attack-first'
        summaryParts.push(`reinforced tower line on ${routeBias.routeLabel}`)
      }
      if (signals.has('mana-surge')) {
        towerUpgrades.mana = 2
        startingManaRatio += 0.22
        startingManaUpgradeProgressRatio += 0.16
        if (!openingPanel) {
          openingPanel = 'tower'
        }
        if (skillPresetKind === 'balanced') {
          skillPresetLabel = 'Arcane Flux'
          skillPresetKind = 'utility'
        }
        towerPolicyLabel = 'Mana First'
        towerPolicyKind = 'mana-first'
        summaryParts.push(`high mana opening on ${routeBias.routeLabel}`)
      }
      if (signals.has('armageddon')) {
        startingManaRatio += 0.18
        openingPanel = 'skill'
        heroRosterLabel = 'Arcane Strike Team'
        heroRosterRole = 'raider'
        heroRosterMembers = ['Juno', 'Manos']
        skillPresetLabel = 'Burst Window'
        skillPresetKind = 'burst'
        summaryParts.push(`skill burst primed for ${routeBias.routeLabel}`)
      }
      if (signals.has('recall')) {
        heroStartMode = 'field'
        heroLane = routeBias.preferredLane ?? supportLane
        dispatchLane = routeBias.preferredLane ?? supportLane
        heroRosterLabel = 'Recovery Wing'
        heroRosterRole = 'support'
        heroRosterMembers = ['Helba', 'Juno']
        if (skillPresetKind === 'balanced') {
          skillPresetLabel = 'Support Recall'
          skillPresetKind = 'support'
        }
        summaryParts.push(`${heroLane ?? supportLane} lane hero anchor via ${routeBias.routeLabel}`)
      }
      if (signals.has('healing')) {
        towerUpgrades.population = Math.max(towerUpgrades.population, 2)
        startingManaUpgradeProgressRatio += 0.08
        if (towerPolicyKind === 'balanced') {
          towerPolicyLabel = 'Balanced Sustain'
        }
        summaryParts.push(`healing buffer for ${routeBias.routeLabel}`)
      }
      if (summaryParts.length === 0) {
        summaryParts.push(`specialized stage channel on ${routeBias.routeLabel}`)
      }

      if (routeInfluence.matchesPreferred) {
        startingQueue += Math.max(0, Math.round(routeInfluence.queueDelta))
        startingManaRatio += routeInfluence.manaDelta
        startingManaUpgradeProgressRatio += Math.max(routeInfluence.queueDelta, 0) * 0.04
        if (routeBias.sustainRoute) {
          towerUpgrades.attack = Math.max(towerUpgrades.attack, 2)
        }
        if (routeBias.manaRoute) {
          towerUpgrades.mana = Math.max(towerUpgrades.mana, 2)
        }
        if (routeBias.flankingRoute) {
          towerUpgrades.population = Math.max(towerUpgrades.population, 2)
        }
        summaryParts.push(routeInfluence.stanceLabel)
      }

      loadouts.push({
        loadoutIndex: loadouts.length + 1,
        id: archetype.archetypeId,
        label: archetype.label,
        summary: summaryParts.join(' / '),
        recommended: true,
        heroRosterLabel,
        heroRosterRole,
        heroRosterMembers,
        skillPresetLabel,
        skillPresetKind,
        towerPolicyLabel,
        towerPolicyKind,
        heroStartMode,
        heroLane,
        dispatchLane,
        openingPanel,
        startingQueue: clamp(startingQueue, 0, 4),
        startingManaRatio: clamp(startingManaRatio, 0.18, 0.92),
        startingManaUpgradeProgressRatio: clamp(startingManaUpgradeProgressRatio, 0.08, 0.88),
        towerUpgrades,
      })
    })

    return loadouts
  }

  private resolveSelectedDeployLoadout(
    storyboard: RecoveryStageStoryboard,
  ): RecoveryStageSnapshot['campaignState']['loadouts'][number] | null {
    const loadouts = this.buildDeployLoadouts(storyboard)
    if (loadouts.length === 0) {
      return null
    }
    const index = clamp(this.campaignSelectedLoadoutIndex, 0, loadouts.length - 1)
    return loadouts[index] ?? loadouts[0] ?? null
  }

  private applyDeployLoadout(
    loadout: RecoveryStageSnapshot['campaignState']['loadouts'][number],
  ): void {
    const routeBias = this.deriveStoryboardRouteBias(this.storyboards[this.storyboardIndex] ?? null)
    const routeInfluence = this.deriveCampaignRouteInfluence(this.storyboards[this.storyboardIndex] ?? null)
    this.activeDeployLoadout = loadout
    this.panelOverride = loadout.openingPanel
    this.selectedDispatchLane = routeInfluence.preferredLane ?? routeBias.preferredLane ?? loadout.dispatchLane
    this.queuedUnitCount = clamp(loadout.startingQueue + Math.max(0, Math.round(routeInfluence.queueDelta)), 0, 5)
    this.alliedManaValue = clamp(
      Math.max(this.alliedManaValue, (loadout.startingManaRatio + routeInfluence.manaDelta) * this.manaCapacityValue),
      this.manaCapacityValue * 0.06,
      this.manaCapacityValue,
    )
    this.setUpgradeProgressRatio(
      clamp(
        Math.max(this.previewManaUpgradeProgressRatio, loadout.startingManaUpgradeProgressRatio + Math.max(routeInfluence.queueDelta, 0) * 0.03),
        0.04,
        1,
      ),
    )
    this.towerUpgradeLevels.mana = Math.max(loadout.towerUpgrades.mana, routeInfluence.matchesPreferred && routeBias.manaRoute ? 2 : 1)
    this.towerUpgradeLevels.population = loadout.towerUpgrades.population
    this.towerUpgradeLevels.attack = Math.max(loadout.towerUpgrades.attack, routeInfluence.matchesPreferred && routeBias.sustainRoute ? 2 : 1)
    this.recalculatePopulationCaps()

    if (loadout.towerPolicyKind === 'mana-first') {
      this.restoreMana('allied', this.manaCapacityValue * 0.08)
    } else if (loadout.towerPolicyKind === 'population-first') {
      this.applyUpgradeProgressDelta(0.1)
    } else if (loadout.towerPolicyKind === 'attack-first') {
      this.damageTower('enemy', 0.03)
    }

    if (loadout.dispatchLane) {
      const openingLane = routeInfluence.preferredLane ?? routeBias.preferredLane ?? loadout.dispatchLane
      const openingCount = Math.min(loadout.startingQueue + (routeBias.flankingRoute ? 1 : 0) + Math.max(0, Math.round(routeInfluence.queueDelta)), 4)
      for (let index = 0; index < openingCount; index += 1) {
        this.spawnBattleUnit('allied', openingLane, 'push', `loadout:${loadout.id}:opening`, {
          powerScale: 1 + routeBias.pressureShift + routeInfluence.pressureDelta + loadout.startingQueue * 0.08,
          speedScale: 1.06,
          initialPositionRatio: 0.1 + index * 0.024,
        })
      }
    }

    if (loadout.towerUpgrades.attack > 1 || loadout.towerUpgrades.population > 1) {
      const guardLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
      this.repairTower('allied', 0.06)
      this.strikeLaneUnits(guardLane, 'enemy', 0.16, 2)
    }

    if (loadout.heroStartMode === 'field') {
      this.heroOverrideMode = 'field'
      this.heroAssignedLane = routeInfluence.preferredLane ?? routeBias.preferredLane ?? loadout.heroLane ?? loadout.dispatchLane ?? (this.currentStageBattleProfile.favoredLane ?? 'upper')
      this.ensureHeroUnit(this.heroAssignedLane, loadout.heroRosterMembers[0] ?? null, `loadout:${loadout.id}:hero`)
      this.damageTower(
        'enemy',
        0.05
        + this.currentStageBattleProfile.heroImpact * 0.08
        + routeBias.heroShift
        + routeInfluence.heroDelta
        + (loadout.heroRosterRole === 'raider' ? 0.03 : loadout.heroRosterRole === 'vanguard' ? 0.02 : 0),
      )
      if (loadout.heroRosterRole === 'support' || loadout.heroRosterRole === 'defender') {
        this.repairTower('allied', 0.05 + routeInfluence.defenseDelta)
      }
    } else {
      this.heroOverrideMode = null
      this.heroAssignedLane = null
      this.clearHeroUnits()
    }

    this.syncResourcePreviewState()
    this.rebuildLaneBattleState()
  }

  private deriveStageBattleProfile(storyboard: RecoveryStageStoryboard): RecoveryStageBattleProfile {
    const stage = storyboard.stageBlueprint
    const runtimeFields = stage?.runtimeFields
    const mapBinding = stage?.mapBinding
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)
    const archetypes = (stage?.recommendedArchetypeIds ?? [])
      .map((archetypeId) => this.featuredArchetypesById.get(archetypeId))
      .filter((entry): entry is NonNullable<typeof entry> => entry !== undefined)

    const signalSet = new Set<string>()
    let dispatchBoost = 0.08
    let towerDefenseBias = 0.04
    let recallSwing = 0.06
    let armageddonBurst = 0.06
    let manaSurge = 0.04

    archetypes.forEach((archetype) => {
      const archetypeSignals = this.deriveArchetypeSignals(archetype)
      archetypeSignals.forEach((signal) => signalSet.add(signal))

      if (archetypeSignals.has('dispatch')) {
        dispatchBoost += 0.06
      }
      if (archetypeSignals.has('tower-defense')) {
        towerDefenseBias += 0.07
      }
      if (archetypeSignals.has('recall')) {
        recallSwing += 0.09
      }
      if (archetypeSignals.has('armageddon')) {
        armageddonBurst += 0.12
      }
      if (archetypeSignals.has('mana-surge')) {
        manaSurge += 0.08
      }
      if (archetypeSignals.has('healing')) {
        towerDefenseBias += 0.04
      }
    })

    const activeRowCount = archetypes.reduce((sum, entry) => sum + entry.activeRows.length, 0)
    const buffRowCount = archetypes.reduce((sum, entry) => sum + entry.buffRows.length, 0)
    const exactTailHitCount = archetypes.reduce(
      (sum, entry) => sum + (entry.evidence.some((item) => item.includes('exact projectile or effect hits')) ? 1 : 0),
      0,
    )
    const stageTier = runtimeFields?.tierCandidate ?? 10
    const effectIntensity = stage?.renderIntent?.effectIntensity ?? 'medium'
    const favoredLane =
      routeInfluence.preferredLane
      ?? routeBias.preferredLane
      ?? (mapBinding?.inlinePairBranchIndex !== null && mapBinding?.inlinePairBranchIndex !== undefined
        ? (mapBinding.inlinePairBranchIndex % 2 === 0 ? 'upper' : 'lower')
        : ((runtimeFields?.variantCandidate ?? 1) % 2 === 0 ? 'lower' : 'upper'))
    const alliedPressureScale = clamp(
      0.18
      + archetypes.length * 0.03
      + activeRowCount * 0.004
      + buffRowCount * 0.003
      + routeBias.pressureShift
      + routeInfluence.pressureDelta
      + (effectIntensity === 'high' ? 0.05 : effectIntensity === 'medium' ? 0.025 : 0),
      0.16,
      0.72,
    )
    const enemyPressureScale = clamp(
      0.22
      + stageTier * 0.006
      + (runtimeFields?.regionCandidate ?? 5) * 0.012
      + (routeBias.directRoute ? 0.03 : routeBias.flankingRoute ? -0.01 : 0)
      - routeInfluence.pressureDelta * 0.3
      + (runtimeFields?.storyFlagCandidate ?? 0) * 0.04,
      0.2,
      0.72,
    )
    const alliedWaveCadenceBeats = Math.max(
      3,
      Math.min(
        7,
        7
        - Math.floor(Math.min(activeRowCount, 12) / 3)
        - (signalSet.has('dispatch') ? 1 : 0)
        + Math.max(routeBias.cadenceShift, 0)
        + Math.min(routeInfluence.cadenceDelta, 0),
      ),
    )
    const enemyWaveCadenceBeats = Math.max(
      3,
      Math.min(7, 7 - Math.floor(stageTier / 15) + Math.min(routeBias.cadenceShift, 0) - Math.max(routeInfluence.cadenceDelta, 0)),
    )
    const heroImpact = clamp(
      0.1 + exactTailHitCount * 0.028 + buffRowCount * 0.008 + recallSwing * 0.12 + routeBias.heroShift + routeInfluence.heroDelta,
      0.1,
      0.42,
    )
    const tacticalBias = `${mapBinding?.storyBranch ?? 'branch-unknown'} / ${favoredLane} initiative / ${routeBias.routeLabel} / ${routeInfluence.stanceLabel}${signalSet.size > 0 ? ` / ${Array.from(signalSet).join('+')}` : ''}`
    return {
      label: `${stage?.title ?? storyboard.scriptFamilyId} / tier ${stageTier}`,
      favoredLane,
      tacticalBias,
      stageTier,
      alliedPressureScale,
      enemyPressureScale,
      alliedWaveCadenceBeats,
      enemyWaveCadenceBeats,
      heroImpact,
      effectIntensity,
      archetypeLabels: archetypes.slice(0, 3).map((entry) => entry.label),
      archetypeSignals: Array.from(signalSet),
      dispatchBoost: clamp(dispatchBoost, 0.08, 0.24),
      towerDefenseBias: clamp(towerDefenseBias, 0.04, 0.24),
      recallSwing: clamp(recallSwing, 0.06, 0.24),
      armageddonBurst: clamp(armageddonBurst, 0.06, 0.28),
      manaSurge: clamp(manaSurge, 0.04, 0.22),
    }
  }

  private currentPopulationUsed(side: RecoveryBattleSide): number {
    return (['upper', 'lower'] as const).reduce(
      (sum, laneId) => sum + this.laneEntities[laneId][side].reduce((laneSum, unit) => laneSum + unit.populationCost, 0),
      0,
    )
  }

  private remainingPopulation(side: RecoveryBattleSide): number {
    const capacity = side === 'allied' ? this.populationCapacity : this.enemyPopulationCapacity
    return Math.max(capacity - this.currentPopulationUsed(side), 0)
  }

  private syncResourcePreviewState(): void {
    this.previewManaRatio = clamp(
      this.manaCapacityValue > 0 ? this.alliedManaValue / this.manaCapacityValue : 0,
      0,
      1,
    )
    this.previewManaUpgradeProgressRatio = clamp(
      this.populationCapacity > 0
        ? (this.remainingPopulation('allied') / this.populationCapacity) * 0.62 + (this.towerUpgradeLevels.population - 1) * 0.09
        : 0.08,
      0,
      1,
    )
  }

  private heroTemplateForMember(memberName: string | null): RecoveryBattleHeroTemplate | null {
    if (!memberName) {
      return null
    }
    return this.heroTemplatesByName.get(memberName.toLowerCase()) ?? null
  }

  private resolveUnitTemplate(
    side: RecoveryBattleSide,
    role: RecoveryBattleUnitRole,
    memberLabel: string | null = null,
  ): RecoveryBattleUnitTemplate | null {
    if (role === 'hero' && memberLabel) {
      const heroTemplate = this.heroTemplateForMember(memberLabel)
      if (heroTemplate) {
        return this.unitTemplatesById.get(heroTemplate.unitTemplateId) ?? null
      }
    }
    const directId = `${side}-${role}`
    return this.unitTemplatesById.get(directId) ?? null
  }

  private resolveProjectileTemplate(projectileTemplateId: string | null): RecoveryBattleProjectileTemplate | null {
    if (!projectileTemplateId) {
      return null
    }
    return this.projectileTemplatesById.get(projectileTemplateId) ?? null
  }

  private resolveEffectTemplate(effectTemplateId: string | null): RecoveryBattleEffectTemplate | null {
    if (!effectTemplateId) {
      return null
    }
    return this.effectTemplatesById.get(effectTemplateId) ?? null
  }

  private createEffect(
    side: RecoveryBattleSide,
    laneId: RecoveryBattleLaneId,
    positionRatio: number,
    effectTemplateId: string | null,
    fallbackKind: string,
    intensityScale = 1,
  ): void {
    const template = this.resolveEffectTemplate(effectTemplateId)
    const effect: RecoveryBattleEffectRuntime = {
      id: this.nextBattleEffectId++,
      side,
      laneId,
      positionRatio,
      kind: template?.label ?? fallbackKind,
      renderFamily: template?.renderFamily ?? (fallbackKind.includes('support') ? 'support' : fallbackKind.includes('burst') || fallbackKind.includes('tower') ? 'burst' : fallbackKind.includes('impact') || fallbackKind.includes('hit') ? 'impact' : 'utility'),
      blendMode: template?.blendMode ?? 'additive',
      emitterSemanticId: template?.emitterSemanticId ?? null,
      ttlBeats: Math.max(2, Math.round((template?.durationBeats ?? 3) * intensityScale)),
      intensity: clamp((template?.intensity ?? 0.8) * intensityScale, 0.25, 2.2),
    }
    this.battleEffects.push(effect)
    this.promoteEffectToRenderPulse(effect.renderFamily, Math.min(effect.intensity, 1.3), effect.blendMode)
  }

  private spendMana(side: RecoveryBattleSide, amount: number): boolean {
    if (amount <= 0) {
      return true
    }
    if (side === 'allied') {
      if (this.alliedManaValue < amount) {
        return false
      }
      this.alliedManaValue -= amount
      this.syncResourcePreviewState()
      return true
    }
    if (this.enemyManaValue < amount) {
      return false
    }
    this.enemyManaValue -= amount
    return true
  }

  private restoreMana(side: RecoveryBattleSide, amount: number): void {
    if (amount <= 0) {
      return
    }
    if (side === 'allied') {
      this.alliedManaValue = clamp(this.alliedManaValue + amount, 0, this.manaCapacityValue)
      this.syncResourcePreviewState()
      return
    }
    this.enemyManaValue = clamp(this.enemyManaValue + amount, 0, this.enemyManaCapacityValue)
  }

  private consumeManaRatio(deltaRatio: number): boolean {
    if (!this.manaCapacityValue) {
      return true
    }
    return this.spendMana('allied', Math.abs(deltaRatio) * this.manaCapacityValue)
  }

  private setUpgradeProgressRatio(value: number): void {
    this.previewManaUpgradeProgressRatio = clamp(value, 0, 1)
  }

  private applyUpgradeProgressDelta(deltaRatio: number): void {
    this.setUpgradeProgressRatio(this.previewManaUpgradeProgressRatio + deltaRatio)
  }

  private recalculatePopulationCaps(): void {
    const resourceRules = this.battleModel?.resourceRules
    const basePopulation = resourceRules?.populationBase ?? 7
    const baseEnemyPopulation = resourceRules?.enemyPopulationBase ?? 8
    const populationPerUpgrade = resourceRules?.populationPerUpgrade ?? 3
    this.populationCapacity = basePopulation + Math.max(this.towerUpgradeLevels.population - 1, 0) * populationPerUpgrade
    this.enemyPopulationCapacity = baseEnemyPopulation + Math.floor(this.currentStageBattleProfile.stageTier / 15)
    this.setUpgradeProgressRatio(
      clamp(
        (this.remainingPopulation('allied') / Math.max(this.populationCapacity, 1)) * 0.62
          + (this.towerUpgradeLevels.population - 1) * 0.09,
        0,
        1,
      ),
    )
  }

  private clearBattleEntities(): void {
    ;(['upper', 'lower'] as const).forEach((laneId) => {
      this.laneEntities[laneId].allied.length = 0
      this.laneEntities[laneId].enemy.length = 0
    })
    this.battleProjectiles.length = 0
    this.battleEffects.length = 0
    this.entityVisuals.clear()
    this.cameraShakeIntensity = 0
    this.cameraShakeAxes = 'both'
    this.overlayMode = null
    this.overlayColor = null
    this.overlayAlpha = 0
    this.burstPulseIntensity = 0
    this.particleBoostIntensity = 0
    this.hitFlashIntensity = 0
  }

  private ensureEntityVisual(unitId: number): RecoveryEntityVisualRuntime {
    const existing = this.entityVisuals.get(unitId)
    if (existing) {
      return existing
    }
    const created: RecoveryEntityVisualRuntime = {
      spriteState: 'idle',
      stateWeight: 0,
      hitFlash: 0,
      overlayMode: null,
      overlayAlpha: 0,
    }
    this.entityVisuals.set(unitId, created)
    return created
  }

  private setEntityVisualState(
    unitId: number,
    spriteState: RecoveryBattleEntityState['spriteState'],
    stateWeight: number,
    overlayMode: string | null = null,
    overlayAlpha = 0,
  ): void {
    const visual = this.ensureEntityVisual(unitId)
    visual.spriteState = spriteState
    visual.stateWeight = Math.max(visual.stateWeight, stateWeight)
    if (overlayMode) {
      visual.overlayMode = overlayMode
      visual.overlayAlpha = Math.max(visual.overlayAlpha, overlayAlpha)
    }
  }

  private markEntityHit(unitId: number, intensity: number, overlayMode = 'impact-hit'): void {
    const visual = this.ensureEntityVisual(unitId)
    visual.spriteState = 'hit'
    visual.stateWeight = Math.max(visual.stateWeight, intensity)
    visual.hitFlash = Math.max(visual.hitFlash, intensity)
    visual.overlayMode = overlayMode
    visual.overlayAlpha = Math.max(visual.overlayAlpha, intensity * 0.48)
    this.hitFlashIntensity = Math.max(this.hitFlashIntensity, intensity)
  }

  private overlayColorForMode(mode: string | null): number | null {
    switch (mode) {
      case 'spawn-aura':
        return 0xb1f0ff
      case 'support-aura':
        return 0x97f3d3
      case 'impact-hit':
      case 'projectile-hit':
        return 0xffffff
      case 'tower-siege':
      case 'tower-impact':
        return 0xffbb7a
      case 'burst-wave':
      case 'burst-cast':
        return 0xffc56d
      default:
        return null
    }
  }

  private triggerCameraShake(intensity: number, axes: RecoveryStageRenderState['cameraShakeAxes'] = 'both'): void {
    this.cameraShakeIntensity = Math.max(this.cameraShakeIntensity, clamp(intensity, 0, 1))
    this.cameraShakeAxes = axes
  }

  private triggerOverlayPulse(mode: string, alpha: number, color: number | null = this.overlayColorForMode(mode)): void {
    this.overlayMode = mode
    this.overlayColor = color
    this.overlayAlpha = Math.max(this.overlayAlpha, clamp(alpha, 0, 0.65))
  }

  private triggerBurstPulse(intensity: number, mode = 'burst-wave'): void {
    const clamped = clamp(intensity, 0, 1)
    this.burstPulseIntensity = Math.max(this.burstPulseIntensity, clamped)
    this.particleBoostIntensity = Math.max(this.particleBoostIntensity, clamped)
    this.triggerOverlayPulse(mode, 0.08 + clamped * 0.18)
    this.triggerCameraShake(0.12 + clamped * 0.34, 'both')
  }

  private promoteEffectToRenderPulse(
    renderFamily: RecoveryBattleEffectRuntime['renderFamily'],
    intensity: number,
    blendMode: string,
  ): void {
    if (renderFamily === 'burst') {
      this.triggerBurstPulse(intensity, 'burst-cast')
      return
    }
    if (renderFamily === 'impact') {
      this.hitFlashIntensity = Math.max(this.hitFlashIntensity, clamp(intensity * 0.7, 0, 1))
      this.particleBoostIntensity = Math.max(this.particleBoostIntensity, clamp(intensity * 0.46, 0, 1))
      this.triggerOverlayPulse('impact-hit', 0.05 + intensity * 0.1)
      this.triggerCameraShake(0.08 + intensity * 0.16, blendMode.includes('add') ? 'both' : 'x')
      return
    }
    if (renderFamily === 'support') {
      this.particleBoostIntensity = Math.max(this.particleBoostIntensity, clamp(intensity * 0.42, 0, 1))
      this.triggerOverlayPulse('support-aura', 0.03 + intensity * 0.06)
      return
    }
    this.particleBoostIntensity = Math.max(this.particleBoostIntensity, clamp(intensity * 0.25, 0, 1))
  }

  private tickRenderPulseState(): void {
    this.cameraShakeIntensity = Math.max(this.cameraShakeIntensity * 0.78, 0)
    this.overlayAlpha = Math.max(this.overlayAlpha * 0.82, 0)
    if (this.overlayAlpha <= 0.01) {
      this.overlayMode = null
      this.overlayColor = null
    }
    this.burstPulseIntensity = Math.max(this.burstPulseIntensity * 0.76, 0)
    this.particleBoostIntensity = Math.max(this.particleBoostIntensity * 0.84, 0)
    this.hitFlashIntensity = Math.max(this.hitFlashIntensity * 0.7, 0)
    for (const [unitId, visual] of this.entityVisuals) {
      visual.stateWeight = Math.max(visual.stateWeight * 0.78, 0)
      visual.hitFlash = Math.max(visual.hitFlash * 0.68, 0)
      visual.overlayAlpha = Math.max(visual.overlayAlpha * 0.8, 0)
      if (visual.stateWeight <= 0.06) {
        visual.spriteState = 'idle'
      }
      if (visual.overlayAlpha <= 0.02) {
        visual.overlayMode = null
      }
      if (visual.stateWeight <= 0.02 && visual.hitFlash <= 0.02 && visual.overlayAlpha <= 0.02) {
        this.entityVisuals.delete(unitId)
      }
    }
  }

  private spawnBattleUnit(
    side: RecoveryBattleSide,
    laneId: RecoveryBattleLaneId,
    role: RecoveryBattleUnitRole,
    source: string,
    options: {
      hero?: boolean
      memberLabel?: string | null
      powerScale?: number
      durabilityScale?: number
      speedScale?: number
      initialPositionRatio?: number
      ignorePopulationCap?: boolean
    } = {},
  ): RecoveryBattleUnitRuntime | null {
    const template = this.resolveUnitTemplate(side, role, options.memberLabel ?? null)
    const hero = options.hero ?? role === 'hero'
    const powerScale = options.powerScale ?? 1
    const durabilityScale = options.durabilityScale ?? 1
    const speedScale = options.speedScale ?? 1
    const sideUnits = this.laneEntities[laneId][side]
    const populationCost = template?.populationCost ?? (hero ? 0 : 1)
    if (!options.ignorePopulationCap && populationCost > 0 && this.remainingPopulation(side) < populationCost) {
      return null
    }
    const maxHp = (template?.maxHp ?? (hero ? 2.8 : 1.25)) * durabilityScale
    const power = (template?.power ?? (hero ? 0.44 : 0.22)) * powerScale
    const speed = (template?.speed ?? 0.028) * speedScale
    const range = template?.range ?? (hero ? 0.14 : 0.045)
    const attackPeriodBeats = template?.attackPeriodBeats ?? (hero ? 2 : 2)
    const spacing = 0.028
    const initialPositionRatio =
      options.initialPositionRatio
      ?? (side === 'allied'
        ? 0.08 + Math.min(sideUnits.length, 5) * spacing
        : 0.92 - Math.min(sideUnits.length, 5) * spacing)

    const unit: RecoveryBattleUnitRuntime = {
      id: this.nextBattleEntityId++,
      side,
      laneId,
      role,
      hero,
      memberLabel: options.memberLabel ?? null,
      source,
      hp: maxHp,
      maxHp,
      power,
      speed,
      range,
      cooldownBeats: 0,
      attackPeriodBeats,
      positionRatio: clamp(initialPositionRatio, 0.04, 0.96),
      templateId: template?.id ?? `${side}-${role}`,
      projectileTemplateId: template?.projectileTemplateId ?? null,
      effectTemplateId: template?.effectTemplateId ?? null,
      populationCost,
      manaCost: template?.manaCost ?? 0,
      attackStyle:
        role === 'siege'
          ? 'siege'
          : role === 'support' || role === 'tower-rally'
            ? 'support'
            : role === 'skill-window' || role === 'hero' || (template?.projectileTemplateId ?? null)
              ? 'projectile'
              : 'melee',
    }
    sideUnits.push(unit)
    this.setEntityVisualState(
      unit.id,
      hero ? 'heroic' : 'spawn',
      hero ? 0.8 : 0.58,
      'spawn-aura',
      hero ? 0.32 : 0.18,
    )
    if (hero) {
      this.triggerOverlayPulse('spawn-aura', 0.08)
      this.particleBoostIntensity = Math.max(this.particleBoostIntensity, 0.16)
    }
    this.syncResourcePreviewState()
    return unit
  }

  private spawnUnitsFromDirective(
    side: RecoveryBattleSide,
    directive: RecoveryBattleWaveDirective | null,
    source: string,
    extraPowerScale = 0,
  ): void {
    if (!directive) {
      return
    }

    const template = this.resolveUnitTemplate(side, directive.role)
    for (let index = 0; index < directive.unitBurst; index += 1) {
      if (template && this.remainingPopulation(side) < template.populationCost) {
        break
      }
      if (template && !this.spendMana(side, template.manaCost)) {
        break
      }
      this.spawnBattleUnit(side, directive.laneId, directive.role, source, {
        powerScale: 1 + directive.pressureBias * 1.6 + extraPowerScale,
        durabilityScale: 1 + directive.pressureBias * 0.55,
        speedScale: 1 + (directive.role === 'push' ? 0.12 : directive.role === 'support' ? -0.05 : 0),
      })
    }
    this.recalculatePopulationCaps()
  }

  private clearHeroUnits(): void {
    ;(['upper', 'lower'] as const).forEach((laneId) => {
      this.laneEntities[laneId].allied = this.laneEntities[laneId].allied.filter((unit) => !unit.hero)
      this.laneEntities[laneId].enemy = this.laneEntities[laneId].enemy.filter((unit) => !unit.hero)
    })
  }

  private ensureHeroUnit(laneId: RecoveryBattleLaneId, memberLabel: string | null, source: string): void {
    this.clearHeroUnits()
    this.spawnBattleUnit('allied', laneId, 'hero', source, {
      hero: true,
      memberLabel,
      powerScale: 1 + this.currentStageBattleProfile.heroImpact * 1.2,
      durabilityScale: 1 + this.currentStageBattleProfile.recallSwing * 0.8,
      initialPositionRatio: 0.22,
    })
  }

  private createProjectile(attacker: RecoveryBattleUnitRuntime, strength: number): void {
    const projectileTemplate = this.resolveProjectileTemplate(attacker.projectileTemplateId)
    this.setEntityVisualState(
      attacker.id,
      attacker.hero || attacker.role === 'skill-window' || attacker.role === 'support' ? 'cast' : 'attack',
      attacker.hero ? 0.9 : 0.68,
      attacker.hero || attacker.role === 'skill-window' ? 'burst-cast' : 'impact-hit',
      attacker.hero ? 0.2 : 0.1,
    )
    if (attacker.hero || attacker.role === 'siege') {
      this.triggerCameraShake(0.08 + Math.min(strength, 1.4) * 0.04, 'x')
    }
    this.battleProjectiles.push({
      id: this.nextBattleProjectileId++,
      side: attacker.side,
      laneId: attacker.laneId,
      source: attacker.source,
      positionRatio: attacker.positionRatio,
      velocity: (attacker.side === 'allied' ? 1 : -1) * (projectileTemplate?.speed ?? 0.12),
      strength: strength * (projectileTemplate?.strengthScale ?? 1),
      ttlBeats: projectileTemplate?.ttlBeats ?? 6,
      effectTemplateId: attacker.effectTemplateId,
    })
  }

  private strikeLaneUnits(
    laneId: RecoveryBattleLaneId,
    targetSide: RecoveryBattleSide,
    damage: number,
    maxTargets = 2,
  ): void {
      const targets = [...this.laneEntities[laneId][targetSide]]
      .filter((unit) => unit.hp > 0)
      .sort((left, right) =>
        targetSide === 'allied' ? right.positionRatio - left.positionRatio : left.positionRatio - right.positionRatio,
      )
      .slice(0, maxTargets)

    if (targets.length === 0) {
      this.damageTower(targetSide, damage * 0.24)
      return
    }

    targets.forEach((unit) => {
      unit.hp = Math.max(unit.hp - damage, 0)
      this.markEntityHit(unit.id, 0.7)
      this.createEffect(targetSide === 'allied' ? 'enemy' : 'allied', laneId, unit.positionRatio, unit.effectTemplateId, 'hit', 0.75)
    })
  }

  private supportLaneUnits(
    laneId: RecoveryBattleLaneId,
    side: RecoveryBattleSide,
    heal: number,
  ): void {
    const units = this.laneEntities[laneId][side]
      .filter((unit) => unit.hp > 0)
      .sort((left, right) => left.hp / left.maxHp - right.hp / right.maxHp)
      .slice(0, 3)

    if (units.length === 0) {
      this.spawnBattleUnit(side, laneId, 'support', `support:${side}`, {
        powerScale: 1,
        durabilityScale: 1,
      })
      return
    }

    units.forEach((unit) => {
      unit.hp = Math.min(unit.maxHp, unit.hp + heal)
      this.setEntityVisualState(unit.id, 'support', 0.62, 'support-aura', 0.24)
      this.createEffect(side, laneId, unit.positionRatio, unit.effectTemplateId, 'support', 0.6)
    })
  }

  private shiftLaneUnits(
    laneId: RecoveryBattleLaneId,
    side: RecoveryBattleSide,
    delta: number,
  ): void {
    this.laneEntities[laneId][side].forEach((unit) => {
      unit.positionRatio = clamp(unit.positionRatio + delta, 0.04, 0.96)
    })
  }

  private damageTower(targetSide: RecoveryBattleSide, damage: number): void {
    const impact = clamp(damage * 5.5, 0.05, 0.9)
    this.hitFlashIntensity = Math.max(this.hitFlashIntensity, impact * 0.56)
    this.triggerCameraShake(impact * 0.72, 'x')
    this.triggerOverlayPulse(targetSide === 'allied' ? 'tower-impact' : 'tower-siege', 0.06 + impact * 0.16)
    if (targetSide === 'allied') {
      this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio - damage, 0.08, 1)
      return
    }
    this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - damage, 0.08, 1)
  }

  private repairTower(targetSide: RecoveryBattleSide, amount: number): void {
    const recovery = clamp(amount * 4.2, 0.03, 0.42)
    this.particleBoostIntensity = Math.max(this.particleBoostIntensity, recovery * 0.6)
    this.triggerOverlayPulse('support-aura', 0.02 + recovery * 0.08)
    if (targetSide === 'allied') {
      this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + amount, 0.1, 1)
      return
    }
    this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio + amount, 0.08, 1)
  }

  private unitBias(
    unit: RecoveryBattleUnitRuntime,
    chainState: RecoveryBattleChainState,
  ): {
    speed: number
    power: number
    defense: number
    attackRate: number
  } {
    const favoredLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
    const selectedLane = this.selectedDispatchLane
    const chained = chainState.active && chainState.focusLane === unit.laneId
    let speed = 1
    let power = 1
    let defense = 1
    let attackRate = 1

    if (unit.side === 'allied') {
      power += this.currentStageBattleProfile.dispatchBoost * (selectedLane === unit.laneId ? 0.6 : 0.2)
      power += this.currentStageBattleProfile.heroImpact * (this.heroAssignedLane === unit.laneId ? 0.45 : 0)
      defense += this.currentStageBattleProfile.towerDefenseBias * (favoredLane === unit.laneId ? 0.5 : 0.2)
      speed += selectedLane === unit.laneId ? 0.18 : 0
      if (unit.hero) {
        power += this.currentStageBattleProfile.heroImpact * 0.7
        speed += 0.08
      }
      if (chained) {
        power += chainState.intensity * 0.5
        speed += chainState.intensity * 0.18
        attackRate += chainState.intensity * 0.24
      }
    } else {
      power += this.currentStageBattleProfile.enemyPressureScale * 0.4
      speed += this.currentStageBattleProfile.enemyPressureScale * 0.18
      defense += this.currentStageBattleProfile.enemyPressureScale * 0.12
      if (favoredLane === unit.laneId) {
        power += 0.05
      }
      if (chained) {
        defense = Math.max(defense - chainState.intensity * 0.16, 0.68)
      }
    }

    return { speed, power, defense, attackRate }
  }

  private tickUnitGroup(
    laneId: RecoveryBattleLaneId,
    side: RecoveryBattleSide,
    chainState: RecoveryBattleChainState,
  ): void {
    const units = this.laneEntities[laneId][side]
    const opposingSide: RecoveryBattleSide = side === 'allied' ? 'enemy' : 'allied'
    const opposingUnits = this.laneEntities[laneId][opposingSide]

    units.sort((left, right) => side === 'allied' ? left.positionRatio - right.positionRatio : right.positionRatio - left.positionRatio)

    units.forEach((unit) => {
      if (unit.hp <= 0) {
        return
      }

      unit.cooldownBeats = Math.max(unit.cooldownBeats - 1, 0)
      const bias = this.unitBias(unit, chainState)
      const nearest = [...opposingUnits]
        .filter((target) => target.hp > 0)
        .sort((left, right) => Math.abs(left.positionRatio - unit.positionRatio) - Math.abs(right.positionRatio - unit.positionRatio))[0]

      if (nearest && Math.abs(nearest.positionRatio - unit.positionRatio) <= unit.range) {
        if (unit.cooldownBeats <= 0) {
          const damage = unit.power * bias.power
          const ranged = unit.role === 'support' || unit.role === 'skill-window' || unit.hero
          if (ranged) {
            this.createProjectile(unit, damage)
          } else {
            this.setEntityVisualState(
              unit.id,
              unit.hero ? 'heroic' : 'attack',
              unit.hero ? 0.92 : 0.72,
              unit.role === 'siege' ? 'tower-siege' : 'impact-hit',
              unit.role === 'siege' ? 0.2 : 0.12,
            )
            nearest.hp = Math.max(nearest.hp - damage / Math.max(this.unitBias(nearest, chainState).defense, 0.7), 0)
            this.markEntityHit(nearest.id, unit.hero ? 0.9 : 0.7)
            this.createEffect(unit.side, laneId, nearest.positionRatio, unit.effectTemplateId, 'melee-hit', 0.65)
            if (nearest.hp <= 0) {
              this.triggerBurstPulse(unit.hero || unit.role === 'siege' ? 0.72 : 0.46)
            }
          }
          unit.cooldownBeats = Math.max(1, Math.round(unit.attackPeriodBeats / Math.max(bias.attackRate, 0.6)))
        }
        return
      }

      const direction = side === 'allied' ? 1 : -1
      const towerDistance = side === 'allied' ? 1 - unit.positionRatio : unit.positionRatio
      if (towerDistance <= unit.range + 0.03 && unit.cooldownBeats <= 0) {
        this.setEntityVisualState(unit.id, unit.hero ? 'heroic' : 'tower-hit', unit.hero ? 0.96 : 0.82, 'tower-siege', 0.24)
        this.damageTower(opposingSide, unit.power * bias.power * (unit.role === 'siege' || unit.role === 'hero' ? 0.08 : 0.05))
        this.createEffect(unit.side, laneId, clamp(side === 'allied' ? 0.96 : 0.04, 0.04, 0.96), unit.effectTemplateId, 'tower-hit', 0.9)
        unit.cooldownBeats = Math.max(1, Math.round(unit.attackPeriodBeats / Math.max(bias.attackRate, 0.6)))
        return
      }

      this.setEntityVisualState(unit.id, unit.hero ? 'heroic' : 'advance', unit.hero ? 0.42 : 0.28)
      unit.positionRatio = clamp(unit.positionRatio + direction * unit.speed * bias.speed, 0.04, 0.96)
    })
  }

  private tickBattleProjectiles(chainState: RecoveryBattleChainState): void {
    for (let index = this.battleProjectiles.length - 1; index >= 0; index -= 1) {
      const projectile = this.battleProjectiles[index]
      projectile.positionRatio = clamp(projectile.positionRatio + projectile.velocity, 0.02, 0.98)
      projectile.ttlBeats -= 1
      const targetSide: RecoveryBattleSide = projectile.side === 'allied' ? 'enemy' : 'allied'
      const targets = this.laneEntities[projectile.laneId][targetSide]
        .filter((unit) => unit.hp > 0)
        .sort((left, right) => Math.abs(left.positionRatio - projectile.positionRatio) - Math.abs(right.positionRatio - projectile.positionRatio))
      const target = targets[0]
      if (target && Math.abs(target.positionRatio - projectile.positionRatio) <= 0.04) {
        target.hp = Math.max(target.hp - projectile.strength / Math.max(this.unitBias(target, chainState).defense, 0.7), 0)
        this.markEntityHit(target.id, 0.84, 'projectile-hit')
        this.createEffect(projectile.side, projectile.laneId, target.positionRatio, projectile.effectTemplateId, 'projectile-hit', 0.8)
        if (target.hp <= 0) {
          this.triggerBurstPulse(0.52)
        }
        this.battleProjectiles.splice(index, 1)
        continue
      }

      if (projectile.positionRatio <= 0.04 || projectile.positionRatio >= 0.96 || projectile.ttlBeats <= 0) {
        if (projectile.ttlBeats > 0) {
          this.damageTower(targetSide, projectile.strength * 0.04)
          this.createEffect(projectile.side, projectile.laneId, clamp(projectile.positionRatio, 0.04, 0.96), projectile.effectTemplateId, 'tower-impact', 0.7)
        }
        this.battleProjectiles.splice(index, 1)
      }
    }
  }

  private tickBattleEffects(): void {
    for (let index = this.battleEffects.length - 1; index >= 0; index -= 1) {
      const effect = this.battleEffects[index]
      effect.ttlBeats -= 1
      effect.intensity = Math.max(effect.intensity * 0.92, 0.1)
      if (effect.ttlBeats <= 0) {
        this.battleEffects.splice(index, 1)
      }
    }
    this.tickRenderPulseState()
  }

  private rebuildLaneBattleState(): void {
    ;(['upper', 'lower'] as const).forEach((laneId) => {
      const alliedUnits = this.laneEntities[laneId].allied.filter((unit) => unit.hp > 0)
      const enemyUnits = this.laneEntities[laneId].enemy.filter((unit) => unit.hp > 0)
      this.laneEntities[laneId].allied = alliedUnits
      this.laneEntities[laneId].enemy = enemyUnits

      const alliedFront = alliedUnits.length > 0 ? Math.max(...alliedUnits.map((unit) => unit.positionRatio)) : 0.08
      const enemyFront = enemyUnits.length > 0 ? Math.min(...enemyUnits.map((unit) => unit.positionRatio)) : 0.92
      const alliedPressure = clamp(
        alliedUnits.reduce((sum, unit) => sum + unit.power * (unit.hp / unit.maxHp) * (unit.hero ? 1.4 : 1), 0) / 2.8,
        alliedUnits.length > 0 ? 0.04 : 0.02,
        1,
      )
      const enemyPressure = clamp(
        enemyUnits.reduce((sum, unit) => sum + unit.power * (unit.hp / unit.maxHp) * (unit.hero ? 1.35 : 1), 0) / 2.8,
        enemyUnits.length > 0 ? 0.04 : 0.02,
        1,
      )
      const frontline = clamp((alliedFront + enemyFront) / 2, 0.04, 0.96)
      const contested = clamp(
        1 - Math.abs((alliedPressure + alliedFront * 0.28) - (enemyPressure + (1 - enemyFront) * 0.28)) * 1.5,
        0.08,
        1,
      )
      const momentumDelta = alliedPressure + alliedFront * 0.18 - (enemyPressure + (1 - enemyFront) * 0.18)
      this.laneBattleState[laneId] = {
        alliedUnits: alliedUnits.length,
        enemyUnits: enemyUnits.length,
        alliedPressure,
        enemyPressure,
        frontline,
        contested,
        momentum:
          momentumDelta > 0.08
            ? 'allied-push'
            : momentumDelta < -0.08
              ? 'enemy-push'
              : contested > 0.58
                ? 'contested'
                : 'stalled',
        heroPresent: alliedUnits.some((unit) => unit.hero),
      }
    })
    const activeEntityIds = new Set(
      (['upper', 'lower'] as const).flatMap((laneId) =>
        (['allied', 'enemy'] as const).flatMap((side) => this.laneEntities[laneId][side].map((unit) => unit.id)),
      ),
    )
    for (const unitId of this.entityVisuals.keys()) {
      if (!activeEntityIds.has(unitId)) {
        this.entityVisuals.delete(unitId)
      }
    }
  }

  private tickBattleEntities(chainState: RecoveryBattleChainState): void {
    this.battleStepCount += 1
    const sideOrder: RecoveryBattleSide[] = this.battleStepCount % 2 === 0 ? ['allied', 'enemy'] : ['enemy', 'allied']
    ;(['upper', 'lower'] as const).forEach((laneId) => {
      sideOrder.forEach((side) => {
        this.tickUnitGroup(laneId, side, chainState)
      })
    })
    this.tickBattleProjectiles(chainState)
    this.tickBattleEffects()
    this.rebuildLaneBattleState()
  }

  private buildBattleEntitySnapshot(): RecoveryBattleEntityState[] {
    return (['upper', 'lower'] as const).flatMap((laneId) =>
      (['allied', 'enemy'] as const).flatMap((side) =>
        this.laneEntities[laneId][side]
          .filter((unit) => unit.hp > 0)
          .map((unit) => ({
            id: unit.id,
            side,
            laneId,
            role: unit.role,
            positionRatio: unit.positionRatio,
            hpRatio: clamp(unit.hp / unit.maxHp, 0, 1),
            power: unit.power,
            hero: unit.hero,
            source: unit.source,
            memberLabel: unit.memberLabel,
            spriteState: this.entityVisuals.get(unit.id)?.spriteState ?? (unit.hero ? 'heroic' : 'advance'),
            stateWeight: this.entityVisuals.get(unit.id)?.stateWeight ?? 0.24,
            hitFlash: this.entityVisuals.get(unit.id)?.hitFlash ?? 0,
            overlayMode: this.entityVisuals.get(unit.id)?.overlayMode ?? null,
            overlayAlpha: this.entityVisuals.get(unit.id)?.overlayAlpha ?? 0,
          })),
      ),
    )
  }

  private buildBattleProjectileSnapshot(): RecoveryBattleProjectileState[] {
    return this.battleProjectiles.map((projectile) => ({
      id: projectile.id,
      side: projectile.side,
      laneId: projectile.laneId,
      positionRatio: projectile.positionRatio,
      strength: projectile.strength,
      source: projectile.source,
    }))
  }

  private buildBattleEffectSnapshot(): RecoveryBattleEffectState[] {
    return this.battleEffects.map((effect) => ({
      id: effect.id,
      side: effect.side,
      laneId: effect.laneId,
      positionRatio: effect.positionRatio,
      kind: effect.kind,
      renderFamily: effect.renderFamily,
      blendMode: effect.blendMode,
      emitterSemanticId: effect.emitterSemanticId,
      ttlBeats: effect.ttlBeats,
      intensity: effect.intensity,
    }))
  }

  private buildBattlePreviewState(): RecoveryBattlePreviewState {
    const lanes: RecoveryLaneBattleState[] = (['upper', 'lower'] as const).map((laneId) => ({
      laneId,
      ...this.laneBattleState[laneId],
    }))
    const allyMomentum = lanes.reduce((sum, lane) => sum + lane.alliedPressure, 0) / lanes.length
    const enemyMomentum = lanes.reduce((sum, lane) => sum + lane.enemyPressure, 0) / lanes.length
    return {
      lanes,
      entities: this.buildBattleEntitySnapshot(),
      projectiles: this.buildBattleProjectileSnapshot(),
      effects: this.buildBattleEffectSnapshot(),
      selectedLane: this.selectedDispatchLane,
      queuedReserve: this.queuedUnitCount,
      allyMomentum,
      enemyMomentum,
      towerThreat: clamp(1 - this.previewOwnTowerHpRatio + enemyMomentum * 0.22, 0, 1),
      activeChain: this.buildActiveChainState(),
      stageProfile: { ...this.currentStageBattleProfile, archetypeLabels: [...this.currentStageBattleProfile.archetypeLabels] },
      objective: {
        phase: this.currentObjectivePhase,
        label: this.currentObjectiveLabel,
        waveIndex: this.currentWaveIndex,
        totalWaves: this.totalWaveCount,
        progressRatio: this.objectiveProgressRatio,
        enemyWaveCountdownBeats: this.enemyWaveCountdownBeats,
        alliedWaveCountdownBeats: this.alliedWaveCountdownBeats,
        favoredLane: this.currentStageBattleProfile.favoredLane,
        enemyDirective: this.currentLoadoutDirective(this.enemyWavePlan, 'enemy', 'preview'),
        alliedDirective: this.currentLoadoutDirective(this.alliedWavePlan, 'allied', 'preview'),
      },
      resolution: {
        status: this.battleResolutionOutcome ?? 'active',
        label:
          this.battleResolutionOutcome === 'victory'
            ? 'Stage Clear'
            : this.battleResolutionOutcome === 'defeat'
              ? 'Tower Breached'
              : 'Battle Active',
        reason:
          this.battleResolutionReason
          ?? (this.battleResolutionOutcome ? 'resolved' : 'battle pressure still contested'),
        autoAdvanceInMs:
          this.battleResolutionOutcome && this.battleResolutionAutoAdvanceAtMs > 0
            ? Math.max(this.battleResolutionAutoAdvanceAtMs - this.lastUpdateNowMs, 0)
            : null,
        questRewardReady: this.battleResolutionOutcome === 'victory' && !this.questRewardClaimed,
      },
    }
  }

  private buildActiveChainState(): RecoveryBattleChainState {
    const members = Object.entries(this.rosterChainBoosts)
      .filter(([, value]) => typeof value === 'number' && value > 0)
      .sort((left, right) => (right[1] ?? 0) - (left[1] ?? 0))
      .map(([member]) => member)
    const intensity = members.length > 0
      ? clamp(Math.max(...members.map((member) => this.rosterChainBoosts[member] ?? 0)), 0, 1)
      : 0

    return {
      active: members.length > 0 && intensity > 0,
      members,
      focusLane: this.rosterChainFocusLane,
      intensity,
      label: members.length > 0 ? this.lastScriptedBeatNote : null,
    }
  }

  private tickLaneBattlePreview(): void {
    const beat = Math.max(this.lastChannelBeat, 0)
    const profile = this.currentStageBattleProfile
    const favoredLane = profile.favoredLane ?? 'upper'
    const supportLane = favoredLane === 'upper' ? 'lower' : 'upper'
    const enemyDirective = this.currentLoadoutDirective(this.enemyWavePlan, 'enemy', 'tick')
    const alliedDirective = this.currentLoadoutDirective(this.alliedWavePlan, 'allied', 'tick')
    const chainState = this.buildActiveChainState()

    this.enemyWaveCountdownBeats = Math.max(this.enemyWaveCountdownBeats - 1, 0)
    if (this.enemyWaveCountdownBeats === 0) {
      const laneId = enemyDirective?.laneId ?? (this.currentWaveIndex % 2 === 0 ? favoredLane : supportLane)
      const reinforcements = enemyDirective?.unitBurst ?? Math.min(
        1 + Math.floor((this.currentWaveIndex - 1) / 2) + (profile.effectIntensity === 'high' ? 1 : 0),
        3,
      )
      const fallbackDirective: RecoveryBattleWaveDirective = {
        waveNumber: this.currentWaveIndex,
        laneId,
        role: 'push',
        unitBurst: reinforcements,
        pressureBias: 0,
        label: `enemy push ${laneId}`,
      }
      const resolvedDirective = enemyDirective ?? this.adaptDirectiveForActiveLoadout('enemy', fallbackDirective, 'tick')
      this.applyWaveDirective('enemy', resolvedDirective)
      this.applyLoadoutWaveBeat('enemy', resolvedDirective, 'tick')
      this.markWaveDispatched('enemy')
      this.resetWaveCountdown('enemy', resolvedDirective)
    }

    this.alliedWaveCountdownBeats = Math.max(this.alliedWaveCountdownBeats - 1, 0)
    if (this.alliedWaveCountdownBeats === 0) {
      const laneId = this.selectedDispatchLane ?? alliedDirective?.laneId ?? favoredLane
      const reinforcements = this.queuedUnitCount > 0
        ? Math.min(this.queuedUnitCount, alliedDirective?.unitBurst ?? 2)
        : (alliedDirective?.unitBurst ?? 1)
      const fallbackDirective: RecoveryBattleWaveDirective = {
        waveNumber: this.currentWaveIndex,
        laneId,
        role: 'push',
        unitBurst: reinforcements,
        pressureBias: 0,
        label: `ally push ${laneId}`,
      }
      const resolvedDirective = alliedDirective ?? this.adaptDirectiveForActiveLoadout('allied', fallbackDirective, 'tick')
      this.applyWaveDirective('allied', resolvedDirective)
      this.applyLoadoutWaveBeat('allied', resolvedDirective, 'tick')
      this.queuedUnitCount = Math.max(this.queuedUnitCount - Math.min(this.queuedUnitCount, reinforcements), 0)
      this.markWaveDispatched('allied')
      this.resetWaveCountdown('allied', resolvedDirective)
    }

    if (profile.recallSwing > 0.12 && this.heroAssignedLane && beat % 9 === 0) {
      this.supportLaneUnits(this.heroAssignedLane, 'allied', 0.12)
      this.shiftLaneUnits(this.heroAssignedLane, 'allied', 0.02)
    }
    if (profile.towerDefenseBias > 0.12 && beat % 8 === 0) {
      this.supportLaneUnits(profile.favoredLane ?? favoredLane, 'allied', 0.1)
    }
    if (profile.effectIntensity === 'high' && beat % 7 === 0) {
      this.spawnBattleUnit('enemy', supportLane, 'siege', 'high-intensity-cycle', {
        powerScale: 1 + profile.enemyPressureScale * 0.4,
      })
    }

    this.tickBattleEntities(chainState)

    const alliedWaveRatio = this.alliedWavesDispatched / Math.max(this.totalWaveCount, 1)
    const enemyWaveRatio = this.enemyWavesDispatched / Math.max(this.totalWaveCount, 1)
    const alliedSecuredLanes = this.securedLaneCount('allied')
    const enemySecuredLanes = this.securedLaneCount('enemy')
    const objectiveScore = clamp(
      alliedWaveRatio * 0.34
      + (1 - this.previewEnemyTowerHpRatio) * 0.34
      + alliedSecuredLanes * 0.12
      + (this.heroAssignedLane ? 0.06 : 0)
      - enemyWaveRatio * 0.08
      - enemySecuredLanes * 0.08,
      0.04,
      1,
    )
    if (chainState.active) {
      this.objectiveProgressRatio = clamp(Math.max(this.objectiveProgressRatio, objectiveScore) + chainState.intensity * 0.006, 0.04, 1)
      if (chainState.members.includes('Juno')) {
        this.restoreMana('allied', this.manaCapacityValue * chainState.intensity * 0.01)
      }
      if (chainState.members.includes('Helba') || chainState.members.includes('Caesar')) {
        this.repairTower('allied', chainState.intensity * 0.008)
      }
      if (chainState.members.includes('Vincent') || chainState.members.includes('Manos')) {
        this.damageTower('enemy', chainState.intensity * 0.008)
      }
    } else {
      this.objectiveProgressRatio = clamp(Math.max(this.objectiveProgressRatio, objectiveScore), 0.04, 1)
    }

    if (this.objectiveProgressRatio >= 0.82) {
      this.currentObjectivePhase = 'siege'
      this.currentObjectiveLabel = 'collapse the last tower segment'
    } else if (this.objectiveProgressRatio >= 0.62 && this.currentObjectivePhase !== 'skill-burst') {
      this.currentObjectivePhase = 'hero-pressure'
      this.currentObjectiveLabel = 'press the advantaged lane with hero support'
    } else if (this.objectiveProgressRatio >= 0.34 && this.currentObjectivePhase === 'opening') {
      this.currentObjectivePhase = 'lane-control'
      this.currentObjectiveLabel = 'convert wave tempo into lane control'
    }

    this.evaluateBattleResolution()
  }
}
