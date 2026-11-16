import type { LinkedIssue } from '@freemocap/skellydocs';
export type { LinkedIssue };

export type OsType = 'windows' | 'macos' | 'linux';
export type ArchType = 'x64' | 'arm64';

export interface DownloadEntry {
  os: OsType;
  arch: ArchType;
  fmt: string;
  recommended: boolean;
  label: string;
  file: string;
  size: string;
}

export interface OsNoteEntry {
  os: OsType;
  arch?: ArchType;
  variant: 'warning' | 'info' | 'tip';
  title: string;
  content: string;
  issues?: LinkedIssue[];
}

export interface GitHubAsset {
  name: string;
  size: number;
  browser_download_url: string;
}

export interface GitHubRelease {
  tag_name: string;
  name: string;
  published_at: string;
  assets: GitHubAsset[];
  prerelease: boolean;
}

export const DEFAULT_VERSION = '2.0.0-alpha.6';
export const REPO = 'freemocap/freemocap';

export function getReleaseBaseUrl(version: string): string {
  return `https://github.com/${REPO}/releases/download/v${version}`;
}

export function downloadUrl(file: string, version: string): string {
  return `${getReleaseBaseUrl(version)}/${file}`;
}

// Filenames mirror the release job's naming in
// .github/workflows/build-installers-pyinstaller.yml exactly:
//   freemocap_<version>_<matrix.label>.<ext>
// matrix.label is windows-x64-cpu | macos-arm64-apple-silicon | linux-x64-cpu. The "-cpu"
// suffix is historical (installed apps auto-update by these names); every build uses CPU
// onnxruntime and gets GPU execution providers from skellytracker's EP packs at runtime.
// There is deliberately no macos-x64-intel or linux-arm64 entry here — CI doesn't
// build either yet (see OS_NOTES below for why, and the linked tracking issues).
export function buildAppDownloads(version: string): DownloadEntry[] {
  return [
    { os: 'windows', arch: 'x64', fmt: 'exe', recommended: true, label: 'Windows Installer', file: `freemocap_${version}_windows-x64-cpu.exe`, size: '' },

    { os: 'macos', arch: 'arm64', fmt: 'dmg', recommended: true,  label: 'macOS Installer (Apple Silicon)', file: `freemocap_${version}_macos-arm64-apple-silicon.dmg`, size: '' },
    { os: 'macos', arch: 'arm64', fmt: 'zip', recommended: false, label: 'macOS Portable (Apple Silicon)',  file: `freemocap_${version}_macos-arm64-apple-silicon.zip`, size: '' },

    { os: 'linux', arch: 'x64', fmt: 'AppImage', recommended: true,  label: 'Linux AppImage', file: `freemocap_${version}_linux-x64-cpu.AppImage`, size: '' },
    { os: 'linux', arch: 'x64', fmt: 'deb',      recommended: false, label: 'Linux .deb',     file: `freemocap_${version}_linux-x64-cpu.deb`,      size: '' },
  ];
}

// Server binaries always ship as .zip: PyInstaller's onedir output is the exe
// plus a required _internal/ support directory, so it can never be a lone file.
export function buildServerDownloads(version: string): DownloadEntry[] {
  return [
    { os: 'windows', arch: 'x64',   fmt: 'zip', recommended: false, label: 'Server — Windows x64',         file: `freemocap_server_${version}_windows-x64-cpu.zip`,           size: '' },
    { os: 'macos',   arch: 'arm64', fmt: 'zip', recommended: false, label: 'Server — macOS Apple Silicon', file: `freemocap_server_${version}_macos-arm64-apple-silicon.zip`, size: '' },
    { os: 'linux',   arch: 'x64',   fmt: 'zip', recommended: false, label: 'Server — Linux x64',           file: `freemocap_server_${version}_linux-x64-cpu.zip`,             size: '' },
  ];
}

export function formatBytes(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return `~${Math.round(mb)} MB`;
}

