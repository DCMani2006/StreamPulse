import React, { useState, useEffect } from 'react';
import {
  Camera,
  Maximize2,
  AlertTriangle,
  Zap,
  Activity,
  Flame,
} from 'lucide-react';
import { CameraGridTileConfig, IncidentCategory } from '../types';

interface MultiCameraGridProps {
  onSelectCamera: (streamId: string, category: IncidentCategory) => void;
  onTriggerSimulatedAnomaly?: (streamId: string, title: string) => void;
}

const DEFAULT_CAMERAS: CameraGridTileConfig[] = [
  {
    stream_id: 'cam_01',
    name: 'Camera 01 - Main Entrance',
    location: 'North Gate Access',
    category: 'TRAFFIC',
    colorTheme: 'cyan',
  },
  {
    stream_id: 'cam_02',
    name: 'Camera 02 - Warehouse Interior',
    location: 'Bay Alpha Heavy Machinery',
    category: 'INDUSTRIAL_SAFETY',
    colorTheme: 'amber',
  },
  {
    stream_id: 'cam_03',
    name: 'Camera 03 - Loading Dock',
    location: 'Freight Cargo Terminal',
    category: 'INDUSTRIAL_SAFETY',
    colorTheme: 'emerald',
  },
  {
    stream_id: 'cam_04',
    name: 'Camera 04 - Perimeter Fence',
    location: 'West Facility Boundary',
    category: 'FACILITY_SECURITY',
    colorTheme: 'purple',
  },
];

