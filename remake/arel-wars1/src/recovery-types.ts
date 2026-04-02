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
  eventPreview?: RecoveryDialogueEvent[]
  decodedPath: string
  eventsPath?: string
  webEventsPath?: string
}

export interface RecoveryDialogueEvent {
  kind: string
  speaker: string | null
  speakerTag: number | null
  text: string
  offset?: number
  prefixHex?: string | null
  prefixCommands?: RecoveryDialoguePrefixCommand[]
  prefixTrailingHex?: string | null
  byteLength?: number
}

export interface RecoveryDialoguePrefixCommand {
  opcode: number
  args: number[]
  mnemonic: string
}

export interface RecoveryOpcodeCounterEntry {
  value: string | number
  count: number
}

export interface RecoveryOpcodeHeuristic {
  mnemonic: string
  label: string
  action: string
  category: string
  confidence: string
  count: number
  topArgs: RecoveryOpcodeCounterEntry[]
  topSequences: RecoveryOpcodeCounterEntry[]
  notes: string[]
  variantHints?: Array<{
    variant: string
    label: string
    action: string
    confidence: string
    count?: number
  }>
}

export interface RecoveryArchetypeActiveRow {
  index: number
  headerBytes: number[]
  timingWindowA: number[]
  timingWindowB: number[]
  timingWindowACompact: number[]
  timingWindowBCompact: number[]
  tailPairBE: number[]
  tailLink?: {
    index: number
    headerBytes: number[]
    tailPairBE: number[]
    pairReports: Array<{
      pair: number[]
      projectileExactMatches: object[]
      effectExactMatches: object[]
      particleExactMatches: object[]
      projectileIdHints: object[]
    }>
  } | null
}

export interface RecoveryArchetypeBuffRow {
  index: number
  familyCandidate: number
  tierCandidate: number
  triggerModeCandidate: number
  skillCodeCandidate: number
  profileCandidate: number
}

export interface RecoveryArchetypeSlotPayload {
  slot: number
  runtimeType: string
  passiveRowIndex: number | null
  activeRowIndex: number | null
  buffTailRowIndices: number[]
}

export interface RecoveryHeroRuntimeArchetype {
  archetypeId: string
  label: string
  archetypeKind: string
  familyType: string
  confidence: string
  slots: number[]
  rowNames: string[]
  passiveNames: string[]
  heroSkillRows: Array<{
    index: number
    name: string
    skillCodeCandidate: number
    aiCodeCandidate: number
    modeKey: string
    slotOrPowerCandidate: number
    description: string
    tags: string[]
  }>
  slotPayloads: RecoveryArchetypeSlotPayload[]
  passiveRows: Array<Record<string, unknown>>
  activeRows: RecoveryArchetypeActiveRow[]
  buffRows: RecoveryArchetypeBuffRow[]
  skillAiBySkillCode: Array<Record<string, unknown>>
  skillAiByAiCode: Array<Record<string, unknown>>
  mechanicHints: string[]
  evidence: string[]
}

export interface RecoveryStageRuntimeFields {
  blobPrefixHex: string
  stageScalarCandidate: number
  tierCandidate: number
  variantCandidate: number
  regionCandidate: number
  constantMarkerCandidate: number
  storyFlagCandidate: number
}

export interface RecoveryStageMapBinding {
  templateGroupId: number
  mapPairIndices: number[]
  preferredMapIndexHeuristic: number | null
  inlinePairBaseIndexCandidate: number | null
  inlinePairBranchIndexCandidate: number | null
  inlinePreferredMapIndexCandidate: number | null
  confidence: string
  proofScore: number
  proofType: string
  storyBranch: string
  pairGeometrySignature: string
  evidenceSummary: string[]
}

export interface RecoveryStageRenderIntent {
  effectIntensity: string
  bankRule: string
  packedPixelHint: string
}

export interface RecoveryTutorialChainCue {
  chainId: string
  label: string
  action: string
  category: string
  confidence: string
  groupId: string
  prefixNeedle: string
}

export interface RecoveryResolvedOpcodeCue {
  mnemonic: string
  label: string
  action: string
  category: string
  confidence: string
  source: 'variant' | 'mnemonic'
  variant?: string
}

export interface RecoveryStageBlueprint {
  familyId: string
  aiIndexCandidate: number | null
  title: string | null
  rewardText: string | null
  hintText: string | null
  scriptFiles: string[]
  scriptFileCount: number
  eventCount: number
  topSpeakers: Array<[string, number]>
  runtimeFields: RecoveryStageRuntimeFields | null
  mapBinding: RecoveryStageMapBinding | null
  opcodeCues: RecoveryOpcodeHeuristic[]
  tutorialChainCues: RecoveryTutorialChainCue[]
  recommendedArchetypeIds: string[]
  renderIntent: RecoveryStageRenderIntent | null
}

export interface RecoveryRenderProfile {
  defaultMplBankRule: {
    label: string
    notes: string[]
  }
  specialPackedPixelStems: Array<{
    stem: string
    sharedMplStem: string
    heuristic: string
    confidence: string
  }>
  ptcBridgeSummary: {
    summary: Record<string, unknown>
    sharedPrimaryGroups: Array<Record<string, unknown>>
    sampleParticleRows: Array<Record<string, unknown>>
  }
  findings: string[]
}

