/**
 * PodMonitor — live status display for CE workshop pods.
 *
 * Polls each pod's /stats endpoint every 5s, interprets the numbers as a
 * health status (healthy/stressed/saturated/down), and shows compact cards
 * with progress bars + sparklines (15-min trailing window).
 *
 * Designed for workshop instructors to make real-time decisions:
 *   - "Is the pod healthy?" → color badge
 *   - "What's the trend?" → sparklines
 *   - "What should I do?" → human-readable recommendation
 *
 * Capacity heuristics derived from actual stress test data:
 *   - peak_conn ceiling ≈ 6 sessions per vCPU (validated 1, 4, 8, 12 vCPU)
 *   - Memory usually NOT the constraint for 5-qubit workloads (max ~44%)
 *   - 1-min load > cpu_count = oversaturated (loads of 14+ on 4 vCPU = bad)
 *
 * /stats is unauthenticated (nginx routes it directly), so no token needed.
 * CORS is whitelisted to https://doqumentation.org in the SSE shim.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { getWorkshopPool } from '@site/src/config/jupyter';

// ─────────────────────────── types ───────────────────────────

interface PodStats {
  kernels: number;
  kernels_busy: number;
  connections: number;
  memory_mb: number | null;
  memory_total_mb: number | null;
  load_1m: number | null;
  load_5m: number | null;
  load_15m: number | null;
  cpu_count: number | null;
  peak_kernels: number;
  peak_connections: number;
  total_sse_connections: number;
  uptime_seconds: number;
  status: 'ready' | 'unavailable' | string;
}

type Health = 'healthy' | 'stressed' | 'saturated' | 'down' | 'loading';

interface HealthInterpretation {
  health: Health;
  reason: string;
  recommendation: string | null;
  driver: 'kernels' | 'memory' | 'load' | 'connections' | 'none';
}

interface HistoryEntry {
  ts: number;
  stats: PodStats;
}

// ─────────────────────────── constants ───────────────────────────

const POLL_INTERVAL_MS = 5000;
const HISTORY_SIZE = 180; // 15 min at 5s polling
const FETCH_TIMEOUT_MS = 3000;
const SESSIONS_PER_VCPU = 6; // From stress test data
const TIMER_STEP_MS = 15 * 60 * 1000; // 15 min per step
const TIMER_MAX_MS = 5 * 60 * 60 * 1000; // 5h max

// ─────────────────────────── health interpretation ───────────────────────────

function interpretHealth(stats: PodStats | null, fetchError: boolean): HealthInterpretation {
  if (fetchError) {
    return {
      health: 'down',
      reason: 'unreachable',
      driver: 'none',
      recommendation:
        'Pod unreachable. Cold-start in progress (typical 15-150s) or pod crashed. ' +
        'First user click in the next 5-10 min should auto-trigger a restart.',
    };
  }
  if (!stats) {
    return { health: 'loading', reason: 'loading', driver: 'none', recommendation: null };
  }

  // Estimated capacity from stress test data
  const cpuCount = stats.cpu_count ?? 1;
  const estimatedKernelCapacity = cpuCount * SESSIONS_PER_VCPU;

  const kernelPct = stats.kernels / estimatedKernelCapacity;
  const memPct =
    stats.memory_mb != null && stats.memory_total_mb && stats.memory_total_mb > 0
      ? stats.memory_mb / stats.memory_total_mb
      : 0;
  const loadPct = stats.load_1m != null && cpuCount > 0 ? stats.load_1m / cpuCount : 0;

  // Find the worst signal — that's the dominant one
  type Signal = { name: HealthInterpretation['driver']; value: number };
  const signals: Signal[] = [
    { name: 'kernels', value: kernelPct },
    { name: 'memory', value: memPct },
    { name: 'load', value: loadPct },
  ];
  signals.sort((a, b) => b.value - a.value);
  const worst = signals[0];

  // Saturated: any signal > 0.8 (kernels/memory) or > 1.0 (load)
  const saturated =
    kernelPct > 0.8 || memPct > 0.8 || loadPct > 1.0;
  const stressed =
    kernelPct > 0.5 || memPct > 0.5 || loadPct > 0.5;

  if (saturated) {
    let recommendation: string;
    switch (worst.name) {
      case 'kernels':
        recommendation =
          `Kernels at ${Math.round(kernelPct * 100)}% of estimated capacity ` +
          `(${stats.kernels}/${estimatedKernelCapacity}). New connections may start ` +
          `failing soon. Consider restarting between sections, or add another instance.`;
        break;
      case 'memory':
        recommendation =
          `Memory at ${Math.round(memPct * 100)}% (${stats.memory_mb}/${stats.memory_total_mb} MB). ` +
          `OOM kill risk. Restart pod ASAP between sections, or escalate pod size.`;
        break;
      case 'load':
        recommendation =
          `CPU load ${stats.load_1m?.toFixed(1)} on ${cpuCount} cores ` +
          `(${Math.round(loadPct * 100)}% saturation). Many simultaneous executions. ` +
          `Latency will be visible to users. Ask participants to space out cell runs.`;
        break;
      default:
        recommendation = 'Pod saturated.';
    }
    return { health: 'saturated', reason: worst.name, driver: worst.name, recommendation };
  }

  if (stressed) {
    let recommendation: string;
    switch (worst.name) {
      case 'kernels':
        recommendation =
          `${stats.kernels} kernels active out of ~${estimatedKernelCapacity} capacity. ` +
          `Comfortable for now but watch for growth.`;
        break;
      case 'memory':
        recommendation =
          `Memory at ${Math.round(memPct * 100)}%. ` +
          `Workshop should still work but advanced cells may slow down.`;
        break;
      case 'load':
        recommendation =
          `CPU load at ${Math.round(loadPct * 100)}% of capacity. ` +
          `New users may see slight delays during cell execution.`;
        break;
      default:
        recommendation = 'Pod stressed.';
    }
    return { health: 'stressed', reason: worst.name, driver: worst.name, recommendation };
  }

  return {
    health: 'healthy',
    reason: 'all signals nominal',
    driver: 'none',
    recommendation: null,
  };
}

// ─────────────────────────── sparkline ───────────────────────────

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  threshold?: number; // optional horizontal line at this value
  thresholdColor?: string;
  color?: string;
}

function Sparkline({
  values,
  width = 80,
  height = 24,
  threshold,
  thresholdColor = 'var(--ifm-color-warning)',
  color = 'currentColor',
}: SparklineProps) {
  // Filter out null/undefined defensively
  const clean = values.filter((v) => v != null && Number.isFinite(v));
  if (clean.length < 2) {
    return (
      <span
        style={{
          display: 'inline-block',
          width,
          height,
          opacity: 0.3,
          fontSize: '0.75rem',
          textAlign: 'center',
          lineHeight: `${height}px`,
        }}
      >
        {clean.length === 1 ? '·' : '⋯'}
      </span>
    );
  }
  const min = Math.min(...clean, threshold ?? Infinity);
  const max = Math.max(...clean, threshold ?? -Infinity);
  const range = max - min || 1;
  const points = clean
    .map((v, i) => {
      const x = (i / (clean.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 2) - 1;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  // Threshold line position
  let thresholdY: number | null = null;
  if (threshold != null && threshold >= min && threshold <= max) {
    thresholdY = height - ((threshold - min) / range) * (height - 2) - 1;
  }

  return (
    <svg
      width={width}
      height={height}
      style={{ verticalAlign: 'middle', display: 'inline-block' }}
      aria-hidden="true"
    >
      {thresholdY != null && (
        <line
          x1={0}
          y1={thresholdY}
          x2={width}
          y2={thresholdY}
          stroke={thresholdColor}
          strokeWidth={1}
          strokeDasharray="2,2"
          opacity={0.5}
        />
      )}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* Dot at the most recent value */}
      <circle
        cx={width}
        cy={height - ((clean[clean.length - 1] - min) / range) * (height - 2) - 1}
        r={1.5}
        fill={color}
      />
    </svg>
  );
}

