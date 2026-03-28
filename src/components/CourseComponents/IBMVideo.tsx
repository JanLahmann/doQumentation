import React, { useState, useEffect, useRef, useCallback } from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import BrowserOnly from '@docusaurus/BrowserOnly';

interface IBMVideoProps {
  id: string;
  title?: string;
}

interface VttCue {
  start: number; // seconds
  end: number;
  text: string;
}

/**
 * IBM Video ID → YouTube video ID mapping.
 * Sources: upstream content (explicit YouTube links) + Qiskit YouTube channel search.
 */
const YOUTUBE_MAP: Record<string, string> = {
  // Basics of Quantum Information — John Watrous
  '134056207': '3-c4xJa7Flk',
  '134627974': 'DfZZS8Spe7U',
  '134056224': '30U2DTfIrOU',
  '134056223': 'GSsElSQgMbU',
  // Fundamentals of Quantum Algorithms — John Watrous
  '134056222': '2wxxvwRGANQ',
  '134056235': '2wticzHE1vs',
  '134056243': 'hnpjC8WQVrQ',
  '134056217': '4nT0BTUxhJY',
  // General Formulation of Quantum Information — John Watrous
  '134056231': 'CeK9ry8G8HQ',
  '134063422': 'cMl-xIDSmXI',
  '134063423': 'Xi9YTYzQErY',
  '134063424': 'jemWEdnJTnI',
  // Foundations of Quantum Error Correction — John Watrous
  '134082557': 'OoQSdcKAIZc',
  '134212334': '3ib2JP_LeIU',
  '134313287': '9TCIOm8gcVQ',
  '134352398': 'aeaqXh2XXMk',
  // Quantum Computing in Practice — Olivia Lanes
  '134063425': 'sVRpKhCfKRI',
  '134063416': 'NTplT4WnNbk',
  '134063426': '33QmsXhIlpU',
  '134397390': 'BiKpHaev0XI',
  '134460549': '7cbNnxDHqeQ',
  '134063421': 'P3s7TIMIvZ0',
  // Quantum Mechanics modules — Katie McCormick
  '134413660': 'pcGIBacW-q0',
  '134413671': 'TZ-sUHK8vVQ',
  '134413665': 'pS69lqCMdy8',
  '134413662': '3h3pwrECbb8',
  // Computer Science modules — Katie McCormick
  '134413658': 'R0SOqLwLOR0',
  '134413680': 'jxqnzltpDdE',
  '134413695': 'QcK0GK7DUh8',
  // Quantum Diagonalization Algorithms — Chris Porter (found on Qiskit YouTube)
  '134325501': 'u53IyCR7sUM',
  '134325510': 'EAW8-LKalCE',
  '134325519': 'DUq-0r-Prw0',
};

/** Parse VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds. */
function parseTimestamp(ts: string): number {
  const parts = ts.trim().split(':');
  if (parts.length === 3) {
    return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
  }
  return parseFloat(parts[0]) * 60 + parseFloat(parts[1]);
}

/** Parse VTT content into cue list. */
function parseVtt(text: string): VttCue[] {
  const cues: VttCue[] = [];
  const blocks = text.trim().split(/\n\n+/);
  for (const block of blocks) {
    if (block.trim() === 'WEBVTT') continue;
    const lines = block.trim().split('\n');
    const tsLine = lines.find(l => l.includes('-->'));
    if (!tsLine) continue;
    const [startStr, endStr] = tsLine.split('-->');
    const tsIdx = lines.indexOf(tsLine);
    const text = lines.slice(tsIdx + 1).join(' ');
    cues.push({
      start: parseTimestamp(startStr),
      end: parseTimestamp(endStr),
      text,
    });
  }
  return cues;
}

