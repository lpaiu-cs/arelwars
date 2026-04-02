import type {
  RecoveryBattleObjectiveState,
  RecoveryBattlePreviewState,
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
  RecoveryRuntimeBlueprint,
  RecoveryScriptEntry,
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
const WORLDMAP_HOLD_MS = 1600
const DEPLOY_BRIEFING_MS = 1800
const MANA_RECOVERY_PER_BEAT = 0.018
const UPGRADE_PROGRESS_RECOVERY_PER_BEAT = 0.012
const SKILL_COOLDOWN_MS = 2600
const ITEM_COOLDOWN_MS = 3200
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
      previewStem,
      stageBlueprint: stageBlueprintsByFamily.get(familyId) ?? null,
    }
  })
}

export class RecoveryStageSystem {
  private readonly storyboards: RecoveryStageStoryboard[]

  private readonly runtimeBlueprint: RecoveryRuntimeBlueprint | null

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

  private objectiveProgressRatio = 0.08

  private enemyWaveCountdownBeats = 4

  private alliedWaveCountdownBeats = 5

  private enemyWavePlan: RecoveryBattleWaveDirective[] = []

  private alliedWavePlan: RecoveryBattleWaveDirective[] = []

  private battleResolutionOutcome: 'victory' | 'defeat' | null = null

  private battleResolutionReason: string | null = null

  private battleResolutionAutoAdvanceAtMs = 0

  private campaignUnlockedStageCount = 1

  private campaignSelectedNodeIndex = 0

  private campaignSelectedLoadoutIndex = 0

  private campaignScenePhase: RecoveryStageSnapshot['campaignState']['scenePhase'] = 'battle'

  private campaignWorldmapAutoEnterAtMs = 0

  private campaignDeployBriefingEndsAtMs = 0

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

