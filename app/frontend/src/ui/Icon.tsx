import React from 'react';

export type IconName =
  | 'spark' | 'grid' | 'pulse' | 'play' | 'archive' | 'stack' | 'sliders'
  | 'sun' | 'moon' | 'monitor' | 'check' | 'x' | 'upload' | 'chevron'
  | 'target' | 'clock' | 'eye' | 'download' | 'refresh' | 'trash' | 'search'
  | 'arrow-right' | 'info' | 'warning' | 'users' | 'map' | 'glass';

const paths: Record<IconName, React.ReactNode> = {
  spark: <><path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><circle cx="12" cy="12" r="4.2"/><path d="M6.3 6.3l2.2 2.2M15.5 15.5l2.2 2.2M17.7 6.3l-2.2 2.2M8.5 15.5l-2.2 2.2"/></>,
  grid: <><rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/></>,
  pulse: <><path d="M3 12h4l2.2-6 4.1 12 2.4-6H21"/></>,
  play: <><circle cx="12" cy="12" r="8.5"/><path d="M10 8.6l5.4 3.4-5.4 3.4z" fill="currentColor" stroke="none"/></>,
  archive: <><rect x="3.5" y="5" width="17" height="4" rx="1.4"/><path d="M5 9v9.2A1.8 1.8 0 0 0 6.8 20h10.4a1.8 1.8 0 0 0 1.8-1.8V9"/><path d="M10 13h4"/></>,
  stack: <><path d="M12 3.5l8.5 4.4L12 12.3 3.5 7.9z"/><path d="M3.5 12.4l8.5 4.4 8.5-4.4M3.5 16.6l8.5 4.4 8.5-4.4"/></>,
  sliders: <><path d="M4 7h8M16 7h4M4 17h4M12 17h8"/><circle cx="14" cy="7" r="2.1"/><circle cx="10" cy="17" r="2.1"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.2 5.2l1.6 1.6M17.2 17.2l1.6 1.6M18.8 5.2l-1.6 1.6M6.8 17.2l-1.6 1.6"/></>,
  moon: <path d="M20 14.4A8.2 8.2 0 0 1 9.6 4a8.4 8.4 0 1 0 10.4 10.4z"/>,
  monitor: <><rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20h6M12 16.5V20"/></>,
  check: <path d="M4.5 12.5l4.6 4.6L19.5 6.7"/>,
  x: <path d="M6 6l12 12M18 6L6 18"/>,
  upload: <><path d="M12 16V4M7.5 8.5L12 4l4.5 4.5"/><path d="M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15"/></>,
  chevron: <path d="M6 9l6 6 6-6"/>,
  target: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></>,
  clock: <><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></>,
  eye: <><path d="M2.8 12s3.2-5.6 9.2-5.6 9.2 5.6 9.2 5.6-3.2 5.6-9.2 5.6S2.8 12 2.8 12z"/><circle cx="12" cy="12" r="2.8"/></>,
  download: <><path d="M12 4v12M7.5 11.5L12 16l4.5-4.5"/><path d="M4 17.5V19a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-1.5"/></>,
  refresh: <><path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v4.4h-4.4"/></>,
  trash: <><path d="M4 7h16M9.5 7V4.8h5V7M6.5 7l1 12.2h9L17.5 7"/><path d="M10.5 10.5v5M13.5 10.5v5"/></>,
  search: <><circle cx="10.8" cy="10.8" r="6.3"/><path d="M15.5 15.5L20 20"/></>,
  'arrow-right': <path d="M4 12h15M13 6l6 6-6 6"/>,
  info: <><circle cx="12" cy="12" r="8.6"/><path d="M12 10.5V17M12 7.4v.1"/></>,
  warning: <><path d="M12 3.6L21 19.5H3z"/><path d="M12 9v4.5M12 16.6v.1"/></>,
  users: <><circle cx="9" cy="8.4" r="3.4"/><path d="M2.8 20c.5-3.5 3-5.6 6.2-5.6s5.7 2.1 6.2 5.6"/><path d="M16.5 5.4a3 3 0 0 1 0 5.8M18 14.2c2.2.5 3.6 2.3 4 5"/></>,
  map: <><path d="M3 6.2l6-2.4 6 2.4 6-2.4V18l-6 2.4-6-2.4L3 18z"/><path d="M9 3.8V18M15 6.2V20.4"/></>,
  glass: <><path d="M7 3.5h10l-1 7.2a4 4 0 0 1-8 0z"/><path d="M12 14.5V20.5M8.5 20.5h7"/></>,
};

export default function Icon({name, size = 18, className}: {name: IconName; size?: number; className?: string}) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {paths[name]}
    </svg>
  );
}
