import Phaser from 'phaser'
import './style.css'
import { RecoveryBootScene } from './scenes/RecoveryBootScene'
import type { RecoveryCatalog } from './recovery-types'

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
          <strong>Capacitor 예정</strong>
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
          <p>Recovered PNG assets are usable already. Core battle art remains locked in \`.pzx\`.</p>
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
  </div>
`

const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game-root',
  width: 960,
  height: 540,
  backgroundColor: '#0e1418',
  scene: [RecoveryBootScene],
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
})

void loadCatalog()

async function loadCatalog(): Promise<void> {
  const stage = document.querySelector<HTMLElement>('#current-stage')
  const summary = document.querySelector<HTMLElement>('#catalog-summary')
  const inventory = document.querySelector<HTMLElement>('#inventory')
  const scripts = document.querySelector<HTMLElement>('#scripts')

  if (!stage || !summary || !inventory || !scripts) {
    return
  }

  try {
    const response = await fetch('/recovery/catalog.json')
    if (!response.ok) {
      throw new Error(`Catalog request failed with ${response.status}`)
    }

    const catalog = (await response.json()) as RecoveryCatalog
    stage.textContent = 'ZT1 decoded, runtime shell online'
    summary.textContent = `${catalog.inventory.zt1Total} decoded ZT1 files, ${catalog.inventory.webSafeAssetCount} web-safe assets, blockers on ${catalog.blockedFormats.map((item) => item.suffix).join(', ')}.`

    inventory.innerHTML = [
      statCard('Scripts', `${catalog.featuredScripts.length} featured`),
      statCard('ZT1 Total', String(catalog.inventory.zt1Total)),
      statCard('Web-safe', String(catalog.inventory.webSafeAssetCount)),
      statCard('Asset Roots', String(Object.keys(catalog.inventory.assetDirectories).length)),
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
            <p>${escapeHtml(entry.stringsPreview.slice(0, 2).join(' / ') || 'Recoverable text not found')}</p>
          </article>
        `,
      )
      .join('')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    stage.textContent = 'Catalog load failed'
    summary.textContent = message
    inventory.innerHTML = statCard('Status', 'Failed')
    scripts.innerHTML = `<article class="script-card error-card"><p>${escapeHtml(message)}</p></article>`
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

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

window.addEventListener('beforeunload', () => {
  game.destroy(true)
})
