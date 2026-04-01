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
  stringCount: number
  stringsPreview: string[]
  decodedPath: string
}

export interface RecoveryCatalog {
  generatedAt: string
  apkPath: string
  runtimeTarget: string
  inventory: {
    extensions: Record<string, number>
    assetDirectories: Record<string, number>
    zt1Total: number
    webSafeAssetCount: number
  }
  featuredScripts: RecoveryScriptEntry[]
  blockedFormats: RecoveryBlockedFormat[]
  webSafeAssets: string[]
}