// ─────────────────────────── progress bar ───────────────────────────

function ProgressBar({
  value,
  max,
  color,
  width = 120,
}: {
  value: number;
  max: number;
  color: string;
  width?: number;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <span
      style={{
        display: 'inline-block',
        width,
        height: 8,
        background: 'var(--ifm-color-emphasis-200)',
        borderRadius: 4,
        overflow: 'hidden',
        verticalAlign: 'middle',
      }}
    >
      <span
        style={{
          display: 'block',
          width: `${pct}%`,
          height: '100%',
          background: color,
          transition: 'width 0.5s ease-out',
        }}
      />
    </span>
  );
}

// ─────────────────────────── health badge ───────────────────────────

const HEALTH_COLORS: Record<Health, { fg: string; bg: string; label: string; icon: string }> = {
  healthy: {
    fg: '#0a6e0a',
    bg: '#d4f4d4',
    label: 'healthy',
    icon: '●',
  },
  stressed: {
    fg: '#8a5a00',
    bg: '#fff4d6',
    label: 'stressed',
    icon: '⚠',
  },
  saturated: {
    fg: '#9e2a00',
    bg: '#ffd6c0',
    label: 'saturated',
    icon: '✗',
  },
  down: {
    fg: '#7a0000',
    bg: '#ffc4c4',
    label: 'unreachable',
    icon: '⛔',
  },
  loading: {
    fg: '#555',
    bg: '#eee',
    label: 'loading…',
    icon: '○',
  },
};

