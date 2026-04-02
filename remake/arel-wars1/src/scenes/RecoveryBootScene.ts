import Phaser from 'phaser'
import type { RecoveryBattleChannelState, RecoveryPreviewStem, RecoveryStageSnapshot } from '../recovery-types'
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

export class RecoveryBootScene extends Phaser.Scene {
  private readonly stageSystem: RecoveryStageSystem | null

  private readonly featuredEntries: RecoveryPreviewStem[]

  private previewImage: Phaser.GameObjects.Image | null = null

  private spriteLabel: Phaser.GameObjects.Text | null = null

  private spriteDetail: Phaser.GameObjects.Text | null = null

  private spriteFooter: Phaser.GameObjects.Text | null = null

  private channelDetail: Phaser.GameObjects.Text | null = null

  private overlayGraphics: Phaser.GameObjects.Graphics | null = null

  private currentSnapshotKey = ''

  constructor(stageSystem: RecoveryStageSystem | null = null) {
    super('RecoveryBootScene')
    this.stageSystem = stageSystem
    this.featuredEntries = stageSystem?.getPreviewEntries().slice(0, 6) ?? []
  }

  preload(): void {
    this.load.image(ICON_KEY, '/recovery/raw/res/drawable-hdpi/icon_normal.png')

    this.featuredEntries.forEach((entry) => {
      this.load.image(this.previewKey(entry.stem), entry.timelineStrip.pngPath)
      entry.eventFrames.forEach((frame, index) => {
        this.load.image(this.frameKey(entry.stem, index), frame.framePath)
      })
    })
  }

  create(): void {
    const { width, height } = this.scale

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

    this.overlayGraphics = this.add.graphics()

    this.applySnapshot(snapshot)
  }

  private createFallbackStrip(frame: Phaser.GameObjects.Rectangle): void {
    const previewImage = this.add.image(frame.x, frame.y - 14, this.previewKey(this.featuredEntries[0].stem))
    this.fitImageToBox(previewImage, 316, 176)
  }

  private applySnapshot(snapshot: RecoveryStageSnapshot): void {
    if (!this.previewImage || !this.spriteLabel || !this.spriteDetail || !this.spriteFooter || !this.channelDetail || !this.overlayGraphics) {
      return
    }

    const previewStem = snapshot.currentStoryboard.previewStem
    this.previewImage.setTexture(this.resolvePreviewTexture(previewStem, snapshot.frameIndex))
    this.fitImageToBox(this.previewImage, 320, 188)
    this.previewImage.setTint(snapshot.renderState.bankOverlayActive ? 0xffe3a1 : 0xffffff)
    this.previewImage.setAlpha(snapshot.renderState.packedPixelStemRule ? 0.96 : 1)

    const stageTitle = snapshot.currentStoryboard.stageBlueprint?.title ?? `Stem ${previewStem.stem}`
    const mapBinding = snapshot.currentStoryboard.stageBlueprint?.mapBinding
    const mapLine = mapBinding
      ? `Map pair ${mapBinding.mapPairIndices.join('/')} → ${mapBinding.preferredMapIndexHeuristic ?? 'n/a'} · ${mapBinding.proofType} ${mapBinding.proofScore.toFixed(2)}`
      : `Stem ${previewStem.stem}`

    this.spriteLabel.setText(`${stageTitle} / ${snapshot.currentStoryboard.locale ?? 'n/a'}`)
    this.spriteDetail.setText(
      `${mapLine} · ${this.formatKind(previewStem.timelineKind)} · ${snapshot.currentStoryboard.scriptPath.replace('assets/', '')}`,
    )
    this.spriteFooter.setText(
      `${snapshot.currentStoryboard.scriptEvents.length} script beats, ${previewStem.eventFrames.length} stage frames, loop ${this.describeLoop(previewStem)} · ${snapshot.renderState.bankRuleLabel}${snapshot.activeTutorialCue ? ` · ${snapshot.activeTutorialCue.label}` : ''}`,
    )
    this.channelDetail.setText(this.describeChannels(snapshot.channelStates, snapshot))
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
      .map((entry) => `${entry.label} ${entry.phaseLabel}`)
      .join(' · ')
    const opcodeCue = snapshot.activeOpcodeCue ? `${snapshot.activeOpcodeCue.label}/${snapshot.activeOpcodeCue.action}` : null
    const tutorialCue = snapshot.activeTutorialCue ? `${snapshot.activeTutorialCue.label}/${snapshot.activeTutorialCue.action}` : null
    const packed = snapshot.renderState.packedPixelStemRule ? '179 shade' : 'std render'
    return `${headline} · fx ${snapshot.renderState.effectPulseCount} · ${packed}${tutorialCue ? ` · ${tutorialCue}` : ''}${opcodeCue ? ` · ${opcodeCue}` : ''}`
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
    graphics.lineStyle(2, borderColor, 0.8)
    graphics.strokeRoundedRect(x, y, width, height, 14)
    this.drawTutorialFocus(graphics, snapshot, { x, y, width, height })

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
