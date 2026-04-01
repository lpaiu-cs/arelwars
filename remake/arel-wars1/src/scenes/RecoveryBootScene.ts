import Phaser from 'phaser'
import type { RecoveryPreviewManifest, RecoveryPreviewStem } from '../recovery-types'

const ICON_KEY = 'recovery-icon'

export class RecoveryBootScene extends Phaser.Scene {
  private readonly featuredEntries: RecoveryPreviewStem[]

  constructor(previewManifest: RecoveryPreviewManifest | null = null) {
    super('RecoveryBootScene')
    this.featuredEntries = previewManifest?.featuredEntries.slice(0, 3) ?? []
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
      .text(80, 100, 'Arel Wars 1 runtime shell', {
        fontFamily: 'Georgia, serif',
        fontSize: '40px',
        color: '#f3ecdf',
      })
      .setAlpha(0.98)

    this.add
      .text(
        80,
        148,
        'Confirmed recoveries: PZX tail timelines, sequence candidates, and runtime strip previews.',
        {
          fontFamily: 'Trebuchet MS, sans-serif',
          fontSize: '16px',
          color: '#b7c0bf',
        },
      )
      .setAlpha(0.9)

    const frame = this.add.rectangle(width * 0.72, height * 0.58, 356, 286, 0x131d22, 0.9)
    frame.setStrokeStyle(2, 0xc09a5a, 0.3)

    if (this.featuredEntries.length > 0) {
      this.createPreviewCarousel(frame)
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

      this.add
        .text(frame.x, frame.y + 104, 'Native sprite archives (.pzx)\nremain the main reverse-engineering target.', {
          align: 'center',
          fontFamily: 'Trebuchet MS, sans-serif',
          fontSize: '16px',
          color: '#cab892',
        })
        .setOrigin(0.5)
    }

    const milestones = [
      '1. Export runtime timeline manifests',
      '2. Resolve packed pixel semantics in 179',
      '3. Decode MPL bank switching and raw timing directives',
      '4. Promote recovered loop windows into runtime playback',
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
      .text(84, height - 52, 'The canvas stays deliberately thin. Simulation and content recovery will live outside Phaser scenes.', {
        fontFamily: 'Trebuchet MS, sans-serif',
        fontSize: '15px',
        color: '#7f908e',
      })
      .setAlpha(0.94)
  }

  private createPreviewCarousel(frame: Phaser.GameObjects.Rectangle): void {
    const previewImage = this.add.image(frame.x, frame.y - 14, this.resolvePreviewTexture(this.featuredEntries[0], 0))
    this.fitImageToBox(previewImage, 316, 176)

    const label = this.add
      .text(frame.x - 148, frame.y + 96, '', {
        fontFamily: 'Georgia, serif',
        fontSize: '18px',
        color: '#f0dfc0',
      })
      .setAlpha(0.98)

    const detail = this.add
      .text(frame.x - 148, frame.y + 124, '', {
        fontFamily: 'Trebuchet MS, sans-serif',
        fontSize: '14px',
        color: '#cab892',
        wordWrap: { width: 300 },
      })
      .setAlpha(0.94)

    const footer = this.add
      .text(frame.x - 148, frame.y + 166, '', {
        fontFamily: 'Trebuchet MS, sans-serif',
        fontSize: '13px',
        color: '#92a09d',
      })
      .setAlpha(0.9)

    let frameTimer: Phaser.Time.TimerEvent | null = null

    const resolveLoopStart = (entry: RecoveryPreviewStem): number => entry.loopSummary?.startEventIndex ?? 0
    const resolveLoopEnd = (entry: RecoveryPreviewStem): number => {
      if (entry.eventFrames.length === 0) {
        return 0
      }
      return Math.min(entry.loopSummary?.endEventIndex ?? entry.eventFrames.length - 1, entry.eventFrames.length - 1)
    }

    const startFramePlayback = (entry: RecoveryPreviewStem): void => {
      frameTimer?.remove(false)
      if (entry.eventFrames.length === 0) {
        previewImage.setTexture(this.resolvePreviewTexture(entry, 0))
        this.fitImageToBox(previewImage, 316, 176)
        return
      }

      let frameIndex = 0
      previewImage.setTexture(this.resolvePreviewTexture(entry, frameIndex))
      this.fitImageToBox(previewImage, 316, 176)

      const scheduleNextFrame = (): void => {
        const current = entry.eventFrames[Math.min(frameIndex, entry.eventFrames.length - 1)]
        const delay = Math.max(current?.playbackDurationMs ?? entry.stemDefaultDurationMs ?? 160, 40)
        frameTimer = this.time.delayedCall(delay, () => {
          const loopStart = resolveLoopStart(entry)
          const loopEnd = resolveLoopEnd(entry)
          if (frameIndex >= loopEnd) {
            frameIndex = loopStart
          } else {
            frameIndex += 1
          }
          previewImage.setTexture(this.resolvePreviewTexture(entry, frameIndex))
          this.fitImageToBox(previewImage, 316, 176)
          scheduleNextFrame()
        })
      }

      if (entry.eventFrames.length > 1) {
        scheduleNextFrame()
      }
    }

    const applyEntry = (entry: RecoveryPreviewStem): void => {
      startFramePlayback(entry)
      label.setText(`Stem ${entry.stem}`)
      detail.setText(`${this.formatKind(entry.timelineKind)} / anchors ${this.describeAnchors(entry)}`)
      footer.setText(
        `${entry.linkedGroupCount} linked, ${entry.overlayGroupCount} overlays, ${Math.max(entry.eventFrames.length, 1)} frames / ${this.describeTiming(entry)} / ${this.describeLoop(entry)}`,
      )
    }

    applyEntry(this.featuredEntries[0])

    if (this.featuredEntries.length < 2) {
      return
    }

    let currentIndex = 0
    this.time.addEvent({
      delay: 2600,
      loop: true,
      callback: () => {
        currentIndex = (currentIndex + 1) % this.featuredEntries.length
        this.tweens.add({
          targets: [previewImage, label, detail, footer],
          alpha: 0.08,
          duration: 180,
          yoyo: false,
          onComplete: () => {
            applyEntry(this.featuredEntries[currentIndex])
            this.tweens.add({
              targets: [previewImage, label, detail, footer],
              alpha: 1,
              duration: 220,
            })
          },
        })
      },
    })
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

  private describeAnchors(entry: RecoveryPreviewStem): string {
    if (entry.anchorFrameSequence.length === 0) {
      return 'overlay only'
    }

    const preview = entry.anchorFrameSequence.slice(0, 4).join(' / ')
    return entry.anchorFrameSequence.length > 4 ? `${preview} ...` : preview
  }

  private describeTiming(entry: RecoveryPreviewStem): string {
    const durations = entry.eventFrames
      .map((frame) => frame.playbackDurationMs)
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
    if (durations.length === 0) {
      return 'timing unresolved'
    }

    const unique = Array.from(new Set(durations)).sort((left, right) => left - right)
    return unique.length === 1 ? `${unique[0]}ms cadence` : `${unique[0]}-${unique[unique.length - 1]}ms cadence`
  }

  private describeLoop(entry: RecoveryPreviewStem): string {
    if (!entry.loopSummary) {
      return 'loop unresolved'
    }
    return `loop ${entry.loopSummary.startEventIndex}-${entry.loopSummary.endEventIndex}`
  }
}