  constructor(
    catalog: RecoveryCatalog,
    previewManifest: RecoveryPreviewManifest,
    runtimeBlueprint: RecoveryRuntimeBlueprint | null = null,
  ) {
    this.runtimeBlueprint = runtimeBlueprint
    runtimeBlueprint?.featuredArchetypes.forEach((entry) => {
      this.featuredArchetypesById.set(entry.archetypeId, entry)
    })
    runtimeBlueprint?.opcodeHeuristics.forEach((entry) => {
      this.opcodeHeuristicsByMnemonic.set(entry.mnemonic, entry)
    })
    this.storyboards = buildStoryboards(catalog, previewManifest, runtimeBlueprint)
    if (this.storyboards.length > 0) {
      this.campaignPreferredRouteLabel = this.deriveStoryboardRouteBias(this.storyboards[0]).routeLabel
      this.campaignRouteCommitment = 1
      this.seedBattlePreviewState(this.storyboards[0])
      const initialLoadout = this.resolveSelectedDeployLoadout(this.storyboards[0])
      if (initialLoadout) {
        this.applyDeployLoadout(initialLoadout)
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

  moveCampaignSelection(direction: -1 | 1): boolean {
    if (!this.isReady()) {
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

    if (!this.battlePaused && this.campaignScenePhase === 'battle') {
      this.lastActionNote = 'campaign route launch locked until pause or result'
      this.version += 1
      return false
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
    const activeOpcodeCue = this.resolveOpcodeCue(activeDialogueEvent)
    const channelStates = this.buildChannelStates(currentStoryboard)
    const hudState = this.buildHudState(currentStoryboard, activeTutorialCue, activeOpcodeCue, channelStates)
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
      activeOpcodeCue,
      channelStates,
      renderState: this.buildRenderState(currentStoryboard, channelStates),
      hudState,
      gameplayState: this.buildGameplayState(
        activeTutorialCue,
        activeOpcodeCue,
        hudState,
      ),
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

    if (this.campaignScenePhase === 'result-hold') {
      if (this.battleResolutionAutoAdvanceAtMs > 0 && nowMs >= this.battleResolutionAutoAdvanceAtMs) {
        this.enterWorldmapSelection(nowMs)
        this.version += 1
        return true
      }
    } else if (this.campaignScenePhase === 'worldmap') {
      if (this.campaignWorldmapAutoEnterAtMs > 0 && nowMs >= this.campaignWorldmapAutoEnterAtMs) {
        this.enterDeployBriefing(this.campaignSelectedNodeIndex, nowMs)
        this.version += 1
        return true
      }
    } else if (this.campaignScenePhase === 'deploy-briefing') {
      if (this.campaignDeployBriefingEndsAtMs > 0 && nowMs >= this.campaignDeployBriefingEndsAtMs) {
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
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = 0
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
  }

  private enterWorldmapSelection(nowMs: number): void {
    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    this.battlePaused = false
    this.pauseStartedAtMs = 0
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
    this.campaignWorldmapAutoEnterAtMs = nowMs + WORLDMAP_HOLD_MS
    this.campaignDeployBriefingEndsAtMs = 0
    this.lastActionNote = `worldmap opened for ${this.storyboardLabel(this.campaignSelectedNodeIndex)}`
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
    this.campaignWorldmapAutoEnterAtMs = 0
    this.campaignDeployBriefingEndsAtMs = nowMs + DEPLOY_BRIEFING_MS
    this.lastActionNote = `deploy briefing ready for ${this.storyboardLabel(this.campaignSelectedNodeIndex)}`
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
    const selectionMode = this.campaignScenePhase === 'result-hold'
      ? 'result-route-selection'
      : this.campaignScenePhase === 'worldmap' || this.battlePaused
        ? 'worldmap-selection'
      : selectedNodeIndex !== this.storyboardIndex
          ? 'queued-route-selection'
          : 'follow-active-stage'
    const autoAdvanceInMs =
      this.campaignScenePhase === 'result-hold' && this.battleResolutionAutoAdvanceAtMs > 0
        ? Math.max(this.battleResolutionAutoAdvanceAtMs - this.lastUpdateNowMs, 0)
      : this.campaignScenePhase === 'worldmap' && this.campaignWorldmapAutoEnterAtMs > 0
        ? Math.max(this.campaignWorldmapAutoEnterAtMs - this.lastUpdateNowMs, 0)
      : this.campaignScenePhase === 'deploy-briefing' && this.campaignDeployBriefingEndsAtMs > 0
        ? Math.max(this.campaignDeployBriefingEndsAtMs - this.lastUpdateNowMs, 0)
      : null
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

  private resolveOpcodeCue(event: RecoveryDialogueEvent | null): RecoveryResolvedOpcodeCue | null {
    const commands = event?.prefixCommands ?? []
    if (commands.length === 0) {
      return null
    }

    const exactVariantCandidates: Array<RecoveryResolvedOpcodeCue & { commandIndex: number }> = []
    const mnemonicCandidates: Array<RecoveryResolvedOpcodeCue & { commandIndex: number }> = []

    commands.forEach((command, commandIndex) => {
      const heuristic = this.opcodeHeuristicsByMnemonic.get(command.mnemonic)
      if (!heuristic) {
        return
      }
      const variantKey = `${command.mnemonic}:${command.args.length > 0 ? command.args.map((value) => value.toString(16).padStart(2, '0')).join(',') : '-'}`
      const variantHint = heuristic.variantHints?.find((hint) => hint.variant === variantKey)
      if (variantHint) {
        exactVariantCandidates.push({
          mnemonic: command.mnemonic,
          label: variantHint.label,
          action: variantHint.action,
          category: heuristic.category,
          confidence: variantHint.confidence,
          source: 'variant',
          variant: variantKey,
          commandIndex,
        })
        return
      }
      mnemonicCandidates.push({
        mnemonic: command.mnemonic,
        label: heuristic.label,
        action: heuristic.action,
        category: heuristic.category,
        confidence: heuristic.confidence,
        source: 'mnemonic',
        commandIndex,
      })
    })

    const nonGenericVariants = exactVariantCandidates.filter((entry) => !GENERIC_OPCODE_VARIANTS.has(entry.variant ?? ''))
    const pickedVariant = (nonGenericVariants.length > 0 ? nonGenericVariants : exactVariantCandidates).sort(
      (left, right) => right.commandIndex - left.commandIndex,
    )[0]
    if (pickedVariant) {
      const { commandIndex: _commandIndex, ...cue } = pickedVariant
      return cue
    }

    const pickedMnemonic = mnemonicCandidates.sort((left, right) => right.commandIndex - left.commandIndex)[0]
    if (!pickedMnemonic) {
      return null
    }
    const { commandIndex: _commandIndex, ...cue } = pickedMnemonic
    return cue
  }

  private applyDialogueBeat(
    storyboard: RecoveryStageStoryboard,
    event: RecoveryDialogueEvent | null,
  ): void {
    this.lastScriptedBeatNote = null
    if (!event) {
      return
    }

    const tutorialCue = this.resolveTutorialCue(storyboard, event)
    const opcodeCue = this.resolveOpcodeCue(event)
    const favoredLane = this.currentStageBattleProfile.favoredLane ?? 'upper'

    if (this.applyLoadoutCuePattern(tutorialCue, opcodeCue, favoredLane)) {
      return
    }

    switch (tutorialCue?.chainId) {
      case 'battle-hud-guard-hp':
        this.setObjectiveState('lane-control', 'hold the tower line', 0.03)
        this.triggerSceneWave('enemy', 'tutorial guard line screen', false)
        this.lastScriptedBeatNote = 'tutorial fixed own-tower objective and triggered enemy screen'
        return
      case 'battle-hud-goal-hp':
        this.setObjectiveState('siege', 'break the enemy tower', 0.05)
        this.triggerSceneWave('enemy', 'tutorial revealed siege wave', true)
        this.lastScriptedBeatNote = 'tutorial fixed siege objective and advanced siege wave'
        return
      case 'battle-hud-dispatch-arrows': {
        this.setObjectiveState('lane-control', `establish ${favoredLane} lane control`, 0.04)
        this.triggerSceneWave('allied', `tutorial triggered ${favoredLane} dispatch wave`, false)
        this.selectedDispatchLane = favoredLane
        this.queuedUnitCount = Math.max(
          this.queuedUnitCount,
          this.currentStageBattleProfile.dispatchBoost >= 0.16 ? 2 : 1,
        )
        const previousActionNote = this.lastActionNote
        this.commitLaneDispatch(favoredLane)
        this.lastActionNote = previousActionNote
        this.lastScriptedBeatNote = `tutorial scripted ${favoredLane} lane push`
        return
      }
      case 'battle-hud-unit-card':
        this.setObjectiveState('lane-control', 'build a dispatch reserve', 0.03)
        this.triggerSceneWave('allied', 'tutorial primed reserve wave', false)
        if (this.applyScriptedAction('produce-unit', 'tutorial queued unit production')) {
          return
        }
        break
      case 'battle-hud-mana-bar':
        this.setObjectiveState('tower-management', 'restore mana tempo', 0.02)
        this.previewManaRatio = clamp(
          this.previewManaRatio + 0.08 + this.currentStageBattleProfile.manaSurge * 0.14,
          0.06,
          1,
        )
        this.lastScriptedBeatNote = 'tutorial restored mana context'
        return
      case 'battle-hud-hero-sortie':
        this.setObjectiveState('hero-pressure', 'deploy the hero strike lane', 0.05)
        this.triggerSceneWave('allied', 'tutorial opened hero pressure wave', true)
        if (this.applyScriptedAction('deploy-hero', `tutorial auto-deployed hero to ${favoredLane}`)) {
          return
        }
        break
      case 'battle-hud-hero-return':
        this.setObjectiveState('tower-management', 'regroup hero at tower', 0.03)
        if (this.applyScriptedAction('return-to-tower', 'tutorial recalled hero to tower')) {
          return
        }
        break
      case 'tower-menu-highlight':
        this.setObjectiveState('tower-management', 'open tower management', 0.02)
        this.panelOverride = 'tower'
        this.lastScriptedBeatNote = 'tutorial focused tower panel'
        return
      case 'mana-upgrade-highlight':
      case 'population-upgrade-highlight':
        this.setObjectiveState(
          'tower-management',
          tutorialCue.chainId === 'mana-upgrade-highlight' ? 'advance mana economy' : 'raise population ceiling',
          0.03,
        )
        this.panelOverride = 'tower'
        if (
          this.applyScriptedAction(
            'upgrade-tower-stat',
            tutorialCue.chainId === 'mana-upgrade-highlight'
              ? 'tutorial advanced mana upgrade'
              : 'tutorial advanced population upgrade',
          )
        ) {
          return
        }
        break
      case 'skill-menu-highlight':
        this.setObjectiveState('skill-burst', 'prepare skill burst window', 0.03)
        this.panelOverride = 'skill'
        this.lastScriptedBeatNote = 'tutorial opened skill channel'
        return
      case 'skill-slot-highlight':
        this.setObjectiveState('skill-burst', 'fire a burst through the skill window', 0.05)
        this.triggerSceneWave('allied', 'tutorial opened skill burst wave', true)
        this.panelOverride = 'skill'
        if (this.applyScriptedAction('cast-skill', 'tutorial fired skill beat')) {
          return
        }
        break
      case 'item-menu-highlight':
        this.setObjectiveState('tower-management', 'stabilize the line with items', 0.03)
        this.panelOverride = 'item'
        if (this.applyScriptedAction('use-item', 'tutorial fired item beat')) {
          return
        }
        this.lastScriptedBeatNote = 'tutorial opened item channel'
        return
      case 'system-menu-highlight':
        this.setObjectiveState('tower-management', 'pause and review battle state', 0.01)
        this.panelOverride = 'system'
        this.lastScriptedBeatNote = 'tutorial surfaced system panel'
        return
      case 'quest-panel-highlight':
        this.setObjectiveState('quest-resolution', 'review quest and bonus objectives', 0.04)
        this.panelOverride = 'system'
        this.lastScriptedBeatNote = 'tutorial surfaced quest rewards'
        return
      default:
        break
    }

    if (!opcodeCue) {
      return
    }

    if (includesAny(opcodeCue.action, ['tower', 'mana', 'population'])) {
      this.setObjectiveState('tower-management', 'rebalance tower economy', 0.02)
      this.panelOverride = 'tower'
    } else if (includesAny(opcodeCue.action, ['skill'])) {
      this.setObjectiveState('skill-burst', 'open a skill timing window', 0.02)
      this.panelOverride = 'skill'
    } else if (includesAny(opcodeCue.action, ['item'])) {
      this.setObjectiveState('tower-management', 'stabilize with an item route', 0.02)
      this.panelOverride = 'item'
    } else if (includesAny(opcodeCue.action, ['system', 'quest'])) {
      this.setObjectiveState('quest-resolution', 'review auxiliary objectives', 0.02)
      this.panelOverride = 'system'
    }

    if (includesAny(opcodeCue.action, ['pose', 'emphasis', 'shock'])) {
      this.setObjectiveState('hero-pressure', 'capitalize on the pressure swing', 0.03)
      this.triggerSceneWave('enemy', `opcode surged ${opcodeCue.action}`, false)
      const targetLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
      this.laneBattleState[targetLane].alliedPressure = clamp(
        this.laneBattleState[targetLane].alliedPressure + 0.03,
        0.08,
        1,
      )
      this.lastScriptedBeatNote = `opcode pulse ${opcodeCue.action}`
      return
    }

    if (includesAny(opcodeCue.action, ['highlight', 'focus', 'anchor'])) {
      this.lastScriptedBeatNote = `opcode focus ${opcodeCue.action}`
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

  private currentWaveDirective(plan: RecoveryBattleWaveDirective[]): RecoveryBattleWaveDirective | null {
    if (plan.length === 0) {
      return null
    }
    return plan[Math.min(Math.max(this.currentWaveIndex - 1, 0), plan.length - 1)] ?? null
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
    return this.adaptDirectiveForActiveLoadout(side, this.currentWaveDirective(plan), source)
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

    const lane = this.laneBattleState[directive.laneId]
    if (side === 'enemy') {
      lane.enemyUnits = Math.min(lane.enemyUnits + directive.unitBurst, 8)
      lane.enemyPressure = clamp(lane.enemyPressure + directive.unitBurst * 0.06 + directive.pressureBias, 0.08, 1)
      if (directive.role === 'siege') {
        this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio - 0.018, 0.1, 1)
      }
      return
    }

    lane.alliedUnits = Math.min(lane.alliedUnits + directive.unitBurst, 8)
    lane.alliedPressure = clamp(
      lane.alliedPressure + directive.unitBurst * (0.04 + this.currentStageBattleProfile.dispatchBoost * 0.08) + directive.pressureBias,
      0.08,
      1,
    )
    if (directive.role === 'push' || directive.role === 'siege' || directive.role === 'skill-window') {
      this.selectedDispatchLane = directive.laneId
    }
    if (directive.role === 'tower-rally' || directive.role === 'support') {
      this.previewOwnTowerHpRatio = clamp(
        this.previewOwnTowerHpRatio + 0.012 + this.currentStageBattleProfile.towerDefenseBias * 0.05,
        0.1,
        1,
      )
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
      if (activeLoadout.skillPresetKind === 'orders' && (directive.role === 'push' || directive.role === 'siege')) {
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, 4)
        this.selectedDispatchLane = directive.laneId
      }
      if (activeLoadout.skillPresetKind === 'burst' && directive.role === 'skill-window') {
        this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - (source === 'scene' ? 0.028 : 0.018), 0.08, 1)
        this.skillCooldownEndsAtMs = Math.max(this.skillCooldownEndsAtMs - 700, this.lastUpdateNowMs)
      }
      if (activeLoadout.skillPresetKind === 'support' && (directive.role === 'support' || directive.role === 'tower-rally')) {
        this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.025, 0.1, 1)
      }
      if (activeLoadout.towerPolicyKind === 'mana-first') {
        this.previewManaRatio = clamp(this.previewManaRatio + (source === 'scene' ? 0.05 : 0.03), 0.06, 1)
      } else if (activeLoadout.towerPolicyKind === 'attack-first' && (directive.role === 'push' || directive.role === 'siege')) {
        this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.016, 0.08, 1)
      } else if (activeLoadout.towerPolicyKind === 'population-first') {
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, 4)
      }

      if (activeLoadout.heroRosterRole === 'support' || activeLoadout.heroRosterRole === 'defender') {
        this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.015, 0.1, 1)
      }
      return `${activeLoadout.label} script`
    }

    if ((activeLoadout.heroRosterRole === 'defender' || activeLoadout.heroRosterRole === 'support') && directive.role === 'siege') {
      this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.01, 0.1, 1)
    }
    if (activeLoadout.skillPresetKind === 'orders' && directive.role === 'push' && this.selectedDispatchLane) {
      this.laneBattleState[this.selectedDispatchLane].alliedPressure = clamp(
        this.laneBattleState[this.selectedDispatchLane].alliedPressure + 0.03,
        0.08,
        1,
      )
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
    tutorialCue: RecoveryTutorialChainCue | null,
    opcodeCue: RecoveryResolvedOpcodeCue | null,
    favoredLane: 'upper' | 'lower',
  ): boolean {
    const activeLoadout = this.activeDeployLoadout
    if (!activeLoadout) {
      return false
    }

    const tutorialChainId = tutorialCue?.chainId ?? ''
    const opcodeAction = opcodeCue?.action ?? ''
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
          tutorialChainId === 'battle-hud-goal-hp'
          || tutorialChainId === 'skill-slot-highlight'
          || stageBias.siegeBias
          || includesAny(opcodeAction, ['siege', 'shock', 'emphasis'])
        )
      ) {
        this.selectedDispatchLane = preferredLane
        this.panelOverride = 'skill'
        this.queuedUnitCount = Math.max(this.queuedUnitCount, 1)
        if (
          this.applyScriptedActionChain(
            ['deploy-hero', 'cast-skill'],
            `committed strike route chained Vincent and Manos (${routeInfluence.stanceLabel})`,
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
          tutorialChainId === 'battle-hud-dispatch-arrows'
          || tutorialChainId === 'battle-hud-unit-card'
          || stageBias.dispatchBias
          || includesAny(opcodeAction, ['dispatch', 'focus', 'anchor'])
        )
      ) {
        this.selectedDispatchLane = preferredLane
        this.queuedUnitCount = Math.max(this.queuedUnitCount, 2)
        if (
          this.applyScriptedActionChain(
            ['produce-unit', 'deploy-hero'],
            `committed flank route chained Rogan and Vincent (${routeInfluence.stanceLabel})`,
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
          tutorialChainId === 'battle-hud-guard-hp'
          || tutorialChainId === 'tower-menu-highlight'
          || tutorialChainId === 'quest-panel-highlight'
          || stageBias.sustainBias
          || stageBias.rewardBias
          || includesAny(opcodeAction, ['guard', 'tower', 'quest', 'population'])
        )
      ) {
        this.panelOverride = tutorialChainId === 'quest-panel-highlight' ? 'item' : 'tower'
        if (
          this.applyScriptedActionChain(
            ['upgrade-tower-stat', 'use-item'],
            `committed hold route chained Helba and Caesar (${routeInfluence.stanceLabel})`,
          )
        ) {
          return true
        }
      }

      if (
        routeInfluence.stanceLabel.includes('branch-hold')
        && hasJuno
        && (
          tutorialChainId === 'battle-hud-mana-bar'
          || tutorialChainId === 'skill-slot-highlight'
          || tutorialChainId === 'mana-upgrade-highlight'
          || stageBias.manaBias
          || includesAny(opcodeAction, ['mana', 'skill', 'shock', 'system'])
        )
      ) {
        this.panelOverride = 'skill'
        if (
          this.applyScriptedActionChain(
            ['upgrade-tower-stat', 'cast-skill'],
            `committed mana route chained Juno channels (${routeInfluence.stanceLabel})`,
          )
        ) {
          return true
        }
      }
    }

    if (
      hasVincent
      && (
        tutorialChainId === 'battle-hud-dispatch-arrows'
        || tutorialChainId === 'battle-hud-hero-sortie'
        || tutorialChainId === 'battle-hud-goal-hp'
        || stageBias.siegeBias
        || stageBias.heroBias
        || includesAny(opcodeAction, ['dispatch', 'hero', 'siege'])
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
        tutorialChainId === 'battle-hud-unit-card'
        || tutorialChainId === 'battle-hud-dispatch-arrows'
        || stageBias.dispatchBias
        || includesAny(opcodeAction, ['dispatch', 'focus', 'anchor'])
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
        tutorialChainId === 'mana-upgrade-highlight'
        || tutorialChainId === 'tower-menu-highlight'
        || tutorialChainId === 'item-menu-highlight'
        || stageBias.sustainBias
        || stageBias.rewardBias
        || includesAny(opcodeAction, ['tower', 'mana', 'item', 'quest'])
      )
    ) {
      this.panelOverride = tutorialChainId === 'item-menu-highlight' ? 'item' : 'tower'
      if (
        this.applyScriptedAction(
          tutorialChainId === 'item-menu-highlight' ? 'use-item' : 'upgrade-tower-stat',
          tutorialChainId === 'item-menu-highlight'
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
        tutorialChainId === 'skill-slot-highlight'
        || tutorialChainId === 'battle-hud-mana-bar'
        || tutorialChainId === 'battle-hud-goal-hp'
        || stageBias.manaBias
        || stageBias.heroBias
        || includesAny(opcodeAction, ['skill', 'mana', 'shock'])
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
        tutorialChainId === 'battle-hud-goal-hp'
        || tutorialChainId === 'skill-slot-highlight'
        || stageBias.siegeBias
        || includesAny(opcodeAction, ['shock', 'siege', 'emphasis', 'pose'])
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
        tutorialChainId === 'battle-hud-guard-hp'
        || tutorialChainId === 'population-upgrade-highlight'
        || tutorialChainId === 'quest-panel-highlight'
        || stageBias.sustainBias
        || stageBias.rewardBias
        || includesAny(opcodeAction, ['guard', 'tower', 'quest', 'population'])
      )
    ) {
      this.panelOverride = 'tower'
      if (this.applyScriptedAction('upgrade-tower-stat', `Caesar auto-shored up the guard line (${stageBias.label})`)) {
        return true
      }
    }

    if (
      (rosterRole === 'vanguard' || rosterRole === 'raider')
      && (tutorialChainId === 'battle-hud-dispatch-arrows' || includesAny(opcodeAction, ['dispatch', 'hero', 'shock', 'siege']))
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
        tutorialChainId === 'mana-upgrade-highlight'
        || tutorialChainId === 'population-upgrade-highlight'
        || tutorialChainId === 'tower-menu-highlight'
        || includesAny(opcodeAction, ['tower', 'mana', 'population', 'quest'])
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
        tutorialChainId === 'battle-hud-mana-bar'
        || tutorialChainId === 'item-menu-highlight'
        || tutorialChainId === 'quest-panel-highlight'
        || includesAny(opcodeAction, ['item', 'quest', 'mana', 'system'])
      )
    ) {
      if (this.applyScriptedAction('use-item', `${activeLoadout.skillPresetLabel} auto-stabilized the lane`)) {
        return true
      }
    }

    if (
      (skillPresetKind === 'burst' || skillPresetKind === 'orders')
      && (
        tutorialChainId === 'skill-slot-highlight'
        || tutorialChainId === 'battle-hud-goal-hp'
        || includesAny(opcodeAction, ['skill', 'pose', 'emphasis', 'shock'])
      )
    ) {
      this.panelOverride = 'skill'
      if (this.applyScriptedAction('cast-skill', `${activeLoadout.skillPresetLabel} auto-opened a channel spike`)) {
        return true
      }
    }

    if (
      towerPolicyKind === 'population-first'
      && (tutorialChainId === 'battle-hud-unit-card' || includesAny(opcodeAction, ['dispatch', 'focus']))
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
    if (advanceWave && this.currentWaveIndex < this.totalWaveCount) {
      this.currentWaveIndex += 1
      this.objectiveProgressRatio = clamp(
        Math.max(
          this.objectiveProgressRatio,
          this.currentWaveIndex / this.totalWaveCount
          - 0.08
          + (routeInfluence.matchesPreferred ? 0.02 * routeInfluence.commitmentFactor : 0),
        ),
        0.04,
        1,
      )
    }

    const plan = side === 'enemy' ? this.enemyWavePlan : this.alliedWavePlan
    const directive = this.adjustSceneDirectiveForRoute(side, this.currentLoadoutDirective(plan, side, 'scene'))
    this.applyWaveDirective(side, directive)
    const loadoutBeat = this.applyLoadoutWaveBeat(side, directive, 'scene')
    if (directive && side === 'allied' && routeInfluence.matchesPreferred) {
      if ((directive.role === 'push' || directive.role === 'siege') && routeBias.directRoute) {
        this.objectiveProgressRatio = clamp(this.objectiveProgressRatio + 0.02 + routeInfluence.commitmentFactor * 0.02, 0.04, 1)
      } else if (directive.role === 'tower-rally' && routeBias.sustainRoute) {
        this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.02 + routeInfluence.defenseDelta * 0.25, 0.1, 1)
      } else if (directive.role === 'skill-window' && routeBias.manaRoute) {
        this.previewManaRatio = clamp(this.previewManaRatio + 0.04 + routeInfluence.manaDelta * 0.3, 0.06, 1)
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
  }

  private evaluateBattleResolution(): void {
    if (this.battleResolutionOutcome) {
      return
    }

    const storyboard = this.storyboards[this.storyboardIndex] ?? null
    const routeBias = this.deriveStoryboardRouteBias(storyboard)
    const routeInfluence = this.deriveCampaignRouteInfluence(storyboard)
    const allyMomentum = (this.laneBattleState.upper.alliedPressure + this.laneBattleState.lower.alliedPressure) / 2
    const enemyMomentum = (this.laneBattleState.upper.enemyPressure + this.laneBattleState.lower.enemyPressure) / 2
    const victoryTowerThreshold = clamp(
      0.11
      + (routeInfluence.matchesPreferred && (routeBias.directRoute || routeBias.flankingRoute) ? 0.018 + routeInfluence.commitmentFactor * 0.03 : 0)
      - (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null ? 0.012 : 0),
      0.08,
      0.18,
    )
    const siegeVictoryThreshold = clamp(
      0.16
      + (routeInfluence.matchesPreferred && routeBias.directRoute ? 0.03 + routeInfluence.commitmentFactor * 0.03 : 0)
      - (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null ? 0.015 : 0),
      0.12,
      0.24,
    )
    const progressVictoryThreshold = clamp(
      0.98
      - (routeInfluence.matchesPreferred ? 0.04 * routeInfluence.commitmentFactor : 0)
      - (routeBias.manaRoute && routeInfluence.matchesPreferred ? 0.02 : 0),
      0.88,
      0.98,
    )
    const progressMomentumAllowance = clamp(
      0.02 + (routeInfluence.matchesPreferred && routeBias.manaRoute ? 0.03 : 0),
      0.02,
      0.06,
    )
    const defeatTowerThreshold = clamp(
      0.12
      - (routeInfluence.matchesPreferred && routeBias.sustainRoute ? 0.02 + routeInfluence.commitmentFactor * 0.02 : 0)
      + (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null ? 0.012 : 0),
      0.08,
      0.16,
    )
    const collapseTowerThreshold = clamp(
      0.18
      - (routeInfluence.matchesPreferred && routeBias.sustainRoute ? 0.03 + routeInfluence.commitmentFactor * 0.02 : 0)
      + (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null ? 0.01 : 0),
      0.12,
      0.2,
    )
    const defeatMomentumGap = clamp(
      0.12
      + (routeInfluence.matchesPreferred && routeBias.sustainRoute ? 0.03 + routeInfluence.commitmentFactor * 0.03 : 0)
      - (!routeInfluence.matchesPreferred && routeInfluence.preferredRouteLabel !== null ? 0.02 : 0),
      0.08,
      0.2,
    )

    if (
      this.previewEnemyTowerHpRatio <= victoryTowerThreshold
      || (this.currentObjectivePhase === 'siege' && this.previewEnemyTowerHpRatio <= siegeVictoryThreshold)
      || (this.objectiveProgressRatio >= progressVictoryThreshold && allyMomentum >= enemyMomentum - progressMomentumAllowance)
      || (
        this.currentObjectivePhase === 'skill-burst'
        && routeInfluence.matchesPreferred
        && routeBias.manaRoute
        && this.objectiveProgressRatio >= progressVictoryThreshold - 0.04
        && this.previewManaRatio >= 0.66
      )
    ) {
      this.resolveBattleOutcome(
        'victory',
        routeInfluence.matchesPreferred
          ? `enemy line collapsed under ${routeInfluence.stanceLabel}`
          : 'enemy tower pressure collapsed',
      )
      return
    }

    if (
      this.previewOwnTowerHpRatio <= defeatTowerThreshold
      || (this.previewOwnTowerHpRatio <= collapseTowerThreshold && enemyMomentum - allyMomentum > defeatMomentumGap)
      || (
        this.currentObjectivePhase === 'lane-control'
        && enemyMomentum > 0.9
        && this.objectiveProgressRatio < (routeInfluence.matchesPreferred && routeBias.sustainRoute ? 0.22 : 0.28)
      )
    ) {
      this.resolveBattleOutcome(
        'defeat',
        routeInfluence.preferredRouteLabel !== null && !routeInfluence.matchesPreferred
          ? `branch pressure broke the tower line (${routeInfluence.stanceLabel})`
          : 'enemy lane pressure breached the guard line',
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
    const ptcHint = this.runtimeBlueprint?.renderProfile.ptcBridgeSummary.sharedPrimaryGroups[0]
    return {
      bankRuleLabel: storyboard.stageBlueprint?.renderIntent?.bankRule ?? this.runtimeBlueprint?.renderProfile.defaultMplBankRule.label ?? 'default-bank-b-flagged-bank-a',
      bankOverlayActive:
        currentFrame?.relation === 'overlay'
        || currentFrame?.linkType === 'overlay-track'
        || currentFrame?.eventType === 'overlay',
      packedPixelStemRule: specialRule?.heuristic ?? null,
      effectPulseCount: channelStates.filter((entry) => entry.intensity > 0.62 && entry.hasBuffLayer).length,
      effectIntensity: storyboard.stageBlueprint?.renderIntent?.effectIntensity ?? 'medium',
      ptcEmitterHint:
        ptcHint && typeof ptcHint === 'object' && 'primaryPtcStem' in ptcHint
          ? String(ptcHint.primaryPtcStem)
          : null,
    }
  }

  private buildHudState(
    storyboard: RecoveryStageStoryboard,
    activeTutorialCue: RecoveryTutorialChainCue | null,
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

    switch (activeTutorialCue?.chainId) {
      case 'battle-hud-guard-hp':
        ownTowerHpRatio = 0.16
        break
      case 'battle-hud-goal-hp':
        enemyTowerHpRatio = 0.14
        break
      case 'battle-hud-dispatch-arrows':
        dispatchArrowsHighlighted = true
        leftDispatchCueVisible = true
        break
      case 'battle-hud-unit-card':
        highlightedUnitCardIndex = 0
        manaRatio = Math.max(manaRatio, 0.62)
        break
      case 'battle-hud-mana-bar':
        manaRatio = 0.34
        manaUpgradeProgressRatio = 0.12
        break
      case 'battle-hud-hero-sortie':
        heroDeployed = false
        heroPortraitHighlighted = true
        returnCooldownRatio = 0
        break
      case 'battle-hud-hero-return':
        heroDeployed = true
        heroPortraitHighlighted = true
        returnCooldownRatio = 0.78
        break
      case 'tower-menu-highlight':
        activePanel = 'tower'
        highlightedMenuId = 'tower'
        break
      case 'mana-upgrade-highlight':
        activePanel = 'tower'
        highlightedMenuId = 'tower'
        highlightedTowerUpgradeId = 'mana'
        manaRatio = 1
        manaUpgradeProgressRatio = 0.82
        break
      case 'population-upgrade-highlight':
        activePanel = 'tower'
        highlightedMenuId = 'tower'
        highlightedTowerUpgradeId = 'population'
        break
      case 'skill-menu-highlight':
        activePanel = 'skill'
        highlightedMenuId = 'skill'
        skillWindowVisible = true
        break
      case 'skill-slot-highlight':
        activePanel = 'skill'
        highlightedMenuId = 'skill'
        skillWindowVisible = true
        skillSlotHighlighted = true
        break
      case 'item-menu-highlight':
        activePanel = 'item'
        highlightedMenuId = 'item'
        itemWindowVisible = true
        itemSlotHighlighted = true
        break
      case 'system-menu-highlight':
        activePanel = 'system'
        highlightedMenuId = 'system'
        break
      case 'quest-panel-highlight':
        questVisible = true
        questRewardReady = true
        highlightedMenuId = 'system'
        break
      default:
        break
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
    activeTutorialCue: RecoveryTutorialChainCue | null,
    activeOpcodeCue: RecoveryResolvedOpcodeCue | null,
    hudState: RecoveryHudGhostState,
  ): RecoveryGameplayState {
    let mode: RecoveryGameplayState['mode'] = activeTutorialCue ? 'tutorial-lock' : activeOpcodeCue ? 'guided-preview' : 'free-preview'
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
    let primaryHint = activeTutorialCue?.label ?? activeOpcodeCue?.label ?? 'free-preview'

    const blockCommonBattleInputs = (): void => {
      blockedInputs.add('open-skill-menu')
      blockedInputs.add('open-item-menu')
      blockedInputs.add('open-system-menu')
    }

    switch (activeTutorialCue?.chainId) {
      case 'battle-hud-guard-hp':
        objectiveMode = 'defend-own-tower'
        enabledInputs.add('inspect-own-tower-hp')
        enabledInputs.add('read-loss-condition')
        blockCommonBattleInputs()
        primaryHint = 'Protect your tower HP'
        break
      case 'battle-hud-goal-hp':
        objectiveMode = 'attack-enemy-tower'
        enabledInputs.add('inspect-enemy-tower-hp')
        enabledInputs.add('read-win-condition')
        blockCommonBattleInputs()
        primaryHint = 'Reduce enemy tower HP to zero'
        break
      case 'battle-hud-dispatch-arrows':
        objectiveMode = 'dispatch-lanes'
        enabledInputs.add('dispatch-up-lane')
        enabledInputs.add('dispatch-down-lane')
        blockedInputs.add('produce-unit')
        blockedInputs.add('toggle-hero-sortie')
        primaryHint = 'Choose a lane for unit dispatch'
        break
      case 'battle-hud-unit-card':
        objectiveMode = 'produce-units'
        enabledInputs.add('produce-unit')
        enabledInputs.add('inspect-unit-card')
        blockedInputs.add('dispatch-up-lane')
        blockedInputs.add('dispatch-down-lane')
        primaryHint = 'Produce a unit from the left card tray'
        break
      case 'battle-hud-mana-bar':
        objectiveMode = 'produce-units'
        enabledInputs.add('inspect-mana-bar')
        blockedInputs.add('open-skill-menu')
        blockedInputs.add('open-item-menu')
        primaryHint = 'Mana is spent on unit production'
        break
      case 'battle-hud-hero-sortie':
        objectiveMode = 'dispatch-lanes'
        enabledInputs.add('toggle-hero-sortie')
        enabledInputs.add('deploy-hero')
        blockedInputs.add('return-to-tower')
        primaryHint = 'Deploy the hero from the portrait button'
        break
      case 'battle-hud-hero-return':
        objectiveMode = 'dispatch-lanes'
        enabledInputs.add('return-to-tower')
        blockedInputs.add('deploy-hero')
        primaryHint = 'Return to the tower and wait out cooldown'
        break
      case 'tower-menu-highlight':
      case 'mana-upgrade-highlight':
      case 'population-upgrade-highlight':
        objectiveMode = 'manage-tower'
        openPanel = 'tower'
        enabledInputs.add('open-tower-menu')
        enabledInputs.add('upgrade-tower-stat')
        blockedInputs.add('cast-skill')
        blockedInputs.add('use-item')
        primaryHint =
          activeTutorialCue.chainId === 'mana-upgrade-highlight'
            ? 'Upgrade mana when the bar is full'
            : activeTutorialCue.chainId === 'population-upgrade-highlight'
              ? 'Increase population before unit cap blocks production'
              : 'Open the tower panel'
        break
      case 'skill-menu-highlight':
      case 'skill-slot-highlight':
        objectiveMode = 'cast-skills'
        openPanel = 'skill'
        enabledInputs.add('open-skill-menu')
        enabledInputs.add('cast-skill')
        blockedInputs.add('use-item')
        primaryHint =
          activeTutorialCue.chainId === 'skill-slot-highlight'
            ? 'Use a skill from the visible skill window'
            : 'Open the skill panel'
        break
      case 'item-menu-highlight':
        objectiveMode = 'use-items'
        openPanel = 'item'
        enabledInputs.add('open-item-menu')
        enabledInputs.add('use-item')
        blockedInputs.add('cast-skill')
        primaryHint = 'Use an equipped item from the item panel'
        break
      case 'system-menu-highlight':
        objectiveMode = 'system-navigation'
        openPanel = 'system'
        enabledInputs.add('open-system-menu')
        enabledInputs.add('resume-battle')
        enabledInputs.add('open-settings')
        primaryHint = 'Use the system menu for pause, resume, and settings'
        break
      case 'quest-panel-highlight':
        objectiveMode = 'review-quests'
        openPanel = 'system'
        enabledInputs.add('open-system-menu')
        enabledInputs.add('review-quest-rewards')
        primaryHint = 'Review quest rewards from the quest panel'
        break
      default:
        if (openPanel) {
          objectiveMode =
            openPanel === 'tower'
              ? 'manage-tower'
              : openPanel === 'skill'
                ? 'cast-skills'
                : openPanel === 'item'
                  ? 'use-items'
                  : 'system-navigation'
        } else if (hudState.highlightedUnitCardIndex !== null) {
          objectiveMode = 'produce-units'
        } else if (hudState.dispatchArrowsHighlighted) {
          objectiveMode = 'dispatch-lanes'
        } else if (questState !== 'hidden') {
          objectiveMode = 'review-quests'
        }
        break
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
      mode = activeTutorialCue ? 'guided-preview' : 'free-preview'
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

    if (this.campaignScenePhase === 'worldmap') {
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
    this.previewOwnTowerHpRatio = 0.74
    this.previewEnemyTowerHpRatio = 0.58
    this.skillCooldownEndsAtMs = 0
    this.itemCooldownEndsAtMs = 0
    this.heroAssignedLane = null
    this.currentObjectivePhase = 'opening'
    this.currentObjectiveLabel = 'stabilize the opening lane'
    this.currentWaveIndex = 1
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

  private applyAction(actionId: RecoveryGameplayActionId, snapshot: RecoveryStageSnapshot): void {
    const gameplayState = snapshot.gameplayState
    const nowMs = this.lastUpdateNowMs
    switch (actionId) {
      case 'open-tower-menu':
        this.panelOverride = 'tower'
        this.lastActionNote = 'tower panel opened'
        break
      case 'open-skill-menu':
        this.panelOverride = 'skill'
        this.lastActionNote = 'skill panel opened'
        break
      case 'open-item-menu':
        this.panelOverride = 'item'
        this.lastActionNote = 'item panel opened'
        break
      case 'open-system-menu':
      case 'open-settings':
        this.panelOverride = 'system'
        this.setBattlePaused(nowMs, true)
        this.lastActionNote = actionId === 'open-settings' ? 'settings route selected' : 'system panel opened'
        break
      case 'resume-battle':
        this.panelOverride = null
        this.setBattlePaused(nowMs, false)
        this.lastActionNote = 'panel closed, battle resumed'
        break
      case 'upgrade-tower-stat':
        this.panelOverride = 'tower'
        this.applyTowerUpgrade(snapshot)
        break
      case 'cast-skill':
        {
          const activeLoadout = this.activeDeployLoadout
          const skillPresetKind = activeLoadout?.skillPresetKind ?? 'balanced'
          const hasJuno = this.loadoutHasMember(activeLoadout, 'Juno')
          const hasManos = this.loadoutHasMember(activeLoadout, 'Manos')
          const hasHelba = this.loadoutHasMember(activeLoadout, 'Helba')
          const cooldownScale =
            skillPresetKind === 'burst'
              ? 1.12
              : skillPresetKind === 'support'
                ? 0.84
                : skillPresetKind === 'orders'
                  ? 0.9
                  : skillPresetKind === 'utility'
                    ? 0.88
                    : 1
          const burstBonus =
            skillPresetKind === 'burst'
              ? 0.05
              : skillPresetKind === 'orders'
                ? 0.02
                : skillPresetKind === 'utility'
                  ? 0.025
                  : 0
        this.panelOverride = 'skill'
        this.skillCooldownEndsAtMs = nowMs + Math.round(SKILL_COOLDOWN_MS * cooldownScale)
        this.previewEnemyTowerHpRatio = clamp(
          this.previewEnemyTowerHpRatio - (0.07 + this.currentStageBattleProfile.armageddonBurst * 0.12 + burstBonus),
          0.08,
          1,
        )
        this.previewManaRatio = clamp(
          this.previewManaRatio
          - 0.08
          + this.currentStageBattleProfile.manaSurge * 0.06
          + (skillPresetKind === 'utility' ? 0.05 : 0)
          + (skillPresetKind === 'support' ? 0.03 : 0),
          0.06,
          1,
        )
        if (this.currentStageBattleProfile.armageddonBurst > 0.12) {
          ;(['upper', 'lower'] as const).forEach((laneId) => {
            this.laneBattleState[laneId].enemyUnits = Math.max(this.laneBattleState[laneId].enemyUnits - 1, 0)
            this.laneBattleState[laneId].enemyPressure = clamp(
              this.laneBattleState[laneId].enemyPressure - this.currentStageBattleProfile.armageddonBurst * 0.14,
              0.08,
              1,
            )
          })
        }
          if (hasJuno) {
            this.previewManaRatio = clamp(this.previewManaRatio + 0.04, 0.06, 1)
            this.skillCooldownEndsAtMs = Math.max(this.skillCooldownEndsAtMs - 220, nowMs)
          }
          if (hasManos) {
            this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.022, 0.08, 1)
            ;(['upper', 'lower'] as const).forEach((laneId) => {
              this.laneBattleState[laneId].enemyPressure = clamp(this.laneBattleState[laneId].enemyPressure - 0.03, 0.08, 1)
            })
          }
          if (hasHelba) {
            this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.025, 0.1, 1)
          }
          if (skillPresetKind === 'support') {
            this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.06, 0.1, 1)
          } else if (skillPresetKind === 'orders' && this.selectedDispatchLane) {
            this.laneBattleState[this.selectedDispatchLane].alliedPressure = clamp(
              this.laneBattleState[this.selectedDispatchLane].alliedPressure + 0.08,
              0.08,
              1,
            )
          }
          this.lastActionNote = `skill cast preview accepted (${this.currentStageBattleProfile.archetypeSignals.join('/') || 'generic'} / ${activeLoadout?.skillPresetLabel ?? 'balanced'})`
        }
        break
      case 'use-item':
        {
          const activeLoadout = this.activeDeployLoadout
          const hasHelba = this.loadoutHasMember(activeLoadout, 'Helba')
          const hasCaesar = this.loadoutHasMember(activeLoadout, 'Caesar')
          const hasRogan = this.loadoutHasMember(activeLoadout, 'Rogan')
        this.panelOverride = 'item'
        this.itemCooldownEndsAtMs = nowMs + ITEM_COOLDOWN_MS
        this.previewOwnTowerHpRatio = clamp(
          this.previewOwnTowerHpRatio + 0.08 + this.currentStageBattleProfile.towerDefenseBias * 0.1,
          0.1,
          1,
        )
        if (this.currentStageBattleProfile.towerDefenseBias > 0.1) {
          const guardLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
          this.laneBattleState[guardLane].enemyPressure = clamp(
            this.laneBattleState[guardLane].enemyPressure - this.currentStageBattleProfile.towerDefenseBias * 0.16,
            0.08,
            1,
          )
          this.laneBattleState[guardLane].frontline = clamp(
            this.laneBattleState[guardLane].frontline + this.currentStageBattleProfile.towerDefenseBias * 0.08,
            0.04,
            0.96,
          )
        }
          if (hasHelba) {
            this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.03, 0.1, 1)
          }
          if (hasCaesar) {
            const guardLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
            this.laneBattleState[guardLane].enemyPressure = clamp(this.laneBattleState[guardLane].enemyPressure - 0.035, 0.08, 1)
          }
          if (hasRogan) {
            this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, 4)
          }
          if (activeLoadout?.towerPolicyKind === 'mana-first') {
            this.previewManaRatio = clamp(this.previewManaRatio + 0.08, 0.06, 1)
          } else if (activeLoadout?.towerPolicyKind === 'population-first') {
            this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, 4)
          } else if (activeLoadout?.towerPolicyKind === 'attack-first') {
            this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.03, 0.08, 1)
          }
          this.lastActionNote = `item use preview accepted (${activeLoadout?.towerPolicyLabel ?? 'balanced towers'})`
        }
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
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, 4)
        this.previewManaRatio = clamp(this.previewManaRatio - 0.16, 0.06, 1)
        this.previewManaUpgradeProgressRatio = clamp(this.previewManaUpgradeProgressRatio + 0.08, 0.04, 1)
        if (hasRogan) {
          this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, 4)
        }
        if (hasVincent && this.selectedDispatchLane) {
          this.laneBattleState[this.selectedDispatchLane].alliedPressure = clamp(
            this.laneBattleState[this.selectedDispatchLane].alliedPressure + 0.03,
            0.08,
            1,
          )
        }
        this.lastActionNote = `unit production preview accepted${activeLoadout ? ` (${activeLoadout.heroRosterLabel})` : ''}`
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
          if (this.heroAssignedLane) {
            this.laneBattleState[this.heroAssignedLane].heroPresent = false
          }
          this.heroAssignedLane = null
          this.previewOwnTowerHpRatio = clamp(
            this.previewOwnTowerHpRatio + 0.04 + (activeLoadout?.heroRosterRole === 'support' ? 0.03 : 0),
            0.1,
            1,
          )
          this.lastActionNote = `hero returned to tower (${activeLoadout?.heroRosterLabel ?? 'core squad'})`
        } else {
          this.heroOverrideMode = 'field'
          this.heroReturnCooldownEndsAtMs = 0
          this.heroAssignedLane = activeLoadout?.heroLane ?? this.selectedDispatchLane ?? 'upper'
          this.laneBattleState[this.heroAssignedLane].heroPresent = true
          this.previewEnemyTowerHpRatio = clamp(
            this.previewEnemyTowerHpRatio
            - 0.04
            - (activeLoadout?.heroRosterRole === 'raider' ? 0.03 : activeLoadout?.heroRosterRole === 'vanguard' ? 0.02 : 0),
            0.08,
            1,
          )
          if ((activeLoadout?.heroRosterRole === 'defender' || activeLoadout?.heroRosterRole === 'support') && this.heroAssignedLane) {
            this.laneBattleState[this.heroAssignedLane].alliedPressure = clamp(
              this.laneBattleState[this.heroAssignedLane].alliedPressure + 0.06,
              0.08,
              1,
            )
          }
          if (hasVincent && this.heroAssignedLane) {
            this.laneBattleState[this.heroAssignedLane].frontline = clamp(this.laneBattleState[this.heroAssignedLane].frontline + 0.04, 0.04, 0.96)
          }
          if (hasJuno) {
            this.skillCooldownEndsAtMs = Math.max(this.skillCooldownEndsAtMs - 240, nowMs)
          }
          if (hasManos) {
            this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.02, 0.08, 1)
          }
          if (hasCaesar && this.heroAssignedLane) {
            this.laneBattleState[this.heroAssignedLane].alliedUnits = Math.min(this.laneBattleState[this.heroAssignedLane].alliedUnits + 1, 8)
          }
          this.lastActionNote = `hero deployed to ${this.heroAssignedLane} lane (${activeLoadout?.heroRosterLabel ?? 'core squad'})`
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
            this.laneBattleState[this.heroAssignedLane].alliedUnits = Math.min(
              this.laneBattleState[this.heroAssignedLane].alliedUnits + 1,
              8,
            )
            this.laneBattleState[this.heroAssignedLane].frontline = clamp(
              this.laneBattleState[this.heroAssignedLane].frontline - this.currentStageBattleProfile.recallSwing * 0.18,
              0.04,
              0.96,
            )
          }
          this.laneBattleState[this.heroAssignedLane].heroPresent = false
        }
        this.heroAssignedLane = null
        this.previewOwnTowerHpRatio = clamp(
          this.previewOwnTowerHpRatio + 0.04 + (activeLoadout?.heroRosterRole === 'support' ? 0.04 : 0) + (hasHelba ? 0.02 : 0),
          0.1,
          1,
        )
        if (hasCaesar) {
          const guardLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
          this.laneBattleState[guardLane].alliedPressure = clamp(this.laneBattleState[guardLane].alliedPressure + 0.04, 0.08, 1)
        }
        this.lastActionNote = `hero return cooldown started (${activeLoadout?.heroRosterLabel ?? 'core squad'})`
        }
        break
      case 'review-quest-rewards':
        this.panelOverride = 'system'
        this.setBattlePaused(nowMs, true)
        this.lastActionNote = 'quest reward panel reviewed'
        break
      case 'claim-quest-reward':
        this.panelOverride = 'system'
        this.questRewardClaimed = true
        this.questRewardClaims += 1
        this.previewManaRatio = clamp(this.previewManaRatio + 0.18, 0.06, 1)
        this.previewManaUpgradeProgressRatio = clamp(this.previewManaUpgradeProgressRatio + 0.16, 0.04, 1)
        this.lastActionNote = 'quest reward claimed'
        break
      default:
        this.lastActionNote = `${actionId} accepted`
        break
    }
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

  private tickPersistentPreview(): void {
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
    this.previewManaRatio = clamp(
      this.previewManaRatio + MANA_RECOVERY_PER_BEAT + manaBonus + (hasJuno ? (stageBias.manaBias ? 0.007 : 0.004) : 0),
      0.06,
      1,
    )
    this.previewManaUpgradeProgressRatio = clamp(
      this.previewManaUpgradeProgressRatio
      + UPGRADE_PROGRESS_RECOVERY_PER_BEAT
      + upgradeBonus
      + (hasRogan ? (stageBias.dispatchBias ? 0.007 : 0.004) : 0),
      0.04,
      1,
    )

    if (this.heroOverrideMode === 'field') {
      this.previewEnemyTowerHpRatio = clamp(
        this.previewEnemyTowerHpRatio
        - 0.004
        - (activeLoadout?.heroRosterRole === 'raider' ? 0.002 : activeLoadout?.heroRosterRole === 'vanguard' ? 0.001 : 0)
        - (hasVincent ? (stageBias.siegeBias || stageBias.heroBias ? 0.0025 : 0.0015) : 0)
        - (hasManos ? (stageBias.siegeBias ? 0.0025 : 0.0015) : 0),
        0.08,
        1,
      )
    }

    if (activeLoadout?.heroRosterRole === 'defender' || activeLoadout?.heroRosterRole === 'support') {
      this.previewOwnTowerHpRatio = clamp(
        this.previewOwnTowerHpRatio
        + 0.002
        + (hasHelba ? (stageBias.sustainBias || stageBias.rewardBias ? 0.0035 : 0.002) : 0)
        + (hasCaesar ? (stageBias.sustainBias ? 0.0025 : 0.0015) : 0),
        0.1,
        1,
      )
    }

    if (this.selectedDispatchLane && this.queuedUnitCount > 0 && this.previewManaRatio > 0.18) {
      this.previewEnemyTowerHpRatio = clamp(
        this.previewEnemyTowerHpRatio - 0.006 - (activeLoadout?.skillPresetKind === 'orders' ? 0.002 : 0),
        0.08,
        1,
      )
      if (hasRogan) {
        this.laneBattleState[this.selectedDispatchLane].alliedUnits = Math.min(this.laneBattleState[this.selectedDispatchLane].alliedUnits + 1, 8)
      }
      if (hasVincent && stageBias.dispatchBias) {
        this.laneBattleState[this.selectedDispatchLane].alliedPressure = clamp(
          this.laneBattleState[this.selectedDispatchLane].alliedPressure + 0.02,
          0.08,
          1,
        )
      }
    }

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
    this.towerUpgradeLevels[upgradeId] = Math.min(this.towerUpgradeLevels[upgradeId] + 1, 5)
    this.previewManaRatio = clamp(
      this.previewManaRatio - 0.22 + (towerPolicyKind === 'mana-first' ? 0.06 : 0),
      0.06,
      1,
    )
    this.previewManaUpgradeProgressRatio = clamp(this.previewManaUpgradeProgressRatio - 0.3, 0.04, 1)
    this.lastActionNote = `${upgradeId} upgrade advanced to tier ${this.towerUpgradeLevels[upgradeId]} (${this.activeDeployLoadout?.towerPolicyLabel ?? 'balanced towers'})`
  }

  private commitLaneDispatch(lane: 'upper' | 'lower'): void {
    this.selectedDispatchLane = lane
    if (this.queuedUnitCount > 0) {
      const queueDamage = Math.min(this.queuedUnitCount * 0.04, 0.16)
      const commitCount = Math.min(
        this.queuedUnitCount,
        this.currentStageBattleProfile.dispatchBoost >= 0.16 ? 3 : 2,
      )
      this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - queueDamage, 0.08, 1)
      this.laneBattleState[lane].alliedUnits = Math.min(this.laneBattleState[lane].alliedUnits + commitCount, 8)
      this.laneBattleState[lane].alliedPressure = clamp(
        this.laneBattleState[lane].alliedPressure + commitCount * (0.08 + this.currentStageBattleProfile.dispatchBoost),
        0.08,
        1,
      )
      this.queuedUnitCount = Math.max(this.queuedUnitCount - commitCount, 0)
      this.lastActionNote = `${lane} lane selected with ${commitCount} unit push`
      return
    }
    this.lastActionNote = `${lane} lane primed`
  }

  private seedBattlePreviewState(storyboard: RecoveryStageStoryboard): void {
    this.currentStageBattleProfile = this.deriveStageBattleProfile(storyboard)
    this.seedBattleObjectiveState(storyboard)
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

    this.laneBattleState[favoredLane] = {
      alliedUnits: favoredAllies,
      enemyUnits: favoredEnemies,
      alliedPressure: clamp(this.currentStageBattleProfile.alliedPressureScale + 0.08, 0.08, 1),
      enemyPressure: clamp(this.currentStageBattleProfile.enemyPressureScale + 0.04, 0.08, 1),
      frontline: favoredFrontline,
      contested: 0.3,
      momentum:
        this.currentStageBattleProfile.alliedPressureScale >= this.currentStageBattleProfile.enemyPressureScale
          ? 'allied-push'
          : 'enemy-push',
      heroPresent: false,
    }

    this.laneBattleState[supportLane] = {
      alliedUnits: supportAllies,
      enemyUnits: supportEnemies,
      alliedPressure: clamp(this.currentStageBattleProfile.alliedPressureScale - 0.05, 0.08, 1),
      enemyPressure: clamp(this.currentStageBattleProfile.enemyPressureScale - 0.02, 0.08, 1),
      frontline: supportFrontline,
      contested: 0.38,
      momentum: 'contested',
      heroPresent: false,
    }

    this.previewManaRatio = clamp(
      0.32 + this.currentStageBattleProfile.alliedPressureScale * 0.55 - this.currentStageBattleProfile.enemyPressureScale * 0.14,
      0.2,
      0.9,
    )
    this.previewManaUpgradeProgressRatio = clamp(
      0.16 + this.currentStageBattleProfile.alliedPressureScale * 0.34,
      0.08,
      0.92,
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
  }

  private seedBattleObjectiveState(storyboard: RecoveryStageStoryboard): void {
    const seed = this.deriveObjectiveSeed(storyboard, this.currentStageBattleProfile)
    this.totalWaveCount = seed.totalWaveCount
    this.currentWaveIndex = 1
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
    this.previewManaRatio = clamp(Math.max(this.previewManaRatio, loadout.startingManaRatio + routeInfluence.manaDelta), 0.06, 1)
    this.previewManaUpgradeProgressRatio = clamp(
      Math.max(this.previewManaUpgradeProgressRatio, loadout.startingManaUpgradeProgressRatio + Math.max(routeInfluence.queueDelta, 0) * 0.03),
      0.04,
      1,
    )
    this.towerUpgradeLevels.mana = Math.max(loadout.towerUpgrades.mana, routeInfluence.matchesPreferred && routeBias.manaRoute ? 2 : 1)
    this.towerUpgradeLevels.population = loadout.towerUpgrades.population
    this.towerUpgradeLevels.attack = Math.max(loadout.towerUpgrades.attack, routeInfluence.matchesPreferred && routeBias.sustainRoute ? 2 : 1)

    if (loadout.towerPolicyKind === 'mana-first') {
      this.previewManaRatio = clamp(this.previewManaRatio + 0.08, 0.06, 1)
    } else if (loadout.towerPolicyKind === 'population-first') {
      this.previewManaUpgradeProgressRatio = clamp(this.previewManaUpgradeProgressRatio + 0.1, 0.04, 1)
    } else if (loadout.towerPolicyKind === 'attack-first') {
      this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.03, 0.08, 1)
    }

    if (loadout.dispatchLane) {
      const openingLane = routeInfluence.preferredLane ?? routeBias.preferredLane ?? loadout.dispatchLane
      this.laneBattleState[openingLane].alliedUnits = Math.min(
        this.laneBattleState[openingLane].alliedUnits + Math.min(loadout.startingQueue + (routeBias.flankingRoute ? 1 : 0) + Math.max(0, Math.round(routeInfluence.queueDelta)), 4),
        8,
      )
      this.laneBattleState[openingLane].alliedPressure = clamp(
        this.laneBattleState[openingLane].alliedPressure + loadout.startingQueue * 0.04 + routeBias.pressureShift + routeInfluence.pressureDelta,
        0.08,
        1,
      )
    }

    if (loadout.towerUpgrades.attack > 1 || loadout.towerUpgrades.population > 1) {
      const guardLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
      this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.06, 0.12, 1)
      this.laneBattleState[guardLane].enemyPressure = clamp(
        this.laneBattleState[guardLane].enemyPressure - 0.06,
        0.08,
        1,
      )
    }

    if (loadout.heroStartMode === 'field') {
      this.heroOverrideMode = 'field'
      this.heroAssignedLane = routeInfluence.preferredLane ?? routeBias.preferredLane ?? loadout.heroLane ?? loadout.dispatchLane ?? (this.currentStageBattleProfile.favoredLane ?? 'upper')
      this.laneBattleState[this.heroAssignedLane].heroPresent = true
      this.previewEnemyTowerHpRatio = clamp(
        this.previewEnemyTowerHpRatio
        - 0.05
        - this.currentStageBattleProfile.heroImpact * 0.08
        - routeBias.heroShift
        - routeInfluence.heroDelta
        - (loadout.heroRosterRole === 'raider' ? 0.03 : loadout.heroRosterRole === 'vanguard' ? 0.02 : 0),
        0.08,
        1,
      )
      if (loadout.heroRosterRole === 'support' || loadout.heroRosterRole === 'defender') {
        this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.05 + routeInfluence.defenseDelta, 0.1, 1)
      }
    } else {
      this.heroOverrideMode = null
      this.heroAssignedLane = null
    }
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
      ?? (mapBinding?.inlinePairBranchIndexCandidate !== null && mapBinding?.inlinePairBranchIndexCandidate !== undefined
        ? (mapBinding.inlinePairBranchIndexCandidate % 2 === 0 ? 'upper' : 'lower')
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

  private buildBattlePreviewState(): RecoveryBattlePreviewState {
    const lanes: RecoveryLaneBattleState[] = (['upper', 'lower'] as const).map((laneId) => ({
      laneId,
      ...this.laneBattleState[laneId],
    }))
    const allyMomentum = lanes.reduce((sum, lane) => sum + lane.alliedPressure, 0) / lanes.length
    const enemyMomentum = lanes.reduce((sum, lane) => sum + lane.enemyPressure, 0) / lanes.length
    return {
      lanes,
      selectedLane: this.selectedDispatchLane,
      queuedReserve: this.queuedUnitCount,
      allyMomentum,
      enemyMomentum,
      towerThreat: clamp(1 - this.previewOwnTowerHpRatio + enemyMomentum * 0.22, 0, 1),
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

  private tickLaneBattlePreview(): void {
    const beat = Math.max(this.lastChannelBeat, 0)
    const profile = this.currentStageBattleProfile
    const favoredLane = profile.favoredLane ?? 'upper'
    const supportLane = favoredLane === 'upper' ? 'lower' : 'upper'
    const enemyDirective = this.currentLoadoutDirective(this.enemyWavePlan, 'enemy', 'tick')
    const alliedDirective = this.currentLoadoutDirective(this.alliedWavePlan, 'allied', 'tick')

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
      this.resetWaveCountdown('allied', resolvedDirective)
    }

    ;(['upper', 'lower'] as const).forEach((laneId, index) => {
      const lane = this.laneBattleState[laneId]
      const phase = oscillate(beat * 120, 3400 + index * 500, index * 700)
      const enemyReinforcement =
        profile.enemyPressureScale * 0.08
        + phase * profile.enemyPressureScale * 0.12
        + (profile.favoredLane === laneId ? 0.014 : 0)
        - (profile.towerDefenseBias * (profile.favoredLane === laneId ? 0.035 : 0.015))
      const alliedReinforcement =
        profile.alliedPressureScale * 0.08
        + (this.selectedDispatchLane === laneId ? 0.03 + profile.dispatchBoost * 0.18 : 0)
        + (this.heroAssignedLane === laneId ? profile.heroImpact : 0)
        + (this.towerUpgradeLevels.attack - 1) * 0.008

      lane.enemyPressure = clamp(lane.enemyPressure * 0.88 + enemyReinforcement, 0.08, 1)
      lane.alliedPressure = clamp(lane.alliedPressure * 0.86 + alliedReinforcement, 0.08, 1)

      const heroBonus = this.heroAssignedLane === laneId ? profile.heroImpact : 0
      const netPush = lane.alliedPressure + lane.alliedUnits * 0.035 + heroBonus - (lane.enemyPressure + lane.enemyUnits * 0.03)
      lane.frontline = clamp(lane.frontline + netPush * 0.11, 0.04, 0.96)
      if (profile.recallSwing > 0.12 && this.heroAssignedLane === laneId && beat % 9 === 0) {
        lane.frontline = clamp(lane.frontline + profile.recallSwing * 0.04, 0.04, 0.96)
      }
      lane.contested = clamp(1 - Math.abs(netPush) * 2.8, 0.08, 1)

      if (lane.frontline > 0.72) {
        this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.004 - lane.alliedUnits * 0.0008, 0.08, 1)
      } else if (lane.frontline < 0.28) {
        this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio - 0.003 - lane.enemyUnits * 0.0007, 0.1, 1)
      }

      if (lane.frontline > 0.6 && lane.enemyUnits > 0 && beat % 3 === 0) {
        lane.enemyUnits = Math.max(lane.enemyUnits - 1, 0)
      } else if (lane.frontline < 0.4 && lane.alliedUnits > 0 && beat % 4 === 0) {
        lane.alliedUnits = Math.max(lane.alliedUnits - 1, 0)
      }

      lane.heroPresent = this.heroAssignedLane === laneId
      lane.momentum =
        netPush > 0.08
          ? 'allied-push'
          : netPush < -0.08
            ? 'enemy-push'
            : lane.contested > 0.62
              ? 'contested'
              : 'stalled'
    })

    const allyMomentum =
      (this.laneBattleState.upper.alliedPressure + this.laneBattleState.lower.alliedPressure) / 2
    const enemyMomentum =
      (this.laneBattleState.upper.enemyPressure + this.laneBattleState.lower.enemyPressure) / 2
    const pressureSwing = clamp(
      (allyMomentum - enemyMomentum) * 0.06 + (1 - this.previewEnemyTowerHpRatio) * 0.02 + (this.heroAssignedLane ? 0.008 : 0),
      0.002,
      0.04,
    )
    this.objectiveProgressRatio = clamp(this.objectiveProgressRatio + pressureSwing, 0.04, 1)
    this.currentWaveIndex = clamp(1 + Math.floor(this.objectiveProgressRatio * this.totalWaveCount), 1, this.totalWaveCount)

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
