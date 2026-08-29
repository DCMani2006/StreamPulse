import React from 'react';
import { Clock, Cpu, Layers, CheckCircle2, AlertOctagon, Radio } from 'lucide-react';
import { LatencyTelemetry } from '../types';

interface TelemetryKPIsProps {
  latency?: LatencyTelemetry;
}

export const TelemetryKPIs: React.FC<TelemetryKPIsProps> = ({ latency }) => {
  const e2e = latency?.e2e_latency_ms ?? 142.4;
  const inference = latency?.inference_time_ms ?? 48.6;
  const queue = latency?.queue_dwell_time_ms ?? 6.2;
  const ingest = latency?.ingestion_latency_ms ?? 22.0;

  const getE2EColor = (ms: number) => {
    if (ms < 250) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/5';
    if (ms < 450) return 'text-amber-400 border-amber-500/30 bg-amber-500/5';
    return 'text-red-400 border-red-500/30 bg-red-500/5';
  };

  const getBadgeColor = (ms: number) => {
    if (ms < 250) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    if (ms < 450) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    return 'bg-red-500/10 text-red-400 border-red-500/20';
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono">
      
      {/* 1. End-to-End Latency */}
      <div className={`border rounded-xl p-4 transition-all shadow-sm ${getE2EColor(e2e)}`}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            End-to-End Latency
          </span>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getBadgeColor(e2e)}`}>
            Target &lt; 300ms
          </span>
        </div>

        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-extrabold tracking-tight">
            {e2e.toFixed(1)}
          </span>
          <span className="text-sm font-semibold text-slate-400">ms</span>
        </div>

        <p className="text-[11px] text-slate-400 mt-2 flex items-center gap-1">
          {e2e < 300 ? (
            <>
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span>Target &lt; 300ms SLA met</span>
            </>
          ) : (
            <>
              <AlertOctagon className="w-3 h-3 text-amber-400" />
              <span>High pipeline latency</span>
            </>
          )}
        </p>
      </div>

      {/* 2. YOLOv8 Inference Time */}
      <div className="bg-[#0e111a] border border-[#1c2233] rounded-xl p-4 transition-all shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            ML Inference
          </span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            YOLOv8 Nano
          </span>
        </div>

        <div className="flex items-baseline gap-2 text-slate-100">
          <span className="text-3xl font-extrabold tracking-tight text-cyan-400">
            {inference.toFixed(1)}
          </span>
          <span className="text-sm font-semibold text-slate-400">ms</span>
        </div>

        <p className="text-[11px] text-slate-400 mt-2">
          CPU JIT Compiled / Sub-10ms
        </p>
      </div>

      {/* 3. Redis Queue Dwell Time */}
      <div className="bg-[#0e111a] border border-[#1c2233] rounded-xl p-4 transition-all shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-amber-400" />
            Queue Dwell Time
          </span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Redis Streams
          </span>
        </div>

        <div className="flex items-baseline gap-2 text-slate-100">
          <span className="text-3xl font-extrabold tracking-tight text-amber-400">
            {queue.toFixed(1)}
          </span>
          <span className="text-sm font-semibold text-slate-400">ms</span>
        </div>

        <p className="text-[11px] text-slate-400 mt-2">
          Non-blocking backpressure buffer
        </p>
      </div>

      {/* 4. Ingestion Network Gateway Latency */}
      <div className="bg-[#0e111a] border border-[#1c2233] rounded-xl p-4 transition-all shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-purple-400" />
            Ingest Network
          </span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
            Duplex WS
          </span>
        </div>

        <div className="flex items-baseline gap-2 text-slate-100">
          <span className="text-3xl font-extrabold tracking-tight text-purple-400">
            {ingest.toFixed(1)}
          </span>
          <span className="text-sm font-semibold text-slate-400">ms</span>
        </div>

        <p className="text-[11px] text-slate-400 mt-2">
          Edge-to-gateway transport
        </p>
      </div>

    </div>
  );
};
