import Phaser from 'phaser'
import './style.css'
import { RecoveryBootScene } from './scenes/RecoveryBootScene'
import type {
  RecoveryBattleModel,
  RecoveryCatalog,
  RecoveryDialogueEvent,
  RecoveryPreviewManifest,
  RecoveryPreviewStem,
  RecoveryRuntimeBlueprint,
  RecoveryStageSnapshot,
} from './recovery-types'
import { RecoveryStageSystem } from './systems/recoveryStageSystem'

const app = document.querySelector<HTMLDivElement>('#app')

if (!app) {
  throw new Error('Missing #app mount point')
}

app.innerHTML = `
  <div class="shell">
    <section class="hero-panel">
      <p class="eyebrow">Arel Wars 1 Reconstruction</p>
      <h1>APK 해체에서 재구현까지</h1>
      <p class="lede">
        32비트 안드로이드 네이티브 유물을 해체해, 현대 Android와 iOS까지 가져갈 수 있는 새 런타임으로 옮기는 작업공간입니다.
      </p>
      <div class="status-row">
        <div class="status-card">
          <span class="label">복구 타깃</span>
          <strong>Phaser + Vite</strong>
        </div>
        <div class="status-card">
          <span class="label">모바일 패키징</span>
          <strong>Capacitor Android APK</strong>
        </div>
        <div class="status-card">
          <span class="label">현재 단계</span>
          <strong id="current-stage">Recovery Catalog Loading</strong>
        </div>
      </div>
    </section>

    <section class="workspace">
      <div class="canvas-panel">
        <div class="panel-header">
          <h2>Recovery Stage</h2>
          <p>Recovered sprite timelines and structured dialogue now share one playback state.</p>
        </div>
        <div id="game-root" class="game-root"></div>
      </div>

      <aside class="intel-panel">
        <div class="panel-header">
          <h2>Recovered Intel</h2>
          <p id="catalog-summary">Catalog not loaded yet.</p>
        </div>
        <div id="inventory" class="stat-grid"></div>
        <div class="divider"></div>
        <div class="panel-header">
          <h2>Featured Scripts</h2>
          <p>High-signal dialogue samples extracted from decoded \`.zt1\` payloads.</p>
        </div>
        <div id="scripts" class="script-list"></div>
      </aside>
    </section>

    <section class="scenario-panel">
      <div class="panel-header">
        <h2>Recovered Storyboard</h2>
        <p id="story-summary">Recovered stage state is not available yet.</p>
      </div>
      <div id="storyboard-panel" class="storyboard-panel"></div>
    </section>

    <section class="analysis-panel">
      <div class="panel-header">
        <h2>Timeline Candidates</h2>
        <p id="timeline-summary">Runtime preview manifest not loaded yet.</p>
      </div>
      <div id="timeline-stats" class="timeline-stats"></div>
      <div id="timeline-gallery" class="timeline-gallery"></div>
    </section>
  </div>
`

let game: Phaser.Game | null = null

void bootstrap()

