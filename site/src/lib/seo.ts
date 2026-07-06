export const SITE = {
  name: "mediaskills",
  title: "mediaskills — Agent Skills for Media",
  description:
    "Open-source Agent Skills for video, audio, captions, timecode, and broadcast workflows. Search 13 skills, 80+ operations, and end-to-end cookbooks for AI agents.",
  url: "https://mediaskills.ai",
  repo: "https://github.com/timelapsetech/mediaskills",
  twitter: "@timelapsetech",
  ogImage: "/og-image.svg",
  sponsor: {
    name: "Time Lapse Technologies",
    url: "https://timelapsetech.com",
  },
} as const;

export function pageTitle(segment?: string): string {
  if (!segment) return SITE.title;
  return `${segment} · mediaskills`;
}

export function canonical(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${SITE.url}${normalized}${normalized.endsWith("/") ? "" : "/"}`;
}

export function jsonLd(data: Record<string, unknown>): string {
  return JSON.stringify(data);
}
