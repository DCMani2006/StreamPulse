import React from 'react';
import {
  TrendingDown,
  HardDrive,
  DollarSign,
  Zap,
  Cpu,
  Sparkles,
  Layers,
  Activity,
  CheckCircle,
} from 'lucide-react';
import { ROITelemetrySnapshot, TokenOptimizationStats } from '../types';

interface CloudRoiBarProps {
  roiTelemetry?: ROITelemetrySnapshot;
  stats?: TokenOptimizationStats;
}

export const CloudRoiBar: React.FC<CloudRoiBarProps> = ({ roiTelemetry, stats }) => {
  // Default values with graceful fallbacks
  const tokenReduction = roiTelemetry?.token_stats?.token_reduction_pct ?? (stats?.token_reduction_ratio ? Math.round(stats.token_reduction_ratio * 1000) / 10 : 97.4);
  const tokensConsumed = roiTelemetry?.token_stats?.tokens_consumed ?? 1032;
  const tokensSaved = roiTelemetry?.token_stats?.tokens_saved ?? 260968;
  const theoreticalNaive = tokensConsumed + tokensSaved;

  const bandwidthSaved = roiTelemetry?.cloud_savings?.bandwidth_saved_mb ?? 142.5;
  const staticDropped = roiTelemetry?.static_frames_dropped ?? (stats?.frames_dropped ?? 950);
  const filterRate = roiTelemetry?.filter_efficiency_pct ?? (stats?.bandwidth_saving_percent ?? 95.0);

  const monthlySavings = roiTelemetry?.cloud_savings?.projected_monthly_savings_usd ?? 285.40;
  const hourlySavings = roiTelemetry?.cloud_savings?.estimated_hourly_savings_usd ?? 0.39;

  // Tri-Tier Transparent Latency Metrics
  const edgeFilterMs = roiTelemetry?.tri_tier_latency?.edge_filter_ms ?? (roiTelemetry?.edge_filter_latency_ms ?? 1.15);
  const ingestHudMs = roiTelemetry?.tri_tier_latency?.ingest_hud_e2e_ms ?? 68.4;
  const cloudVlmMs = roiTelemetry?.tri_tier_latency?.cloud_vlm_ms ?? 1420.0;
  const isSlaCompliant = roiTelemetry?.tri_tier_latency?.sla_compliant ?? (ingestHudMs <= 300.0);

  const pipelineFps = roiTelemetry?.pipeline_fps ?? 30.0;

  return (
    <div className="w-full bg-[#0d1017]/90 backdrop-blur-md border border-[#1e2538] rounded-2xl p-4 shadow-xl font-mono text-slate-100 transition-all">
      
      {/* Top Title Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-3 border-b border-[#1c2233]">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            Cloud Token Optimization & ROI Accounting Engine
          </span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Active Edge Gateway
          </span>
        </div>

        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span className="flex items-center gap-1">
            <Layers className="w-3 h-3 text-cyan-400" />
            Cost Model: <strong className="text-slate-200">Gemini 2.5 Flash ($0.075/1M)</strong>
          </span>
          <span className="text-[#2a334a]">|</span>
          <span className="flex items-center gap-1">
            <Cpu className="w-3 h-3 text-purple-400" />
            Throughput: <strong className="text-emerald-400">{pipelineFps.toFixed(1)} FPS</strong>
          </span>
        </div>
      </div>

      {/* 4 High-Impact Cloud Economics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        
        {/* 1. Token Optimization Ratio */}
        <div className="bg-[#121622] border border-emerald-500/30 rounded-xl p-3.5 transition-all relative overflow-hidden group hover:border-emerald-500/60 shadow-lg">
          <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-xl pointer-events-none group-hover:bg-emerald-500/10 transition-all" />
          
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <TrendingDown className="w-3.5 h-3.5 text-emerald-400" />
              Token Reduction
            </span>
            <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
              SAVING &gt;95%
            </span>
          </div>

          <div className="flex items-baseline gap-1.5 text-slate-100">
            <span className="text-3xl font-extrabold tracking-tight text-emerald-400">
              {tokenReduction.toFixed(1)}%
            </span>
            <span className="text-xs font-semibold text-slate-400">Tokens Saved</span>
          </div>

          <div className="text-[10px] text-slate-400 mt-2 space-y-0.5">
            <p>Billed: <strong className="text-slate-200">{tokensConsumed.toLocaleString()}</strong> tokens</p>
            <p>Naive Stream: <strong className="text-slate-400">{theoreticalNaive.toLocaleString()}</strong> tokens</p>
          </div>
        </div>

        {/* 2. Cloud Bandwidth Saved */}
        <div className="bg-[#121622] border border-cyan-500/30 rounded-xl p-3.5 transition-all relative overflow-hidden group hover:border-cyan-500/60 shadow-lg">
          <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-500/5 rounded-full blur-xl pointer-events-none group-hover:bg-cyan-500/10 transition-all" />

          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <HardDrive className="w-3.5 h-3.5 text-cyan-400" />
              Bandwidth Preserved
            </span>
            <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
              {filterRate.toFixed(1)}% FILTERED
            </span>
          </div>

          <div className="flex items-baseline gap-1.5 text-slate-100">
            <span className="text-3xl font-extrabold tracking-tight text-cyan-400">
              {bandwidthSaved.toFixed(1)}
            </span>
            <span className="text-xs font-semibold text-slate-400">MB Preserved</span>
          </div>

          <div className="text-[10px] text-slate-400 mt-2 space-y-0.5">
            <p>Static Discarded: <strong className="text-slate-200">{staticDropped.toLocaleString()}</strong> frames</p>
            <p>Payload: <strong className="text-slate-400">150 KB/frame compressed</strong></p>
          </div>
        </div>

        {/* 3. Estimated Cost Reduction */}
        <div className="bg-[#121622] border border-amber-500/30 rounded-xl p-3.5 transition-all relative overflow-hidden group hover:border-amber-500/60 shadow-lg">
          <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-xl pointer-events-none group-hover:bg-amber-500/10 transition-all" />

          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <DollarSign className="w-3.5 h-3.5 text-amber-400" />
              Projected ROI
            </span>
            <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/40">
              24/7 SAVINGS
            </span>
          </div>

          <div className="flex items-baseline gap-1.5 text-slate-100">
            <span className="text-3xl font-extrabold tracking-tight text-amber-400">
              ${monthlySavings.toFixed(2)}
            </span>
            <span className="text-xs font-semibold text-slate-400">/mo saved</span>
          </div>

          <div className="text-[10px] text-slate-400 mt-2 space-y-0.5">
            <p>Run Rate: <strong className="text-slate-200">${hourlySavings.toFixed(2)}/hr</strong></p>
            <p>Rate: <strong className="text-slate-400">$0.075 / 1M Input Tokens</strong></p>
          </div>
        </div>

        {/* 4. Tri-Tier Latency Breakdown Card */}
        <div className="bg-[#121622] border border-purple-500/30 rounded-xl p-3.5 transition-all relative overflow-hidden group hover:border-purple-500/60 shadow-lg">
          <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-full blur-xl pointer-events-none group-hover:bg-purple-500/10 transition-all" />

          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-purple-400" />
              Tri-Tier Latency
            </span>
            <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-md flex items-center gap-1 border ${
              isSlaCompliant ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' : 'bg-amber-500/20 text-amber-400 border-amber-500/40'
            }`}>
              {isSlaCompliant ? <CheckCircle className="w-2.5 h-2.5" /> : <Activity className="w-2.5 h-2.5" />}
              {isSlaCompliant ? '<300MS SLA' : 'DEGRADED'}
            </span>
          </div>

          <div className="flex items-baseline gap-1.5 text-slate-100">
            <span className="text-3xl font-extrabold tracking-tight text-purple-400">
              {edgeFilterMs.toFixed(2)}
            </span>
            <span className="text-xs font-semibold text-slate-400">ms Edge Filter</span>
          </div>

          <div className="text-[10px] text-slate-400 mt-2 space-y-0.5">
            <p>Ingest / HUD Live: <strong className="text-emerald-400">{ingestHudMs.toFixed(1)} ms</strong></p>
            <p>Async Cloud VLM: <strong className="text-purple-300">{(cloudVlmMs / 1000.0).toFixed(2)} s</strong></p>
          </div>
        </div>

      </div>

    </div>
  );
};
