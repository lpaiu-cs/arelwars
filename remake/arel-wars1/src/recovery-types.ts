export interface RecoveryBlockedFormat {
  suffix: string
  count: number
  reason: string
}

export interface RecoveryScriptEntry {
  path: string
  kind: string
  locale: string | null
  packedSize: number
  decodedSize: number
  encoding: string | null
  scriptEncoding?: string | null
  stringCount: number
  stringsPreview: string[]
  eventCount?: number
  eventPreview?: Array<{
    kind: string
    speaker: string | null
    speakerTag: number | null
    text: string
  }>
  decodedPath: string
}

export interface RecoveryCatalog {
  generatedAt: string
  apkPath: string
  runtimeTarget: string
  inventory: {
    extensions: Record<string, number>
    assetDirectories: Record<string, number>
    zt1Total: number
    scriptEventTotal?: number
    webSafeAssetCount: number
  }
  featuredScripts: RecoveryScriptEntry[]
  blockedFormats: RecoveryBlockedFormat[]
  webSafeAssets: string[]
}

export interface RecoveryTimelineRun {
  groupIndices: number[]
  anchorFrames?: number[]
  anchorFrameIndex?: number
  length: number
}

export interface RecoveryLoopSummary {
  startEventIndex: number
  endEventIndex: number
  reason: string
  confidence: string
}

export interface RecoveryPreviewFrame {
  framePath: string
  groupIndex: number | null
  eventType: string | null
  linkType: string | null
  anchorFrameIndex: number | null
  relation: string | null
  tupleCount: number | null
  durationHintMs: number | null
  playbackDurationMs: number | null
  playbackSource: string | null
  playbackDonorStem?: string | null
  playbackDonorScore?: number | null
  playbackDonorGroupIndex?: number | null
  playbackDonorTimelineKind?: string | null
  timingMarkers: string[] | null
  timingValues: number[] | null
  timingExplicitValues: number[] | null
  anchorRecordMarkers: string[] | null
  anchorRecordTimingValues: number[] | null
}

export interface RecoveryPreviewStem {
  stem: string
  sequenceKind: string
  timelineKind: string
  anchorFrameSequence: number[]
  linkedGroupCount: number
  overlayGroupCount: number
  bestContiguousRun: RecoveryTimelineRun | null
  timelineStrip: {
    pngPath: string
    jsonPath: string
  }
  eventFramePaths: string[]
  eventFrames: RecoveryPreviewFrame[]
  stemDefaultDurationMs: number | null
  loopSummary: RecoveryLoopSummary | null
  sequenceSummaryPath: string
  linkedSequencePngPath: string | null
  overlaySequencePngPath: string | null
}

export interface RecoveryPreviewManifest {
  generatedAt?: string | null
  activeStemCount: number
  sequenceKindCounts: Record<string, number>
  timelineKindCounts: Record<string, number>
  featuredStems: string[]
  featuredEntries: RecoveryPreviewStem[]
  stems: RecoveryPreviewStem[]
}
