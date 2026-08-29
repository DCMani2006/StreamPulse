import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { LatencyHistoryPoint } from '../types';
import { Activity, ShieldCheck } from 'lucide-react';

interface LatencyChartProps {
  data: LatencyHistoryPoint[];
}

export const LatencyChart: React.FC<LatencyChartProps> = ({ data }) => {
  // Custom dark-mode tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const point: LatencyHistoryPoint = payload[0].payload;
      return (
        <div className="bg-[#0b0e14] border border-[#222a3d] p-3 rounded-lg shadow-xl font-mono text-xs text-slate-200">
          <div className="text-slate-400 text-[10px] mb-1.5 font-bold">
            {point.timeStr}
          </div>
          <div className="space-y-1">
            <div className="flex justify-between gap-4 text-emerald-400 font-bold">
              <span>Total E2E:</span>
              <span>{point.e2e} ms</span>
            </div>
            <div className="flex justify-between gap-4 text-cyan-400">
              <span>Inference:</span>
              <span>{point.inference} ms</span>
            </div>
            <div className="flex justify-between gap-4 text-amber-400">
              <span>Queue Dwell:</span>
              <span>{point.queue} ms</span>
            </div>
            <div className="flex justify-between gap-4 text-blue-400">
              <span>Network Ingest:</span>
              <span>{point.ingest} ms</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-[#0e111a] border border-[#1c2233] rounded-xl p-4 shadow-sm flex flex-col gap-3 font-mono">
      
      {/* Chart Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Real-Time Latency Timeline (Last 30s)
          </span>
        </div>

        <div className="flex items-center gap-3 text-[11px]">
          <div className="flex items-center gap-1 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span>E2E Latency</span>
          </div>
          <div className="flex items-center gap-1 text-cyan-400">
            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
            <span>Inference</span>
          </div>
          <div className="flex items-center gap-1 text-red-400 font-bold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Target SLA: &lt; 300ms</span>
          </div>
        </div>
      </div>

      {/* Recharts Area Container */}
      <div className="w-full h-44">
        {data && data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="e2eGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="inferGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                </linearGradient>
              </defs>

              <XAxis
                dataKey="timeStr"
                stroke="#334155"
                tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'monospace' }}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="#334155"
                domain={[0, 350]}
                tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'monospace' }}
                unit="ms"
              />
              <Tooltip content={<CustomTooltip />} />

              {/* SLA Target Line */}
              <ReferenceLine
                y={300}
                stroke="#ef4444"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{
                  value: 'SLA LIMIT 300ms',
                  fill: '#ef4444',
                  fontSize: 9,
                  position: 'insideTopRight',
                  fontFamily: 'monospace',
                }}
              />

              <Area
                type="monotone"
                dataKey="e2e"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#e2eGradient)"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="inference"
                stroke="#06b6d4"
                strokeWidth={1.5}
                fillOpacity={1}
                fill="url(#inferGradient)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-500 text-xs font-mono">
            Buffering telemetry data points...
          </div>
        )}
      </div>

    </div>
  );
};
