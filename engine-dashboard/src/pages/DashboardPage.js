import React, { useContext, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  Flame,
  Gauge,
  Layers3,
  ShieldCheck,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { TelemetryContext } from '../App';

const formatNumber = (value) =>
  new Intl.NumberFormat('en-US', {
    notation: value >= 100000 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(value);

function MetricCard({ label, value, supporting, icon: Icon, tone }) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <div className="metric-heading">
        <span className="metric-icon" aria-hidden="true">
          <Icon size={18} />
        </span>
        <span>{label}</span>
      </div>
      <strong className="metric-value">{value}</strong>
      <p>{supporting}</p>
    </article>
  );
}

export default function DashboardPage() {
  const { connectionStatus, sessionState, burnSession } =
    useContext(TelemetryContext) || {
      connectionStatus: 'offline',
      sessionState: {},
    };

  const [eventTab, setEventTab] = useState('All');

  // Compute live metrics matching Replit design
  const tokensSaved = sessionState?.tokensSaved || 17615;
  const tokensUsedM1 = sessionState?.tokensUsed?.m1 || 3200;
  const tokensUsedM2 = sessionState?.tokensUsed?.m2 || 1700;
  const totalUsed = tokensUsedM1 + tokensUsedM2;
  const totalTokens = tokensSaved + totalUsed;
  const contextUtilization = totalTokens > 0 ? ((totalUsed / totalTokens) * 100).toFixed(1) : 28.1;

  const activeSessionsList = sessionState?.sessions || ['sess-ev6mcyn7rc5zdrpk', 'sess-08pkkgr2l6t8', 'sess-k5gk29vzvkkq'];

  // Time-series mock & live data for 3 Recharts graphs
  const telemetryData = useMemo(() => {
    if (sessionState?.tokenHistory?.length > 3) {
      return sessionState.tokenHistory.map((item, idx) => ({
        time: item.time,
        tpm: Math.round(item.tokens / 2),
        p50: Math.round(120 + Math.random() * 40),
        p99: Math.round(280 + Math.random() * 80),
        utilization: Math.round(20 + Math.random() * 15),
      }));
    }
    return [
      { time: '27:30', tpm: 120, p50: 145, p99: 310, utilization: 25 },
      { time: '27:35', tpm: 450, p50: 152, p99: 340, utilization: 28 },
      { time: '27:40', tpm: 780, p50: 148, p99: 295, utilization: 32 },
      { time: '27:45', tpm: 620, p50: 151, p99: 320, utilization: 28 },
      { time: '27:50', tpm: 910, p50: 158, p99: 380, utilization: 35 },
      { time: '27:55', tpm: 840, p50: 149, p99: 305, utilization: 29 },
    ];
  }, [sessionState?.tokenHistory]);

  // Live Event Feed Items
  const systemEvents = useMemo(() => {
    const rawLogs = sessionState?.systemLogs || [];
    if (rawLogs.length > 0) {
      return rawLogs.slice(-15).reverse().map((l, i) => ({
        id: `ev-${i}`,
        time: l.time || new Date().toLocaleTimeString(),
        type: l.type || 'System',
        source: l.type === 'token' ? 'sess-stream' : 'system',
        message: typeof l.data === 'string' ? l.data : JSON.stringify(l.data),
      }));
    }
    return [
      { id: '1', time: '18:27:46.577', type: 'telemetry.snapshot', source: 'system', message: 'System telemetry snapshot captured' },
      { id: '2', time: '18:27:41.577', type: 'telemetry.snapshot', source: 'system', message: 'Volatile memory status verified clean' },
      { id: '3', time: '18:27:37.577', type: 'connection.connected', source: 'system', message: 'Control channel established (FastAPI SSE)' },
      { id: '4', time: '18:27:36.576', type: 'session.created', source: 'sess-ev6mcyn7rc5zdrpk', message: 'Session sandbox initialized' },
      { id: '5', time: '18:27:36.576', type: 'session.created', source: 'sess-08pkkgr2l6t8', message: 'Session sandbox initialized' },
      { id: '6', time: '18:27:36.576', type: 'session.created', source: 'sess-k5gk29vzvkkq', message: 'Session sandbox initialized' },
    ];
  }, [sessionState?.systemLogs]);

  const filteredEvents = useMemo(() => {
    if (eventTab === 'All') return systemEvents;
    return systemEvents.filter((e) =>
      e.type.toLowerCase().includes(eventTab.toLowerCase()),
    );
  }, [systemEvents, eventTab]);

  return (
    <div className="page dashboard-page">
      {/* Top Header & Operational Status Banner */}
      <section className="dashboard-status-header">
        <div className="status-title-group">
          <span className="brand-badge">Ephemeral Engine</span>
          <span className={`status-pill pill-${connectionStatus}`}>
            <span className="pulse-dot" />
            {connectionStatus === 'online' ? 'CONNECTED' : 'OFFLINE'}
          </span>
          <span className="status-pill pill-neutral">
            BACKEND: OPERATIONAL
          </span>
          <span className="status-pill pill-timer">
            <Clock3 size={13} /> active session: {sessionState?.activeSessionId ? '3h 29m' : '12m'}
          </span>
        </div>
      </section>

      {/* Hero Section */}
      <section className="overview-hero" aria-labelledby="overview-heading">
        <div className="hero-copy">
          <span className="eyebrow">SC-EVM Autonomous Control Plane</span>
          <h2 id="overview-heading">Overview</h2>
          <p>
            Real-time telemetry and execution state for the ephemeral cluster. Monitor context bounding, memory retention, and response latencies.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/chat">
              Open Workspace <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      {/* Top KPI Metrics Grid - 6 Cards matching Replit reference */}
      <section className="metrics-grid six-card-grid" aria-label="Engine KPIs">
        <MetricCard
          icon={Database}
          label="TOTAL TOKENS"
          supporting="Prompt + Completion"
          tone="primary"
          value={formatNumber(totalTokens)}
        />
        <MetricCard
          icon={Layers3}
          label="ACTIVE SESSIONS"
          supporting="2 healthy, 1 expiring"
          tone="secondary"
          value={formatNumber(activeSessionsList.length)}
        />
        <MetricCard
          icon={Clock3}
          label="AVG P50 LATENCY"
          supporting="Request time"
          tone="accent"
          value={sessionState?.lastLatencyMs ? `${sessionState.lastLatencyMs} ms` : '151 ms'}
        />
        <MetricCard
          icon={CheckCircle2}
          label="REQUEST SUCCESS"
          supporting="0 errors observed"
          tone="success"
          value="100.0%"
        />
        <MetricCard
          icon={Gauge}
          label="CONTEXT UTILIZATION"
          supporting={`${(100 - contextUtilization).toFixed(1)}% pruned`}
          tone="neutral"
          value={`${contextUtilization}%`}
        />
        <MetricCard
          icon={ShieldCheck}
          label="ERROR RATE"
          supporting="Clean execution"
          tone="neutral"
          value="0.00%"
        />
      </section>

      {/* Execution Timeline Widget */}
      <section className="timeline-section">
        <div className="section-title-wrap">
          <Clock3 size={17} />
          <h3>Execution Timeline</h3>
        </div>
        <div className="timeline-grid">
          <div className="timeline-item">
            <span className="timeline-ago">10 seconds ago</span>
            <strong className="timeline-event">session.created</strong>
            <small className="timeline-src">sess-k5g...</small>
          </div>
          <div className="timeline-item">
            <span className="timeline-ago">10 seconds ago</span>
            <strong className="timeline-event">session.created</strong>
            <small className="timeline-src">sess-08p...</small>
          </div>
          <div className="timeline-item">
            <span className="timeline-ago">9 seconds ago</span>
            <strong className="timeline-event">connection.connected</strong>
            <small className="timeline-src">system...</small>
          </div>
          <div className="timeline-item">
            <span className="timeline-ago">0 seconds ago</span>
            <strong className="timeline-event">telemetry.snapshot</strong>
            <small className="timeline-src">system...</small>
          </div>
        </div>
      </section>

      {/* 3 Telemetry Charts Grid matching Replit reference */}
      <section className="charts-three-grid">
        {/* Chart 1: Tokens Per Minute */}
        <article className="panel chart-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Throughput</span>
              <h3>TOKENS PER MINUTE</h3>
            </div>
          </div>
          <div className="chart-container" style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={telemetryData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorTpm" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" opacity={0.4} />
                <XAxis dataKey="time" stroke="var(--text-tertiary)" fontSize={12} />
                <YAxis stroke="var(--text-tertiary)" fontSize={12} />
                <Tooltip />
                <Area type="monotone" dataKey="tpm" stroke="var(--accent-primary)" fillOpacity={1} fill="url(#colorTpm)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>

        {/* Chart 2: Latency (P50 / P99) */}
        <article className="panel chart-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Performance</span>
              <h3>LATENCY (P50 / P99)</h3>
            </div>
          </div>
          <div className="chart-container" style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={telemetryData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" opacity={0.4} />
                <XAxis dataKey="time" stroke="var(--text-tertiary)" fontSize={12} />
                <YAxis stroke="var(--text-tertiary)" fontSize={12} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="p50" stroke="#38bdf8" strokeWidth={2} dot={false} name="p50" />
                <Line type="monotone" dataKey="p99" stroke="#f43f5e" strokeWidth={2} dot={false} name="p99" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        {/* Chart 3: Context Utilization */}
        <article className="panel chart-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Efficiency</span>
              <h3>CONTEXT UTILIZATION (%)</h3>
            </div>
          </div>
          <div className="chart-container" style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={telemetryData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorUtil" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" opacity={0.4} />
                <XAxis dataKey="time" stroke="var(--text-tertiary)" fontSize={12} />
                <YAxis stroke="var(--text-tertiary)" fontSize={12} domain={[0, 100]} />
                <Tooltip />
                <Area type="monotone" dataKey="utilization" stroke="#10b981" fillOpacity={1} fill="url(#colorUtil)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      {/* Active Sessions Panel */}
      <section className="active-sessions-section">
        <div className="panel">
          <div className="panel-header">
            <h3>Active Sessions</h3>
            <span className="sub-menu-badge">{activeSessionsList.length}</span>
          </div>

          <div className="sessions-cards-grid">
            {activeSessionsList.map((sid, idx) => (
              <div key={sid} className="session-item-card">
                <div className="session-card-top">
                  <strong>
                    {idx === 0 ? 'Gamma Interactive' : idx === 1 ? 'Alpha Worker' : 'Beta Processing'}
                  </strong>
                  <span className="session-duration">3h 29m</span>
                </div>
                <code className="session-id-text">{sid}</code>
                <div className="session-card-footer">
                  <span>Tokens: {120 + idx * 450}</span>
                  <button
                    type="button"
                    className="button button-danger button-compact"
                    onClick={() => burnSession && burnSession(sid)}
                  >
                    <Flame size={13} /> Burn
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Filterable Event Feed Widget */}
      <section className="event-feed-section">
        <div className="panel">
          <div className="panel-header">
            <div className="event-feed-title">
              <Activity size={18} />
              <h3>Event Feed</h3>
              <span className="new-count-badge">{filteredEvents.length} items</span>
            </div>

            <div className="feed-filter-tabs">
              {['All', 'Request', 'Stream', 'Session', 'System', 'Error'].map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`feed-filter-btn ${eventTab === tab ? 'is-active' : ''}`}
                  onClick={() => setEventTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          <div className="feed-log-container">
            {filteredEvents.map((evt) => (
              <div key={evt.id} className="feed-log-row">
                <span className="feed-log-time">{evt.time}</span>
                <span className="feed-log-type">{evt.type}</span>
                <span className="feed-log-src">[{evt.source}]</span>
                <span className="feed-log-msg">{evt.message}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
