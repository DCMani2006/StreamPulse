import React, { useState, useEffect } from 'react';
import {
  GitMerge,
  ArrowRight,
  Camera,
  CheckCircle2,
} from 'lucide-react';
import { CorrelatedMultiCameraIncident } from '../types';
import { getBackendApiUrl } from '../config/api';

interface GlobalIncidentTimelineProps {
  apiBaseUrl?: string;
  onSelectIncident?: (incident: any) => void;
}

export const GlobalIncidentTimeline: React.FC<GlobalIncidentTimelineProps> = ({
  apiBaseUrl,
  onSelectIncident,
}) => {
  const resolvedApiBaseUrl = apiBaseUrl || getBackendApiUrl();
  const [activeTab, setActiveTab] = useState<'correlated' | 'unified'>('correlated');
  const [correlatedList, setCorrelatedList] = useState<CorrelatedMultiCameraIncident[]>([]);
  const [unifiedEvents, setUnifiedEvents] = useState<any[]>([]);

  // Poll backend endpoints
  const fetchTimelineData = async () => {
    try {
      const [corrRes, uniRes] = await Promise.all([
        fetch(`${resolvedApiBaseUrl}/api/v1/incidents/correlated?limit=20`),
        fetch(`${resolvedApiBaseUrl}/api/v1/timeline/unified?limit=30`),
      ]);

      if (corrRes.ok) {
        const data = await corrRes.json();
        setCorrelatedList(data);
      }
      if (uniRes.ok) {
        const data = await uniRes.json();
        setUnifiedEvents(data);
      }
    } catch (e) {
      // Graceful fallback for local offline simulation
    }
  };

  useEffect(() => {
    fetchTimelineData();
    const interval = setInterval(fetchTimelineData, 4000);
    return () => clearInterval(interval);
  }, [apiBaseUrl]);

  // Demo fallback if no incidents recorded yet
  const demoCorrelatedList: CorrelatedMultiCameraIncident[] = [
    {
      type: 'CORRELATED_INCIDENT',
      correlation_id: 'corr_demo_9812',
      timestamp: Date.now() / 1000 - 45,
      timestamp_utc: new Date(Date.now() - 45000).toISOString(),
      streams_involved: ['cam_04', 'cam_02'],
      title: 'Multi-Zone Security Progression: Perimeter Breach ➔ Warehouse Bay A Entry',
      severity: 'CRITICAL',
      entities_involved: ['person', 'backpack', 'forklift'],
      progression: [
        {
          time: '10:31:02',
          stream_id: 'cam_04',
          camera_name: 'Camera 04 - Perimeter Security Zone',
          event: 'Perimeter Boundary Motion & Fence Breach',
          severity: 'HIGH',
        },
        {
          time: '10:31:24',
          stream_id: 'cam_02',
          camera_name: 'Camera 02 - Warehouse Interior (Bay A)',
          event: 'Unauthorized Zone Access & Heavy Machinery Vicinity',
          severity: 'CRITICAL',
        },
      ],
      recommended_action: 'Dispatch security patrol to Warehouse Bay North immediately. Verify facility access badge.',
    },
    {
      type: 'CORRELATED_INCIDENT',
      correlation_id: 'corr_demo_4419',
      timestamp: Date.now() / 1000 - 120,
      timestamp_utc: new Date(Date.now() - 120000).toISOString(),
      streams_involved: ['cam_01', 'cam_03'],
      title: 'Traffic & Freight Sync: Heavy Vehicle Tailgate ➔ Loading Dock Staging',
      severity: 'HIGH',
      entities_involved: ['truck', 'car'],
      progression: [
        {
          time: '10:28:15',
          stream_id: 'cam_01',
          camera_name: 'Camera 01 - Main Entrance (North Gate)',
          event: 'Restricted Lane Entry without Deceleration',
          severity: 'HIGH',
        },
        {
          time: '10:28:48',
          stream_id: 'cam_03',
          camera_name: 'Camera 03 - Loading Dock & Freight',
          event: 'Unscheduled Cargo Staging & Proximity Warning',
          severity: 'MEDIUM',
        },
      ],
      recommended_action: 'Alert dock master to halt forklift movement until truck confirms clearance.',
    },
  ];

  const displayedCorrelated = correlatedList.length > 0 ? correlatedList : demoCorrelatedList;

  return (
    <div className="bg-[#0e111a] border border-[#1c2233] rounded-2xl p-4 shadow-sm flex flex-col font-mono text-xs space-y-3">
      {/* Header & Tab Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#1c2233]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
            <GitMerge className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Cross-Stream Event Correlation Engine
            </h3>
            <span className="text-[10px] text-slate-400">
              60s Multi-Camera Temporal Aggregator & Incident Chains
            </span>
          </div>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-1 bg-[#141824] p-0.5 rounded-lg border border-[#222a3d] text-[10px]">
          <button
            onClick={() => setActiveTab('correlated')}
            className={`px-2.5 py-1 rounded transition-all font-semibold ${
              activeTab === 'correlated'
                ? 'bg-purple-600 text-white font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Correlated Chains ({displayedCorrelated.length})
          </button>
          <button
            onClick={() => setActiveTab('unified')}
            className={`px-2.5 py-1 rounded transition-all font-semibold ${
              activeTab === 'unified'
                ? 'bg-purple-600 text-white font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Unified Feed
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="space-y-3 overflow-y-auto max-h-[520px] pr-1">
        {activeTab === 'correlated' ? (
          displayedCorrelated.map((corr) => (
            <div
              key={corr.correlation_id}
              onClick={() => onSelectIncident?.(corr)}
              className="bg-[#121522] border border-[#232b40] hover:border-purple-500/50 rounded-xl p-3.5 space-y-3 transition-all shadow-md group cursor-pointer"
            >
              {/* Chain Header */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40">
                    🔗 MULTI-CAMERA CHAIN
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    ID: {corr.correlation_id}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`text-[9px] font-bold px-2 py-0.5 rounded ${
                      corr.severity === 'CRITICAL'
                        ? 'bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse'
                        : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                    }`}
                  >
                    {corr.severity}
                  </span>
                </div>
              </div>

              {/* Title */}
              <h4 className="text-xs font-bold text-slate-100 group-hover:text-purple-300 transition-colors">
                {corr.title}
              </h4>

              {/* Visual Progression Timeline Flow */}
              <div className="bg-[#0b0e17] border border-[#1a2030] rounded-xl p-3 space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Temporal Camera Progression:
                </span>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                  {corr.progression.map((step, idx) => (
                    <React.Fragment key={idx}>
                      <div className="flex-1 bg-[#141826] border border-[#252f47] rounded-lg p-2.5 space-y-1">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-purple-300 font-bold flex items-center gap-1">
                            <Camera className="w-3 h-3" /> {step.stream_id.toUpperCase()}
                          </span>
                          <span className="text-slate-400 font-mono">{step.time}</span>
                        </div>
                        <span className="text-[10px] text-slate-300 font-semibold block line-clamp-1">
                          {step.event}
                        </span>
                        <span className="text-[9px] text-slate-500 block truncate">
                          {step.camera_name}
                        </span>
                      </div>

                      {idx < corr.progression.length - 1 && (
                        <div className="flex items-center justify-center text-purple-400 py-1 sm:py-0">
                          <ArrowRight className="w-4 h-4 shrink-0 rotate-90 sm:rotate-0" />
                        </div>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>

              {/* Recommended Action & Entity Tags */}
              <div className="space-y-2">
                {corr.recommended_action && (
                  <div className="bg-purple-500/10 border border-purple-500/25 rounded-lg p-2.5 text-[10px] text-purple-200 flex items-start gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                    <div>
                      <b className="text-purple-300 uppercase tracking-wider text-[9px] block">
                        Cross-Stream Response Directive:
                      </b>
                      <span>{corr.recommended_action}</span>
                    </div>
                  </div>
                )}

                {corr.entities_involved && corr.entities_involved.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap text-[9px]">
                    <span className="text-slate-500">Tracked Entities:</span>
                    {corr.entities_involved.map((ent, eIdx) => (
                      <span
                        key={eIdx}
                        className="px-1.5 py-0.5 rounded bg-[#1c2233] text-cyan-300 font-semibold border border-[#2a334a]"
                      >
                        {ent}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className="space-y-2">
            {unifiedEvents.length > 0 ? (
              unifiedEvents.map((evt, idx) => (
                <div
                  key={idx}
                  className="bg-[#121522] border border-[#1e2538] rounded-xl p-2.5 flex items-center justify-between text-[11px]"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500 font-mono text-[10px]">{evt.time_str}</span>
                    <span className="text-purple-300 font-bold">[{evt.stream_id}]</span>
                    <span className="text-slate-200 font-semibold">{evt.title}</span>
                  </div>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#1c2233] text-slate-300">
                    {evt.severity || 'INFO'}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-slate-500 text-xs">
                No active events logged in current timeline window.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
