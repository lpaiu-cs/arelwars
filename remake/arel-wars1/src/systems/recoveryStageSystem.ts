import type {
  RecoveryCatalog,
  RecoveryDialogueEvent,
  RecoveryPreviewFrame,
  RecoveryPreviewManifest,
  RecoveryPreviewStem,
  RecoveryScriptEntry,
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

function buildStoryboards(catalog: RecoveryCatalog, previewManifest: RecoveryPreviewManifest): RecoveryStageStoryboard[] {
  const scripts = chooseScripts(catalog, 6)
  const previews = choosePreviewEntries(previewManifest, Math.max(6, scripts.length))
  if (scripts.length === 0 || previews.length === 0) {
    return []
  }

  return scripts.map((script, index) => {
    const previewStem = previews[index % previews.length]
    return {
      id: `${index}-${script.path}-${previewStem.stem}`,
      scriptPath: script.path,
      locale: script.locale,
      scriptEventCount: script.eventCount ?? script.eventPreview?.length ?? 0,
      scriptEvents: normalizeScriptEvents(script),
      previewStem,
    }
  })
}

export class RecoveryStageSystem {
  private readonly storyboards: RecoveryStageStoryboard[]

  private storyboardIndex = 0

  private dialogueIndex = 0

  private frameIndex = 0

  private nextDialogueAtMs = Number.POSITIVE_INFINITY

  private nextFrameAtMs = Number.POSITIVE_INFINITY

  private version = 0

  constructor(catalog: RecoveryCatalog, previewManifest: RecoveryPreviewManifest) {
    this.storyboards = buildStoryboards(catalog, previewManifest)
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
    return {
      storyboardIndex: this.storyboardIndex,
      dialogueIndex: this.dialogueIndex,
      frameIndex: this.frameIndex,
      currentStoryboard,
    }
  }

  advance(nowMs: number): boolean {
    if (!this.isReady()) {
      return false
    }

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

    if (changed) {
      this.version += 1
    }
    return changed
  }

  private resetDeadlines(nowMs: number): void {
    const storyboard = this.storyboards[this.storyboardIndex]
    this.dialogueIndex = 0
    this.frameIndex = 0
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
}
