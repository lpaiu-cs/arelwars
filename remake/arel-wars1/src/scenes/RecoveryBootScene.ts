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
    this.drawHudGhost(graphics, snapshot, { x, y, width, height })
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
        graphics.lineStyle(2.2, hud.dispatchArrowsHighlighted ? 0xf0b45e : 0x6a7c80, 0.88)
        graphics.lineBetween(arrowLane.x + arrowLane.width / 2, arrowY, arrowLane.x + arrowLane.width / 2, arrowY + 20)
        graphics.lineBetween(arrowLane.x + arrowLane.width / 2, arrowY, arrowLane.x + arrowLane.width / 2 - 8, arrowY + 8)
        graphics.lineBetween(arrowLane.x + arrowLane.width / 2, arrowY, arrowLane.x + arrowLane.width / 2 + 8, arrowY + 8)
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
