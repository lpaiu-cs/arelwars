import type {
  RecoveryBattleChannelState,
  RecoveryCatalog,
  RecoveryDialogueEvent,
  RecoveryGameplayState,
  RecoveryHudGhostState,
  RecoveryResolvedOpcodeCue,
  RecoveryPreviewFrame,
  RecoveryPreviewManifest,
  RecoveryPreviewStem,
  RecoveryRuntimeBlueprint,
  RecoveryScriptEntry,
  RecoveryStageBlueprint,
  RecoveryStageRenderState,
  RecoveryStageSnapshot,
  RecoveryStageStoryboard,
  RecoveryTutorialChainCue,
} from '../recovery-types'

const MIN_DIALOGUE_DURATION_MS = 1400
const MAX_DIALOGUE_DURATION_MS = 4200
const STORYBOARD_GAP_MS = 900
const GENERIC_OPCODE_VARIANTS = new Set([
  'cmd-02:05',
  'cmd-05:03',
  'cmd-08:00',
  'cmd-10:00',
  'cmd-18:00',
  'cmd-43:00',
])

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
    return {
      storyboardIndex: this.storyboardIndex,
      dialogueIndex: this.dialogueIndex,
      frameIndex: this.frameIndex,
      elapsedStoryboardMs: Math.max(this.lastUpdateNowMs - this.storyboardStartedAtMs, 0),
      currentStoryboard,
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
    }
  }

  advance(nowMs: number): boolean {
    if (!this.isReady()) {
      return false
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

    while (nowMs >= this.nextDialogueAtMs) {
      this.stepDialogue(nowMs)
      changed = true
    }

    const channelBeat = Math.floor(Math.max(nowMs - this.storyboardStartedAtMs, 0) / 120)
    if (channelBeat !== this.lastChannelBeat) {
      this.lastChannelBeat = channelBeat
      changed = true
    }

    if (changed) {
      this.version += 1
    }
    return changed
  }

  private resetDeadlines(nowMs: number): void {
    const storyboard = this.storyboards[this.storyboardIndex]
    this.dialogueIndex = 0
    this.frameIndex = 0
    this.storyboardStartedAtMs = nowMs
    this.lastChannelBeat = -1
    this.nextDialogueAtMs = nowMs + this.currentDialogueDuration()
    this.scheduleNextFrame(storyboard.previewStem, nowMs)
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
      this.advanceStoryboard(nowMs)
      return
    }

    if (this.dialogueIndex >= storyboard.scriptEvents.length - 1) {
      this.advanceStoryboard(nowMs)
      return
    }

    this.dialogueIndex += 1
    this.nextDialogueAtMs = nowMs + this.currentDialogueDuration()
  }

  private advanceStoryboard(nowMs: number): void {
    this.storyboardIndex = (this.storyboardIndex + 1) % this.storyboards.length
    this.dialogueIndex = 0
    this.frameIndex = 0
    this.storyboardStartedAtMs = nowMs
    this.lastChannelBeat = -1
    this.nextDialogueAtMs = nowMs + this.currentDialogueDuration() + STORYBOARD_GAP_MS
    this.scheduleNextFrame(this.storyboards[this.storyboardIndex].previewStem, nowMs)
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
    let ownTowerHpRatio = clamp(0.72 + oscillate(elapsed, 5800, 0) * 0.12 - channelEnergy * 0.04, 0.1, 1)
    let enemyTowerHpRatio = clamp(0.54 + oscillate(elapsed, 5300, 900) * 0.18, 0.1, 1)
    let manaRatio = clamp(0.42 + oscillate(elapsed, 3600, 1400) * 0.5, 0.06, 1)
    let manaUpgradeProgressRatio = clamp(0.18 + oscillate(elapsed, 4200, 600) * 0.72, 0.04, 1)
    let activePanel: RecoveryHudGhostState['activePanel'] = null
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
    const enabledInputs = new Set<string>()
    const blockedInputs = new Set<string>()
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

    if (heroMode === 'field') {
      enabledInputs.add('hero-combat-active')
    }
    if (heroMode === 'return-cooldown') {
      blockedInputs.add('deploy-hero')
    }
    if (questState === 'reward-ready') {
      enabledInputs.add('claim-quest-reward')
    }
    if (mode === 'free-preview' && enabledInputs.size === 0) {
      enabledInputs.add('observe-stage-preview')
    }

    return {
      mode,
      openPanel,
      heroMode,
      objectiveMode,
      questState,
      enabledInputs: Array.from(enabledInputs),
      blockedInputs: Array.from(blockedInputs),
      primaryHint,
    }
  }
}