function HealthBadge({ health }: { health: Health }) {
  const c = HEALTH_COLORS[health];
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 12,
        fontSize: '0.75rem',
        fontWeight: 600,
        color: c.fg,
        background: c.bg,
        verticalAlign: 'middle',
      }}
    >
      {c.icon} {c.label}
    </span>
  );
}

// ─────────────────────────── pod card ───────────────────────────

function shortName(url: string): string {
  // https://ce-doqumentation-01.27boe8ie8nv4.eu-de.codeengine.appdomain.cloud → ce-doqumentation-01
  try {
    const u = new URL(url);
    return u.hostname.split('.')[0];
  } catch {
    return url.replace(/^https?:\/\//, '').split('.')[0];
  }
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

interface PodCardProps {
  url: string;
  paused: boolean;
}

function PodCard({ url, paused }: PodCardProps) {
  const [stats, setStats] = useState<PodStats | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [fetchError, setFetchError] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
      const r = await fetch(`${url.replace(/\/+$/, '')}/stats`, {
        signal: ctrl.signal,
      });
      clearTimeout(timer);
      if (r.ok) {
        const data: PodStats = await r.json();
        setStats(data);
        setFetchError(false);
        setLastUpdate(new Date());
        setHistory((prev) => {
          const next = [...prev, { ts: Date.now(), stats: data }];
          return next.length > HISTORY_SIZE ? next.slice(-HISTORY_SIZE) : next;
        });
      } else {
        setFetchError(true);
      }
    } catch {
      setFetchError(true);
    }
  }, [url]);

  useEffect(() => {
    if (paused) return;
    fetchStats();
    const id = setInterval(fetchStats, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [paused, fetchStats]);

  const interp = interpretHealth(stats, fetchError);
  const cardBorderColor = (() => {
    switch (interp.health) {
      case 'healthy':
        return 'var(--ifm-color-success-light)';
      case 'stressed':
        return 'var(--ifm-color-warning)';
      case 'saturated':
        return 'var(--ifm-color-danger)';
      case 'down':
        return 'var(--ifm-color-danger-dark)';
      default:
        return 'var(--ifm-color-emphasis-300)';
    }
  })();

  // Derived values for display
  const cpuCount = stats?.cpu_count ?? 1;
  const estimatedKernelCapacity = Math.round(cpuCount * SESSIONS_PER_VCPU);
  const memPct =
    stats?.memory_mb != null && stats?.memory_total_mb
      ? (stats.memory_mb / stats.memory_total_mb) * 100
      : 0;
  const loadPct = stats?.load_1m != null && cpuCount ? (stats.load_1m / cpuCount) * 100 : 0;

  // Sparkline data
  const memSeries = history.map((h) => h.stats.memory_mb ?? 0);
  const kernelSeries = history.map((h) => h.stats.kernels);
  const loadSeries = history.map((h) => h.stats.load_1m ?? 0);
  const connSeries = history.map((h) => h.stats.connections);

  return (
    <div
      style={{
        border: `2px solid ${cardBorderColor}`,
        borderRadius: 8,
        padding: '1rem 1.25rem',
        marginBottom: '1rem',
        background: 'var(--ifm-background-surface-color)',
        transition: 'border-color 0.3s',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '0.75rem',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <strong style={{ fontSize: '1rem' }}>{shortName(url)}</strong>
          <HealthBadge health={interp.health} />
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--ifm-color-emphasis-600)' }}>
          {stats?.cpu_count != null && (
            <span>
              {stats.cpu_count} vCPU / {Math.round((stats.memory_total_mb ?? 0) / 1024)} GB ·{' '}
            </span>
          )}
          {stats?.uptime_seconds != null && <span>up {formatUptime(stats.uptime_seconds)} · </span>}
          {lastUpdate && <span>updated {lastUpdate.toLocaleTimeString()}</span>}
        </div>
      </div>

      {stats && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'auto 1fr auto auto',
            gap: '0.5rem 0.75rem',
            alignItems: 'center',
            fontSize: '0.85rem',
            fontFamily: 'var(--ifm-font-family-monospace)',
          }}
        >
          {/* Kernels row */}
          <span style={{ color: 'var(--ifm-color-emphasis-700)' }}>Kernels:</span>
          <ProgressBar
            value={stats.kernels}
            max={estimatedKernelCapacity}
            color={stats.kernels / estimatedKernelCapacity > 0.8 ? '#e74c3c' : stats.kernels / estimatedKernelCapacity > 0.5 ? '#f39c12' : '#27ae60'}
          />
          <span>
            <strong>{stats.kernels}</strong> / ~{estimatedKernelCapacity}
            {stats.kernels_busy > 0 && <span style={{ opacity: 0.6 }}> ({stats.kernels_busy} busy)</span>}
          </span>
          <Sparkline
            values={kernelSeries}
            color="var(--ifm-color-emphasis-700)"
            threshold={estimatedKernelCapacity * 0.8}
          />

          {/* Memory row */}
          <span style={{ color: 'var(--ifm-color-emphasis-700)' }}>Memory:</span>
          <ProgressBar
            value={memPct}
            max={100}
            color={memPct > 80 ? '#e74c3c' : memPct > 50 ? '#f39c12' : '#27ae60'}
          />
          <span>
            <strong>{Math.round(memPct)}%</strong>
            <span style={{ opacity: 0.6 }}>
              {' '}
              ({stats.memory_mb} / {stats.memory_total_mb} MB)
            </span>
          </span>
          <Sparkline values={memSeries} color="var(--ifm-color-emphasis-700)" />

          {/* CPU load row */}
          <span style={{ color: 'var(--ifm-color-emphasis-700)' }}>CPU load:</span>
          <ProgressBar
            value={loadPct}
            max={100}
            color={loadPct > 100 ? '#e74c3c' : loadPct > 50 ? '#f39c12' : '#27ae60'}
          />
          <span>
            <strong>{stats.load_1m?.toFixed(2) ?? '?'}</strong>
            <span style={{ opacity: 0.6 }}> / {cpuCount} cores</span>
          </span>
          <Sparkline
            values={loadSeries}
            color="var(--ifm-color-emphasis-700)"
            threshold={cpuCount}
          />

          {/* Connections row */}
          <span style={{ color: 'var(--ifm-color-emphasis-700)' }}>Connections:</span>
          <ProgressBar
            value={stats.connections}
            max={Math.max(estimatedKernelCapacity, stats.peak_connections, 1)}
            color="#3498db"
          />
          <span>
            <strong>{stats.connections}</strong>
            <span style={{ opacity: 0.6 }}>
              {' '}
              (peak {stats.peak_connections}, total {stats.total_sse_connections})
            </span>
          </span>
          <Sparkline values={connSeries} color="var(--ifm-color-emphasis-700)" />
        </div>
      )}

      {interp.recommendation && (
        <div
          style={{
            marginTop: '0.75rem',
            padding: '0.5rem 0.75rem',
            borderRadius: 4,
            background: HEALTH_COLORS[interp.health].bg,
            color: HEALTH_COLORS[interp.health].fg,
            fontSize: '0.85rem',
            lineHeight: 1.4,
          }}
        >
          <strong>{HEALTH_COLORS[interp.health].icon} </strong>
          {interp.recommendation}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────── top-level component ───────────────────────────

function formatTimeRemaining(ms: number): string {
  if (ms <= 0) return '0:00';
  const totalSec = Math.ceil(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

export default function PodMonitor() {
  const [pool, setPool] = useState<string[] | null>(null);
  const [manualUrl, setManualUrl] = useState('');
  const [manualUrls, setManualUrls] = useState<string[]>([]);

  // Timer-based polling: starts at 15 min, extendable in 15 min steps up to 5h
  const [timerEnd, setTimerEnd] = useState<number | null>(null); // null = not started
  const [remaining, setRemaining] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Derived: polling is active when timer is running and has time left
  const paused = timerEnd == null || remaining <= 0;

  // Start the countdown ticker
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (timerEnd == null) { setRemaining(0); return; }
    const tick = () => {
      const left = Math.max(0, timerEnd - Date.now());
      setRemaining(left);
      if (left <= 0 && timerRef.current) clearInterval(timerRef.current);
    };
    tick();
    timerRef.current = setInterval(tick, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [timerEnd]);

  const startTimer = useCallback(() => {
    setTimerEnd(Date.now() + TIMER_STEP_MS);
  }, []);

  const extendTimer = useCallback(() => {
    setTimerEnd((prev) => {
      const base = prev && prev > Date.now() ? prev : Date.now();
      const newEnd = base + TIMER_STEP_MS;
      const maxEnd = Date.now() + TIMER_MAX_MS;
      return Math.min(newEnd, maxEnd);
    });
  }, []);

  const stopTimer = useCallback(() => {
    setTimerEnd(null);
  }, []);

  // Read workshop pool from localStorage on mount
  useEffect(() => {
    const wsPool = getWorkshopPool();
    if (wsPool && wsPool.pool.length > 0) {
      setPool(wsPool.pool);
    }
  }, []);

  const allUrls = pool ?? manualUrls;
  const hasUrls = allUrls.length > 0;

  const handleAddManual = () => {
    const trimmed = manualUrl.trim().replace(/\/+$/, '');
    if (!trimmed) return;
    if (!/^https?:\/\//i.test(trimmed)) {
      // eslint-disable-next-line no-alert
      alert('URL must start with https:// or http://');
      return;
    }
    if (manualUrls.includes(trimmed)) {
      setManualUrl('');
      return;
    }
    setManualUrls([...manualUrls, trimmed]);
    setManualUrl('');
  };

  const handleRemoveManual = (url: string) => {
    setManualUrls(manualUrls.filter((u) => u !== url));
  };

  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '0.75rem',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div style={{ fontSize: '0.85rem', color: 'var(--ifm-color-emphasis-600)' }}>
          {pool
            ? `Monitoring ${pool.length} pod${pool.length === 1 ? '' : 's'} from configured workshop pool.`
            : manualUrls.length > 0
              ? `Monitoring ${manualUrls.length} manually-entered pod${manualUrls.length === 1 ? '' : 's'}.`
              : 'No workshop pool configured.'}{' '}
          {hasUrls && (
            <span>
              {paused
                ? 'Polling paused. Click Start to begin monitoring (auto-stops after 15 min to prevent keeping the pod alive).'
                : `Polling every ${POLL_INTERVAL_MS / 1000}s. Sparklines show last ${Math.round((HISTORY_SIZE * POLL_INTERVAL_MS) / 60000)} min.`}
            </span>
          )}
        </div>
        {hasUrls && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {paused ? (
              <button
                type="button"
                onClick={timerEnd == null || remaining <= 0 ? startTimer : startTimer}
                style={{
                  padding: '0.25rem 0.75rem',
                  fontSize: '0.85rem',
                  background: 'var(--ifm-color-success)',
                  color: 'white',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                ▶ Start (15 min)
              </button>
            ) : (
              <>
                <span style={{ fontSize: '0.85rem', fontFamily: 'var(--ifm-font-family-monospace)', fontWeight: 600 }}>
                  {formatTimeRemaining(remaining)}
                </span>
                <button
                  type="button"
                  onClick={extendTimer}
                  title="Extend polling by 15 min (max 5h total)"
                  style={{
                    padding: '0.25rem 0.75rem',
                    fontSize: '0.85rem',
                    background: 'var(--ifm-color-emphasis-200)',
                    color: 'var(--ifm-color-emphasis-800)',
                    border: 'none',
                    borderRadius: 4,
                    cursor: 'pointer',
                  }}
                >
                  +15 min
                </button>
                <button
                  type="button"
                  onClick={stopTimer}
                  style={{
                    padding: '0.25rem 0.75rem',
                    fontSize: '0.85rem',
                    background: 'var(--ifm-color-emphasis-200)',
                    color: 'var(--ifm-color-emphasis-800)',
                    border: 'none',
                    borderRadius: 4,
                    cursor: 'pointer',
                  }}
                >
                  ⏸ Stop
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {hasUrls && allUrls.map((url) => <PodCard key={url} url={url} paused={paused} />)}

      {!pool && (
        <div
          style={{
            marginTop: '0.5rem',
            padding: '0.75rem 1rem',
            border: '1px dashed var(--ifm-color-emphasis-300)',
            borderRadius: 4,
            fontSize: '0.85rem',
            background: 'var(--ifm-color-emphasis-100)',
          }}
        >
          <div style={{ marginBottom: '0.5rem', color: 'var(--ifm-color-emphasis-700)' }}>
            {manualUrls.length === 0 ? (
              <>
                <strong>No workshop pool configured.</strong> Either configure one in{' '}
                <a href="/jupyter-settings#code-engine">Settings → Code Engine</a>, or paste a CE
                URL below to monitor a single pod.
              </>
            ) : (
              <>Add another CE URL to monitor:</>
            )}
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              placeholder="https://ce-doqumentation-01.xxx.eu-de.codeengine.appdomain.cloud"
              value={manualUrl}
              onChange={(e) => setManualUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleAddManual();
              }}
              style={{
                flex: 1,
                padding: '0.4rem 0.6rem',
                fontSize: '0.85rem',
                border: '1px solid var(--ifm-color-emphasis-300)',
                borderRadius: 4,
                fontFamily: 'var(--ifm-font-family-monospace)',
              }}
            />
            <button
              type="button"
              onClick={handleAddManual}
              style={{
                padding: '0.4rem 1rem',
                fontSize: '0.85rem',
                background: 'var(--ifm-color-primary)',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
              }}
            >
              Add
            </button>
          </div>
          {manualUrls.length > 0 && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--ifm-color-emphasis-600)' }}>
              {manualUrls.map((u) => (
                <div key={u} style={{ marginTop: '0.25rem' }}>
                  <code>{shortName(u)}</code>{' '}
                  <button
                    type="button"
                    onClick={() => handleRemoveManual(u)}
                    style={{
                      marginLeft: '0.5rem',
                      padding: '0 0.4rem',
                      fontSize: '0.7rem',
                      background: 'transparent',
                      color: 'var(--ifm-color-emphasis-600)',
                      border: '1px solid var(--ifm-color-emphasis-300)',
                      borderRadius: 3,
                      cursor: 'pointer',
                    }}
                  >
                    remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