export function enrichDownloadsWithAssets(
  downloads: DownloadEntry[],
  assets: GitHubAsset[],
): DownloadEntry[] {
  const assetMap = new Map(assets.map(a => [a.name, a]));
  return downloads.map(d => {
    const asset = assetMap.get(d.file);
    return asset ? { ...d, size: formatBytes(asset.size) } : d;
  });
}

/** Check if a release's assets match our expected filename patterns */
export function matchesExpectedPattern(assets: GitHubAsset[], version: string): boolean {
  const expectedFiles = [
    ...buildAppDownloads(version).map(d => d.file),
    ...buildServerDownloads(version).map(d => d.file),
  ];
  const assetNames = new Set(assets.map(a => a.name));
  // Consider it a match if at least 3 of our expected files exist
  const matchCount = expectedFiles.filter(f => assetNames.has(f)).length;
  return matchCount >= 3;
}

// Only ever called for buildable combos (windows-x64, macos-arm64, linux-x64) —
// callers gate unbuilt platforms (macos-x64, linux-arm64) before reaching here.
export function fileLabel(os: OsType): string {
  if (os === 'macos') return 'macos-arm64-apple-silicon';
  return os === 'linux' ? 'linux-x64-cpu' : 'windows-x64-cpu';
}

export function formatMeta(d: DownloadEntry): string {
  const parts = [d.fmt.toUpperCase()];
  if (d.os !== 'windows') parts.push(d.arch === 'arm64' ? 'ARM64' : 'x64');
  return parts.join(' · ');
}

export const OS_LABELS: Record<string, string> = {
  windows: 'Windows x64',
  macos: 'macOS',
  linux: 'Linux',
  unknown: 'Unknown OS',
};

export function archLabel(arch: ArchType): string {
  return arch === 'arm64' ? 'ARM64 / Apple Silicon' : 'x64 / Intel';
}

export function stripVersionPrefix(tag: string): string {
  return tag.replace(/^v/, '');
}

// Per-OS/arch advisories shown above the download cards for the matching system.
// Add FreeMoCap-specific notes here (platform caveats, known issues, help wanted).
export const OS_NOTES: OsNoteEntry[] = [
  {
    os: 'macos',
    arch: 'x64',
    variant: 'warning',
    title: 'Intel Mac builds aren’t available yet',
    content:
      'FreeMoCap’s pose-tracking backend (onnxruntime, via skellytracker) doesn’t currently publish a macOS x86_64 wheel, so we can’t build for Intel Macs yet. If you’re on Apple Silicon, select that option above instead.',
    issues: [
      {
        label: 'Add macOS Intel (x86_64) installer build',
        url: 'https://github.com/freemocap/freemocap/issues/823',
      },
    ],
  },
  {
    os: 'linux',
    arch: 'arm64',
    variant: 'warning',
    title: 'Linux ARM64 builds aren’t available',
    content:
      'We can’t build a Linux ARM64 release (e.g. for Raspberry Pi) yet: mediapipe — a core dependency of the pose-tracking backend — ships no linux-aarch64 wheel, so the build is unsatisfiable on that platform. It’ll stay unavailable until mediapipe publishes ARM64 Linux wheels.',
    issues: [
      {
        label: 'Add Linux ARM64 installer build',
        url: 'https://github.com/freemocap/freemocap/issues/822',
      },
    ],
  },
];

export const OS_PILL_OPTIONS = [
  { os: 'windows' as OsType, arch: 'x64' as ArchType, label: 'Windows' },
  { os: 'macos' as OsType, arch: 'arm64' as ArchType, label: 'Mac (Apple Silicon)' },
  { os: 'macos' as OsType, arch: 'x64' as ArchType, label: 'Mac (Intel)' },
  { os: 'linux' as OsType, arch: 'x64' as ArchType, label: 'Linux x64' },
  { os: 'linux' as OsType, arch: 'arm64' as ArchType, label: 'Linux ARM64' },
] as const;
