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
  commandId: string
  commandType: string
  target: string
  count: number
  topArgs: RecoveryOpcodeCounterEntry[]
  topSequences: RecoveryOpcodeCounterEntry[]
  notes: string[]
  variantHints?: Array<{
    variant: string
    label: string
    action: string
    commandId: string
    commandType: string
    target: string
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
  preferredMapIndex: number | null
  inlinePairBaseIndex: number | null
  inlinePairBranchIndex: number | null
  bindingType: string
  bindingConfirmed: boolean
  scriptBindingType: string
  mapBindingType: string
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
  commandId: string
  commandType: string
  target: string
  args: number[]
  source: 'variant' | 'mnemonic'
  variant?: string
}

export interface RecoveryStageBlueprint {
  familyId: string
  aiIndex: number | null
  scriptBindingType: string | null
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
    selectorRule?: string
    notes: string[]
  }
  specialPackedPixelStems: Array<{
    stem: string
    sharedMplStem: string
    heuristic: string
    confidence: string
    transparentValue?: number
    valueOffset?: number
    paletteSize?: number
    coreBandSize?: number
    coreBandCount?: number
    highlightRange?: number[]
    highlightBlendMode?: string
  }>
  ptcBridgeSummary: {
    summary: Record<string, unknown>
    familyRepresentativeEmitters?: Record<string, string>
    sharedPrimaryGroups: Array<Record<string, unknown>>
    sampleParticleRows: Array<Record<string, unknown>>
  }
  findings: string[]
}

export interface RecoveryRenderStemAsset {
  stem: string
  sequenceKind: string
  timelineKind: string
  framePaths: string[]
  linkedFramePaths: string[]
  overlayFramePaths: string[]
  bankProbePath: string | null
}

export interface RecoveryRenderEmitterPreset {
  id: string
  semanticKey?: string
  label: string
  family?: string
  relationKind: string
  blendMode?: string
  primaryPtcStem: string | null
  secondaryPtcStem: string | null
  timingFields: number[]
  emissionFields: number[]
  ratioFieldsFloat: number[]
  signedDeltaFields: number[]
  warmupTicks?: number
  releaseTicks?: number
  lifeTicks?: number
  burstCount?: number
  sustainCount?: number
  spreadUnits?: number
  cadenceTicks?: number
  radiusScale?: number
  alphaScale?: number
  sizeScale?: number
  jitterScale?: number
  driftX?: number
  driftY?: number
  accelX?: number
  accelY?: number
}

export interface RecoveryRenderSemantics {
  mplBankSwitching?: Record<string, unknown>
  packedPixel179?: Record<string, unknown>
}

export interface RecoveryRenderPack {
  generatedAt: string | null
  summary: {
    stemCount: number
    bankProbeCount: number
    packedSpecialCount: number
    emitterPresetCount: number
  }
  stemAssets: RecoveryRenderStemAsset[]
  roleAssignments: {
    allied: Record<'screen' | 'push' | 'support' | 'siege' | 'tower-rally' | 'skill-window' | 'hero', string>
    enemy: Record<'screen' | 'push' | 'support' | 'siege' | 'tower-rally' | 'skill-window' | 'hero', string>
    projectile: {
      allied: string
      enemy: string
    }
    effect: {
      support: string
      impact: string
      burst: string
      utility: string
    }
  }
  effectEmitterAssignments: {
    support: string | null
    impact: string | null
    burst: string | null
    utility: string | null
  }
  packedPixelSpecials: Array<{
    stem: string
    heuristic: string
    confidence: string
    transparentValue?: number
    valueOffset?: number
    paletteSize?: number
    coreBandSize?: number
    coreBandCount?: number
    highlightRange?: number[]
    highlightBlendMode?: string
    compositePath: string | null
    probeSheetPath: string | null
  }>
  emitterPresets: RecoveryRenderEmitterPreset[]
  semantics?: RecoveryRenderSemantics
}