async function bootstrap(): Promise<void> {
  const stage = document.querySelector<HTMLElement>('#current-stage')
  const summary = document.querySelector<HTMLElement>('#catalog-summary')
  const inventory = document.querySelector<HTMLElement>('#inventory')
  const scripts = document.querySelector<HTMLElement>('#scripts')
  const timelineSummary = document.querySelector<HTMLElement>('#timeline-summary')
  const timelineStats = document.querySelector<HTMLElement>('#timeline-stats')
  const timelineGallery = document.querySelector<HTMLElement>('#timeline-gallery')
  const storySummary = document.querySelector<HTMLElement>('#story-summary')
  const storyboardPanel = document.querySelector<HTMLElement>('#storyboard-panel')

  if (!stage || !summary || !inventory || !scripts || !timelineSummary || !timelineStats || !timelineGallery || !storySummary || !storyboardPanel) {
    return
  }

  const [catalogResult, previewResult, blueprintResult, battleModelResult] = await Promise.allSettled([
    fetchJson<RecoveryCatalog>('/recovery/catalog.json'),
    fetchJson<RecoveryPreviewManifest>('/recovery/analysis/preview_manifest.json'),
    fetchJson<RecoveryRuntimeBlueprint>('/recovery/analysis/aw1_runtime_blueprint.json'),
    fetchJson<RecoveryBattleModel>('/recovery/analysis/aw1_battle_model.json'),
  ])

  const previewManifest = previewResult.status === 'fulfilled' ? previewResult.value : null
  const runtimeBlueprint = blueprintResult.status === 'fulfilled' ? blueprintResult.value : null
  const battleModel = battleModelResult.status === 'fulfilled' ? battleModelResult.value : null
  let stageSystem: RecoveryStageSystem | null = null

  if (catalogResult.status === 'fulfilled') {
    const catalog = await hydrateCatalogScripts(catalogResult.value)
    if (previewManifest) {
      stageSystem = new RecoveryStageSystem(catalog, previewManifest, runtimeBlueprint, battleModel)
    }
    game = createGame(stageSystem)
    stage.textContent = previewManifest
      ? `Recovered stage online (${previewManifest.activeStemCount} stems / ${runtimeBlueprint?.summary.stageBlueprintCount ?? 0} stage blueprints / ${runtimeBlueprint?.summary.stageMapProofCount ?? 0} map proofs / ${battleModel?.summary.unitTemplateCount ?? 0} unit templates)`
      : 'ZT1 decoded, Android APK verified'
    summary.textContent = `${catalog.inventory.zt1Total} decoded ZT1 files, ${catalog.inventory.webSafeAssetCount} web-safe assets, blockers on ${catalog.blockedFormats.map((item) => item.suffix).join(', ')}.${previewManifest ? ` Active timeline stems: ${previewManifest.activeStemCount}.` : ''}${runtimeBlueprint ? ` Runtime blueprint: ${runtimeBlueprint.summary.stageBlueprintCount} stages, ${runtimeBlueprint.summary.stageMapProofCount} scored map proofs, ${runtimeBlueprint.summary.archetypeCount} archetypes, ${runtimeBlueprint.summary.opcodeHeuristicCount} opcode heuristics, ${runtimeBlueprint.summary.tutorialChainCount} mirrored tutorial chains.` : ''}${battleModel ? ` Battle model: ${battleModel.summary.unitTemplateCount} unit templates, ${battleModel.summary.projectileTemplateCount} projectiles, ${battleModel.summary.effectTemplateCount} effects, ${battleModel.summary.heroTemplateCount} hero AI profiles.` : ''} Android packaging has been verified on a modern emulator.`

    inventory.innerHTML = [
      statCard('Scripts', `${catalog.featuredScripts.length} featured`),
      statCard('ZT1 Total', String(catalog.inventory.zt1Total)),
      statCard('Script Events', String(catalog.inventory.scriptEventTotal ?? 0)),
      statCard('Web-safe', String(catalog.inventory.webSafeAssetCount)),
      statCard('Timeline Stems', String(previewManifest?.activeStemCount ?? 0)),
      statCard('Archetypes', String(runtimeBlueprint?.summary.archetypeCount ?? 0)),
      statCard('Units', String(battleModel?.summary.unitTemplateCount ?? 0)),
      statCard('Effects', String(battleModel?.summary.effectTemplateCount ?? 0)),
      statCard('Stage Plans', String(runtimeBlueprint?.summary.stageBlueprintCount ?? 0)),
      statCard('Opcode Hints', String(runtimeBlueprint?.summary.opcodeHeuristicCount ?? 0)),
      statCard('Tutorial Chains', String(runtimeBlueprint?.summary.tutorialChainCount ?? 0)),
    ].join('')

    scripts.innerHTML = catalog.featuredScripts
      .slice(0, 8)
      .map(
        (entry) => `
          <article class="script-card">
            <header>
              <span class="pill">${entry.locale ?? 'n/a'}</span>
              <code>${entry.path}</code>
            </header>
            <p>${escapeHtml(describeScriptPreview(entry))}</p>
          </article>
        `,
      )
      .join('')
  } else {
    game = createGame(null)
    const message = catalogResult.reason instanceof Error ? catalogResult.reason.message : 'Unknown error'
    stage.textContent = 'Catalog load failed'
    summary.textContent = message
    inventory.innerHTML = statCard('Status', 'Failed')
    scripts.innerHTML = `<article class="script-card error-card"><p>${escapeHtml(message)}</p></article>`
  }

  renderStoryboard(stageSystem, storySummary, storyboardPanel)
  renderTimelinePreview(previewManifest, timelineSummary, timelineStats, timelineGallery)
}

