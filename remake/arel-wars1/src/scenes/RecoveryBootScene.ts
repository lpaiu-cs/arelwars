import Phaser from 'phaser'
import type { RecoveryPreviewStem, RecoveryStageSnapshot } from '../recovery-types'
import { RecoveryStageSystem } from '../systems/recoveryStageSystem'

const ICON_KEY = 'recovery-icon'

export class RecoveryBootScene extends Phaser.Scene {
  private readonly stageSystem: RecoveryStageSystem | null

  private readonly featuredEntries: RecoveryPreviewStem[]

  private previewImage: Phaser.GameObjects.Image | null = null

  private spriteLabel: Phaser.GameObjects.Text | null = null

  private spriteDetail: Phaser.GameObjects.Text | null = null

  private spriteFooter: Phaser.GameObjects.Text | null = null

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
          ? 'Recovered sprite timelines and structured dialogue now drive a shared stage state.'
          : 'Confirmed recoveries: PZX tail timelines, sequence candidates, and runtime strip previews.',
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
      '2. MPL palette banks normalized into runtime render rules',
      '3. ZT1 scripts elevated from raw strings to caption/speech events',
      '4. Shared stage state now drives both sprite playback and narrative HUD',
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
      .text(84, height - 52, 'This remains a reconstruction layer, not a claim of 1:1 engine parity. Unknown opcodes and battle state semantics are still being recovered.', {
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

    this.applySnapshot(snapshot)
  }

  private createFallbackStrip(frame: Phaser.GameObjects.Rectangle): void {
    const previewImage = this.add.image(frame.x, frame.y - 14, this.previewKey(this.featuredEntries[0].stem))
    this.fitImageToBox(previewImage, 316, 176)
  }

  private applySnapshot(snapshot: RecoveryStageSnapshot): void {
    if (!this.previewImage || !this.spriteLabel || !this.spriteDetail || !this.spriteFooter) {
      return
    }

    const previewStem = snapshot.currentStoryboard.previewStem
    this.previewImage.setTexture(this.resolvePreviewTexture(previewStem, snapshot.frameIndex))
    this.fitImageToBox(this.previewImage, 320, 188)

    this.spriteLabel.setText(`Stem ${previewStem.stem} / ${snapshot.currentStoryboard.locale ?? 'n/a'}`)
    this.spriteDetail.setText(`${this.formatKind(previewStem.timelineKind)} / ${snapshot.currentStoryboard.scriptPath.replace('assets/', '')}`)
    this.spriteFooter.setText(
      `${snapshot.currentStoryboard.scriptEvents.length} script beats, ${previewStem.eventFrames.length} stage frames, loop ${this.describeLoop(previewStem)}`,
    )
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
}
