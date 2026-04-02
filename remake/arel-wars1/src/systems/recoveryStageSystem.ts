import type {
  RecoveryBattleChannelState,
  RecoveryCatalog,
  RecoveryDialogueEvent,
  RecoveryPreviewFrame,
  RecoveryPreviewManifest,
  RecoveryPreviewStem,
  RecoveryRuntimeBlueprint,
  RecoveryScriptEntry,
  RecoveryStageBlueprint,
  RecoveryStageRenderState,
  RecoveryStageSnapshot,
  RecoveryStageStoryboard,
} from '../recovery-types'

const MIN_DIALOGUE_DURATION_MS = 1400
const MAX_DIALOGUE_DURATION_MS = 4200
const STORYBOARD_GAP_MS = 900

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
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
    const channelStates = this.buildChannelStates(currentStoryboard)
    return {
      storyboardIndex: this.storyboardIndex,
      dialogueIndex: this.dialogueIndex,
      frameIndex: this.frameIndex,
      elapsedStoryboardMs: Math.max(this.lastUpdateNowMs - this.storyboardStartedAtMs, 0),
      currentStoryboard,
      channelStates,
      renderState: this.buildRenderState(currentStoryboard, channelStates),
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
    const snapshot = this.getSnapshot()
    const event = snapshot?.currentStoryboard.scriptEvents[snapshot.dialogueIndex]
    if (!event) {
      return 1800
    }
    return dialogueDurationMs(event)
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
}