export interface RecoveryRuntimeBlueprint {
  summary: {
    stageBlueprintCount: number
    archetypeCount: number
    featuredArchetypeCount: number
    opcodeHeuristicCount: number
    stageMapBindingCount: number
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

export interface RecoveryEngineSchema {
  summary: {
    unitCount: number
    heroCount: number
    heroAiProfileCount: number
    skillAiProfileCount: number
    projectileCount: number
    effectCount: number
    particleCount: number
    balanceRowCount: number
  }
  sourceTables: Record<string, string>
  findings: string[]
}

export interface RecoveryBattleUnitTemplate {
  id: string
  label: string
  side: 'allied' | 'enemy'
  role: 'screen' | 'push' | 'support' | 'siege' | 'tower-rally' | 'skill-window' | 'hero'
  hero: boolean
  baseAttackIndex: number
  projectileTemplateId: string | null
  effectTemplateId: string | null
  maxHp: number
  power: number
  speed: number
  range: number
  attackPeriodBeats: number
  populationCost: number
  manaCost: number
  projectileSpeed: number
  projectileStrengthScale: number
  projectileTtlBeats: number
}

export interface RecoveryBattleProjectileTemplate {
  id: string
  label: string
  projectileIndex: number
  familyCandidate: number
  variantCandidate: number
  speed: number
  ttlBeats: number
  strengthScale: number
  motionCandidate: number
}

export interface RecoveryBattleEffectTemplate {
  id: string
  label: string
  effectIndex: number
  familyCandidate: number
  variantCandidate: number
  durationBeats: number
  intensity: number
  loop: boolean
  blendFlagCandidate: number
  blendMode: string
  renderFamily: 'support' | 'impact' | 'burst' | 'utility'
  emitterSemanticId: string | null
}

export interface RecoveryBattleSkillTemplate {
  id: string
  name: string
  skillIndex: number
  skillCodeCandidate: number
  aiCodeCandidate: number
  kind: 'balanced' | 'burst' | 'support' | 'orders' | 'utility'
  slotCandidate: number
  modeKey: string
  manaCost: number
  cooldownBeats: number
  powerScale: number
  projectileTemplateId: string | null
  effectTemplateId: string | null
}

export interface RecoveryBattleItemTemplate {
  id: string
  name: string
  itemIndex: number
  itemCodeCandidate: number
  categoryCandidate: number
  kind: 'burst' | 'heal' | 'mana' | 'orders' | 'support' | 'utility'
  cost: number
  cooldownBeats: number
  powerScale: number
  projectileTemplateId: string | null
  effectTemplateId: string | null
}

export interface RecoveryBattleHeroTemplate {
  id: string
  heroId: number
  name: string
  memberRole: string
  unitTemplateId: string
  preferredSkillNames: string[]
  preferredItemNames: string[]
  ai: {
    aggression: number
    support: number
    burst: number
    mana: number
    spawnCadenceBeats: number
    skillCadenceBeats: number
    itemCadenceBeats: number
    heroCadenceBeats: number
  }
}

export interface RecoveryBattleModel {
  summary: {
    unitTemplateCount: number
    projectileTemplateCount: number
    effectTemplateCount: number
    skillTemplateCount: number
    itemTemplateCount: number
    heroTemplateCount: number
  }
  resourceRules: {
    manaCapacity: number
    enemyManaCapacity: number
    manaRegenPerBeat: number
    enemyManaRegenPerBeat: number
    populationBase: number
    enemyPopulationBase: number
    populationPerUpgrade: number
    queueCapacity: number
    skillCooldownBaseBeats: number
    itemCooldownBaseBeats: number
  }
  unitTemplates: RecoveryBattleUnitTemplate[]
  projectileTemplates: RecoveryBattleProjectileTemplate[]
  effectTemplates: RecoveryBattleEffectTemplate[]
  skillTemplates: RecoveryBattleSkillTemplate[]
  itemTemplates: RecoveryBattleItemTemplate[]
  heroTemplates: RecoveryBattleHeroTemplate[]
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
  baseItemCount?: number | null
  baseFlaggedCount?: number | null
  tailItemCount?: number | null
  tailFlaggedCount?: number | null
  anchorBankState?: string | null
  tailBankState?: string | null
  bankTransition?: string | null
  bankStateId?: string | null
  bankBlendMode?: string | null
  bankOverlayWeight?: number | null
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

export interface RecoverySceneScriptDirective {
  kind:
    | 'set-objective'
    | 'set-panel'
    | 'trigger-wave'
    | 'set-selected-lane'
    | 'ensure-queue'
    | 'commit-dispatch'
    | 'invoke-action'
    | 'restore-mana'
    | 'spawn-unit'
    | 'shift-lane'
    | 'note'
  phase?: RecoveryBattleObjectiveState['phase']
  label?: string
  progressDelta?: number
  panel?: RecoveryGameplayState['openPanel']
  side?: 'allied' | 'enemy'
  advanceWave?: boolean
  laneId?: 'upper' | 'lower'
  queueCount?: number
  actionId?: RecoveryGameplayActionId
  manaScale?: number
  role?: RecoveryBattleWaveDirective['role']
  powerScale?: number
  shiftDelta?: number
  note?: string
}

export interface RecoverySceneScriptStep {
  dialogueIndex: number
  stepId: string
  label: string
  sources: string[]
  tags: string[]
  directives: RecoverySceneScriptDirective[]
}

export interface RecoveryStageStoryboard {
  id: string
  scriptPath: string
  scriptFamilyId: string
  locale: string | null
  scriptEventCount: number
  scriptEvents: RecoveryDialogueEvent[]
  sceneScriptSteps: RecoverySceneScriptStep[]
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
  loadoutMode: string | null
  focusLane: 'upper' | 'lower' | null
  focusSource: 'roster' | 'skill' | 'policy' | null
}

export interface RecoveryStageRenderState {
  bankRuleLabel: string
  bankOverlayActive: boolean
  bankStateId: string
  bankTransition: string | null
  bankBlendMode: string
  bankOverlayWeight: number
  baseFlaggedCount: number
  tailFlaggedCount: number
  packedPixelStemRule: string | null
  packedPixelBlendMode: string | null
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
    | 'worldmap-selection'
    | 'deploy-briefing'
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
  scriptedBeatNote: string | null
  lastActionId: RecoveryGameplayActionId | null
  lastActionAccepted: boolean
  lastActionNote: string | null
}

export interface RecoveryLaneBattleState {
  laneId: 'upper' | 'lower'
  alliedUnits: number
  enemyUnits: number
  alliedPressure: number
  enemyPressure: number
  frontline: number
  contested: number
  momentum: 'allied-push' | 'enemy-push' | 'contested' | 'stalled'
  heroPresent: boolean
}

export interface RecoveryStageBattleProfile {
  label: string
  favoredLane: 'upper' | 'lower' | null
  tacticalBias: string
  stageTier: number
  alliedPressureScale: number
  enemyPressureScale: number
  alliedWaveCadenceBeats: number
  enemyWaveCadenceBeats: number
  heroImpact: number
  effectIntensity: string
  archetypeLabels: string[]
  archetypeSignals: string[]
  dispatchBoost: number
  towerDefenseBias: number
  recallSwing: number
  armageddonBurst: number
  manaSurge: number
}

export interface RecoveryBattleObjectiveState {
  phase:
    | 'opening'
    | 'lane-control'
    | 'hero-pressure'
    | 'tower-management'
    | 'skill-burst'
    | 'quest-resolution'
    | 'siege'
  label: string
  waveIndex: number
  totalWaves: number
  progressRatio: number
  enemyWaveCountdownBeats: number
  alliedWaveCountdownBeats: number
  favoredLane: 'upper' | 'lower' | null
  enemyDirective: RecoveryBattleWaveDirective | null
  alliedDirective: RecoveryBattleWaveDirective | null
}

export interface RecoveryBattleWaveDirective {
  waveNumber: number
  laneId: 'upper' | 'lower'
  role: 'screen' | 'push' | 'siege' | 'support' | 'hero-bait' | 'tower-rally' | 'skill-window'
  unitBurst: number
  pressureBias: number
  label: string
}

export interface RecoveryBattleResolutionState {
  status: 'active' | 'victory' | 'defeat'
  label: string
  reason: string
  autoAdvanceInMs: number | null
  questRewardReady: boolean
}

export interface RecoveryBattleChainState {
  active: boolean
  members: string[]
  focusLane: 'upper' | 'lower' | null
  intensity: number
  label: string | null
}

export interface RecoveryBattleEntityState {
  id: number
  side: 'allied' | 'enemy'
  laneId: 'upper' | 'lower'
  role: RecoveryBattleWaveDirective['role'] | 'hero'
  positionRatio: number
  hpRatio: number
  power: number
  hero: boolean
  source: string
  memberLabel: string | null
}

export interface RecoveryBattleProjectileState {
  id: number
  side: 'allied' | 'enemy'
  laneId: 'upper' | 'lower'
  positionRatio: number
  strength: number
  source: string
}

export interface RecoveryBattleEffectState {
  id: number
  side: 'allied' | 'enemy'
  laneId: 'upper' | 'lower'
  positionRatio: number
  kind: string
  renderFamily: 'support' | 'impact' | 'burst' | 'utility'
  blendMode: string
  emitterSemanticId: string | null
  ttlBeats: number
  intensity: number
}

export interface RecoveryCampaignNodeState {
  nodeIndex: number
  label: string
  familyId: string
  routeLabel: string
  preferredRoute: boolean
  unlocked: boolean
  cleared: boolean
  active: boolean
  selected: boolean
  recommended: boolean
}

export interface RecoveryCampaignBriefing {
  objectivePhase: RecoveryBattleObjectiveState['phase']
  objectiveLabel: string
  favoredLane: 'upper' | 'lower' | null
  tacticalBias: string
  totalWaves: number
  stageTier: number
  effectIntensity: string
  recommendedArchetypes: string[]
  alliedForecast: string[]
  enemyForecast: string[]
}

export interface RecoveryCampaignLoadout {
  loadoutIndex: number
  id: string
  label: string
  summary: string
  recommended: boolean
  heroRosterLabel: string
  heroRosterRole: 'balanced' | 'vanguard' | 'defender' | 'support' | 'raider'
  heroRosterMembers: string[]
  skillPresetLabel: string
  skillPresetKind: 'balanced' | 'burst' | 'support' | 'orders' | 'utility'
  towerPolicyLabel: string
  towerPolicyKind: 'balanced' | 'mana-first' | 'population-first' | 'attack-first'
  heroStartMode: 'tower' | 'field'
  heroLane: 'upper' | 'lower' | null
  dispatchLane: 'upper' | 'lower' | null
  openingPanel: 'tower' | 'skill' | 'item' | null
  startingQueue: number
  startingManaRatio: number
  startingManaUpgradeProgressRatio: number
  towerUpgrades: RecoveryTowerUpgradeLevels
}

export interface RecoveryCampaignState {
  currentNodeIndex: number
  selectedNodeIndex: number
  recommendedNodeIndex: number
  selectedLoadoutIndex: number
  unlockedNodeCount: number
  clearedStageCount: number
  totalNodeCount: number
  activeStageTitle: string
  activeFamilyId: string
  routeLabel: string
  scenePhase: 'battle' | 'result-hold' | 'worldmap' | 'deploy-briefing'
  selectionMode: 'follow-active-stage' | 'queued-route-selection' | 'worldmap-selection' | 'result-route-selection'
  selectionLaunchable: boolean
  autoAdvanceInMs: number | null
  nextUnlockLabel: string | null
  nextUnlockRouteLabel: string | null
  lastResolvedStageTitle: string | null
  lastOutcome: 'victory' | 'defeat' | null
  selectedStageTitle: string
  selectedRouteLabel: string
  selectedHintText: string | null
  selectedRewardText: string | null
  selectedLoadoutLabel: string
  activeLoadoutLabel: string | null
  preferredRouteLabel: string | null
  routeCommitment: number
  recommendedRouteLabel: string | null
  recommendedLoadoutLabel: string | null
  recommendedReason: string | null
  routeGoalNodeIndex: number | null
  routeGoalLabel: string | null
  routeGoalRouteLabel: string | null
  routeGoalReason: string | null
  briefing: RecoveryCampaignBriefing
  loadouts: RecoveryCampaignLoadout[]
  nodes: RecoveryCampaignNodeState[]
}

export interface RecoveryBattlePreviewState {
  lanes: RecoveryLaneBattleState[]
  entities: RecoveryBattleEntityState[]
  projectiles: RecoveryBattleProjectileState[]
  effects: RecoveryBattleEffectState[]
  selectedLane: 'upper' | 'lower' | null
  queuedReserve: number
  allyMomentum: number
  enemyMomentum: number
  towerThreat: number
  activeChain: RecoveryBattleChainState
  stageProfile: RecoveryStageBattleProfile
  objective: RecoveryBattleObjectiveState
  resolution: RecoveryBattleResolutionState
}

export interface RecoveryStageSnapshot {
  storyboardIndex: number
  dialogueIndex: number
  frameIndex: number
  elapsedStoryboardMs: number
  currentStoryboard: RecoveryStageStoryboard
  campaignState: RecoveryCampaignState
  activeDialogueEvent: RecoveryDialogueEvent | null
  activeTutorialCue: RecoveryTutorialChainCue | null
  activeSceneCommands: RecoveryResolvedOpcodeCue[]
  activeOpcodeCue: RecoveryResolvedOpcodeCue | null
  channelStates: RecoveryBattleChannelState[]
  renderState: RecoveryStageRenderState
  hudState: RecoveryHudGhostState
  gameplayState: RecoveryGameplayState
  battlePreviewState: RecoveryBattlePreviewState
}
