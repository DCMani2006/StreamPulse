import React from 'react';
import {
  Activity,
  Layers,
  Camera,
  Maximize2,
  Minimize2,
  Sliders,
  Radio,
} from 'lucide-react';

interface NavbarProps {
  isBackendConnected: boolean;
  isFailsafeActive: boolean;
  activeFeedName: string;
  isFullscreen: boolean;
  viewMode?: 'single' | 'quad';
  onToggleViewMode?: (mode: 'single' | 'quad') => void;
  onToggleFullscreen: () => void;
  onTakeSnapshot: () => void;
  onOpenSettings: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  isBackendConnected,
  isFailsafeActive,
  activeFeedName,
  isFullscreen,
  viewMode = 'single',
  onToggleViewMode,
  onToggleFullscreen,
  onTakeSnapshot,
  onOpenSettings,
}) => {
  return (
    <header className="bg-[#0e1017] border-b border-[#1c2233] px-5 py-3 sticky top-0 z-50">
      <div className="max-w-[1920px] mx-auto flex flex-wrap items-center justify-between gap-4">
        
        {/* Brand & Connection Status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-sm shadow-emerald-500/20">
              <Activity className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-extrabold tracking-wider text-white font-mono uppercase">
                  Stream<span className="text-emerald-400">Pulse</span>
                </span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Enterprise
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono">
                Real-Time AI Video Intelligence Command Center
              </p>
            </div>
          </div>

          {/* Connection Status Pill */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-mono font-semibold backdrop-blur-md">
            {isBackendConnected ? (
              <div className="flex items-center gap-2 text-emerald-400 border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                <span>● LIVE STREAM CONNECTED</span>
              </div>
            ) : isFailsafeActive ? (
              <div className="flex items-center gap-2 text-amber-400 border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 rounded-full border">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                <span>● LOCAL DEMO FAILSAFE (0 BLANK SCREEN)</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-red-400 border-red-500/30 bg-red-500/10 px-2.5 py-0.5 rounded-full border">
                <span className="w-2 h-2 rounded-full bg-red-400"></span>
                <span>● DISCONNECTED</span>
              </div>
            )}
          </div>

          {/* Active Camera Feed Name Pill */}
          <div className="hidden lg:flex items-center gap-2 bg-[#141824] border border-[#222a3d] px-3 py-1 rounded-lg text-xs font-mono text-slate-300">
            <Radio className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">Feed:</span>
            <span className="text-emerald-300 font-semibold">{activeFeedName}</span>
          </div>
        </div>

        {/* View Mode Grid Switcher */}
        {onToggleViewMode && (
          <div className="flex items-center gap-1 bg-[#141824] p-1 rounded-xl border border-[#222a3d] text-xs font-mono">
            <button
              onClick={() => onToggleViewMode('single')}
              className={`px-3 py-1 rounded-lg transition-all font-bold flex items-center gap-1.5 ${
                viewMode === 'single'
                  ? 'bg-emerald-500 text-black shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Radio className="w-3.5 h-3.5" />
              <span>Single Feed</span>
            </button>

            <button
              onClick={() => onToggleViewMode('quad')}
              className={`px-3 py-1 rounded-lg transition-all font-bold flex items-center gap-1.5 ${
                viewMode === 'quad'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>2x2 Quad Grid</span>
            </button>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={onTakeSnapshot}
            title="Capture Emergency Snapshot"
            className="flex items-center gap-1.5 bg-[#141824] hover:bg-[#1d2334] text-slate-200 border border-[#262f45] px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all shadow-sm active:scale-95"
          >
            <Camera className="w-4 h-4 text-emerald-400" />
            <span className="hidden md:inline">Snapshot</span>
          </button>

          <button
            onClick={onOpenSettings}
            title="Configure Restricted Zones & Thresholds"
            className="flex items-center gap-1.5 bg-[#141824] hover:bg-[#1d2334] text-slate-200 border border-[#262f45] px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all shadow-sm active:scale-95"
          >
            <Sliders className="w-4 h-4 text-cyan-400" />
            <span className="hidden md:inline">Zone Config</span>
          </button>

          <button
            onClick={onToggleFullscreen}
            title="Toggle Fullscreen Mode"
            className="p-1.5 bg-[#141824] hover:bg-[#1d2334] text-slate-200 border border-[#262f45] rounded-lg transition-all active:scale-95"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>

      </div>
    </header>
  );
};
