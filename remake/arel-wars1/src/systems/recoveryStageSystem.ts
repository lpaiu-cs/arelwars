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

  private readonly campaignClearedStoryboardIds = new Set<string>()

  private campaignLastResolvedStageTitle: string | null = null

  private campaignLastOutcome: 'victory' | 'defeat' | null = null

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
      this.seedBattlePreviewState(this.storyboards[0])
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

    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    const nextIndex = clamp(this.campaignSelectedNodeIndex + direction, 0, unlockedCount - 1)
    if (nextIndex === this.campaignSelectedNodeIndex) {
      return false
    }

    this.campaignSelectedNodeIndex = nextIndex
    const target = this.storyboards[nextIndex]
    this.lastActionNote = `campaign route selected: ${target?.stageBlueprint?.title ?? target?.scriptPath ?? `node ${nextIndex + 1}`}`
    this.version += 1
    return true
  }

  launchSelectedCampaignNode(): boolean {
    if (!this.isReady()) {
      return false
    }

    if (!this.battlePaused && !this.battleResolutionOutcome) {
      this.lastActionNote = 'campaign route launch locked until pause or result'
      this.version += 1
      return false
    }

    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    const nextIndex = clamp(this.campaignSelectedNodeIndex, 0, unlockedCount - 1)
    this.activateStoryboard(nextIndex, this.lastUpdateNowMs, STORYBOARD_GAP_MS)
    const target = this.storyboards[nextIndex]
    this.lastActionNote = `campaign node launched: ${target?.stageBlueprint?.title ?? target?.scriptPath ?? `node ${nextIndex + 1}`}`
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

    if (this.battleResolutionOutcome) {
      if (this.battleResolutionAutoAdvanceAtMs > 0 && nowMs >= this.battleResolutionAutoAdvanceAtMs) {
        this.advanceCampaign(nowMs)
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

  private advanceCampaign(nowMs: number): void {
    if (this.battleResolutionOutcome === 'victory') {
      const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
      this.campaignSelectedNodeIndex = clamp(this.campaignSelectedNodeIndex, 0, unlockedCount - 1)
      const nextIndex = this.campaignSelectedNodeIndex
      this.activateStoryboard(nextIndex, nowMs, STORYBOARD_GAP_MS)
      return
    }
    this.campaignSelectedNodeIndex = this.storyboardIndex
    this.activateStoryboard(this.storyboardIndex, nowMs, STORYBOARD_GAP_MS)
  }

  private buildCampaignState(currentStoryboard: RecoveryStageStoryboard): RecoveryStageSnapshot['campaignState'] {
    const unlockedCount = Math.max(this.campaignUnlockedStageCount, 1)
    const selectedNodeIndex = clamp(this.campaignSelectedNodeIndex, 0, unlockedCount - 1)
    const activeStageTitle = currentStoryboard.stageBlueprint?.title ?? currentStoryboard.scriptPath
    const nextUnlock = this.campaignUnlockedStageCount < this.storyboards.length
      ? this.storyboards[this.campaignUnlockedStageCount]?.stageBlueprint?.title
        ?? this.storyboards[this.campaignUnlockedStageCount]?.scriptPath
        ?? null
      : null
    const recommendedNodeIndex = this.battleResolutionOutcome === 'victory'
      ? Math.min(this.storyboardIndex + 1, unlockedCount - 1)
      : this.storyboardIndex
    const selectionMode = this.battleResolutionOutcome
      ? 'result-route-selection'
      : this.battlePaused
        ? 'worldmap-selection'
        : selectedNodeIndex !== this.storyboardIndex
          ? 'queued-route-selection'
          : 'follow-active-stage'
    return {
      currentNodeIndex: this.storyboardIndex + 1,
      selectedNodeIndex: selectedNodeIndex + 1,
      unlockedNodeCount: unlockedCount,
      clearedStageCount: this.campaignClearedStoryboardIds.size,
      totalNodeCount: this.storyboards.length,
      activeStageTitle,
      activeFamilyId: currentStoryboard.scriptFamilyId,
      routeLabel: currentStoryboard.stageBlueprint?.mapBinding?.storyBranch ?? 'route-unknown',
      selectionMode,
      selectionLaunchable: this.battlePaused || this.battleResolutionOutcome !== null,
      nextUnlockLabel: nextUnlock,
      lastResolvedStageTitle: this.campaignLastResolvedStageTitle,
      lastOutcome: this.campaignLastOutcome,
      nodes: this.storyboards.map((storyboard, index) => ({
        nodeIndex: index + 1,
        label: storyboard.stageBlueprint?.title ?? storyboard.scriptPath.replace('assets/', ''),
        familyId: storyboard.scriptFamilyId,
        routeLabel: storyboard.stageBlueprint?.mapBinding?.storyBranch ?? 'route-unknown',
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
      this.objectiveProgressRatio = clamp(this.objectiveProgressRatio + progressDelta, 0.02, 1)
    }
  }

  private currentWaveDirective(plan: RecoveryBattleWaveDirective[]): RecoveryBattleWaveDirective | null {
    if (plan.length === 0) {
      return null
    }
    return plan[Math.min(Math.max(this.currentWaveIndex - 1, 0), plan.length - 1)] ?? null
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

  private triggerSceneWave(
    side: 'enemy' | 'allied',
    note: string,
    advanceWave: boolean,
  ): void {
    if (advanceWave && this.currentWaveIndex < this.totalWaveCount) {
      this.currentWaveIndex += 1
      this.objectiveProgressRatio = clamp(
        Math.max(this.objectiveProgressRatio, this.currentWaveIndex / this.totalWaveCount - 0.08),
        0.04,
        1,
      )
    }

    const plan = side === 'enemy' ? this.enemyWavePlan : this.alliedWavePlan
    const directive = this.currentWaveDirective(plan)
    this.applyWaveDirective(side, directive)
    this.resetWaveCountdown(side, directive)
    this.evaluateBattleResolution()
    this.lastScriptedBeatNote = directive ? `${note} (${directive.label})` : note
  }

  private resolveBattleOutcome(outcome: 'victory' | 'defeat', reason: string): void {
    if (this.battleResolutionOutcome) {
      return
    }
    const currentStoryboard = this.storyboards[this.storyboardIndex]
    this.battleResolutionOutcome = outcome
    this.battleResolutionReason = reason
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
    if (outcome === 'victory') {
      this.campaignSelectedNodeIndex = clamp(
        Math.min(this.storyboardIndex + 1, Math.max(this.campaignUnlockedStageCount, 1) - 1),
        0,
        Math.max(this.campaignUnlockedStageCount, 1) - 1,
      )
    } else {
      this.campaignSelectedNodeIndex = this.storyboardIndex
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

    const allyMomentum = (this.laneBattleState.upper.alliedPressure + this.laneBattleState.lower.alliedPressure) / 2
    const enemyMomentum = (this.laneBattleState.upper.enemyPressure + this.laneBattleState.lower.enemyPressure) / 2

    if (
      this.previewEnemyTowerHpRatio <= 0.11
      || (this.currentObjectivePhase === 'siege' && this.previewEnemyTowerHpRatio <= 0.16)
      || (this.objectiveProgressRatio >= 0.98 && allyMomentum >= enemyMomentum - 0.02)
    ) {
      this.resolveBattleOutcome('victory', 'enemy tower pressure collapsed')
      return
    }

    if (
      this.previewOwnTowerHpRatio <= 0.12
      || (this.previewOwnTowerHpRatio <= 0.18 && enemyMomentum - allyMomentum > 0.12)
      || (this.currentObjectivePhase === 'lane-control' && enemyMomentum > 0.9 && this.objectiveProgressRatio < 0.28)
    ) {
      this.resolveBattleOutcome('defeat', 'enemy lane pressure breached the guard line')
    }
  }

  private buildWavePlan(
    storyboard: RecoveryStageStoryboard,
    side: 'enemy' | 'allied',
  ): RecoveryBattleWaveDirective[] {
    const stage = storyboard.stageBlueprint
    const favoredLane = this.currentStageBattleProfile.favoredLane ?? 'upper'
    const supportLane = favoredLane === 'upper' ? 'lower' : 'upper'
    const stageTier = stage?.runtimeFields?.tierCandidate ?? 10
    const storyBranch = stage?.mapBinding?.storyBranch ?? 'primary'
    const title = (stage?.title ?? '').toLowerCase()
    const hintText = (stage?.hintText ?? '').toLowerCase()
    const signals = new Set(this.currentStageBattleProfile.archetypeSignals)
    const highIntensity = (stage?.renderIntent?.effectIntensity ?? 'medium') === 'high'

    return Array.from({ length: this.totalWaveCount }, (_, index) => {
      const waveNumber = index + 1
      if (side === 'enemy') {
        const role: RecoveryBattleWaveDirective['role'] =
          waveNumber === this.totalWaveCount || includesAny(title, ['seize', 'siege', 'enemy camp', 'defeat'])
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
              : storyBranch === 'secondary'
                ? (waveNumber % 2 === 0 ? favoredLane : supportLane)
                : (waveNumber % 2 === 0 ? supportLane : favoredLane)
        const unitBurst = clamp(
          1 + Math.floor(stageTier / 20) + (highIntensity ? 1 : 0) + (role === 'siege' ? 1 : 0),
          1,
          4,
        )
        const pressureBias = clamp(
          0.04
          + stageTier * 0.002
          + (role === 'siege' ? 0.12 : role === 'push' ? 0.08 : role === 'hero-bait' ? 0.06 : 0.04),
          0.04,
          0.32,
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
        signals.has('armageddon') && waveNumber >= Math.max(this.totalWaveCount - 1, 2)
          ? 'skill-window'
          : signals.has('dispatch') && waveNumber <= Math.ceil(this.totalWaveCount / 2)
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
            : waveNumber % 2 === 0 && signals.has('dispatch')
              ? supportLane
              : favoredLane
      const unitBurst = clamp(
        1
        + (signals.has('dispatch') ? 1 : 0)
        + (role === 'skill-window' ? 1 : 0)
        + (role === 'siege' ? 1 : 0),
        1,
        4,
      )
      const pressureBias = clamp(
        0.03
        + this.currentStageBattleProfile.dispatchBoost * 0.3
        + this.currentStageBattleProfile.heroImpact * 0.1
        + (role === 'support' ? 0.03 : role === 'tower-rally' ? 0.04 : role === 'skill-window' ? 0.06 : 0.05),
        0.03,
        0.28,
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
        const intensity = 0.25 + Math.max(pulse, 0) * 0.75
        const phaseLabel =
          intensity > 0.82 ? 'burst' : intensity > 0.52 ? 'arming' : markerCount > 0 ? 'ready' : 'idle'
        const hasExactTailHit = archetype.evidence.some((entry) => entry.includes('exact projectile or effect hits'))

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
      objectiveMode = 'system-navigation'
      primaryHint = 'Battle paused; resume or open settings'
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

    if (this.battleResolutionOutcome) {
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
        primaryHint = 'Stage clear. Claim the reward or wait for auto-advance.'
        enabledInputs.add('open-system-menu')
        enabledInputs.add('review-quest-rewards')
        if (!this.questRewardClaimed) {
          enabledInputs.add('claim-quest-reward')
        }
      } else {
        objectiveMode = 'system-navigation'
        questState = 'hidden'
        primaryHint = 'Tower breached. Preview will roll to the next storyboard.'
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
        this.panelOverride = 'skill'
        this.skillCooldownEndsAtMs = nowMs + SKILL_COOLDOWN_MS
        this.previewEnemyTowerHpRatio = clamp(
          this.previewEnemyTowerHpRatio - (0.07 + this.currentStageBattleProfile.armageddonBurst * 0.12),
          0.08,
          1,
        )
        this.previewManaRatio = clamp(
          this.previewManaRatio - 0.08 + this.currentStageBattleProfile.manaSurge * 0.06,
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
        this.lastActionNote = `skill cast preview accepted (${this.currentStageBattleProfile.archetypeSignals.join('/') || 'generic'})`
        break
      case 'use-item':
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
        this.lastActionNote = 'item use preview accepted'
        break
      case 'dispatch-up-lane':
        this.commitLaneDispatch('upper')
        break
      case 'dispatch-down-lane':
        this.commitLaneDispatch('lower')
        break
      case 'produce-unit':
        this.queuedUnitCount = Math.min(this.queuedUnitCount + 1, 4)
        this.previewManaRatio = clamp(this.previewManaRatio - 0.16, 0.06, 1)
        this.previewManaUpgradeProgressRatio = clamp(this.previewManaUpgradeProgressRatio + 0.08, 0.04, 1)
        this.lastActionNote = 'unit production preview accepted'
        break
      case 'deploy-hero':
      case 'toggle-hero-sortie':
        if (gameplayState.heroMode === 'field') {
          this.heroOverrideMode = 'return-cooldown'
          this.heroReturnCooldownEndsAtMs = nowMs + HERO_RETURN_COOLDOWN_MS
          if (this.heroAssignedLane) {
            this.laneBattleState[this.heroAssignedLane].heroPresent = false
          }
          this.heroAssignedLane = null
          this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.04, 0.1, 1)
          this.lastActionNote = 'hero returned to tower'
        } else {
          this.heroOverrideMode = 'field'
          this.heroReturnCooldownEndsAtMs = 0
          this.heroAssignedLane = this.selectedDispatchLane ?? 'upper'
          this.laneBattleState[this.heroAssignedLane].heroPresent = true
          this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.04, 0.08, 1)
          this.lastActionNote = `hero deployed to ${this.heroAssignedLane} lane`
        }
        break
      case 'return-to-tower':
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
        this.previewOwnTowerHpRatio = clamp(this.previewOwnTowerHpRatio + 0.04, 0.1, 1)
        this.lastActionNote = 'hero return cooldown started'
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
    this.previewManaRatio = clamp(this.previewManaRatio + MANA_RECOVERY_PER_BEAT, 0.06, 1)
    this.previewManaUpgradeProgressRatio = clamp(
      this.previewManaUpgradeProgressRatio + UPGRADE_PROGRESS_RECOVERY_PER_BEAT,
      0.04,
      1,
    )

    if (this.heroOverrideMode === 'field') {
      this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.004, 0.08, 1)
    }

    if (this.selectedDispatchLane && this.queuedUnitCount > 0 && this.previewManaRatio > 0.18) {
      this.previewEnemyTowerHpRatio = clamp(this.previewEnemyTowerHpRatio - 0.006, 0.08, 1)
    }

    this.tickLaneBattlePreview()
  }

  private applyTowerUpgrade(snapshot: RecoveryStageSnapshot): void {
    const gameplayState = snapshot.gameplayState
    const focusedUpgrade = snapshot.hudState.highlightedTowerUpgradeId
    const upgradeId =
      focusedUpgrade
      ?? (gameplayState.primaryHint.includes('population')
        ? 'population'
        : gameplayState.primaryHint.includes('mana')
          ? 'mana'
          : gameplayState.openPanel === 'tower' && this.towerUpgradeLevels.attack < this.towerUpgradeLevels.mana
            ? 'attack'
            : 'mana')
    this.towerUpgradeLevels[upgradeId] = Math.min(this.towerUpgradeLevels[upgradeId] + 1, 5)
    this.previewManaRatio = clamp(this.previewManaRatio - 0.22, 0.06, 1)
    this.previewManaUpgradeProgressRatio = clamp(this.previewManaUpgradeProgressRatio - 0.3, 0.04, 1)
    this.lastActionNote = `${upgradeId} upgrade advanced to tier ${this.towerUpgradeLevels[upgradeId]}`
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
    const stage = storyboard.stageBlueprint
    const stageTier = stage?.runtimeFields?.tierCandidate ?? 10
    const archetypeCount = stage?.recommendedArchetypeIds.length ?? 0
    const eventCount = Math.max(storyboard.scriptEventCount, storyboard.scriptEvents.length, 1)
    const storyBranch = stage?.mapBinding?.storyBranch ?? 'unknown'
    const title = stage?.title ?? storyboard.scriptFamilyId
    const hintText = stage?.hintText ?? ''
    const effectIntensity = stage?.renderIntent?.effectIntensity ?? 'medium'

    this.totalWaveCount = clamp(
      Math.round(eventCount / 24) + Math.max(Math.round(stageTier / 20), 1) + Math.min(archetypeCount, 2),
      3,
      8,
    )
    this.currentWaveIndex = 1
    this.objectiveProgressRatio = clamp(
      0.06
      + (storyBranch === 'secondary' ? 0.03 : 0.01)
      + (effectIntensity === 'high' ? 0.03 : effectIntensity === 'medium' ? 0.015 : 0),
      0.04,
      0.18,
    )
    this.enemyWaveCountdownBeats = Math.max(
      1,
      this.currentStageBattleProfile.enemyWaveCadenceBeats - (effectIntensity === 'high' ? 1 : 0),
    )
    this.alliedWaveCountdownBeats = Math.max(1, this.currentStageBattleProfile.alliedWaveCadenceBeats)
    this.enemyWavePlan = this.buildWavePlan(storyboard, 'enemy')
    this.alliedWavePlan = this.buildWavePlan(storyboard, 'allied')

    if (includesAny(title, ['defeat', 'siege', 'seize', 'enemy camp'])) {
      this.currentObjectivePhase = 'siege'
      this.currentObjectiveLabel = 'break the enemy defensive line'
      return
    }
    if (includesAny(hintText, ['hero', 'eliminate'])) {
      this.currentObjectivePhase = 'hero-pressure'
      this.currentObjectiveLabel = 'use the hero to disrupt clustered enemies'
      return
    }
    if (includesAny(hintText, ['bonus', 'reward', 'clear the stage'])) {
      this.currentObjectivePhase = 'lane-control'
      this.currentObjectiveLabel = 'secure lanes before the bonus window closes'
      return
    }

    this.currentObjectivePhase = 'opening'
    this.currentObjectiveLabel = 'stabilize the opening lane'
  }

  private deriveStageBattleProfile(storyboard: RecoveryStageStoryboard): RecoveryStageBattleProfile {
    const stage = storyboard.stageBlueprint
    const runtimeFields = stage?.runtimeFields
    const mapBinding = stage?.mapBinding
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
      const haystacks = [
        archetype.label,
        archetype.archetypeKind,
        archetype.familyType,
        ...archetype.mechanicHints,
      ]
      const joined = haystacks.join(' ').toLowerCase()

      if (includesAny(joined, ['dispatch', 'redeploy', 'respawn'])) {
        signalSet.add('dispatch')
        dispatchBoost += 0.06
      }
      if (includesAny(joined, ['tower defense', 'defend tower', 'barrier'])) {
        signalSet.add('tower-defense')
        towerDefenseBias += 0.07
      }
      if (includesAny(joined, ['recall', 'relocation'])) {
        signalSet.add('recall')
        recallSwing += 0.09
      }
      if (includesAny(joined, ['armageddon', 'meteor'])) {
        signalSet.add('armageddon')
        armageddonBurst += 0.12
      }
      if (includesAny(joined, ['mana', 'resource-conversion', 'mana gain', 'reactive-mana-proc'])) {
        signalSet.add('mana-surge')
        manaSurge += 0.08
      }
      if (includesAny(joined, ['heal', 'healing'])) {
        signalSet.add('healing')
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
      mapBinding?.inlinePairBranchIndexCandidate !== null && mapBinding?.inlinePairBranchIndexCandidate !== undefined
        ? (mapBinding.inlinePairBranchIndexCandidate % 2 === 0 ? 'upper' : 'lower')
        : ((runtimeFields?.variantCandidate ?? 1) % 2 === 0 ? 'lower' : 'upper')
    const alliedPressureScale = clamp(
      0.18
      + archetypes.length * 0.03
      + activeRowCount * 0.004
      + buffRowCount * 0.003
      + (effectIntensity === 'high' ? 0.05 : effectIntensity === 'medium' ? 0.025 : 0),
      0.16,
      0.64,
    )
    const enemyPressureScale = clamp(
      0.22
      + stageTier * 0.006
      + (runtimeFields?.regionCandidate ?? 5) * 0.012
      + (runtimeFields?.storyFlagCandidate ?? 0) * 0.04,
      0.2,
      0.72,
    )
    const alliedWaveCadenceBeats = Math.max(
      3,
      Math.min(7, 7 - Math.floor(Math.min(activeRowCount, 12) / 3) - (signalSet.has('dispatch') ? 1 : 0)),
    )
    const enemyWaveCadenceBeats = Math.max(3, Math.min(7, 7 - Math.floor(stageTier / 15)))
    const heroImpact = clamp(0.1 + exactTailHitCount * 0.028 + buffRowCount * 0.008 + recallSwing * 0.12, 0.1, 0.36)
    const tacticalBias = `${mapBinding?.storyBranch ?? 'branch-unknown'} / ${favoredLane} initiative${signalSet.size > 0 ? ` / ${Array.from(signalSet).join('+')}` : ''}`
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
        enemyDirective: this.currentWaveDirective(this.enemyWavePlan),
        alliedDirective: this.currentWaveDirective(this.alliedWavePlan),
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
    const enemyDirective = this.currentWaveDirective(this.enemyWavePlan)
    const alliedDirective = this.currentWaveDirective(this.alliedWavePlan)

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
      this.applyWaveDirective('enemy', enemyDirective ?? fallbackDirective)
      this.resetWaveCountdown('enemy', enemyDirective)
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
      this.applyWaveDirective('allied', alliedDirective ?? fallbackDirective)
      this.queuedUnitCount = Math.max(this.queuedUnitCount - Math.min(this.queuedUnitCount, reinforcements), 0)
      this.resetWaveCountdown('allied', alliedDirective)
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
