import React, { useContext, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  Clock3,
  Database,
  Gauge,
  Layers3,
  MessageSquare,
  Server,
  Sparkles,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { TelemetryContext } from '../App';

const formatNumber = (value) => new Intl.NumberFormat('en-US', {
  notation: value >= 100000 ? 'compact' : 'standard',
  maximumFractionDigits: 1,
}).format(value);

function MetricCard({ label, value, supporting, icon: Icon, tone }) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <div className="metric-heading">
        <span className="metric-icon" aria-hidden="true"><Icon size={18} /></span>
        <span>{label}</span>
      </div>
      <strong className="metric-value">{value}</strong>
      <p>{supporting}</p>
    </article>
  );
}

function EmptyChart({ icon: Icon, title, description }) {
  return (
    <div className="chart-empty">
      <span className="empty-icon" aria-hidden="true"><Icon size={22} /></span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function ChartTooltip({ active, payload, label, valueLabel }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <span>{label}</span>
      <strong>{valueLabel}: {formatNumber(payload[0].value)}</strong>
    </div>
  );
}

export default function DashboardPage() {
  const { connectionStatus, sessionState } = useContext(TelemetryContext);
  const [showTables, setShowTables] = useState(false);

  const intentData = useMemo(
    () => Object.entries(sessionState.intentDistribution)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value),
    [sessionState.intentDistribution],
  );
  const tokenData = sessionState.tokenHistory;
  const totalUsed = sessionState.tokensUsed.m1 + sessionState.tokensUsed.m2;
  const totalObserved = sessionState.tokensSaved + totalUsed;
  const efficiencyRate = totalObserved > 0
    ? (sessionState.tokensSaved / totalObserved) * 100
    : 0;
  const lastTokenPoint = tokenData[tokenData.length - 1];

  return (
    <div className="page dashboard-page">
      <section className="overview-hero" aria-labelledby="overview-heading">
        <div className="hero-copy">
          <span className="eyebrow">Runtime overview</span>
          <h2 id="overview-heading">Context you can see, control, and remove.</h2>
          <p>
            Monitor how each session narrows context before reasoning, then move directly into
            the workspace when intervention is needed.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/chat">
              Open workspace <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <span className={`service-state service-${connectionStatus}`}>
              <span className="status-dot" aria-hidden="true" />
              {connectionStatus === 'online' ? 'Runtime available' : 'Runtime unavailable'}
            </span>
          </div>
        </div>

        <div className="hero-system-card" aria-label="Current runtime state">
          <div className="system-card-header">
            <span><Server size={16} aria-hidden="true" /> Live session</span>
            <span className="live-indicator"><span aria-hidden="true" /> live</span>
          </div>
          <dl className="system-list">
            <div>
              <dt>Active session</dt>
              <dd>{sessionState.activeSessionId || 'Waiting for runtime'}</dd>
            </div>
            <div>
              <dt>Lifecycle state</dt>
              <dd>{sessionState.phase.replaceAll('_', ' ')}</dd>
            </div>
            <div>
              <dt>Memory anchors</dt>
              <dd>{sessionState.memoryAnchors.length}</dd>
            </div>
          </dl>
          <div className="context-meter">
            <div>
              <span>Context efficiency</span>
              <strong>{efficiencyRate.toFixed(1)}%</strong>
            </div>
            <span className="meter-track" aria-hidden="true">
              <span style={{ width: `${Math.min(efficiencyRate, 100)}%` }} />
            </span>
          </div>
        </div>
      </section>

      <section className="metrics-grid" aria-label="Session metrics">
        <MetricCard
          icon={Database}
          label="Tokens removed"
          supporting="Kept outside active model context"
          tone="primary"
          value={formatNumber(sessionState.tokensSaved)}
        />
        <MetricCard
          icon={Clock3}
          label="Last response"
          supporting="End-to-end request latency"
          tone="accent"
          value={sessionState.lastLatencyMs === null
            ? 'No data'
            : `${formatNumber(sessionState.lastLatencyMs)} ms`}
        />
        <MetricCard
          icon={Layers3}
          label="Active sessions"
          supporting="Isolated working contexts"
          tone="secondary"
          value={formatNumber(sessionState.sessions.length)}
        />
        <MetricCard
          icon={Gauge}
          label="Context efficiency"
          supporting={`${formatNumber(totalUsed)} tokens sent to models`}
          tone="neutral"
          value={`${efficiencyRate.toFixed(1)}%`}
        />
      </section>

      <section className="analytics-grid" aria-label="Telemetry charts">
        <article className="panel chart-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Context trend</span>
              <h3>Tokens removed over time</h3>
            </div>
            <span className="panel-stat">
              {lastTokenPoint ? formatNumber(lastTokenPoint.tokens) : 'Awaiting data'}
            </span>
          </div>
          <p className="panel-description">
            Cumulative context excluded from model requests in this runtime.
          </p>
          <div
            className="chart-container"
            role="img"
            aria-label="Line chart showing cumulative tokens removed over time"
          >
            {tokenData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={tokenData} margin={{ top: 12, right: 8, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--chart-primary)" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="var(--chart-primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="4 4" vertical={false} />
                  <XAxis
                    axisLine={false}
                    dataKey="time"
                    tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }}
                    tickLine={false}
                  />
                  <YAxis
                    axisLine={false}
                    tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }}
                    tickFormatter={formatNumber}
                    tickLine={false}
                  />
                  <Tooltip content={<ChartTooltip valueLabel="Tokens removed" />} />
                  <Area
                    dataKey="tokens"
                    fill="url(#tokenGradient)"
                    isAnimationActive={false}
                    stroke="var(--chart-primary)"
                    strokeWidth={2.5}
                    type="monotone"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart
                description="Run two or more requests to reveal the context trend."
                icon={Activity}
                title="No trend yet"
              />
            )}
          </div>
        </article>

        <article className="panel chart-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Request mix</span>
              <h3>Intent distribution</h3>
            </div>
            <span className="panel-stat">
              {intentData.length ? `${intentData.length} intents` : 'Awaiting data'}
            </span>
          </div>
          <p className="panel-description">
            Requests grouped by the intent observed during orchestration.
          </p>
          <div
            className="chart-container"
            role="img"
            aria-label="Bar chart comparing observed request intents"
          >
            {intentData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={intentData} margin={{ top: 12, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="4 4" vertical={false} />
                  <XAxis
                    axisLine={false}
                    dataKey="name"
                    tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    axisLine={false}
                    tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }}
                    tickLine={false}
                  />
                  <Tooltip content={<ChartTooltip valueLabel="Requests" />} cursor={false} />
                  <Bar
                    dataKey="value"
                    fill="var(--chart-secondary)"
                    isAnimationActive={false}
                    radius={[5, 5, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart
                description="Intent categories appear after the first completed request."
                icon={Sparkles}
                title="No requests classified"
              />
            )}
          </div>
        </article>
      </section>

      <section className="details-grid">
        <article className="panel flow-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Session lifecycle</span>
              <h3>One controlled path</h3>
            </div>
          </div>
          <ol className="lifecycle-flow">
            <li>
              <span>01</span>
              <div><strong>Receive</strong><p>A request enters an isolated session.</p></div>
            </li>
            <li>
              <span>02</span>
              <div><strong>Ground</strong><p>Only relevant working context is assembled.</p></div>
            </li>
            <li>
              <span>03</span>
              <div><strong>Reason</strong><p>The model works from a bounded evidence set.</p></div>
            </li>
            <li>
              <span>04</span>
              <div><strong>Burn</strong><p>Temporary state is removed on command.</p></div>
            </li>
          </ol>
        </article>

        <article className="panel activity-panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Current workload</span>
              <h3>Runtime snapshot</h3>
            </div>
            <Link className="text-link" to="/chat">
              Inspect <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </div>
          <dl className="snapshot-list">
            <div>
              <dt><MessageSquare size={15} aria-hidden="true" /> Messages</dt>
              <dd>{sessionState.chatHistory.length}</dd>
            </div>
            <div>
              <dt><Database size={15} aria-hidden="true" /> Memory anchors</dt>
              <dd>{sessionState.memoryAnchors.length}</dd>
            </div>
            <div>
              <dt><Activity size={15} aria-hidden="true" /> Runtime events</dt>
              <dd>{sessionState.systemLogs.length}</dd>
            </div>
          </dl>
        </article>
      </section>

      {(tokenData.length > 1 || intentData.length > 0) && (
        <section className="data-disclosure">
          <button
            aria-expanded={showTables}
            className="text-link"
            onClick={() => setShowTables((current) => !current)}
            type="button"
          >
            {showTables ? 'Hide accessible data tables' : 'Show accessible data tables'}
          </button>
          {showTables && (
            <div className="table-grid">
              <div className="data-table-wrap">
                <table>
                  <caption>Tokens removed over time</caption>
                  <thead><tr><th>Time</th><th>Tokens</th></tr></thead>
                  <tbody>
                    {tokenData.map((point, index) => (
                      <tr key={`${point.time}-${index}`}>
                        <td>{point.time}</td>
                        <td>{point.tokens.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="data-table-wrap">
                <table>
                  <caption>Request intent distribution</caption>
                  <thead><tr><th>Intent</th><th>Requests</th></tr></thead>
                  <tbody>
                    {intentData.map((intent) => (
                      <tr key={intent.name}><td>{intent.name}</td><td>{intent.value}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