export interface RecoveryRuntimeBlueprint {
  summary: {
    stageBlueprintCount: number
    archetypeCount: number
    featuredArchetypeCount: number
    opcodeHeuristicCount: number
    stageMapProofCount: number
    tutorialChainCount: number
    tutorialFamilyCueCount: number
  }
  stageBlueprints: RecoveryStageBlueprint[]
  opcodeHeuristics: RecoveryOpcodeHeuristic[]
  tutorialChains: RecoveryTutorialChainCue[]
  featuredArchetypes: RecoveryHeroRuntimeArchetype[]
  renderProfile: RecoveryRenderProfile
  findings: string[]
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

export interface RecoveryStageStoryboard {
  id: string
  scriptPath: string
  scriptFamilyId: string
  locale: string | null
  scriptEventCount: number
  scriptEvents: RecoveryDialogueEvent[]
  previewStem: RecoveryPreviewStem
  stageBlueprint: RecoveryStageBlueprint | null
}

export interface RecoveryBattleChannelState {
  archetypeId: string
  label: string
  archetypeKind: string
  confidence: string
  intensity: number
  phaseLabel: string
  cycleMs: number
  markerCount: number
  hasBuffLayer: boolean
  hasExactTailHit: boolean
}

export interface RecoveryStageRenderState {
  bankRuleLabel: string
  bankOverlayActive: boolean
  packedPixelStemRule: string | null
  effectPulseCount: number
  effectIntensity: string
  ptcEmitterHint: string | null
}

export interface RecoveryTowerUpgradeLevels {
  mana: number
  population: number
  attack: number
}

export interface RecoveryHudGhostState {
  ownTowerHpRatio: number
  enemyTowerHpRatio: number
  manaRatio: number
  manaUpgradeProgressRatio: number
  activePanel: 'tower' | 'skill' | 'item' | 'system' | null
  highlightedMenuId: 'tower' | 'skill' | 'item' | 'system' | null
  highlightedTowerUpgradeId: 'mana' | 'population' | 'attack' | null
  highlightedUnitCardIndex: number | null
  questVisible: boolean
  questRewardReady: boolean
  skillWindowVisible: boolean
  itemWindowVisible: boolean
  skillSlotHighlighted: boolean
  itemSlotHighlighted: boolean
  heroDeployed: boolean
  heroPortraitHighlighted: boolean
  returnCooldownRatio: number
  dispatchArrowsHighlighted: boolean
  leftDispatchCueVisible: boolean
  selectedDispatchLane: 'upper' | 'lower' | null
  queuedUnitCount: number
  towerUpgradeLevels: RecoveryTowerUpgradeLevels
  skillCooldownRatio: number
  itemCooldownRatio: number
  battlePaused: boolean
  questRewardClaims: number
}

export type RecoveryGameplayActionId =
  | 'open-tower-menu'
  | 'open-skill-menu'
  | 'open-item-menu'
  | 'open-system-menu'
  | 'resume-battle'
  | 'open-settings'
  | 'upgrade-tower-stat'
  | 'cast-skill'
  | 'use-item'
  | 'dispatch-up-lane'
  | 'dispatch-down-lane'
  | 'produce-unit'
  | 'deploy-hero'
  | 'return-to-tower'
  | 'toggle-hero-sortie'
  | 'review-quest-rewards'
  | 'claim-quest-reward'
  | 'inspect-own-tower-hp'
  | 'read-loss-condition'
  | 'inspect-enemy-tower-hp'
  | 'read-win-condition'
  | 'inspect-unit-card'
  | 'inspect-mana-bar'
  | 'hero-combat-active'
  | 'observe-stage-preview'

export interface RecoveryGameplayState {
  mode: 'tutorial-lock' | 'guided-preview' | 'free-preview'
  openPanel: 'tower' | 'skill' | 'item' | 'system' | null
  heroMode: 'tower' | 'field' | 'return-cooldown'
  objectiveMode:
    | 'defend-own-tower'
    | 'attack-enemy-tower'
    | 'dispatch-lanes'
    | 'produce-units'
    | 'manage-tower'
    | 'cast-skills'
    | 'use-items'
    | 'review-quests'
    | 'system-navigation'
    | 'generic-preview'
  questState: 'hidden' | 'available' | 'reward-ready'
  selectedDispatchLane: 'upper' | 'lower' | null
  queuedUnitCount: number
  battlePaused: boolean
  towerUpgradeLevels: RecoveryTowerUpgradeLevels
  skillReady: boolean
  itemReady: boolean
  questRewardClaims: number
  enabledInputs: RecoveryGameplayActionId[]
  blockedInputs: RecoveryGameplayActionId[]
  primaryHint: string
  lastActionId: RecoveryGameplayActionId | null
  lastActionAccepted: boolean
  lastActionNote: string | null
}

export interface RecoveryStageSnapshot {
  storyboardIndex: number
  dialogueIndex: number
  frameIndex: number
  elapsedStoryboardMs: number
  currentStoryboard: RecoveryStageStoryboard
  activeDialogueEvent: RecoveryDialogueEvent | null
  activeTutorialCue: RecoveryTutorialChainCue | null
  activeOpcodeCue: RecoveryResolvedOpcodeCue | null
  channelStates: RecoveryBattleChannelState[]
  renderState: RecoveryStageRenderState
  hudState: RecoveryHudGhostState
  gameplayState: RecoveryGameplayState
}
