import Phaser from 'phaser'

const ICON_KEY = 'recovery-icon'

export class RecoveryBootScene extends Phaser.Scene {
  constructor() {
    super('RecoveryBootScene')
  }

  preload(): void {
    this.load.image(ICON_KEY, '/recovery/raw/res/drawable-hdpi/icon_normal.png')
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
        'Confirmed recoveries: ZT1 decompression, dialogue previews, PNG and OGG extraction.',
        {
          fontFamily: 'Trebuchet MS, sans-serif',
          fontSize: '16px',
          color: '#b7c0bf',
        },
      )
      .setAlpha(0.9)

    const frame = this.add.rectangle(width * 0.72, height * 0.58, 280, 280, 0x131d22, 0.9)
    frame.setStrokeStyle(2, 0xc09a5a, 0.3)

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

    const milestones = [
      '1. Recover PZX image decode',
      '2. Recover MPL animation metadata',
      '3. Map script events to scene actions',
      '4. Replace placeholder board with recovered assets',
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
}
