import React, { useState } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  Info,
  Clock,
  ChevronRight,
  Eye,
  Cpu,
  Sparkles,
  CheckCircle2,
  Tag,
  ArrowRight,
} from 'lucide-react';
import {
  AlertTrigger,
  ForensicAnomalyIncident,
  IncidentAnalysisResult,
  IncidentCategory,
  SeverityLevel,
} from '../types';

interface IncidentFeedProps {
  incidents: AlertTrigger[];
}

export const IncidentFeed: React.FC<IncidentFeedProps> = ({ incidents }) => {
  const [filter, setFilter] = useState<'all' | 'critical' | 'high_medium'>('all');
  const [selectedIncident, setSelectedIncident] = useState<AlertTrigger | null>(null);

  const filteredIncidents = incidents.filter((inc) => {
    if (filter === 'all') return true;
    const sev = inc.forensic_incident?.vlm_synthesis?.severity || inc.severity;
    if (filter === 'critical') return sev.toUpperCase() === 'CRITICAL';
    if (filter === 'high_medium') return ['HIGH', 'MEDIUM', 'WARNING'].includes(sev.toUpperCase());
    return true;
  });

  const getSeverityBadge = (severity?: string | SeverityLevel) => {
    const s = (severity || 'WARNING').toUpperCase();
    switch (s) {
      case 'CRITICAL':
        return (
          <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-red-500/20 text-red-400 border border-red-500/40 flex items-center gap-1">
            <ShieldAlert className="w-3 h-3" />
            CRITICAL
          </span>
        );
      case 'HIGH':
        return (
          <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-orange-500/20 text-orange-400 border border-orange-500/40 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            HIGH
          </span>
        );
      case 'MEDIUM':
      case 'WARNING':
        return (
          <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/40 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            MEDIUM
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-400 border border-blue-500/40 flex items-center gap-1">
            <Info className="w-3 h-3" />
            LOW
          </span>
        );
    }
  };

  const getCategoryBadge = (category?: IncidentCategory) => {
    const cat = category || 'ANOMALY';
    switch (cat) {
      case 'TRAFFIC':
        return (
          <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            🚗 TRAFFIC
          </span>
        );
      case 'INDUSTRIAL_SAFETY':
        return (
          <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
            🏭 SAFETY
          </span>
        );
      case 'FACILITY_SECURITY':
        return (
          <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30">
            🏢 SECURITY
          </span>
        );
      default:
        return (
          <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            ⚡ ANOMALY
          </span>
        );
    }
  };

  const formatTimestamp = (ts: number) => {
    const d = new Date(ts * 1000);
    const timeStr = d.toLocaleTimeString([], {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    const ms = String(d.getMilliseconds()).padStart(3, '0');
    return `${timeStr}.${ms}`;
  };

  const activeForensic: ForensicAnomalyIncident | undefined = selectedIncident?.forensic_incident;
  const activeVlm: IncidentAnalysisResult | undefined = activeForensic?.vlm_synthesis;

  return (
    <div className="bg-[#0e111a] border border-[#1c2233] rounded-2xl p-4 shadow-sm flex flex-col h-full font-mono">
      
      {/* Feed Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#1c2233]">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-400" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Cloud VLM Incident Dossiers (Gemini 2.5)
          </h2>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#1c2233] text-emerald-400">
            {incidents.length} Verified
          </span>
        </div>

        {/* Severity Filter */}
        <div className="flex items-center gap-1 bg-[#141824] p-0.5 rounded-lg border border-[#222a3d] text-[10px]">
          <button
            onClick={() => setFilter('all')}
            className={`px-2 py-1 rounded transition-all font-semibold ${
              filter === 'all'
                ? 'bg-emerald-500 text-black font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter('critical')}
            className={`px-2 py-1 rounded transition-all font-semibold ${
              filter === 'critical'
                ? 'bg-red-500 text-white font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Critical
          </button>
          <button
            onClick={() => setFilter('high_medium')}
            className={`px-2 py-1 rounded transition-all font-semibold ${
              filter === 'high_medium'
                ? 'bg-amber-500 text-black font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            High/Med
          </button>
        </div>
      </div>

      {/* Incident Cards Feed */}
      <div className="flex-1 overflow-y-auto space-y-3 mt-3 pr-1 max-h-[600px]">
        {filteredIncidents.length > 0 ? (
          filteredIncidents.map((incident, idx) => {
            const vlm = incident.forensic_incident?.vlm_synthesis;
            const title = vlm?.title || incident.message;
            const desc = vlm?.description || incident.message;
            const severity = vlm?.severity || incident.severity;
            const category = vlm?.category;
            const entities = vlm?.entities_involved || [];
            const action = vlm?.recommended_action;

            return (
              <div
                key={incident.id || idx}
                onClick={() => setSelectedIncident(incident)}
                className="bg-[#121520] hover:bg-[#161a28] border border-[#1e2436] hover:border-emerald-500/40 rounded-xl p-3.5 transition-all duration-150 flex flex-col gap-2.5 shadow-md cursor-pointer group"
              >
                {/* Card Top Row: Category, Severity & Timestamp */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {getCategoryBadge(category)}
                    {getSeverityBadge(severity)}
                  </div>
                  <span className="text-[10px] text-slate-400 flex items-center gap-1 shrink-0">
                    <Clock className="w-3 h-3 text-slate-500" />
                    {formatTimestamp(incident.timestamp)}
                  </span>
                </div>

                {/* Card Middle Row: Snapshot + Structured Forensic Content */}
                <div className="flex gap-3">
                  {/* Forensic Snapshot Thumbnail */}
                  {incident.snapshot_url ? (
                    <div className="w-24 h-16 bg-black rounded-lg overflow-hidden shrink-0 border border-[#2a334a] relative group/img">
                      <img
                        src={incident.snapshot_url}
                        alt="Forensic Snapshot"
                        className="w-full h-full object-cover group-hover/img:scale-105 transition-transform"
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/img:opacity-100 flex items-center justify-center transition-opacity">
                        <Eye className="w-3.5 h-3.5 text-white" />
                      </div>
                    </div>
                  ) : (
                    <div className="w-24 h-16 bg-[#1a1f2e] rounded-lg shrink-0 border border-[#2a334a] flex items-center justify-center text-slate-500 text-[10px]">
                      Keyframe
                    </div>
                  )}

                  {/* Title & Forensic Description */}
                  <div className="flex-1 min-w-0 flex flex-col justify-between">
                    <h3 className="text-xs font-bold text-slate-100 group-hover:text-emerald-400 transition-colors line-clamp-1">
                      {title}
                    </h3>
                    <p className="text-[11px] text-slate-300 line-clamp-2 leading-relaxed mt-0.5">
                      {desc}
                    </p>
                  </div>
                </div>

                {/* Entity Pills */}
                {entities.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t border-[#1a1f2e]">
                    <span className="text-[9px] text-slate-500 uppercase flex items-center gap-1">
                      <Tag className="w-2.5 h-2.5" /> Entities:
                    </span>
                    {entities.map((ent, eIdx) => (
                      <span
                        key={eIdx}
                        className="text-[9px] px-1.5 py-0.5 rounded bg-[#1c2233] text-cyan-300 font-semibold border border-[#2a334a]"
                      >
                        {ent}
                      </span>
                    ))}
                  </div>
                )}

                {/* Recommended Action Callout */}
                {action && (
                  <div className="bg-emerald-500/10 border border-emerald-500/25 rounded-lg px-2.5 py-1.5 flex items-center gap-1.5 text-[10px] text-emerald-300">
                    <ArrowRight className="w-3 h-3 text-emerald-400 shrink-0" />
                    <span className="truncate"><b>Action:</b> {action}</span>
                  </div>
                )}

                {/* Footer Badges */}
                <div className="flex items-center justify-between text-[9px] text-slate-500 pt-1">
                  <span>Stream: <b className="text-slate-400">{incident.stream_id}</b></span>
                  <span className="text-emerald-400 font-semibold flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
                    Inspect Gemini Dossier <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            );
          })
        ) : (
          <div className="h-48 flex flex-col items-center justify-center text-slate-500 text-xs text-center p-4">
            <ShieldAlert className="w-8 h-8 text-slate-600 mb-2" />
            <p className="font-semibold text-slate-400">No Incidents Detected</p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Edge gatekeeper filtering normal motion. Gemini VLM standby.
            </p>
          </div>
        )}
      </div>

      {/* Modal: Full High-Fidelity Gemini Incident Dossier */}
      {selectedIncident && (
        <div
          onClick={() => setSelectedIncident(null)}
          className="fixed inset-0 bg-black/85 backdrop-blur-md z-50 flex items-center justify-center p-3 md:p-6 cursor-pointer"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-[#0e111a] border border-[#2a334a] rounded-2xl p-5 max-w-4xl w-full shadow-2xl max-h-[90vh] overflow-y-auto font-mono text-xs space-y-4"
          >
            {/* Modal Header */}
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#1c2233]">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-emerald-400" />
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Cloud VLM Forensic Intelligence Dossier
                  </h3>
                  <span className="text-[10px] text-slate-400">
                    ID: {activeForensic?.incident_id || selectedIncident.id || 'N/A'} • {formatTimestamp(selectedIncident.timestamp)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {activeVlm?.category && getCategoryBadge(activeVlm.category)}
                {getSeverityBadge(activeVlm?.severity || selectedIncident.severity)}
                <button
                  onClick={() => setSelectedIncident(null)}
                  className="text-slate-400 hover:text-white font-bold p-1 text-sm ml-2"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* VLM Headline & Forensic Narrative */}
            <div className="bg-[#141824] border border-[#222a3d] rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-emerald-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" />
                  Gemini 2.5 Flash Structured Synthesis
                </span>
                {activeVlm?.estimated_confidence && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                    Confidence: {Math.round(activeVlm.estimated_confidence * 100)}%
                  </span>
                )}
              </div>
              <h4 className="text-sm font-bold text-slate-100">
                {activeVlm?.title || selectedIncident.message}
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                {activeVlm?.description || selectedIncident.message}
              </p>
            </div>

            {/* Recommended Operator Action Banner */}
            {activeVlm?.recommended_action && (
              <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-3.5 flex items-start gap-2.5 text-xs text-emerald-200">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <b className="text-emerald-400 uppercase tracking-wider text-[10px] block mb-0.5">
                    Automated Recommended Action
                  </b>
                  <p>{activeVlm.recommended_action}</p>
                </div>
              </div>
            )}

            {/* 3-Frame Chronological Temporal Filmstrip */}
            {(() => {
              const temporalFrames =
                activeForensic?.temporal_keyframes ||
                activeForensic?.visual_context?.temporal_keyframes ||
                selectedIncident?.temporal_keyframes ||
                [];

              if (temporalFrames.length === 3) {
                return (
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-1">
                      <span className="text-[11px] font-bold text-slate-300 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-emerald-400" />
                        Chronological Temporal Keyframe Sequence
                      </span>
                      <span className="text-[10px] text-emerald-400 font-bold font-mono bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                        Multi-Part Temporal VLM Analysis (T-1s ➔ T0 ➔ T+1s)
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                      {/* Frame 1: T-1s Pre-Event */}
                      <div className="bg-[#0b0e17] border border-[#222a3d] rounded-xl overflow-hidden flex flex-col">
                        <div className="px-2.5 py-1 bg-[#141824] border-b border-[#222a3d] flex items-center justify-between text-[10px]">
                          <span className="text-slate-400 font-bold">1. Pre-Event</span>
                          <span className="text-slate-500 font-mono">T - 1.0s</span>
                        </div>
                        <div className="aspect-video bg-black flex items-center justify-center overflow-hidden">
                          <img
                            src={temporalFrames[0]}
                            alt="T-1s Pre-Event"
                            className="w-full h-full object-contain"
                          />
                        </div>
                      </div>

                      {/* Frame 2: T0 Trigger Keyframe */}
                      <div className="bg-[#0b0e17] border-2 border-red-500 ring-2 ring-red-500/30 rounded-xl overflow-hidden flex flex-col shadow-lg">
                        <div className="px-2.5 py-1 bg-red-600 text-white flex items-center justify-between text-[10px] font-bold">
                          <span className="flex items-center gap-1">⚡ Trigger Keyframe</span>
                          <span className="font-mono">T 0</span>
                        </div>
                        <div className="aspect-video bg-black flex items-center justify-center overflow-hidden">
                          <img
                            src={temporalFrames[1]}
                            alt="T0 Trigger Keyframe"
                            className="w-full h-full object-contain"
                          />
                        </div>
                      </div>

                      {/* Frame 3: T+1s Post-Event */}
                      <div className="bg-[#0b0e17] border border-[#222a3d] rounded-xl overflow-hidden flex flex-col">
                        <div className="px-2.5 py-1 bg-[#141824] border-b border-[#222a3d] flex items-center justify-between text-[10px]">
                          <span className="text-slate-400 font-bold">3. Post-Event</span>
                          <span className="text-slate-500 font-mono">T + 1.0s</span>
                        </div>
                        <div className="aspect-video bg-black flex items-center justify-center overflow-hidden">
                          <img
                            src={temporalFrames[2]}
                            alt="T+1s Post-Event"
                            className="w-full h-full object-contain"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              }

              // Fallback single snapshot
              return (
                <div className="space-y-2">
                  <span className="text-[11px] font-bold text-slate-300 flex items-center gap-1.5">
                    <Eye className="w-3.5 h-3.5 text-emerald-400" />
                    Forensic Keyframe Capture
                  </span>
                  <div className="bg-black rounded-xl overflow-hidden border border-[#2a334a] relative aspect-video flex items-center justify-center">
                    <img
                      src={activeForensic?.visual_context?.snapshot_annotated_base64 || selectedIncident.snapshot_url}
                      alt="Forensic Keyframe"
                      className="w-full h-full object-contain"
                    />
                  </div>
                </div>
              );
            })()}

            {/* Entities Involved & Multimodal Telemetry Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Entities Identified */}
              <div className="bg-[#121520] border border-[#1e2436] rounded-xl p-3 space-y-2">
                <span className="text-[11px] font-bold text-cyan-400 flex items-center gap-1.5">
                  <Tag className="w-3.5 h-3.5" /> Entities Observed
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {activeVlm?.entities_involved && activeVlm.entities_involved.length > 0 ? (
                    activeVlm.entities_involved.map((e, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 rounded bg-[#1c2233] text-cyan-300 font-semibold border border-[#2a334a] text-xs"
                      >
                        {e}
                      </span>
                    ))
                  ) : (
                    <span className="text-slate-500">None specified</span>
                  )}
                </div>
              </div>

              {/* Multimodal Telemetry */}
              <div className="bg-[#121520] border border-[#1e2436] rounded-xl p-3 space-y-2">
                <span className="text-[11px] font-bold text-purple-400 flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5" /> Edge & Cloud Telemetry
                </span>
                <div className="space-y-1 text-slate-300">
                  <div className="flex justify-between py-1 border-b border-[#1c2233]">
                    <span className="text-slate-400">VLM Token Payload:</span>
                    <strong className="text-emerald-400">258 Input Tokens</strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#1c2233]">
                    <span className="text-slate-400">Visual Delta Score:</span>
                    <strong className="text-cyan-400">
                      {activeForensic?.decision_basis?.visual_trigger?.observed !== undefined
                        ? `${(Number(activeForensic.decision_basis.visual_trigger.observed) * 100).toFixed(1)}%`
                        : '12.4%'}
                    </strong>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Acoustic Surge:</span>
                    <strong className="text-amber-400">
                      {activeForensic?.decision_basis?.audio_trigger?.delta_percentage || '-18.5 dBFS'}
                    </strong>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end pt-2 border-t border-[#1c2233]">
              <button
                onClick={() => setSelectedIncident(null)}
                className="bg-[#141824] hover:bg-[#1d2334] text-white border border-[#2a334a] font-bold px-4 py-1.5 rounded-lg transition-all"
              >
                Close Dossier
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};
