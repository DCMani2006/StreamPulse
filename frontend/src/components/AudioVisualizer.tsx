import React from 'react';
import { Mic } from 'lucide-react';
import { AudioAnalysisResult } from '../types';

interface AudioVisualizerProps {
  audioLevel: number;
  vadActive: boolean;
  audioAnalysis?: AudioAnalysisResult;
}

export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({
  audioLevel,
  vadActive,
  audioAnalysis,
}) => {
  const energy = audioAnalysis?.energy_rms ?? audioLevel;
  const db = audioAnalysis?.energy_db ?? Math.round(20 * Math.log10(Math.max(energy, 1e-4)));
  const isSpike = audioAnalysis?.spike_detected || energy > 0.35;
  const isVad = audioAnalysis?.voice_activity_detected || vadActive;

  // Generate 24 animated bars for waveform display
  const bars = Array.from({ length: 24 }).map((_, i) => {
    const baseHeight = Math.max(8, energy * 100);
    const jitter = Math.sin(i * 0.5 + Date.now() * 0.01) * (energy * 30);
    const h = Math.min(100, Math.max(6, baseHeight + jitter));
    return h;
  });

  return (
    <div className="bg-[#0e111a] border border-[#1c2233] rounded-xl p-3.5 shadow-sm font-mono text-xs flex flex-col gap-2.5">
      
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-slate-300">
          <Mic className="w-3.5 h-3.5 text-purple-400" />
          <span className="font-bold uppercase tracking-wider text-[11px]">
            Acoustic Signal & VAD
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* VAD Indicator */}
          <span
            className={`text-[9px] font-bold px-2 py-0.5 rounded transition-all ${
              isVad
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-slate-800 text-slate-500 border border-slate-700'
            }`}
          >
            {isVad ? 'VAD ACTIVE' : 'NO SPEECH'}
          </span>

          {/* Spike Warning */}
          {isSpike && (
            <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse">
              VOLUME SPIKE
            </span>
          )}
        </div>
      </div>

      {/* Waveform Bars */}
      <div className="h-8 bg-[#090b12] rounded-lg p-1.5 flex items-end justify-between gap-1 border border-[#1c2233]">
        {bars.map((h, idx) => (
          <div
            key={idx}
            className={`w-full rounded-sm transition-all duration-75 ${
              isSpike
                ? 'bg-red-500'
                : isVad
                ? 'bg-emerald-400'
                : 'bg-slate-600'
            }`}
            style={{ height: `${h}%` }}
          />
        ))}
      </div>

      {/* Levels and RMS Metric */}
      <div className="flex items-center justify-between text-[10px] text-slate-400">
        <div className="flex items-center gap-2">
          <span>RMS Energy: <strong className="text-slate-200">{energy.toFixed(3)}</strong></span>
          <span>•</span>
          <span>Level: <strong className="text-slate-200">{db} dB</strong></span>
        </div>
        <span className="text-slate-500">Threshold: 0.050</span>
      </div>

    </div>
  );
};