export const MultiCameraGrid: React.FC<MultiCameraGridProps> = ({
  onSelectCamera,
  onTriggerSimulatedAnomaly,
}) => {
  const [activeAlerts, setActiveAlerts] = useState<Record<string, { title: string; time: string }>>({});
  const [tileMetrics, setTileMetrics] = useState<Record<string, { fps: number; dropRate: number; latency: number }>>({
    cam_01: { fps: 29.8, dropRate: 95.4, latency: 24 },
    cam_02: { fps: 30.0, dropRate: 97.1, latency: 28 },
    cam_03: { fps: 29.4, dropRate: 96.0, latency: 22 },
    cam_04: { fps: 30.1, dropRate: 98.2, latency: 19 },
  });

  // Periodically jitter metrics slightly for realistic surveillance heartbeat
  useEffect(() => {
    const timer = setInterval(() => {
      setTileMetrics({
        cam_01: { fps: +(29.2 + Math.random() * 1.2).toFixed(1), dropRate: +(94.8 + Math.random() * 1.5).toFixed(1), latency: Math.floor(22 + Math.random() * 6) },
        cam_02: { fps: +(29.5 + Math.random() * 1.0).toFixed(1), dropRate: +(96.5 + Math.random() * 1.2).toFixed(1), latency: Math.floor(26 + Math.random() * 8) },
        cam_03: { fps: +(29.0 + Math.random() * 1.4).toFixed(1), dropRate: +(95.2 + Math.random() * 1.6).toFixed(1), latency: Math.floor(20 + Math.random() * 5) },
        cam_04: { fps: +(29.8 + Math.random() * 0.8).toFixed(1), dropRate: +(97.6 + Math.random() * 1.0).toFixed(1), latency: Math.floor(18 + Math.random() * 4) },
      });
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  const handleSimulateIncident = (cam: CameraGridTileConfig) => {
    const timeStr = new Date().toLocaleTimeString();
    const eventTitles: Record<string, string> = {
      cam_01: 'High-Speed Tailgating & Restricted Lane Intrusion',
      cam_02: 'Heavy Forklift Proximity & PPE Zone Breach',
      cam_03: 'Unauthorized Cargo Loading & Unattended Freight',
      cam_04: 'Perimeter Fence Motion Trigger & Access Breach',
    };
    const title = eventTitles[cam.stream_id] || 'Candidate Motion Anomaly';
    
    setActiveAlerts((prev) => ({
      ...prev,
      [cam.stream_id]: { title, time: timeStr },
    }));

    if (onTriggerSimulatedAnomaly) {
      onTriggerSimulatedAnomaly(cam.stream_id, title);
    }

    // Auto clear alert flashing after 8 seconds
    setTimeout(() => {
      setActiveAlerts((prev) => {
        const next = { ...prev };
        delete next[cam.stream_id];
        return next;
      });
    }, 8000);
  };

  const getCategoryBadge = (category: IncidentCategory) => {
    switch (category) {
      case 'TRAFFIC':
        return <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">🚗 TRAFFIC</span>;
      case 'INDUSTRIAL_SAFETY':
        return <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">🏭 SAFETY</span>;
      case 'FACILITY_SECURITY':
        return <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30">🏢 SECURITY</span>;
      default:
        return <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">⚡ SURVEILLANCE</span>;
    }
  };

  return (
    <div className="space-y-3 font-mono">
      {/* 2x2 Multi-Camera Grid Container */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {DEFAULT_CAMERAS.map((cam) => {
          const isAlert = !!activeAlerts[cam.stream_id];
          const metrics = tileMetrics[cam.stream_id] || { fps: 30.0, dropRate: 96.0, latency: 25 };

          return (
            <div
              key={cam.stream_id}
              className={`bg-[#0e111a] rounded-2xl border transition-all duration-300 relative overflow-hidden flex flex-col group ${
                isAlert
                  ? 'border-red-500 shadow-xl shadow-red-500/20 ring-2 ring-red-500/40 animate-pulse'
                  : 'border-[#1c2233] hover:border-[#2a354f] shadow-md'
              }`}
            >
              {/* Tile Top Status Header */}
              <div className="p-3 bg-[#131722] border-b border-[#1c2233] flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></div>
                  <span className="text-xs font-bold text-slate-100 truncate">
                    {cam.name}
                  </span>
                  <span className="text-[10px] text-slate-500 hidden sm:inline">
                    [{cam.location}]
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {getCategoryBadge(cam.category)}
                  <button
                    onClick={() => onSelectCamera(cam.stream_id, cam.category)}
                    className="p-1.5 rounded-lg bg-[#1c2233] hover:bg-emerald-500 hover:text-black text-slate-300 text-[10px] font-bold flex items-center gap-1 transition-all"
                    title="Focus Camera Feed"
                  >
                    <Maximize2 className="w-3 h-3" />
                    <span className="hidden lg:inline">Focus</span>
                  </button>
                </div>
              </div>

              {/* Video Simulated Stage Canvas */}
              <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden">
                {/* Surveillance Grid Overlay Lines */}
                <div className="absolute inset-0 bg-[radial-gradient(#1c2233_1px,transparent_1px)] [background-size:16px_16px] opacity-40 pointer-events-none"></div>

                {/* Camera Center Graphic Simulation */}
                <div className="text-center space-y-1.5 z-10">
                  <div className="w-12 h-12 mx-auto rounded-full bg-[#141824] border border-[#222a3d] flex items-center justify-center text-slate-400 group-hover:text-emerald-400 group-hover:border-emerald-500/40 transition-all">
                    <Camera className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">
                    {cam.stream_id} • REAL-TIME FEED
                  </span>
                  <span className="text-[9px] text-slate-500 font-mono block">
                    Sub-2ms Area Gatekeeper Active
                  </span>
                </div>

                {/* Active Anomaly Banner */}
                {isAlert && (
                  <div className="absolute bottom-2 inset-x-2 bg-red-600/90 backdrop-blur-md text-white p-2 rounded-xl border border-red-400/50 shadow-lg flex items-center justify-between text-[10px] font-bold animate-bounce z-20">
                    <div className="flex items-center gap-1.5 truncate">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-amber-300" />
                      <span className="truncate">{activeAlerts[cam.stream_id]?.title}</span>
                    </div>
                    <span className="bg-black/40 px-1.5 py-0.5 rounded text-[9px] font-mono shrink-0">
                      {activeAlerts[cam.stream_id]?.time}
                    </span>
                  </div>
                )}
              </div>

              {/* Tile Bottom Telemetry Bar */}
              <div className="p-2.5 bg-[#10141f] border-t border-[#1c2233] flex flex-wrap items-center justify-between gap-2 text-[10px]">
                <div className="flex items-center gap-3 text-slate-400">
                  <span className="flex items-center gap-1">
                    <Activity className="w-3 h-3 text-emerald-400" />
                    <b>{metrics.fps}</b> FPS
                  </span>
                  <span className="flex items-center gap-1 text-cyan-300">
                    <Zap className="w-3 h-3 text-cyan-400" />
                    <b>{metrics.dropRate}%</b> Dropped
                  </span>
                  <span className="text-slate-500">
                    Lat: <b className="text-slate-300">{metrics.latency}ms</b>
                  </span>
                </div>

                {/* Inject Simulated Event Button for Live Hackathon Judging */}
                <button
                  onClick={() => handleSimulateIncident(cam)}
                  className="px-2 py-1 rounded bg-[#181d2c] hover:bg-red-500/20 text-slate-300 hover:text-red-300 border border-[#2a354f] hover:border-red-500/40 text-[9px] font-bold flex items-center gap-1 transition-all"
                >
                  <Flame className="w-3 h-3 text-amber-400" />
                  Simulate Trigger
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