function createGame(stageSystem: RecoveryStageSystem | null): Phaser.Game {
  return new Phaser.Game({
    type: Phaser.AUTO,
    parent: 'game-root',
    width: 960,
    height: 540,
    backgroundColor: '#0e1418',
    scene: [new RecoveryBootScene(stageSystem)],
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH,
    },
  })
}

function renderStoryboard(system: RecoveryStageSystem | null, summary: HTMLElement, panel: HTMLElement): void {
  if (!system?.isReady()) {
    summary.textContent = 'Need both the catalog and the preview manifest before storyboard playback can start.'
    panel.innerHTML = `<article class="story-card error-card"><p>Storyboard state unavailable.</p></article>`
    return
  }

  const render = (): void => {
    const snapshot = system.getSnapshot()
    if (!snapshot) {
      return
    }
    summary.textContent = `${system.getStoryboards().length} paired storyboards, ${snapshot.currentStoryboard.previewStem.eventFrames.length} sprite frames on the active stem, ${snapshot.currentStoryboard.scriptEventCount} recovered script beats in the source scene.`
    panel.innerHTML = storyboardMarkup(snapshot)
  }

  let lastVersion = -1
  const loop = (timestamp: number): void => {
    if (system.advance(timestamp) || system.getVersion() !== lastVersion) {
      lastVersion = system.getVersion()
      render()
    }
    window.requestAnimationFrame(loop)
  }

  render()
  window.requestAnimationFrame(loop)
}

function renderTimelinePreview(
  previewManifest: RecoveryPreviewManifest | null,
  summary: HTMLElement,
  stats: HTMLElement,
  gallery: HTMLElement,
): void {
  if (!previewManifest) {
    summary.textContent = 'Timeline preview manifest is not available yet.'
    stats.innerHTML = statCard('Timeline', 'Unavailable')
    gallery.innerHTML = `<article class="timeline-card error-card"><p>Run \`npm run sync:recovery\` after regenerating timeline strips.</p></article>`
    return
  }

  summary.textContent = `${previewManifest.activeStemCount} active stems, ${Object.keys(previewManifest.timelineKindCounts).length} timeline classes, featured runtime strips ready.`
  stats.innerHTML = [
    timelineStatCard('Active Stems', String(previewManifest.activeStemCount)),
    timelineStatCard('Timeline Kinds', String(Object.keys(previewManifest.timelineKindCounts).length)),
    timelineStatCard('Featured', String(previewManifest.featuredEntries.length)),
    timelineStatCard('Overlay Only', String(previewManifest.timelineKindCounts['overlay-track-only'] ?? 0)),
  ].join('')

  gallery.innerHTML = previewManifest.featuredEntries.map((entry) => timelineCard(entry)).join('')
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`${path} request failed with ${response.status}`)
  }
  return (await response.json()) as T
}

async function hydrateCatalogScripts(catalog: RecoveryCatalog): Promise<RecoveryCatalog> {
  const featuredScripts = await Promise.all(
    catalog.featuredScripts.map(async (entry) => {
      if (!entry.webEventsPath) {
        return entry
      }
      try {
        const events = await fetchJson<RecoveryDialogueEvent[]>(entry.webEventsPath)
        return {
          ...entry,
          eventPreview: events,
          eventCount: events.length,
        }
      } catch {
        return entry
      }
    }),
  )

  return {
    ...catalog,
    featuredScripts,
  }
}

function statCard(label: string, value: string): string {
  return `
    <article class="stat-card">
      <span>${label}</span>
      <strong>${value}</strong>
    </article>
  `
}

function timelineStatCard(label: string, value: string): string {
  return `
    <article class="timeline-stat-card">
      <span>${label}</span>
      <strong>${value}</strong>
    </article>
  `
}

function timelineCard(entry: RecoveryPreviewStem): string {
  return `
    <article class="timeline-card">
      <header class="timeline-card-header">
        <div>
          <strong>Stem ${entry.stem}</strong>
          <p>${escapeHtml(formatKind(entry.timelineKind))}</p>
        </div>
        <span class="pill">${escapeHtml(formatKind(entry.sequenceKind))}</span>
      </header>
      <p class="timeline-card-copy">
        Anchors ${escapeHtml(describeAnchors(entry))}. Linked ${entry.linkedGroupCount}, overlays ${entry.overlayGroupCount}, cadence ${escapeHtml(describeTiming(entry))}, ${escapeHtml(describeLoop(entry))}.
      </p>
      <div class="timeline-strip-frame">
        <img src="${entry.timelineStrip.pngPath}" alt="Timeline strip for stem ${entry.stem}" loading="lazy" />
      </div>
    </article>
  `
}

