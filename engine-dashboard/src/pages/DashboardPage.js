import React, { useContext } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Activity, Database, Cpu, Zap } from 'lucide-react';
import { TelemetryContext } from '../App';

export default function DashboardPage() {
  const { sessionState } = useContext(TelemetryContext);

  // Transform intent mapping to recharts format
  const intentData = Object.keys(sessionState.intentDistribution).map(key => ({
    name: key,
    value: sessionState.intentDistribution[key]
  }));

  // Ensure there's at least a fallback if empty
  const displayTokenData = sessionState.tokenHistory.length > 0 ? sessionState.tokenHistory : [{ time: 'Start', tokens: 0 }];
  const displayIntentData = intentData.length > 0 ? intentData : [{ name: 'Awaiting Queries', value: 0 }];

  // Calculate Cache Hit Rate
  const totalUsed = sessionState.tokensUsed.m1 + sessionState.tokensUsed.m2;
  const hitRate = totalUsed > 0 ? ((sessionState.tokensSaved / (sessionState.tokensSaved + totalUsed)) * 100).toFixed(1) : "0.0";

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-gray-950 flex flex-col gap-8">
      <header>
        <h2 className="text-2xl font-bold text-gray-100">Analytics Overview</h2>
        <p className="text-sm text-gray-500 mt-1">Real-time system telemetry and resource savings.</p>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-lg">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs text-gray-500 uppercase font-bold tracking-wider">Total Tokens Saved</p>
              <h3 className="text-2xl font-bold text-emerald-400 mt-1">{sessionState.tokensSaved.toLocaleString()}</h3>
            </div>
            <div className="p-2 bg-emerald-900/20 rounded text-emerald-500"><Database size={20}/></div>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-lg">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs text-gray-500 uppercase font-bold tracking-wider">Last Request Latency</p>
              <h3 className="text-2xl font-bold text-purple-400 mt-1">
                {sessionState.lastLatencyMs === null ? 'Not measured' : `${sessionState.lastLatencyMs}ms`}
              </h3>
            </div>
            <div className="p-2 bg-purple-900/20 rounded text-purple-500"><Activity size={20}/></div>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-lg">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs text-gray-500 uppercase font-bold tracking-wider">Active Tenants</p>
              <h3 className="text-2xl font-bold text-blue-400 mt-1">{sessionState.sessions.length}</h3>
            </div>
            <div className="p-2 bg-blue-900/20 rounded text-blue-500"><Cpu size={20}/></div>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-lg">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs text-gray-500 uppercase font-bold tracking-wider">Cache Hit Rate</p>
              <h3 className="text-2xl font-bold text-amber-400 mt-1">{hitRate}%</h3>
            </div>
            <div className="p-2 bg-amber-900/20 rounded text-amber-500"><Zap size={20}/></div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-[400px]">
        {/* Line Chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-lg flex flex-col">
          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-widest mb-6">Cumulative Tokens Saved (SC-EVM)</h3>
          <div className="flex-1 w-full min-h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={displayTokenData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis dataKey="time" stroke="#4b5563" tick={{fill: '#9ca3af', fontSize: 12}} />
                <YAxis stroke="#4b5563" tick={{fill: '#9ca3af', fontSize: 12}} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#f3f4f6' }}
                  itemStyle={{ color: '#34d399' }}
                />
                <Line type="monotone" dataKey="tokens" stroke="#10b981" strokeWidth={3} dot={{r: 4, fill: '#10b981', strokeWidth: 0}} activeDot={{r: 6}} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bar Chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 shadow-lg flex flex-col">
          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-widest mb-6">Intent Distribution (Model 1 Gating)</h3>
          <div className="flex-1 w-full min-h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={displayIntentData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis dataKey="name" stroke="#4b5563" tick={{fill: '#9ca3af', fontSize: 12}} />
                <YAxis stroke="#4b5563" tick={{fill: '#9ca3af', fontSize: 12}} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#f3f4f6' }}
                  cursor={{fill: '#1f2937'}}
                />
                <Bar dataKey="value" fill="#a855f7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
