/** Mirror of archivetools/gui/constants.py:ARCHIVE_FORMATS */
export interface ArchiveFormat {
  label: string;
  key: string;
  ext: string;
  supportsPassword: boolean;
}

export const ARCHIVE_FORMATS: ArchiveFormat[] = [
  {
    label: "ZIP (no password)",
    key: "zip",
    ext: ".zip",
    supportsPassword: false,
  },
  {
    label: "ZIP (AES-256 encrypted)",
    key: "zip-aes",
    ext: ".zip",
    supportsPassword: true,
  },
  { label: "7z", key: "7z", ext: ".7z", supportsPassword: true },
  { label: "TAR (.tar)", key: "tar", ext: ".tar", supportsPassword: false },
  {
    label: "TAR.GZ (.tar.gz)",
    key: "tar.gz",
    ext: ".tar.gz",
    supportsPassword: false,
  },
  {
    label: "TAR.BZ2 (.tar.bz2)",
    key: "tar.bz2",
    ext: ".tar.bz2",
    supportsPassword: false,
  },
  {
    label: "TAR.XZ (.tar.xz)",
    key: "tar.xz",
    ext: ".tar.xz",
    supportsPassword: false,
  },
];

export const ARCHIVE_EXTENSIONS = [
  "zip",
  "rar",
  "7z",
  "z01",
  "r00",
  "r01",
  "001",
  "tar",
  "tar.gz",
  "tgz",
  "tar.bz2",
  "tar.xz",
];

export const NAV_RECENT = 0;
export const NAV_EXTRACT = 1;
export const NAV_CREATE = 2;
export const NAV_BATCH = 3;
export const NAV_CONVERT = 4;

/** Format bytes as human-readable string (B / KB / MB / GB / TB) */
export function formatBytes(bytes: number): string {
  if (bytes < 0) return "?";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  if (bytes < 1024 ** 4) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  return `${(bytes / 1024 ** 4).toFixed(1)} TB`;
}

/** Format a Date as relative time string ("5m ago", "Yesterday", etc.) */
export function relativeTime(date: Date): string {
  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString();
}