function describeScriptPreview(entry: RecoveryCatalog['featuredScripts'][number]): string {
  if (entry.eventPreview && entry.eventPreview.length > 0) {
    return entry.eventPreview
      .slice(0, 2)
      .map((event) => (event.speaker ? `${event.speaker}: ${event.text}` : event.text))
      .join(' / ')
  }
  return entry.stringsPreview.slice(0, 2).join(' / ') || 'Recoverable text not found'
}

function storyboardMarkup(snapshot: RecoveryStageSnapshot): string {
  const activeEvent = snapshot.currentStoryboard.scriptEvents[snapshot.dialogueIndex]
  const previewStem = snapshot.currentStoryboard.previewStem
  const speakerLine = activeEvent.speaker ? `${activeEvent.speaker} · tag ${activeEvent.speakerTag ?? 'n/a'}` : 'Narration'
  const stage = snapshot.currentStoryboard.stageBlueprint
  const opcodePills = stage?.opcodeCues.slice(0, 4).map((cue) => cue.label) ?? []
  const tutorialPills = stage?.tutorialChainCues.slice(0, 4).map((cue) => cue.label) ?? []
  const archetypePills = stage?.recommendedArchetypeIds.slice(0, 4) ?? []
  const channelPills = snapshot.channelStates
    .slice(0, 4)
    .map((channel) => `${channel.label} ${channel.phaseLabel}${channel.loadoutMode ? ` [${channel.loadoutMode}${channel.focusLane ? ` ${channel.focusLane}` : ''}]` : ''}`)
  const mapLine = stage?.mapBinding
    ? `Map ${stage.mapBinding.mapPairIndices.join('/')} → ${stage.mapBinding.preferredMapIndexHeuristic ?? 'n/a'} (${stage.mapBinding.proofType} ${stage.mapBinding.proofScore.toFixed(2)})`
    : 'Map unresolved'
  const activeTutorial = snapshot.activeTutorialCue
    ? `${snapshot.activeTutorialCue.label} / ${snapshot.activeTutorialCue.action}`
    : null
  const activeOpcode = snapshot.activeOpcodeCue
    ? `${snapshot.activeOpcodeCue.label} / ${snapshot.activeOpcodeCue.action}`
    : stage?.opcodeCues[0]
      ? `${stage.opcodeCues[0].label} / ${stage.opcodeCues[0].action}`
      : null
  const gameplayState = snapshot.gameplayState
  const campaign = snapshot.campaignState
  const briefing = campaign.briefing
  const selectedLoadout = campaign.loadouts[Math.max(campaign.selectedLoadoutIndex - 1, 0)] ?? null
  const profile = snapshot.battlePreviewState.stageProfile
  const objective = snapshot.battlePreviewState.objective
  const resolution = snapshot.battlePreviewState.resolution
  const activeChain = snapshot.battlePreviewState.activeChain
  const entityCount = snapshot.battlePreviewState.entities.length
  const projectileCount = snapshot.battlePreviewState.projectiles.length
  const effectCount = snapshot.battlePreviewState.effects.length
  const battleLine = snapshot.battlePreviewState.lanes
    .map((lane) => `${lane.laneId} ${lane.alliedUnits}-${lane.enemyUnits} ${lane.momentum} @ ${lane.frontline.toFixed(2)}`)
    .join(' · ')
  const gameplayLine = `mode ${gameplayState.mode}${gameplayState.battlePaused ? ' paused' : ''} · phase ${campaign.scenePhase}${campaign.autoAdvanceInMs !== null ? ` auto ${Math.ceil(campaign.autoAdvanceInMs / 100) / 10}s` : ''} · campaign node ${campaign.currentNodeIndex}/${campaign.totalNodeCount} selected ${campaign.selectedNodeIndex} loadout ${campaign.selectedLoadoutIndex}/${campaign.loadouts.length} ${campaign.selectedLoadoutLabel}${campaign.activeLoadoutLabel ? ` active ${campaign.activeLoadoutLabel}` : ''} · pref ${campaign.preferredRouteLabel ?? 'route-unknown'} x${campaign.routeCommitment} · recommend ${campaign.recommendedNodeIndex}/${campaign.recommendedRouteLabel ?? 'route-unknown'}${campaign.recommendedLoadoutLabel ? ` / ${campaign.recommendedLoadoutLabel}` : ''}${campaign.recommendedReason ? ` / ${campaign.recommendedReason}` : ''}${campaign.routeGoalNodeIndex !== null ? ` · goal ${campaign.routeGoalNodeIndex}/${campaign.routeGoalRouteLabel ?? 'route-unknown'}${campaign.routeGoalLabel ? ` / ${campaign.routeGoalLabel}` : ''}${campaign.routeGoalReason ? ` / ${campaign.routeGoalReason}` : ''}` : ''} · ${selectedLoadout?.heroRosterLabel ?? 'core squad'} / ${selectedLoadout?.skillPresetLabel ?? 'balanced kit'} / ${selectedLoadout?.towerPolicyLabel ?? 'balanced towers'} unlocked ${campaign.unlockedNodeCount} cleared ${campaign.clearedStageCount} · ${campaign.selectionMode}${campaign.selectionLaunchable ? ' launch-ready' : ''}${campaign.nextUnlockLabel ? ` next ${campaign.nextUnlockLabel}${campaign.nextUnlockRouteLabel ? ` / ${campaign.nextUnlockRouteLabel}` : ''}` : ''}${campaign.lastOutcome ? ` · last ${campaign.lastOutcome} ${campaign.lastResolvedStageTitle ?? ''}` : ''} · target ${campaign.selectedStageTitle} / ${campaign.selectedRouteLabel}${campaign.selectedHintText ? ` / ${campaign.selectedHintText}` : ''}${campaign.selectedRewardText ? ` / reward ${campaign.selectedRewardText}` : ''} · briefing ${briefing.objectivePhase} ${briefing.objectiveLabel} / lane ${briefing.favoredLane ?? 'mixed'} / ally ${briefing.alliedForecast[0] ?? 'idle'} / enemy ${briefing.enemyForecast[0] ?? 'idle'} · profile ${profile.label} · bias ${profile.tacticalBias} · signals ${profile.archetypeSignals.join('/') || 'baseline'} · tempo a${profile.alliedWaveCadenceBeats}/e${profile.enemyWaveCadenceBeats} · heroImpact ${profile.heroImpact.toFixed(2)} · objective ${objective.phase} ${objective.waveIndex}/${objective.totalWaves} ${objective.label} · next a${objective.alliedWaveCountdownBeats}/e${objective.enemyWaveCountdownBeats} · waves ${objective.alliedDirective?.label ?? 'ally idle'} / ${objective.enemyDirective?.label ?? 'enemy idle'} · result ${resolution.status}${resolution.status !== 'active' ? ` ${resolution.label}${resolution.autoAdvanceInMs !== null ? ` in ${Math.ceil(resolution.autoAdvanceInMs / 100) / 10}s` : ''}` : ''} · panel ${gameplayState.openPanel ?? 'none'} · hero ${gameplayState.heroMode} · lane ${gameplayState.selectedDispatchLane ?? 'none'} · queue ${gameplayState.queuedUnitCount} · upgrades ${gameplayState.towerUpgradeLevels.mana}/${gameplayState.towerUpgradeLevels.population}/${gameplayState.towerUpgradeLevels.attack} · skill ${gameplayState.skillReady ? 'ready' : 'cooldown'} · item ${gameplayState.itemReady ? 'ready' : 'cooldown'} · battle ${battleLine} · entities ${entityCount} / projectiles ${projectileCount} / effects ${effectCount}${activeChain.active ? ` · chain ${activeChain.members.join('+')} @ ${activeChain.focusLane ?? 'mixed'} x${activeChain.intensity.toFixed(2)}` : ''} · objectiveMode ${gameplayState.objectiveMode} · ${gameplayState.primaryHint}${gameplayState.scriptedBeatNote ? ` · script ${gameplayState.scriptedBeatNote}` : ''}${gameplayState.lastActionId ? ` · ${gameplayState.lastActionId} ${gameplayState.lastActionAccepted ? 'ok' : 'blocked'}` : ''}`
  const campaignStrip = campaign.nodes
    .map((node) => {
      const classes = [
        'campaign-node',
        node.unlocked ? 'campaign-node-unlocked' : 'campaign-node-locked',
        node.preferredRoute ? 'campaign-node-preferred-route' : '',
        node.cleared ? 'campaign-node-cleared' : '',
        node.active ? 'campaign-node-active' : '',
        node.selected ? 'campaign-node-selected' : '',
        node.recommended ? 'campaign-node-recommended' : '',
      ]
        .filter(Boolean)
        .join(' ')
      return `<span class="${classes}" title="${escapeHtml(`${node.nodeIndex}. ${node.label} / ${node.routeLabel}`)}"><strong>${node.nodeIndex}</strong><em>${escapeHtml(node.label)}</em></span>`
    })
    .join('')
  const loadoutStrip = campaign.loadouts
    .map((loadout) => {
      const classes = [
        'loadout-pill',
        loadout.loadoutIndex === campaign.selectedLoadoutIndex ? 'loadout-pill-selected' : '',
        campaign.activeLoadoutLabel === loadout.label ? 'loadout-pill-active' : '',
        loadout.recommended ? 'loadout-pill-recommended' : '',
      ]
        .filter(Boolean)
        .join(' ')
      return `<span class="${classes}" title="${escapeHtml(loadout.summary)}"><strong>${loadout.loadoutIndex}</strong><em>${escapeHtml(loadout.label)}</em></span>`
    })
    .join('')
  return `
    <article class="story-card">
      <header class="story-card-header">
        <div>
          <strong>${escapeHtml(stage?.title ?? snapshot.currentStoryboard.scriptPath)}</strong>
          <p>${escapeHtml(mapLine)} / ${escapeHtml(formatKind(previewStem.timelineKind))} / stem ${previewStem.stem}</p>
        </div>
        <span class="pill">${escapeHtml(snapshot.currentStoryboard.locale ?? 'n/a')}</span>
      </header>
      <div class="story-meta">
        <span>Storyboard ${snapshot.storyboardIndex + 1}</span>
        <span>Dialogue ${snapshot.dialogueIndex + 1}/${snapshot.currentStoryboard.scriptEvents.length}</span>
        <span>Frame ${snapshot.frameIndex + 1}/${Math.max(previewStem.eventFrames.length, 1)}</span>
        <span>Elapsed ${Math.round(snapshot.elapsedStoryboardMs / 100) / 10}s</span>
      </div>
      <div class="campaign-strip">${campaignStrip}</div>
      <div class="loadout-strip">${loadoutStrip}</div>
      <p class="story-runtime-copy">Target ${escapeHtml(campaign.selectedStageTitle)} / ${escapeHtml(campaign.selectedRouteLabel)}${campaign.selectedHintText ? ` / ${escapeHtml(campaign.selectedHintText)}` : ''}${campaign.selectedRewardText ? ` / reward ${escapeHtml(campaign.selectedRewardText)}` : ''}${campaign.autoAdvanceInMs !== null ? ` / auto ${Math.ceil(campaign.autoAdvanceInMs / 100) / 10}s` : ''}</p>
      <p class="story-runtime-copy">Route ${escapeHtml(`${campaign.preferredRouteLabel ?? 'route-unknown'} / commitment ${campaign.routeCommitment}`)}${campaign.routeGoalNodeIndex !== null ? ` / goal ${escapeHtml(`${campaign.routeGoalNodeIndex} / ${campaign.routeGoalRouteLabel ?? 'route-unknown'} / ${campaign.routeGoalLabel ?? 'pending'}${campaign.routeGoalReason ? ` / ${campaign.routeGoalReason}` : ''}`)}` : ''}</p>
      <p class="story-runtime-copy">Recommended ${escapeHtml(`${campaign.recommendedNodeIndex} / ${campaign.recommendedRouteLabel ?? 'route-unknown'} / ${campaign.recommendedLoadoutLabel ?? 'Balanced Vanguard'}${campaign.recommendedReason ? ` / ${campaign.recommendedReason}` : ''}`)}</p>
      <div class="story-briefing">
        <p><strong>Objective:</strong> ${escapeHtml(`${briefing.objectivePhase} · ${briefing.objectiveLabel}`)}</p>
        <p><strong>Lane:</strong> ${escapeHtml(briefing.favoredLane ?? 'mixed')} / <strong>Bias:</strong> ${escapeHtml(briefing.tacticalBias)}</p>
        <p><strong>Loadout:</strong> ${escapeHtml(selectedLoadout?.label ?? 'Balanced Vanguard')} / ${escapeHtml(selectedLoadout?.heroRosterLabel ?? 'Core Squad')} / ${escapeHtml(selectedLoadout?.skillPresetLabel ?? 'Balanced Kit')} / ${escapeHtml(selectedLoadout?.towerPolicyLabel ?? 'Balanced Towers')}</p>
        <p><strong>Roster:</strong> ${escapeHtml(selectedLoadout?.heroRosterMembers.join(' / ') ?? 'Vincent / Helba / Juno')}</p>
        <p><strong>Recommended:</strong> ${escapeHtml(briefing.recommendedArchetypes.join(' / ') || 'baseline loadout')}</p>
        <p><strong>Allied Waves:</strong> ${escapeHtml(briefing.alliedForecast.join(' · ') || 'idle')}</p>
        <p><strong>Enemy Waves:</strong> ${escapeHtml(briefing.enemyForecast.join(' · ') || 'idle')}</p>
        ${activeChain.active ? `<p><strong>Chain:</strong> ${escapeHtml(`${activeChain.members.join(' / ')} / ${activeChain.focusLane ?? 'mixed'} / x${activeChain.intensity.toFixed(2)}`)}</p>` : ''}
      </div>
      <div class="story-dialogue">
        <p class="story-speaker">${escapeHtml(speakerLine)}</p>
        <p class="story-text">${escapeHtml(activeEvent.text)}</p>
      </div>
      <div class="story-tags">
        ${activeTutorial ? `<span class="story-pill story-pill-accent">${escapeHtml(activeTutorial)}</span>` : ''}
        ${opcodePills.map((item) => `<span class="story-pill">${escapeHtml(item)}</span>`).join('')}
        ${tutorialPills.map((item) => `<span class="story-pill">${escapeHtml(item)}</span>`).join('')}
        ${archetypePills.map((item) => `<span class="story-pill story-pill-accent">${escapeHtml(item)}</span>`).join('')}
      </div>
      <p class="story-runtime-copy">${escapeHtml(channelPills.join(' · ') || 'No channel state yet')} · ${escapeHtml(snapshot.renderState.bankRuleLabel)}${activeOpcode ? ` · ${escapeHtml(activeOpcode)}` : ''} · ${escapeHtml(gameplayLine)}</p>
      <p class="story-runtime-copy">ArrowLeft/ArrowRight selects an unlocked campaign node. ArrowUp/ArrowDown cycles deploy loadouts. Enter launches the selected node while the battle is paused or after a result hold.</p>
      <div class="story-strip">
        <img src="${previewStem.timelineStrip.pngPath}" alt="Timeline strip for stem ${previewStem.stem}" loading="lazy" />
      </div>
    </article>
  `
}

function formatKind(value: string): string {
  return value.replaceAll('-', ' ')
}

function describeAnchors(entry: RecoveryPreviewStem): string {
  if (entry.anchorFrameSequence.length === 0) {
    return 'overlay only'
  }

  const preview = entry.anchorFrameSequence.slice(0, 5).join(' / ')
  return entry.anchorFrameSequence.length > 5 ? `${preview} ...` : preview
}

function describeTiming(entry: RecoveryPreviewStem): string {
  const durations = entry.eventFrames
    .map((frame) => frame.playbackDurationMs)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
  if (durations.length === 0) {
    return 'unresolved'
  }

  const unique = Array.from(new Set(durations)).sort((left, right) => left - right)
  return unique.length === 1 ? `${unique[0]}ms` : `${unique[0]}-${unique[unique.length - 1]}ms`
}

function describeLoop(entry: RecoveryPreviewStem): string {
  if (!entry.loopSummary) {
    return 'loop unresolved'
  }
  return `loop ${entry.loopSummary.startEventIndex}-${entry.loopSummary.endEventIndex}`
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

window.addEventListener('beforeunload', () => {
  game?.destroy(true)
})
