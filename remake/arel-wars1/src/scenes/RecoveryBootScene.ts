import Phaser from 'phaser'
import type {
  RecoveryBattleChannelState,
  RecoveryBattleEffectState,
  RecoveryBattleEntityState,
  RecoveryGameplayActionId,
  RecoveryPreviewStem,
  RecoveryRenderEmitterPreset,
  RecoveryRenderPack,
  RecoveryRenderStemAsset,
  RecoveryStageSnapshot,
} from '../recovery-types'
import { RecoveryStageSystem } from '../systems/recoveryStageSystem'

const ICON_KEY = 'recovery-icon'

type FocusRegionKind = 'rect' | 'circle'

interface FocusRegion {
  kind: FocusRegionKind
  x: number
  y: number
  width?: number
  height?: number
  radius?: number
  label: string
}

interface FocusLayoutBounds {
  x: number
  y: number
  width: number
  height: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export class RecoveryBootScene extends Phaser.Scene {
  private readonly stageSystem: RecoveryStageSystem | null

  private readonly renderPack: RecoveryRenderPack | null

  private readonly featuredEntries: RecoveryPreviewStem[]

  private readonly textureKeysByPath = new Map<string, string>()

  private readonly stemAssetsByStem = new Map<string, RecoveryRenderStemAsset>()

  private readonly emitterPresetsById = new Map<string, RecoveryRenderEmitterPreset>()

  private readonly entitySprites = new Map<string, Phaser.GameObjects.Image>()

  private readonly entityOverlaySprites = new Map<string, Phaser.GameObjects.Image>()

  private readonly projectileSprites = new Map<string, Phaser.GameObjects.Image>()

  private readonly effectSprites = new Map<string, Phaser.GameObjects.Image>()

  private readonly particleSprites = new Map<string, Phaser.GameObjects.Image>()

  private previewImage: Phaser.GameObjects.Image | null = null

  private bankProbeImage: Phaser.GameObjects.Image | null = null

  private spriteLabel: Phaser.GameObjects.Text | null = null

  private spriteDetail: Phaser.GameObjects.Text | null = null

  private spriteFooter: Phaser.GameObjects.Text | null = null

  private channelDetail: Phaser.GameObjects.Text | null = null

  private interactionDetail: Phaser.GameObjects.Text | null = null

  private overlayGraphics: Phaser.GameObjects.Graphics | null = null

  private currentSnapshotKey = ''

  private previewBaseX = 0

  private previewBaseY = 0

  private bankProbeBaseX = 0

  private bankProbeBaseY = 0

  constructor(stageSystem: RecoveryStageSystem | null = null, renderPack: RecoveryRenderPack | null = null) {
    super('RecoveryBootScene')
    this.stageSystem = stageSystem
    this.renderPack = renderPack
    this.featuredEntries = stageSystem?.getPreviewEntries().slice(0, 6) ?? []
    renderPack?.stemAssets.forEach((asset) => {
      this.stemAssetsByStem.set(asset.stem, asset)
    })
    renderPack?.emitterPresets.forEach((preset) => {
      this.emitterPresetsById.set(preset.id, preset)
    })
  }

  preload(): void {
    this.load.image(ICON_KEY, '/recovery/raw/res/drawable-hdpi/icon_normal.png')

    this.renderPack?.stemAssets.forEach((asset) => {
      asset.framePaths.forEach((path) => {
        this.load.image(this.ensureTextureKey(path), path)
      })
      if (asset.bankProbePath) {
        this.load.image(this.ensureTextureKey(asset.bankProbePath), asset.bankProbePath)
      }
    })
    this.renderPack?.packedPixelSpecials.forEach((entry) => {
      if (entry.compositePath) {
        this.load.image(this.ensureTextureKey(entry.compositePath), entry.compositePath)
      }
      if (entry.probeSheetPath) {
        this.load.image(this.ensureTextureKey(entry.probeSheetPath), entry.probeSheetPath)
      }
    })

    this.featuredEntries.forEach((entry) => {
      this.load.image(this.previewKey(entry.stem), entry.timelineStrip.pngPath)
      entry.eventFrames.forEach((frame, index) => {
        this.load.image(this.frameKey(entry.stem, index), frame.framePath)
      })
    })
  }

  create(): void {
    const { width, height } = this.scale
    this.createGeneratedTextures()

    this.add.rectangle(width / 2, height / 2, width, height, 0x0c1215)
    this.drawGrid(width, height)

    const banner = this.add.rectangle(width / 2, 108, width - 80, 124, 0x121a1f, 0.94)
    banner.setStrokeStyle(1, 0xc09a5a, 0.35)

    this.add
      .text(80, 70, 'Recovery Stage', {
        fontFamily: 'Georgia, serif',
        fontSize: '20px',
        color: '#d6a55c',
      })
      .setAlpha(0.95)

    this.add
      .text(80, 100, 'Arel Wars 1 reconstruction playback', {
        fontFamily: 'Georgia, serif',
        fontSize: '38px',
        color: '#f3ecdf',
      })
      .setAlpha(0.98)

    this.add
      .text(
        80,
        148,
        this.stageSystem?.isReady()
          ? 'Recovered sprite timelines, stage blueprints, opcode cues, and hero runtime channels now drive one shared battle-state layer.'
          : 'Confirmed recoveries: PZX tail timelines, sequence candidates, runtime strip previews, and Android packaging.',
        {
          fontFamily: 'Trebuchet MS, sans-serif',
          fontSize: '16px',
          color: '#b7c0bf',
        },
      )
      .setAlpha(0.9)

    const frame = this.add.rectangle(width * 0.72, height * 0.56, 372, 304, 0x131d22, 0.9)
    frame.setStrokeStyle(2, 0xc09a5a, 0.3)

    if (this.stageSystem?.isReady()) {
      this.createStagePlayback(frame)
    } else if (this.featuredEntries.length > 0) {
      this.createFallbackStrip(frame)
    } else {
      const icon = this.add.image(frame.x, frame.y - 18, ICON_KEY)
      icon.setScale(3.2)
      this.tweens.add({
        targets: icon,
        y: icon.y - 10,
        duration: 2200,
        yoyo: true,
        repeat: -1,
        ease: 'Sine.InOut',
      })
    }

    const milestones = [
      '1. PZX first-stream, frame-record, and tail groups recovered',
      '2. MPL palette banks and PTC bridges lifted into runtime render cues',
      '3. ZT1 scripts elevated from raw strings to stage blueprints and opcode cues',
      '4. Shared battle-state now drives sprite playback, channel pulses, and narrative HUD',
    ]

    milestones.forEach((line, index) => {
      this.add
        .text(84, 250 + index * 42, line, {
          fontFamily: 'Trebuchet MS, sans-serif',
          fontSize: '18px',
          color: '#d7ddd7',
        })
        .setAlpha(0.92)
    })

    this.add
      .text(84, height - 52, 'Android APK packaging is verified. This runtime now consumes inferred stage bindings, hero archetypes, and render rules, but it is still a reconstruction layer rather than a final 1:1 engine clone.', {
        fontFamily: 'Trebuchet MS, sans-serif',
        fontSize: '15px',
        color: '#7f908e',
        wordWrap: { width: 540 },
      })
      .setAlpha(0.94)

    if (this.stageSystem?.isReady()) {
      this.input.keyboard?.on('keydown', (event: KeyboardEvent) => {
        this.handleActionKey(event.key)
      })
    }
  }

  update(): void {
    if (!this.stageSystem?.isReady()) {
      return
    }

    const snapshot = this.stageSystem.getSnapshot()
    if (!snapshot) {
      return
    }

    const snapshotKey = `${this.stageSystem.getVersion()}:${snapshot.storyboardIndex}:${snapshot.dialogueIndex}:${snapshot.frameIndex}`
    if (snapshotKey === this.currentSnapshotKey) {
      return
    }
    this.currentSnapshotKey = snapshotKey
    this.applySnapshot(snapshot)
  }

  private createStagePlayback(frame: Phaser.GameObjects.Rectangle): void {
    const snapshot = this.stageSystem?.getSnapshot()
    if (!snapshot) {
      return
    }

    this.previewImage = this.add.image(frame.x, frame.y - 18, this.resolvePreviewTexture(snapshot.currentStoryboard.previewStem, snapshot.frameIndex))
    this.fitImageToBox(this.previewImage, 320, 188)
    this.previewImage.setDepth(1)
    this.previewBaseX = this.previewImage.x
    this.previewBaseY = this.previewImage.y

    this.bankProbeImage = this.add.image(frame.x + 116, frame.y - 98, this.resolveFallbackBankProbeTexture())
    this.bankProbeImage.setVisible(false)
    this.bankProbeImage.setDepth(2.8)
    this.fitImageToBox(this.bankProbeImage, 86, 60)
    this.bankProbeBaseX = this.bankProbeImage.x
    this.bankProbeBaseY = this.bankProbeImage.y

    this.spriteLabel = this.add
      .text(frame.x - 156, frame.y + 96, '', {
        fontFamily: 'Georgia, serif',
        fontSize: '18px',
        color: '#f0dfc0',
      })
      .setAlpha(0.98)

    this.spriteDetail = this.add
      .text(frame.x - 156, frame.y + 124, '', {
        fontFamily: 'Trebuchet MS, sans-serif',
        fontSize: '14px',
        color: '#cab892',
        wordWrap: { width: 312 },
      })
      .setAlpha(0.94)

    this.spriteFooter = this.add
      .text(frame.x - 156, frame.y + 168, '', {
        fontFamily: 'Trebuchet MS, sans-serif',
        fontSize: '13px',
        color: '#92a09d',
        wordWrap: { width: 320 },
      })
      .setAlpha(0.9)

    this.channelDetail = this.add
      .text(frame.x - 156, frame.y + 204, '', {
        fontFamily: 'Trebuchet MS, sans-serif',
        fontSize: '12px',
        color: '#d9c9ab',
        wordWrap: { width: 320 },
      })
      .setAlpha(0.88)

    this.interactionDetail = this.add
      .text(frame.x - 156, frame.y + 232, '', {
        fontFamily: 'Trebuchet MS, sans-serif',
        fontSize: '11px',
        color: '#9fb1ae',
        wordWrap: { width: 320 },
      })
      .setAlpha(0.84)

    this.overlayGraphics = this.add.graphics()
    this.overlayGraphics.setDepth(5)

    this.applySnapshot(snapshot)
  }

  private createFallbackStrip(frame: Phaser.GameObjects.Rectangle): void {
    const previewImage = this.add.image(frame.x, frame.y - 14, this.previewKey(this.featuredEntries[0].stem))
    this.fitImageToBox(previewImage, 316, 176)
  }

  private applySnapshot(snapshot: RecoveryStageSnapshot): void {
    if (!this.previewImage || !this.spriteLabel || !this.spriteDetail || !this.spriteFooter || !this.channelDetail || !this.interactionDetail || !this.overlayGraphics) {
      return
    }

    const shake = this.shakeOffset(snapshot)
    this.previewImage.setPosition(this.previewBaseX + shake.x, this.previewBaseY + shake.y)
    if (this.bankProbeImage) {
      this.bankProbeImage.setPosition(this.bankProbeBaseX + shake.x * 0.7, this.bankProbeBaseY + shake.y * 0.7)
    }
    const previewStem = snapshot.currentStoryboard.previewStem
    this.previewImage.setTexture(this.resolvePreviewTexture(previewStem, snapshot.frameIndex))
    this.fitImageToBox(this.previewImage, 320, 188)
    this.previewImage.setTint(snapshot.renderState.bankOverlayActive ? 0xffe3a1 : 0xffffff)
    this.previewImage.setAlpha(snapshot.renderState.packedPixelStemRule ? 0.94 + snapshot.renderState.bankOverlayWeight * 0.04 : 1)
    this.syncBankProbe(snapshot)

    const stageTitle = snapshot.currentStoryboard.stageBlueprint?.title ?? `Stem ${previewStem.stem}`
    const mapBinding = snapshot.currentStoryboard.stageBlueprint?.mapBinding
    const mapLine = mapBinding
      ? `Map pair ${mapBinding.mapPairIndices.join('/')} → ${mapBinding.preferredMapIndex ?? 'n/a'} · ${mapBinding.bindingType}${mapBinding.bindingConfirmed ? ' exact' : ''}`
      : `Stem ${previewStem.stem}`
    const campaign = snapshot.campaignState
    const briefing = campaign.briefing
    const selectedLoadout = campaign.loadouts[Math.max(campaign.selectedLoadoutIndex - 1, 0)] ?? null
    const campaignPhaseLine =
      campaign.scenePhase === 'battle'
        ? `battle live on ${campaign.activeStageTitle}`
        : campaign.scenePhase === 'result-hold'
          ? `result hold on ${campaign.lastResolvedStageTitle ?? campaign.activeStageTitle}`
          : campaign.scenePhase === 'worldmap'
            ? `worldmap route ${campaign.selectedNodeIndex}: ${campaign.selectedStageTitle}`
            : `deploy briefing ${campaign.selectedNodeIndex}: ${campaign.selectedStageTitle}`
    const autoPhaseLine =
      campaign.autoAdvanceInMs !== null
        ? ` · auto ${Math.ceil(campaign.autoAdvanceInMs / 100) / 10}s`
        : ''

    this.spriteLabel.setText(`${stageTitle} / ${snapshot.currentStoryboard.locale ?? 'n/a'}`)
    this.spriteDetail.setText(
      `${mapLine} · ${this.formatKind(previewStem.timelineKind)} · ${snapshot.currentStoryboard.scriptPath.replace('assets/', '')} · ${campaignPhaseLine}${autoPhaseLine}`,
    )
    this.spriteFooter.setText(
      `campaign node ${campaign.currentNodeIndex}/${campaign.totalNodeCount} selected ${campaign.selectedNodeIndex} loadout ${campaign.selectedLoadoutIndex}/${campaign.loadouts.length} ${campaign.selectedLoadoutLabel} · pref ${campaign.preferredRouteLabel ?? 'route-unknown'} x${campaign.routeCommitment} · recommend ${campaign.recommendedNodeIndex}/${campaign.recommendedRouteLabel ?? 'route-unknown'}${campaign.recommendedLoadoutLabel ? `/${campaign.recommendedLoadoutLabel}` : ''}${campaign.recommendedReason ? `/${campaign.recommendedReason}` : ''}${campaign.routeGoalNodeIndex !== null ? ` · goal ${campaign.routeGoalNodeIndex}/${campaign.routeGoalRouteLabel ?? 'route-unknown'}${campaign.routeGoalLabel ? `/${campaign.routeGoalLabel}` : ''}${campaign.routeGoalReason ? `/${campaign.routeGoalReason}` : ''}` : ''} · ${selectedLoadout?.heroRosterLabel ?? 'core squad'} / ${selectedLoadout?.skillPresetLabel ?? 'balanced kit'} / ${selectedLoadout?.towerPolicyLabel ?? 'balanced towers'} · ${campaign.selectionMode}${campaign.selectionLaunchable ? ' launch-ready' : ''} · route ${campaign.selectedRouteLabel}${campaign.selectedRewardText ? ` · reward ${campaign.selectedRewardText}` : ''} · briefing ${briefing.objectivePhase} ${briefing.objectiveLabel} · ally ${briefing.alliedForecast[0] ?? 'idle'} / enemy ${briefing.enemyForecast[0] ?? 'idle'} · ${snapshot.currentStoryboard.scriptEvents.length} script beats, ${previewStem.eventFrames.length} stage frames, loop ${this.describeLoop(previewStem)} · wave ${snapshot.battlePreviewState.objective.waveIndex}/${snapshot.battlePreviewState.objective.totalWaves} · ${snapshot.battlePreviewState.objective.label} · ${snapshot.renderState.bankRuleLabel}${snapshot.activeTutorialCue ? ` · ${snapshot.activeTutorialCue.label}` : ''}`,
    )
    this.channelDetail.setText(this.describeChannels(snapshot.channelStates, snapshot))
    this.interactionDetail.setText(this.describeGameplayState(snapshot))
    this.syncBattleRenderSprites(snapshot)
    this.drawBattleOverlay(snapshot)
  }

  private drawGrid(width: number, height: number): void {
    const graphics = this.add.graphics()
    graphics.lineStyle(1, 0x243138, 0.48)

    for (let x = 0; x <= width; x += 48) {
      graphics.lineBetween(x, 0, x, height)
    }

    for (let y = 0; y <= height; y += 48) {
      graphics.lineBetween(0, y, width, y)
    }
  }

  private previewKey(stem: string): string {
    return `timeline-preview-${stem}`
  }

  private frameKey(stem: string, index: number): string {
    return `timeline-frame-${stem}-${index}`
  }

  private resolvePreviewTexture(entry: RecoveryPreviewStem, index: number): string {
    if (entry.eventFrames.length === 0) {
      return this.previewKey(entry.stem)
    }
    return this.frameKey(entry.stem, Math.min(index, entry.eventFrames.length - 1))
  }

  private fitImageToBox(image: Phaser.GameObjects.Image, maxWidth: number, maxHeight: number): void {
    const width = image.width || 1
    const height = image.height || 1
    const scale = Math.min(maxWidth / width, maxHeight / height)
    image.setScale(scale)
  }

  private ensureTextureKey(path: string): string {
    const existing = this.textureKeysByPath.get(path)
    if (existing) {
      return existing
    }
    const normalized = path.replace(/[^a-zA-Z0-9]+/g, '-')
    const key = `render-${this.textureKeysByPath.size}-${normalized}`
    this.textureKeysByPath.set(path, key)
    return key
  }

  private createGeneratedTextures(): void {
    const dot = this.make.graphics({ x: 0, y: 0 })
    dot.fillStyle(0xffffff, 1)
    dot.fillCircle(6, 6, 5)
    dot.generateTexture('ptc-dot', 12, 12)
    dot.clear()
    dot.fillStyle(0xffffff, 1)
    dot.fillTriangle(8, 0, 16, 8, 0, 8)
    dot.generateTexture('ptc-spark', 16, 8)
    dot.clear()
    dot.fillStyle(0xffffff, 0.9)
    dot.fillCircle(12, 12, 10)
    dot.generateTexture('ptc-glow', 24, 24)
    dot.destroy()
  }

  private resolveFallbackBankProbeTexture(): string {
    const firstPath = this.renderPack?.stemAssets.find((asset) => asset.bankProbePath)?.bankProbePath
    return firstPath ? this.ensureTextureKey(firstPath) : ICON_KEY
  }

  private stemAsset(stem: string | null | undefined): RecoveryRenderStemAsset | null {
    if (!stem) {
      return null
    }
    return this.stemAssetsByStem.get(stem) ?? null
  }

  private pickStemTexture(
    asset: RecoveryRenderStemAsset | null,
    seed: number,
    preferOverlay: boolean,
  ): string | null {
    if (!asset) {
      return null
    }
    const framePaths = preferOverlay && asset.overlayFramePaths.length > 0
      ? asset.overlayFramePaths
      : asset.linkedFramePaths.length > 0
        ? asset.linkedFramePaths
        : asset.framePaths
    if (framePaths.length === 0) {
      return null
    }
    const index = Math.abs(seed) % framePaths.length
    return this.ensureTextureKey(framePaths[index])
  }

  private resolveEntityStemAsset(entity: RecoveryBattleEntityState): RecoveryRenderStemAsset | null {
    if (!this.renderPack) {
      return null
    }
    const sideMap = entity.side === 'allied' ? this.renderPack.roleAssignments.allied : this.renderPack.roleAssignments.enemy
    const role =
      entity.role === 'hero-bait'
        ? 'screen'
        : entity.role
    return this.stemAsset(sideMap[role])
  }

  private resolveProjectileStemAsset(side: 'allied' | 'enemy'): RecoveryRenderStemAsset | null {
    if (!this.renderPack) {
      return null
    }
    return this.stemAsset(this.renderPack.roleAssignments.projectile[side])
  }

  private phaserBlendMode(label: string | null | undefined): Phaser.BlendModes {
    const lowered = (label ?? '').toLowerCase()
    if (lowered.includes('add')) {
      return Phaser.BlendModes.ADD
    }
    return Phaser.BlendModes.NORMAL
  }

  private overlayTint(mode: string | null | undefined, side: 'allied' | 'enemy'): number {
    switch (mode) {
      case 'spawn-aura':
        return 0xb1f0ff
      case 'support-aura':
        return 0x97f3d3
      case 'tower-siege':
      case 'tower-impact':
        return 0xffbe7f
      case 'burst-wave':
      case 'burst-cast':
        return 0xffd37d
      case 'impact-hit':
      case 'projectile-hit':
        return 0xffffff
      default:
        return side === 'allied' ? 0xb6efff : 0xffd78b
    }
  }

  private entityStateScale(state: RecoveryBattleEntityState['spriteState'], weight: number): number {
    switch (state) {
      case 'spawn':
        return 0.94 + weight * 0.22
      case 'attack':
        return 1 + weight * 0.16
      case 'cast':
        return 1.02 + weight * 0.2
      case 'support':
        return 1 + weight * 0.12
      case 'hit':
        return 0.97 + weight * 0.08
      case 'tower-hit':
        return 1.04 + weight * 0.18
      case 'heroic':
        return 1.05 + weight * 0.16
      default:
        return 1 + weight * 0.04
    }
  }

  private entityStateAngle(
    entity: RecoveryBattleEntityState,
    state: RecoveryBattleEntityState['spriteState'],
    weight: number,
  ): number {
    const direction = entity.side === 'allied' ? 1 : -1
    switch (state) {
      case 'attack':
      case 'tower-hit':
        return direction * (5 + weight * 12)
      case 'cast':
        return direction * (2 + weight * 5)
      case 'hit':
        return -direction * (4 + weight * 10)
      case 'advance':
        return direction * (1 + weight * 3)
      default:
        return 0
    }
  }

  private shakeOffset(snapshot: RecoveryStageSnapshot): { x: number; y: number } {
    const intensity = snapshot.renderState.cameraShakeIntensity
    if (intensity <= 0.01) {
      return { x: 0, y: 0 }
    }
    const amplitude = 3 + intensity * 11
    const phase = snapshot.elapsedStoryboardMs / 40
    const allowX = snapshot.renderState.cameraShakeAxes !== 'y'
    const allowY = snapshot.renderState.cameraShakeAxes !== 'x'
    return {
      x: allowX ? Math.sin(phase * 1.4) * amplitude + Math.cos(phase * 2.3) * amplitude * 0.35 : 0,
      y: allowY ? Math.cos(phase * 1.1) * amplitude * 0.55 + Math.sin(phase * 2.7) * amplitude * 0.18 : 0,
    }
  }

  private resolveEffectStemTexture(effect: RecoveryBattleEffectState, seed: number): string | null {
    if (!this.renderPack) {
      return null
    }
    const family = effect.renderFamily
    if (family === 'burst') {
      const special = this.renderPack.packedPixelSpecials.find((entry) => entry.stem === this.renderPack?.roleAssignments.effect.burst)
      if (special?.compositePath) {
        return this.ensureTextureKey(special.compositePath)
      }
    }
    const stem = this.renderPack.roleAssignments.effect[family]
    return this.pickStemTexture(this.stemAsset(stem), seed, family !== 'impact')
  }

  private resolveEmitterPreset(effect: RecoveryBattleEffectState): RecoveryRenderEmitterPreset | null {
    if (!this.renderPack) {
      return null
    }
    const presetId = effect.emitterSemanticId ?? this.renderPack.effectEmitterAssignments[effect.renderFamily]
    return presetId ? this.emitterPresetsById.get(presetId) ?? null : null
  }

  private laneRenderGeometry(bounds: FocusLayoutBounds): {
    startX: number
    endX: number
    laneY: (laneId: 'upper' | 'lower') => number
  } {
    const startX = bounds.x + bounds.width * 0.18
    const endX = bounds.x + bounds.width * 0.82
    return {
      startX,
      endX,
      laneY: (laneId: 'upper' | 'lower') => bounds.y + bounds.height * (laneId === 'upper' ? 0.36 : 0.62),
    }
  }

  private syncBattleRenderSprites(snapshot: RecoveryStageSnapshot): void {
    if (!this.previewImage) {
      return
    }

    const bounds = {
      x: this.previewImage.x - ((this.previewImage.displayWidth || 320) + 16) / 2,
      y: this.previewImage.y - ((this.previewImage.displayHeight || 188) + 16) / 2,
      width: (this.previewImage.displayWidth || 320) + 16,
      height: (this.previewImage.displayHeight || 188) + 16,
    }
    const { startX, endX, laneY } = this.laneRenderGeometry(bounds)

    const activeEntityKeys = new Set<string>()
    snapshot.battlePreviewState.entities.forEach((entity) => {
      const spriteKey = `entity-${entity.id}`
      const overlayKey = `entity-overlay-${entity.id}`
      activeEntityKeys.add(spriteKey)
      activeEntityKeys.add(overlayKey)
      const textureKey =
        this.pickStemTexture(
          this.resolveEntityStemAsset(entity),
          snapshot.frameIndex + entity.id,
          false,
        ) ?? this.resolvePreviewTexture(snapshot.currentStoryboard.previewStem, snapshot.frameIndex)
      const x = startX + (endX - startX) * entity.positionRatio
      const y = laneY(entity.laneId) + (entity.side === 'allied' ? -14 : 14)
      const scale = entity.hero ? 0.34 : entity.role === 'siege' || entity.role === 'skill-window' ? 0.24 : 0.2
      const tint = entity.side === 'allied' ? 0xe6f4ff : 0xffe1d0
      const stateScale = this.entityStateScale(entity.spriteState, entity.stateWeight)
      const hitTint = entity.hitFlash > 0.05 ? 0xffffff : tint

      let sprite = this.entitySprites.get(spriteKey)
      if (!sprite) {
        sprite = this.add.image(x, y, textureKey).setDepth(2.2)
        this.entitySprites.set(spriteKey, sprite)
      }
      sprite.setTexture(textureKey)
      sprite.setPosition(x, y)
      sprite.setScale(scale * stateScale)
      sprite.setFlipX(entity.side === 'enemy')
      sprite.setTint(hitTint)
      sprite.setAngle(this.entityStateAngle(entity, entity.spriteState, entity.stateWeight))
      sprite.setAlpha(clamp(0.48 + entity.hpRatio * 0.44 + entity.hitFlash * 0.18, 0.35, 1))

      const overlayTexture = this.pickStemTexture(
        this.resolveEntityStemAsset(entity),
        snapshot.frameIndex + entity.id,
        true,
      )
      const overlayActive =
        snapshot.renderState.bankOverlayWeight > 0.04
        || entity.overlayAlpha > 0.03
        || entity.role === 'hero'
        || entity.role === 'support'
        || entity.role === 'skill-window'
      let overlay = this.entityOverlaySprites.get(overlayKey)
      if (overlayTexture && overlayActive) {
        if (!overlay) {
          overlay = this.add.image(x, y, overlayTexture).setDepth(2.4)
          this.entityOverlaySprites.set(overlayKey, overlay)
        }
        overlay.setVisible(true)
        overlay.setTexture(overlayTexture)
        overlay.setPosition(x, y)
        overlay.setScale(scale * stateScale * 1.05)
        overlay.setFlipX(entity.side === 'enemy')
        overlay.setBlendMode(this.phaserBlendMode(entity.overlayMode ?? snapshot.renderState.bankBlendMode))
        overlay.setTint(this.overlayTint(entity.overlayMode, entity.side))
        overlay.setAlpha(Math.max(0.12 + snapshot.renderState.bankOverlayWeight * 0.24, entity.overlayAlpha))
      } else if (overlay) {
        overlay.setVisible(false)
      }
    })

    for (const [key, sprite] of this.entitySprites) {
      if (!activeEntityKeys.has(key)) {
        sprite.destroy()
        this.entitySprites.delete(key)
      }
    }
    for (const [key, sprite] of this.entityOverlaySprites) {
      if (!activeEntityKeys.has(key)) {
        sprite.destroy()
        this.entityOverlaySprites.delete(key)
      }
    }

    const activeProjectileKeys = new Set<string>()
    snapshot.battlePreviewState.projectiles.forEach((projectile) => {
      const spriteKey = `projectile-${projectile.id}`
      activeProjectileKeys.add(spriteKey)
      const textureKey =
        this.pickStemTexture(this.resolveProjectileStemAsset(projectile.side), snapshot.frameIndex + projectile.id, true)
        ?? 'ptc-spark'
      const x = startX + (endX - startX) * projectile.positionRatio
      const y = laneY(projectile.laneId)
      let sprite = this.projectileSprites.get(spriteKey)
      if (!sprite) {
        sprite = this.add.image(x, y, textureKey).setDepth(3)
        this.projectileSprites.set(spriteKey, sprite)
      }
      sprite.setTexture(textureKey)
      sprite.setPosition(x, y)
      sprite.setScale(0.12 + projectile.strength * 0.03 + snapshot.renderState.particleBoostIntensity * 0.04)
      sprite.setTint(projectile.side === 'allied' ? 0x9fe7ff : 0xffcca4)
      sprite.setAlpha(0.72 + snapshot.renderState.particleBoostIntensity * 0.16)
    })
    for (const [key, sprite] of this.projectileSprites) {
      if (!activeProjectileKeys.has(key)) {
        sprite.destroy()
        this.projectileSprites.delete(key)
      }
    }

    const activeEffectKeys = new Set<string>()
    snapshot.battlePreviewState.effects.forEach((effect) => {
      const effectKey = `effect-${effect.id}`
      activeEffectKeys.add(effectKey)
      const textureKey = this.resolveEffectStemTexture(effect, snapshot.frameIndex + effect.id) ?? 'ptc-glow'
      const x = startX + (endX - startX) * effect.positionRatio
      const y = laneY(effect.laneId) + (effect.side === 'allied' ? -2 : 2)
      let sprite = this.effectSprites.get(effectKey)
      if (!sprite) {
        sprite = this.add.image(x, y, textureKey).setDepth(3.2)
        this.effectSprites.set(effectKey, sprite)
      }
      sprite.setTexture(textureKey)
      sprite.setPosition(x, y)
      sprite.setBlendMode(this.phaserBlendMode(effect.blendMode))
      sprite.setScale(0.14 + effect.intensity * 0.08 + snapshot.renderState.burstPulseIntensity * 0.05)
      sprite.setTint(effect.side === 'allied' ? 0xaee9ff : 0xffc69c)
      sprite.setAlpha(0.24 + Math.min(effect.intensity, 1.4) * 0.22 + snapshot.renderState.particleBoostIntensity * 0.12)

      const preset = this.resolveEmitterPreset(effect)
      const particleCount = Math.max(
        2,
        Math.min(
          10,
          Math.round(((preset?.burstCount ?? 8) + (preset?.sustainCount ?? 0)) / 16 + snapshot.renderState.particleBoostIntensity * 4) + 2,
        ),
      )
      for (let index = 0; index < particleCount; index += 1) {
        const particleKey = `${effectKey}-particle-${index}`
        activeEffectKeys.add(particleKey)
        const particleTexture = index % 3 === 0 ? 'ptc-glow' : index % 2 === 0 ? 'ptc-spark' : 'ptc-dot'
        const cadence = Math.max(1, preset?.cadenceTicks ?? 4)
        const angle = (Math.PI * 2 * index) / particleCount + snapshot.frameIndex * (0.05 + cadence * 0.004)
        const radius = 6 + (preset?.radiusScale ?? 0.2) * 44 + (preset?.spreadUnits ?? 4) * 0.6
        const driftX = (preset?.driftX ?? 0) / 128
        const driftY = (preset?.driftY ?? 0) / 128
        const accelX = (preset?.accelX ?? 0) / 256
        const accelY = (preset?.accelY ?? 0) / 256
        const offsetX = Math.cos(angle) * radius + driftX * 12 + accelX * index * 2
        const offsetY = Math.sin(angle) * radius * (0.4 + (preset?.jitterScale ?? 0.04) * 2) + driftY * 12 + accelY * index * 2
        let particle = this.particleSprites.get(particleKey)
        if (!particle) {
          particle = this.add.image(x, y, particleTexture).setDepth(3.4)
          this.particleSprites.set(particleKey, particle)
        }
        particle.setTexture(particleTexture)
        particle.setPosition(x + offsetX, y + offsetY)
        particle.setBlendMode(this.phaserBlendMode(preset?.blendMode ?? effect.blendMode))
        particle.setScale(0.06 + effect.intensity * 0.03 + (preset?.sizeScale ?? 0.04) * 0.4 + index * 0.008)
        particle.setTint(effect.side === 'allied' ? 0xaee9ff : 0xffd3ae)
        particle.setAlpha(0.12 + effect.intensity * 0.08 + (preset?.alphaScale ?? 0.1) * 0.16)
      }
    })

    for (const [key, sprite] of this.effectSprites) {
      if (!activeEffectKeys.has(key)) {
        sprite.destroy()
        this.effectSprites.delete(key)
      }
    }
    for (const [key, sprite] of this.particleSprites) {
      if (!activeEffectKeys.has(key)) {
        sprite.destroy()
        this.particleSprites.delete(key)
      }
    }
  }

  private syncBankProbe(snapshot: RecoveryStageSnapshot): void {
    if (!this.bankProbeImage) {
      return
    }
    const previewAsset = this.stemAsset(snapshot.currentStoryboard.previewStem.stem)
    const heroStem = this.renderPack?.roleAssignments.allied.hero ?? null
    const heroAsset = this.stemAsset(heroStem)
    const probePath = previewAsset?.bankProbePath ?? heroAsset?.bankProbePath ?? null
    if (!probePath) {
      this.bankProbeImage.setVisible(false)
      return
    }
    this.bankProbeImage.setVisible(true)
    this.bankProbeImage.setTexture(this.ensureTextureKey(probePath))
    this.fitImageToBox(this.bankProbeImage, 86, 60)
    this.bankProbeImage.setAlpha(0.52 + snapshot.renderState.bankOverlayWeight * 0.4)
    this.bankProbeImage.setTint(snapshot.renderState.bankOverlayActive ? 0xffd78b : 0xffffff)
  }

  private formatKind(value: string): string {
    return value.replaceAll('-', ' ')
  }

  private describeLoop(entry: RecoveryPreviewStem): string {
    if (!entry.loopSummary) {
      return 'none'
    }
    return `${entry.loopSummary.startEventIndex}-${entry.loopSummary.endEventIndex} (${entry.loopSummary.reason})`
  }

  private describeChannels(channelStates: RecoveryBattleChannelState[], snapshot: RecoveryStageSnapshot): string {
    if (channelStates.length === 0) {
      return 'No battle channels resolved for this storyboard yet.'
    }

    const headline = channelStates
      .slice(0, 3)
      .map((entry) => `${entry.label} ${entry.phaseLabel}${entry.loadoutMode ? ` [${entry.loadoutMode}${entry.focusLane ? ` ${entry.focusLane}` : ''}]` : ''}`)
      .join(' · ')
    const sceneCommands = snapshot.activeSceneCommands
      .filter((command) => command.commandType !== 'portrait' && command.commandType !== 'expression')
      .slice(0, 3)
      .map((command) => `${command.commandId}/${command.commandType}`)
      .join(' · ')
    const opcodeCue = snapshot.activeOpcodeCue
      ? `${snapshot.activeOpcodeCue.label}/${snapshot.activeOpcodeCue.action}${sceneCommands ? ` · ${sceneCommands}` : ''}`
      : sceneCommands || null
    const tutorialCue = snapshot.activeTutorialCue ? `${snapshot.activeTutorialCue.label}/${snapshot.activeTutorialCue.action}` : null
    const packed = snapshot.renderState.packedPixelStemRule ? `179 final ${snapshot.renderState.bankStateId}` : `std ${snapshot.renderState.bankStateId}`
    const activeChain = snapshot.battlePreviewState.activeChain.active
      ? ` · chain ${snapshot.battlePreviewState.activeChain.members.join('+')} ${snapshot.battlePreviewState.activeChain.focusLane ?? 'mixed'} x${snapshot.battlePreviewState.activeChain.intensity.toFixed(2)}`
      : ''
    return `${headline} · fx ${snapshot.renderState.effectPulseCount} · ${packed}${tutorialCue ? ` · ${tutorialCue}` : ''}${opcodeCue ? ` · ${opcodeCue}` : ''}${activeChain}`
  }

  private describeGameplayState(snapshot: RecoveryStageSnapshot): string {
    const state = snapshot.gameplayState
    const campaign = snapshot.campaignState
    const activeSceneStep = snapshot.currentStoryboard.sceneScriptSteps[snapshot.dialogueIndex] ?? null
    const selectedLoadout = campaign.loadouts[Math.max(campaign.selectedLoadoutIndex - 1, 0)] ?? null
    const profile = snapshot.battlePreviewState.stageProfile
    const panel = state.openPanel ?? 'none'
    const enabled = state.enabledInputs.slice(0, 3).join(', ') || 'observe-stage-preview'
    const lane = state.selectedDispatchLane ?? 'none'
    const cooldowns = `skill ${state.skillReady ? 'ready' : 'cooldown'} / item ${state.itemReady ? 'ready' : 'cooldown'}`
    const upgrades = `up ${state.towerUpgradeLevels.mana}/${state.towerUpgradeLevels.population}/${state.towerUpgradeLevels.attack}`
    const battle = snapshot.battlePreviewState.lanes
      .map((entry) => `${entry.laneId}:${entry.momentum} ${entry.alliedUnits}-${entry.enemyUnits}`)
      .join(' · ')
    const objective = snapshot.battlePreviewState.objective
    const resolution = snapshot.battlePreviewState.resolution
    const directives = `waves ${objective.alliedDirective?.label ?? 'ally idle'} / ${objective.enemyDirective?.label ?? 'enemy idle'}`
    const signals = profile.archetypeSignals.length > 0 ? profile.archetypeSignals.join('/') : 'baseline'
    const scriptedBeat = state.scriptedBeatNote ? `script ${state.scriptedBeatNote}` : 'script idle'
    const activeChain = snapshot.battlePreviewState.activeChain.active
      ? `chain ${snapshot.battlePreviewState.activeChain.members.join('+')} ${snapshot.battlePreviewState.activeChain.focusLane ?? 'mixed'} x${snapshot.battlePreviewState.activeChain.intensity.toFixed(2)}`
      : 'chain idle'
    const resolutionLine =
      resolution.status === 'active'
        ? 'result active'
        : `result ${resolution.status} ${resolution.label} ${resolution.autoAdvanceInMs !== null ? `in ${Math.ceil(resolution.autoAdvanceInMs / 100) / 10}s` : ''}`
    const lastAction = state.lastActionId
      ? `${state.lastActionId} ${state.lastActionAccepted ? 'ok' : 'blocked'}`
      : 'no-input-yet'
    return `${state.mode}${state.battlePaused ? ' paused' : ''} · phase ${campaign.scenePhase}${campaign.autoAdvanceInMs !== null ? ` auto ${Math.ceil(campaign.autoAdvanceInMs / 100) / 10}s` : ''} · campaign node ${campaign.currentNodeIndex}/${campaign.totalNodeCount} selected ${campaign.selectedNodeIndex} loadout ${campaign.selectedLoadoutIndex}/${campaign.loadouts.length} ${campaign.selectedLoadoutLabel}${campaign.activeLoadoutLabel ? ` active ${campaign.activeLoadoutLabel}` : ''} · pref ${campaign.preferredRouteLabel ?? 'route-unknown'} x${campaign.routeCommitment} · recommend ${campaign.recommendedNodeIndex}/${campaign.recommendedRouteLabel ?? 'route-unknown'}${campaign.recommendedLoadoutLabel ? `/${campaign.recommendedLoadoutLabel}` : ''}${campaign.recommendedReason ? `/${campaign.recommendedReason}` : ''}${campaign.routeGoalNodeIndex !== null ? ` · goal ${campaign.routeGoalNodeIndex}/${campaign.routeGoalRouteLabel ?? 'route-unknown'}${campaign.routeGoalLabel ? `/${campaign.routeGoalLabel}` : ''}${campaign.routeGoalReason ? `/${campaign.routeGoalReason}` : ''}` : ''} · ${selectedLoadout?.heroRosterLabel ?? 'core squad'} / ${selectedLoadout?.skillPresetLabel ?? 'balanced kit'} / ${selectedLoadout?.towerPolicyLabel ?? 'balanced towers'} unlocked ${campaign.unlockedNodeCount} cleared ${campaign.clearedStageCount} · ${campaign.selectionMode}${campaign.selectionLaunchable ? ' launch-ready' : ''}${campaign.nextUnlockLabel ? ` next ${campaign.nextUnlockLabel}${campaign.nextUnlockRouteLabel ? `/${campaign.nextUnlockRouteLabel}` : ''}` : ''}${campaign.lastOutcome ? ` · last ${campaign.lastOutcome} ${campaign.lastResolvedStageTitle ?? ''}` : ''} · target ${campaign.selectedStageTitle} / ${campaign.selectedRouteLabel}${campaign.selectedHintText ? ` / ${campaign.selectedHintText}` : ''} · briefing ${campaign.briefing.objectivePhase} ${campaign.briefing.objectiveLabel} / lane ${campaign.briefing.favoredLane ?? 'mixed'} / a ${campaign.briefing.alliedForecast[0] ?? 'idle'} / e ${campaign.briefing.enemyForecast[0] ?? 'idle'} · scene ${activeSceneStep?.label ?? 'idle'}${activeSceneStep ? `/${activeSceneStep.directives.length}d` : ''} · ${profile.label} · ${profile.tacticalBias} · signals ${signals} · objective ${objective.phase} ${objective.waveIndex}/${objective.totalWaves} ${objective.label} · next a${objective.alliedWaveCountdownBeats}/e${objective.enemyWaveCountdownBeats} · ${directives} · ${resolutionLine} · panel ${panel} · hero ${state.heroMode} · lane ${lane} · queue ${state.queuedUnitCount} · ${upgrades} · ${cooldowns} · ${battle} · ${activeChain} · ${state.primaryHint} · ${scriptedBeat} · inputs ${enabled} · ${lastAction}`
  }

  private handleActionKey(key: string): void {
    if (!this.stageSystem?.isReady()) {
      return
    }
    const snapshot = this.stageSystem.getSnapshot()
    if (!snapshot) {
      return
    }
    if (this.handleCampaignKey(key)) {
      const nextSnapshot = this.stageSystem.getSnapshot()
      if (nextSnapshot) {
        this.currentSnapshotKey = ''
        this.applySnapshot(nextSnapshot)
      }
      return
    }
    const actionId = this.resolveActionForKey(key, snapshot)
    if (!actionId) {
      return
    }
    this.stageSystem.dispatchAction(actionId)
    const nextSnapshot = this.stageSystem.getSnapshot()
    if (nextSnapshot) {
      this.currentSnapshotKey = ''
      this.applySnapshot(nextSnapshot)
    }
  }

  private handleCampaignKey(key: string): boolean {
    if (!this.stageSystem) {
      return false
    }

    const normalized = key.toLowerCase()
    if (normalized === 'arrowleft') {
      return this.stageSystem.moveCampaignSelection(-1)
    }
    if (normalized === 'arrowright') {
      return this.stageSystem.moveCampaignSelection(1)
    }
    if (normalized === 'arrowup') {
      return this.stageSystem.moveCampaignLoadout(-1)
    }
    if (normalized === 'arrowdown') {
      return this.stageSystem.moveCampaignLoadout(1)
    }
    if (normalized === 'enter') {
      return this.stageSystem.launchSelectedCampaignNode()
    }
    return false
  }

  private resolveActionForKey(key: string, snapshot: RecoveryStageSnapshot): RecoveryGameplayActionId | null {
    const normalized = key.toLowerCase()
    const gameplayState = snapshot.gameplayState
    switch (normalized) {
      case '1':
        return 'open-tower-menu'
      case '2':
        return 'open-skill-menu'
      case '3':
        return 'open-item-menu'
      case '4':
        return 'open-system-menu'
      case '5':
        return 'open-settings'
      case 'q':
        return 'dispatch-up-lane'
      case 'w':
        return 'dispatch-down-lane'
      case 'e':
        return 'produce-unit'
      case 'r':
        return gameplayState.heroMode === 'field' ? 'return-to-tower' : 'toggle-hero-sortie'
      case 't':
        return 'cast-skill'
      case 'y':
        return 'use-item'
      case 'u':
        return gameplayState.questState === 'reward-ready' ? 'claim-quest-reward' : 'review-quest-rewards'
      case 'escape':
        return 'resume-battle'
      default:
        return null
    }
  }

  private drawBattleOverlay(snapshot: RecoveryStageSnapshot): void {
    if (!this.previewImage || !this.overlayGraphics) {
      return
    }

    const graphics = this.overlayGraphics
    graphics.clear()

    const width = (this.previewImage.displayWidth || 320) + 16
    const height = (this.previewImage.displayHeight || 188) + 16
    const x = this.previewImage.x - width / 2
    const y = this.previewImage.y - height / 2

    const borderColor = snapshot.activeTutorialCue
      ? 0xd58b39
      : snapshot.renderState.bankOverlayActive
        ? 0xe3c17d
        : 0x4c676f
    if (snapshot.renderState.overlayAlpha > 0.01 && snapshot.renderState.overlayColor !== null) {
      graphics.fillStyle(snapshot.renderState.overlayColor, snapshot.renderState.overlayAlpha)
      graphics.fillRoundedRect(x, y, width, height, 14)
    }
    graphics.lineStyle(2, borderColor, 0.8)
    graphics.strokeRoundedRect(x, y, width, height, 14)
    this.drawLaneBattlePreview(graphics, snapshot, { x, y, width, height })
    this.drawHudGhost(graphics, snapshot, { x, y, width, height })
    this.drawTutorialFocus(graphics, snapshot, { x, y, width, height })
    this.drawCampaignRoute(graphics, snapshot, { x, y, width, height })

    const channelStates = snapshot.channelStates.slice(0, 4)
    channelStates.forEach((channel, index) => {
      const barWidth = 56
      const barHeight = 10
      const barX = x + 18 + index * (barWidth + 10)
      const barY = y + height + 10
      const baseAlpha = 0.18 + channel.intensity * 0.42
      const fillColor = channel.hasExactTailHit ? 0xb7f0ff : channel.hasBuffLayer ? 0xc6a16a : 0x70858b
      graphics.fillStyle(fillColor, baseAlpha)
      graphics.fillRoundedRect(barX, barY, barWidth * channel.intensity, barHeight, 5)
      graphics.lineStyle(1, 0x27363d, 0.8)
      graphics.strokeRoundedRect(barX, barY, barWidth, barHeight, 5)
    })

    if (snapshot.renderState.effectPulseCount > 0) {
      for (let index = 0; index < snapshot.renderState.effectPulseCount; index += 1) {
        const radius = 18 + index * 14
        graphics.lineStyle(2, 0xdca863, 0.22)
        graphics.strokeCircle(this.previewImage.x + 96, this.previewImage.y - 52, radius)
      }
    }
    if (snapshot.renderState.burstPulseIntensity > 0.02) {
      const pulseCount = Math.max(1, Math.round(snapshot.renderState.burstPulseIntensity * 4))
      for (let index = 0; index < pulseCount; index += 1) {
        const radius = 26 + index * 18 + snapshot.renderState.burstPulseIntensity * 12
        graphics.lineStyle(2.4, 0xffcf7b, 0.18 + snapshot.renderState.burstPulseIntensity * 0.14)
        graphics.strokeCircle(this.previewImage.x, this.previewImage.y, radius)
      }
    }
    if (snapshot.renderState.hitFlashIntensity > 0.02) {
      graphics.lineStyle(4, 0xffffff, 0.12 + snapshot.renderState.hitFlashIntensity * 0.38)
      graphics.strokeRoundedRect(x + 3, y + 3, width - 6, height - 6, 12)
    }
  }

  private drawCampaignRoute(
    graphics: Phaser.GameObjects.Graphics,
    snapshot: RecoveryStageSnapshot,
    bounds: FocusLayoutBounds,
  ): void {
    const nodes = snapshot.campaignState.nodes
    if (nodes.length === 0) {
      return
    }

    const startX = bounds.x + 10
    const endX = bounds.x + bounds.width - 10
    const y = bounds.y - 26
    const step = nodes.length === 1 ? 0 : (endX - startX) / (nodes.length - 1)

    graphics.lineStyle(2, 0x334148, 0.82)
    graphics.lineBetween(startX, y, endX, y)

    nodes.forEach((node, index) => {
      const nodeX = startX + step * index
      const fillColor = node.active
        ? 0xd6a55c
        : node.selected
          ? 0xf0d6a0
          : node.cleared
            ? 0x76c989
            : node.unlocked
              ? 0x70858b
              : 0x253138
      const lineColor = node.recommended ? 0xf0b45e : node.unlocked ? 0x66797e : 0x2b373d
      const radius = node.active ? 8 : node.selected ? 7 : 6

      graphics.fillStyle(fillColor, node.unlocked ? 0.96 : 0.5)
      graphics.fillCircle(nodeX, y, radius)
      graphics.lineStyle(node.selected ? 2.2 : 1.4, lineColor, 0.92)
      graphics.strokeCircle(nodeX, y, radius + (node.selected ? 4 : 2))

      if (node.selected) {
        graphics.lineStyle(1.4, 0xf0b45e, 0.76)
        graphics.lineBetween(nodeX, y + radius + 6, nodeX, y + radius + 18)
        graphics.fillStyle(0xf0b45e, 0.82)
        graphics.fillTriangle(nodeX - 5, y + radius + 18, nodeX + 5, y + radius + 18, nodeX, y + radius + 24)
      }
    })
  }

  private drawHudGhost(
    graphics: Phaser.GameObjects.Graphics,
    snapshot: RecoveryStageSnapshot,
    bounds: FocusLayoutBounds,
  ): void {
    const hud = snapshot.hudState
    const rect = (x: number, y: number, width: number, height: number) => ({
      x: bounds.x + x * bounds.width,
      y: bounds.y + y * bounds.height,
      width: width * bounds.width,
      height: height * bounds.height,
    })
    const circle = (x: number, y: number, radius: number) => ({
      x: bounds.x + x * bounds.width,
      y: bounds.y + y * bounds.height,
      radius: radius * Math.min(bounds.width, bounds.height),
    })
    const drawBar = (
      region: { x: number; y: number; width: number; height: number },
      ratio: number,
      fillColor: number,
      highlighted: boolean,
    ): void => {
      graphics.fillStyle(0x0d1418, 0.92)
      graphics.fillRoundedRect(region.x, region.y, region.width, region.height, 6)
      graphics.fillStyle(fillColor, highlighted ? 0.95 : 0.72)
      graphics.fillRoundedRect(region.x + 2, region.y + 2, Math.max((region.width - 4) * ratio, 8), region.height - 4, 5)
      graphics.lineStyle(1.4, highlighted ? 0xf0b45e : 0x5a7176, highlighted ? 0.95 : 0.7)
      graphics.strokeRoundedRect(region.x, region.y, region.width, region.height, 6)
    }

    drawBar(rect(0.06, 0.06, 0.28, 0.08), hud.ownTowerHpRatio, 0xcf4f53, snapshot.activeTutorialCue?.chainId === 'battle-hud-guard-hp')
    drawBar(rect(0.66, 0.06, 0.28, 0.08), hud.enemyTowerHpRatio, 0x8c62d8, snapshot.activeTutorialCue?.chainId === 'battle-hud-goal-hp')
    drawBar(rect(0.06, 0.16, 0.26, 0.06), hud.manaRatio, 0x4b9df0, snapshot.activeTutorialCue?.chainId === 'battle-hud-mana-bar')
    drawBar(rect(0.06, 0.23, 0.26, 0.035), hud.manaUpgradeProgressRatio, 0xe25c64, hud.highlightedTowerUpgradeId === 'mana')

    const unitCardBase = rect(0.02, 0.58, 0.18, 0.26)
    for (let index = 0; index < 4; index += 1) {
      const card = {
        x: unitCardBase.x,
        y: unitCardBase.y + index * (unitCardBase.height / 4 + 2),
        width: unitCardBase.width,
        height: unitCardBase.height / 4 - 2,
      }
      const highlighted = hud.highlightedUnitCardIndex === index
      graphics.fillStyle(highlighted ? 0xe3bb78 : 0x52646b, highlighted ? 0.85 : 0.5)
      graphics.fillRoundedRect(card.x, card.y, card.width, card.height, 5)
      graphics.lineStyle(1.2, highlighted ? 0xf0b45e : 0x304148, 0.8)
      graphics.strokeRoundedRect(card.x, card.y, card.width, card.height, 5)
    }
    for (let index = 0; index < hud.queuedUnitCount; index += 1) {
      graphics.fillStyle(0xf0b45e, 0.9)
      graphics.fillCircle(unitCardBase.x + 10 + index * 12, unitCardBase.y - 10, 4)
    }

    const heroPortrait = circle(0.12, 0.84, 0.06)
    graphics.fillStyle(hud.heroDeployed ? 0x69a15b : 0x687882, hud.heroPortraitHighlighted ? 0.92 : 0.72)
    graphics.fillCircle(heroPortrait.x, heroPortrait.y, heroPortrait.radius)
    graphics.lineStyle(1.4, hud.heroPortraitHighlighted ? 0xf0b45e : 0x304148, 0.92)
    graphics.strokeCircle(heroPortrait.x, heroPortrait.y, heroPortrait.radius)
    if (hud.returnCooldownRatio > 0) {
      graphics.lineStyle(4, 0xce6a70, 0.85)
      graphics.beginPath()
      graphics.arc(heroPortrait.x, heroPortrait.y, heroPortrait.radius + 7, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * hud.returnCooldownRatio, false)
      graphics.strokePath()
    }

    if (hud.dispatchArrowsHighlighted || hud.leftDispatchCueVisible) {
      const arrowLane = rect(0.88, 0.28, 0.07, 0.28)
      for (let index = 0; index < 2; index += 1) {
        const arrowY = arrowLane.y + 22 + index * 40
        const laneSelected =
          (hud.selectedDispatchLane === 'upper' && index === 0)
          || (hud.selectedDispatchLane === 'lower' && index === 1)
        graphics.lineStyle(2.2, laneSelected || hud.dispatchArrowsHighlighted ? 0xf0b45e : 0x6a7c80, laneSelected ? 1 : 0.88)
        graphics.lineBetween(arrowLane.x + arrowLane.width / 2, arrowY, arrowLane.x + arrowLane.width / 2, arrowY + 20)
        graphics.lineBetween(arrowLane.x + arrowLane.width / 2, arrowY, arrowLane.x + arrowLane.width / 2 - 8, arrowY + 8)
        graphics.lineBetween(arrowLane.x + arrowLane.width / 2, arrowY, arrowLane.x + arrowLane.width / 2 + 8, arrowY + 8)
        if (laneSelected) {
          graphics.fillStyle(0xf0b45e, 0.16)
          graphics.fillRoundedRect(arrowLane.x - 4, arrowY - 8, arrowLane.width + 8, 32, 6)
        }
      }
      if (hud.leftDispatchCueVisible) {
        const cue = rect(0.04, 0.36, 0.06, 0.16)
        graphics.fillStyle(0xf0b45e, 0.24)
        graphics.fillRoundedRect(cue.x, cue.y, cue.width, cue.height, 6)
        graphics.lineStyle(1.4, 0xf0b45e, 0.8)
        graphics.strokeRoundedRect(cue.x, cue.y, cue.width, cue.height, 6)
      }
    }

    const menuBar = rect(0.30, 0.78, 0.50, 0.12)
    const menuIds: Array<NonNullable<typeof hud.highlightedMenuId>> = ['tower', 'skill', 'item', 'system']
    menuIds.forEach((menuId, index) => {
      const buttonWidth = menuBar.width / 4 - 6
      const button = {
        x: menuBar.x + index * (buttonWidth + 6),
        y: menuBar.y,
        width: buttonWidth,
        height: menuBar.height,
      }
      const active = hud.highlightedMenuId === menuId || hud.activePanel === menuId
      graphics.fillStyle(active ? 0x7e6238 : 0x27343a, active ? 0.9 : 0.68)
      graphics.fillRoundedRect(button.x, button.y, button.width, button.height, 7)
      graphics.lineStyle(1.4, active ? 0xf0b45e : 0x425359, 0.88)
      graphics.strokeRoundedRect(button.x, button.y, button.width, button.height, 7)
    })

    if (hud.activePanel === 'tower') {
      const ids: Array<NonNullable<typeof hud.highlightedTowerUpgradeId>> = ['mana', 'population', 'attack']
      ids.forEach((upgradeId, index) => {
        const slot = circle(0.35 + index * 0.06, 0.72, 0.038)
        const active = hud.highlightedTowerUpgradeId === upgradeId
        graphics.fillStyle(active ? 0xf0b45e : 0x5a6b70, active ? 0.9 : 0.55)
        graphics.fillCircle(slot.x, slot.y, slot.radius)
        graphics.lineStyle(1.2, active ? 0xffefbf : 0x324147, 0.9)
        graphics.strokeCircle(slot.x, slot.y, slot.radius)
        const level = hud.towerUpgradeLevels[upgradeId]
        for (let pip = 0; pip < level; pip += 1) {
          graphics.fillStyle(active ? 0xffefbf : 0x9ca8aa, 0.88)
          graphics.fillCircle(slot.x - 10 + pip * 6, slot.y + slot.radius + 8, 2)
        }
      })
    }

    if (hud.skillWindowVisible) {
      const skillWindow = rect(0.48, 0.60, 0.28, 0.12)
      graphics.fillStyle(0x182228, 0.86)
      graphics.fillRoundedRect(skillWindow.x, skillWindow.y, skillWindow.width, skillWindow.height, 8)
      graphics.lineStyle(1.2, 0x5f7478, 0.82)
      graphics.strokeRoundedRect(skillWindow.x, skillWindow.y, skillWindow.width, skillWindow.height, 8)
      for (let index = 0; index < 3; index += 1) {
        const slot = {
          x: skillWindow.x + 8 + index * ((skillWindow.width - 28) / 3 + 6),
          y: skillWindow.y + 8,
          width: (skillWindow.width - 28) / 3,
          height: skillWindow.height - 16,
        }
        const highlighted = hud.skillSlotHighlighted && index === 0
        graphics.fillStyle(highlighted ? 0xd88763 : 0x54666b, highlighted ? 0.88 : 0.55)
        graphics.fillRoundedRect(slot.x, slot.y, slot.width, slot.height, 5)
        graphics.lineStyle(1.2, highlighted ? 0xf0b45e : 0x304148, 0.85)
        graphics.strokeRoundedRect(slot.x, slot.y, slot.width, slot.height, 5)
      }
      if (hud.skillCooldownRatio > 0.02) {
        graphics.fillStyle(0x091014, 0.52)
        graphics.fillRoundedRect(
          skillWindow.x + 8,
          skillWindow.y + 8,
          (skillWindow.width - 16) * hud.skillCooldownRatio,
          skillWindow.height - 16,
          5,
        )
      }
    }

    if (hud.itemWindowVisible) {
      const itemWindow = rect(0.62, 0.60, 0.18, 0.12)
      graphics.fillStyle(0x182228, 0.86)
      graphics.fillRoundedRect(itemWindow.x, itemWindow.y, itemWindow.width, itemWindow.height, 8)
      graphics.lineStyle(1.2, 0x5f7478, 0.82)
      graphics.strokeRoundedRect(itemWindow.x, itemWindow.y, itemWindow.width, itemWindow.height, 8)
      for (let index = 0; index < 2; index += 1) {
        const slot = {
          x: itemWindow.x + 8 + index * ((itemWindow.width - 22) / 2 + 6),
          y: itemWindow.y + 8,
          width: (itemWindow.width - 22) / 2,
          height: itemWindow.height - 16,
        }
        const highlighted = hud.itemSlotHighlighted && index === 0
        graphics.fillStyle(highlighted ? 0xd88763 : 0x54666b, highlighted ? 0.88 : 0.55)
        graphics.fillRoundedRect(slot.x, slot.y, slot.width, slot.height, 5)
        graphics.lineStyle(1.2, highlighted ? 0xf0b45e : 0x304148, 0.85)
        graphics.strokeRoundedRect(slot.x, slot.y, slot.width, slot.height, 5)
      }
      if (hud.itemCooldownRatio > 0.02) {
        graphics.fillStyle(0x091014, 0.52)
        graphics.fillRoundedRect(
          itemWindow.x + 8,
          itemWindow.y + 8,
          (itemWindow.width - 16) * hud.itemCooldownRatio,
          itemWindow.height - 16,
          5,
        )
      }
    }

    if (hud.questVisible) {
      const questPanel = rect(0.74, 0.16, 0.20, 0.12)
      graphics.fillStyle(0x182228, 0.9)
      graphics.fillRoundedRect(questPanel.x, questPanel.y, questPanel.width, questPanel.height, 8)
      graphics.lineStyle(1.3, hud.questRewardReady ? 0xf0b45e : 0x5f7478, 0.88)
      graphics.strokeRoundedRect(questPanel.x, questPanel.y, questPanel.width, questPanel.height, 8)
      if (hud.questRewardReady) {
        graphics.fillStyle(0xf0b45e, 0.92)
        graphics.fillCircle(questPanel.x + questPanel.width - 12, questPanel.y + 12, 5)
      }
      for (let index = 0; index < Math.min(hud.questRewardClaims, 3); index += 1) {
        graphics.fillStyle(0x8bcf7a, 0.88)
        graphics.fillCircle(questPanel.x + 12 + index * 10, questPanel.y + questPanel.height - 10, 3)
      }
    }

    if (hud.battlePaused) {
      const pauseBox = rect(0.38, 0.36, 0.24, 0.18)
      graphics.fillStyle(0x081114, 0.78)
      graphics.fillRoundedRect(pauseBox.x, pauseBox.y, pauseBox.width, pauseBox.height, 10)
      graphics.lineStyle(1.4, 0xf0b45e, 0.72)
      graphics.strokeRoundedRect(pauseBox.x, pauseBox.y, pauseBox.width, pauseBox.height, 10)
      graphics.fillStyle(0xf0b45e, 0.88)
      graphics.fillRoundedRect(pauseBox.x + pauseBox.width * 0.34, pauseBox.y + 18, 10, pauseBox.height - 36, 4)
      graphics.fillRoundedRect(pauseBox.x + pauseBox.width * 0.56, pauseBox.y + 18, 10, pauseBox.height - 36, 4)
    }
  }

  private drawLaneBattlePreview(
    graphics: Phaser.GameObjects.Graphics,
    snapshot: RecoveryStageSnapshot,
    bounds: FocusLayoutBounds,
  ): void {
    const laneY = (index: number): number => bounds.y + bounds.height * (index === 0 ? 0.36 : 0.62)
    const laneStartX = bounds.x + bounds.width * 0.18
    const laneEndX = bounds.x + bounds.width * 0.82

    snapshot.battlePreviewState.lanes.forEach((lane, index) => {
      const y = laneY(index)
      const selected = snapshot.battlePreviewState.selectedLane === lane.laneId
      const chained = snapshot.battlePreviewState.activeChain.active && snapshot.battlePreviewState.activeChain.focusLane === lane.laneId
      const momentumColor =
        lane.momentum === 'allied-push'
          ? 0x85d46a
          : lane.momentum === 'enemy-push'
            ? 0xd56565
            : lane.momentum === 'contested'
              ? 0xf0b45e
              : 0x6c7c82

      graphics.lineStyle(2.4, chained ? 0x76d6ff : selected ? 0xf0b45e : 0x314048, chained ? 0.92 : 0.74)
      graphics.lineBetween(laneStartX, y, laneEndX, y)

      const contestedWidth = (laneEndX - laneStartX) * lane.contested * 0.35
      const frontlineX = laneStartX + (laneEndX - laneStartX) * lane.frontline
      graphics.lineStyle(6, momentumColor, 0.22)
      graphics.lineBetween(frontlineX - contestedWidth, y, frontlineX + contestedWidth, y)
      graphics.fillStyle(momentumColor, chained ? 1 : selected ? 0.95 : 0.78)
      graphics.fillCircle(frontlineX, y, chained ? 8 : selected ? 7 : 6)

      if (chained) {
        graphics.lineStyle(1.6, 0x76d6ff, 0.7)
        graphics.strokeCircle(frontlineX, y, 13 + snapshot.battlePreviewState.activeChain.intensity * 10)
      }
    })
  }

  private drawTutorialFocus(
    graphics: Phaser.GameObjects.Graphics,
    snapshot: RecoveryStageSnapshot,
    bounds: FocusLayoutBounds,
  ): void {
    const regions = this.focusRegionsForCue(snapshot, bounds)
    if (regions.length === 0) {
      return
    }

    graphics.lineStyle(2, 0xf0b45e, 0.95)
    graphics.fillStyle(0xf0b45e, 0.12)

    regions.forEach((region, index) => {
      if (region.kind === 'rect' && region.width && region.height) {
        graphics.fillRoundedRect(region.x, region.y, region.width, region.height, 8)
        graphics.strokeRoundedRect(region.x, region.y, region.width, region.height, 8)
      } else if (region.kind === 'circle' && region.radius) {
        graphics.fillCircle(region.x, region.y, region.radius)
        graphics.strokeCircle(region.x, region.y, region.radius)
      }

      const anchorX = region.kind === 'circle' ? region.x : region.x + (region.width ?? 0) / 2
      const anchorY = region.kind === 'circle' ? region.y : region.y + (region.height ?? 0) / 2
      const calloutX = bounds.x + bounds.width + 18
      const calloutY = bounds.y + 22 + index * 18
      graphics.lineStyle(1.5, 0xf0b45e, 0.7)
      graphics.lineBetween(anchorX, anchorY, calloutX - 8, calloutY + 6)
      graphics.fillStyle(0xf0b45e, 0.72)
      graphics.fillCircle(calloutX, calloutY + 6, 3)
    })
  }

  private focusRegionsForCue(snapshot: RecoveryStageSnapshot, bounds: FocusLayoutBounds): FocusRegion[] {
    const chainId = snapshot.activeTutorialCue?.chainId
    if (!chainId) {
      return []
    }
    const rect = (x: number, y: number, width: number, height: number, label: string): FocusRegion => ({
      kind: 'rect',
      x: bounds.x + x * bounds.width,
      y: bounds.y + y * bounds.height,
      width: width * bounds.width,
      height: height * bounds.height,
      label,
    })
    const circle = (x: number, y: number, radius: number, label: string): FocusRegion => ({
      kind: 'circle',
      x: bounds.x + x * bounds.width,
      y: bounds.y + y * bounds.height,
      radius: radius * Math.min(bounds.width, bounds.height),
      label,
    })

    switch (chainId) {
      case 'battle-hud-guard-hp':
        return [rect(0.06, 0.06, 0.28, 0.08, 'Our tower HP')]
      case 'battle-hud-goal-hp':
        return [rect(0.66, 0.06, 0.28, 0.08, 'Enemy tower HP')]
      case 'battle-hud-dispatch-arrows':
        return [rect(0.88, 0.28, 0.07, 0.28, 'Path arrows'), rect(0.04, 0.36, 0.06, 0.16, 'Dispatch cue')]
      case 'battle-hud-unit-card':
        return [rect(0.02, 0.58, 0.18, 0.26, 'Unit cards')]
      case 'battle-hud-mana-bar':
        return [rect(0.06, 0.16, 0.26, 0.06, 'Mana bar')]
      case 'battle-hud-hero-sortie':
        return [circle(0.12, 0.84, 0.06, 'Hero sortie')]
      case 'battle-hud-hero-return':
        return [circle(0.12, 0.84, 0.06, 'Return to tower')]
      case 'tower-menu-highlight':
        return [rect(0.30, 0.78, 0.22, 0.12, 'Tower menu')]
      case 'mana-upgrade-highlight':
        return [circle(0.35, 0.84, 0.045, 'Mana upgrade')]
      case 'population-upgrade-highlight':
        return [circle(0.41, 0.84, 0.045, 'Population')]
      case 'skill-menu-highlight':
        return [rect(0.53, 0.78, 0.12, 0.12, 'Skill menu')]
      case 'skill-slot-highlight':
        return [rect(0.48, 0.60, 0.28, 0.12, 'Skill window')]
      case 'item-menu-highlight':
        return [rect(0.67, 0.78, 0.12, 0.12, 'Item menu')]
      case 'system-menu-highlight':
        return [circle(0.92, 0.10, 0.045, 'System')]
      case 'quest-panel-highlight':
        return [rect(0.74, 0.16, 0.20, 0.12, 'Quest panel')]
      default:
        return []
    }
  }
}