/** Transcript panel shown below the video. */
function TranscriptPanel({
  cues,
  currentTime,
  onSeek,
}: {
  cues: VttCue[];
  currentTime: number;
  onSeek: (time: number) => void;
}) {
  const activeRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const activeIdx = cues.findIndex((c, i) => {
    const next = cues[i + 1];
    return currentTime >= c.start && (next ? currentTime < next.start : currentTime <= c.end);
  });

  useEffect(() => {
    if (activeRef.current && containerRef.current) {
      const container = containerRef.current;
      const el = activeRef.current;
      const top = el.offsetTop - container.offsetTop - container.clientHeight / 3;
      container.scrollTo({ top, behavior: 'smooth' });
    }
  }, [activeIdx]);

  return (
    <div
      ref={containerRef}
      style={{
        maxHeight: '200px',
        overflowY: 'auto',
        border: '1px solid var(--ifm-color-emphasis-300)',
        borderRadius: '0 0 8px 8px',
        padding: '0.5rem',
        fontSize: '0.85rem',
        lineHeight: '1.5',
        background: 'var(--ifm-background-surface-color)',
      }}
    >
      {cues.map((cue, i) => {
        const isActive = i === activeIdx;
        return (
          <div
            key={i}
            ref={isActive ? activeRef : undefined}
            onClick={() => onSeek(cue.start)}
            style={{
              padding: '0.25rem 0.5rem',
              borderRadius: '4px',
              cursor: 'pointer',
              background: isActive ? 'var(--ifm-color-primary-lightest)' : 'transparent',
              fontWeight: isActive ? 600 : 400,
              transition: 'background 0.2s',
            }}
          >
            <span style={{ color: 'var(--ifm-color-emphasis-500)', marginRight: '0.5rem', fontSize: '0.75rem' }}>
              {Math.floor(cue.start / 60)}:{String(Math.floor(cue.start % 60)).padStart(2, '0')}
            </span>
            {cue.text}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Renders an embedded video player for IBM Quantum course content,
 * with an optional synced transcript panel below.
 */
export default function IBMVideo({ id, title }: IBMVideoProps) {
  return (
    <BrowserOnly>
      {() => <IBMVideoInner id={id} title={title} />}
    </BrowserOnly>
  );
}

declare global {
  interface Window {
    YT?: {
      Player: new (el: HTMLElement, config: Record<string, unknown>) => YTPlayer;
    };
    onYouTubeIframeAPIReady?: () => void;
  }
}

interface YTPlayer {
  getCurrentTime: () => number;
  seekTo: (seconds: number, allowSeekAhead: boolean) => void;
  destroy: () => void;
}

function IBMVideoInner({ id, title }: IBMVideoProps) {
  const { i18n: { currentLocale } } = useDocusaurusContext();
  const youtubeId = YOUTUBE_MAP[id];
  const [cues, setCues] = useState<VttCue[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const playerRef = useRef<YTPlayer | null>(null);
  const playerElRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<number | null>(null);

  // Load transcript VTT
  useEffect(() => {
    const locale = currentLocale || 'en';
    const tryLocales = locale === 'en' ? ['en'] : [locale, 'en'];

    (async () => {
      for (const loc of tryLocales) {
        try {
          const resp = await fetch(`/transcripts/${id}/${loc}.vtt`);
          if (resp.ok) {
            const text = await resp.text();
            const parsed = parseVtt(text);
            if (parsed.length > 0) {
              setCues(parsed);
              return;
            }
          }
        } catch { /* try next */ }
      }
    })();
  }, [id, currentLocale]);

  // YouTube IFrame API setup
  useEffect(() => {
    if (!youtubeId || cues.length === 0) return;

    const loadApi = () => {
      if (window.YT) {
        createPlayer();
        return;
      }
      const existing = document.querySelector('script[src*="youtube.com/iframe_api"]');
      if (!existing) {
        const tag = document.createElement('script');
        tag.src = 'https://www.youtube.com/iframe_api';
        document.head.appendChild(tag);
      }
      window.onYouTubeIframeAPIReady = createPlayer;
    };

    const createPlayer = () => {
      if (!playerElRef.current || playerRef.current) return;
      const params: Record<string, string> = { hl: currentLocale };
      if (currentLocale !== 'en') {
        params.cc_load_policy = '1';
        params.cc_lang_pref = currentLocale;
      }
      playerRef.current = new window.YT!.Player(playerElRef.current, {
        videoId: youtubeId,
        playerVars: {
          ...params,
          rel: '0',
          modestbranding: '1',
        },
        events: {
          onReady: () => {
            // Poll current time for transcript sync
            timerRef.current = window.setInterval(() => {
              if (playerRef.current) {
                setCurrentTime(playerRef.current.getCurrentTime());
              }
            }, 250);
          },
        },
      } as Record<string, unknown>);
    };

    loadApi();

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (playerRef.current) {
        try { playerRef.current.destroy(); } catch { /* ignore */ }
        playerRef.current = null;
      }
    };
  }, [youtubeId, cues.length, currentLocale]);

  const handleSeek = useCallback((time: number) => {
    if (playerRef.current) {
      playerRef.current.seekTo(time, true);
      setCurrentTime(time);
    }
  }, []);

  // YouTube with transcript: use IFrame API
  if (youtubeId && cues.length > 0) {
    return (
      <div style={{ margin: '1rem 0' }}>
        <div style={{
          position: 'relative',
          paddingBottom: '56.25%',
          height: 0,
          overflow: 'hidden',
          borderRadius: '8px 8px 0 0',
        }}>
          <div
            ref={playerElRef}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
            }}
          />
        </div>
        <TranscriptPanel cues={cues} currentTime={currentTime} onSeek={handleSeek} />
      </div>
    );
  }

  // Fallback: regular iframe (no transcript or IBM Video)
  let iframeSrc: string;
  if (youtubeId) {
    const params = new URLSearchParams({ hl: currentLocale });
    if (currentLocale !== 'en') {
      params.set('cc_load_policy', '1');
      params.set('cc_lang_pref', currentLocale);
    }
    iframeSrc = `https://www.youtube-nocookie.com/embed/${youtubeId}?${params}`;
  } else {
    iframeSrc = `https://video.ibm.com/embed/recorded/${id}`;
  }

  return (
    <div style={{ margin: '1rem 0' }}>
      <div
        style={{
          position: 'relative',
          paddingBottom: '56.25%',
          height: 0,
          overflow: 'hidden',
          borderRadius: cues.length > 0 ? '8px 8px 0 0' : '8px',
        }}
      >
        <iframe
          src={iframeSrc}
          title={title || 'Video'}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            border: 0,
          }}
          allowFullScreen
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          loading="lazy"
        />
      </div>
      {cues.length > 0 && (
        <TranscriptPanel cues={cues} currentTime={currentTime} onSeek={() => {}} />
      )}
    </div>
  );
}
