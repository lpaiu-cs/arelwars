import Phaser from 'phaser'
import './style.css'
import { RecoveryBootScene } from './scenes/RecoveryBootScene'
import type { RecoveryCatalog, RecoveryPreviewManifest, RecoveryPreviewStem } from './recovery-types'

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

  if (!stage || !summary || !inventory || !scripts || !timelineSummary || !timelineStats || !timelineGallery) {
    return
  }

  const [catalogResult, previewResult] = await Promise.allSettled([
    fetchJson<RecoveryCatalog>('/recovery/catalog.json'),
    fetchJson<RecoveryPreviewManifest>('/recovery/analysis/preview_manifest.json'),
  ])

  const previewManifest = previewResult.status === 'fulfilled' ? previewResult.value : null
  game = createGame(previewManifest)

  if (catalogResult.status === 'fulfilled') {
    const catalog = catalogResult.value
    stage.textContent = previewManifest
      ? `Timeline candidates indexed (${previewManifest.activeStemCount} stems)`
      : 'ZT1 decoded, runtime shell online'
    summary.textContent = `${catalog.inventory.zt1Total} decoded ZT1 files, ${catalog.inventory.webSafeAssetCount} web-safe assets, blockers on ${catalog.blockedFormats.map((item) => item.suffix).join(', ')}.${previewManifest ? ` Active timeline stems: ${previewManifest.activeStemCount}.` : ''}`

    inventory.innerHTML = [
      statCard('Scripts', `${catalog.featuredScripts.length} featured`),
      statCard('ZT1 Total', String(catalog.inventory.zt1Total)),
      statCard('Script Events', String(catalog.inventory.scriptEventTotal ?? 0)),
      statCard('Web-safe', String(catalog.inventory.webSafeAssetCount)),
      statCard('Timeline Stems', String(previewManifest?.activeStemCount ?? 0)),
      statCard('Timeline Kinds', String(Object.keys(previewManifest?.timelineKindCounts ?? {}).length)),
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
            <p>${escapeHtml(describeScriptPreview(entry))}</p>
          </article>
        `,
      )
      .join('')
  } else {
    const message = catalogResult.reason instanceof Error ? catalogResult.reason.message : 'Unknown error'
    stage.textContent = 'Catalog load failed'
    summary.textContent = message
    inventory.innerHTML = statCard('Status', 'Failed')
    scripts.innerHTML = `<article class="script-card error-card"><p>${escapeHtml(message)}</p></article>`
  }

  renderTimelinePreview(previewManifest, timelineSummary, timelineStats, timelineGallery)
}

function createGame(previewManifest: RecoveryPreviewManifest | null): Phaser.Game {
  return new Phaser.Game({
    type: Phaser.AUTO,
    parent: 'game-root',
    width: 960,
    height: 540,
    backgroundColor: '#0e1418',
    scene: [new RecoveryBootScene(previewManifest)],
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH,
    },
  })
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
