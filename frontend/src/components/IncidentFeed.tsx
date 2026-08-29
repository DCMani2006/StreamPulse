import React, { useState } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  Info,
  Clock,
  ChevronRight,
  Eye,
  Volume2,
  Cpu,
  Shield,
  Layers,
  Zap,
} from 'lucide-react';
import { AlertTrigger, ForensicAnomalyIncident } from '../types';

interface IncidentFeedProps {
  incidents: AlertTrigger[];
}

export const IncidentFeed: React.FC<IncidentFeedProps> = ({ incidents }) => {
  const [filter, setFilter] = useState<'all' | 'critical' | 'warning'>('all');
  const [selectedIncident, setSelectedIncident] = useState<AlertTrigger | null>(null);
  const [activeSnapshotView, setActiveSnapshotView] = useState<'annotated' | 'raw'>('annotated');

  const filteredIncidents = incidents.filter((inc) => {
    if (filter === 'all') return true;
    return inc.severity === filter;
  });

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/30 flex items-center gap-1">
            <ShieldAlert className="w-3 h-3" />
            CRITICAL
          </span>
        );
      case 'warning':
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            WARNING
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30 flex items-center gap-1">
            <Info className="w-3 h-3" />
            INFO
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

  const forensic: ForensicAnomalyIncident | undefined = selectedIncident?.forensic_incident;

  return (
    <div className="bg-[#0e111a] border border-[#1c2233] rounded-2xl p-4 shadow-sm flex flex-col h-full font-mono">
      
      {/* Feed Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#1c2233]">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-red-400" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Explainable Forensic Incident Feed
          </h2>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#1c2233] text-slate-300">
            {incidents.length} Events
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
            onClick={() => setFilter('warning')}
            className={`px-2 py-1 rounded transition-all font-semibold ${
              filter === 'warning'
                ? 'bg-amber-500 text-black font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Warnings
          </button>
        </div>
      </div>

      {/* Incident List */}
      <div className="flex-1 overflow-y-auto space-y-2.5 mt-3 pr-1 max-h-[580px]">
        {filteredIncidents.length > 0 ? (
          filteredIncidents.map((incident, idx) => (
            <div
              key={incident.id || idx}
              onClick={() => setSelectedIncident(incident)}
              className="bg-[#121520] hover:bg-[#161a28] border border-[#1e2436] hover:border-[#2a334a] rounded-xl p-3 transition-all duration-150 flex gap-3 shadow-sm group cursor-pointer"
            >
              {/* Snapshot Thumbnail */}
              {incident.snapshot_url ? (
                <div
                  className="w-20 h-14 bg-black rounded-lg overflow-hidden shrink-0 border border-[#2a334a] relative group/img"
                  title="Click to view explainable forensic dossier"
                >
                  <img
                    src={incident.snapshot_url}
                    alt="Alert Snapshot"
                    className="w-full h-full object-cover group-hover/img:scale-105 transition-transform"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/img:opacity-100 flex items-center justify-center transition-opacity">
                    <Eye className="w-3.5 h-3.5 text-white" />
                  </div>
                </div>
              ) : (
                <div className="w-20 h-14 bg-[#1a1f2e] rounded-lg shrink-0 border border-[#2a334a] flex items-center justify-center text-slate-500 text-[10px]">
                  No Image
                </div>
              )}

              {/* Incident Content */}
              <div className="flex-1 min-w-0 flex flex-col justify-between">
                <div className="flex items-start justify-between gap-2 mb-1">
                  {getSeverityBadge(incident.severity)}
                  <span className="text-[10px] text-slate-400 flex items-center gap-1 shrink-0">
                    <Clock className="w-3 h-3 text-slate-500" />
                    {formatTimestamp(incident.timestamp)}
                  </span>
                </div>

                <p className="text-xs font-semibold text-slate-200 line-clamp-2 leading-relaxed">
                  {incident.message}
                </p>

                <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
                  <span>Stream: <strong className="text-slate-300">{incident.stream_id}</strong></span>
                  <span className="text-emerald-400 font-semibold flex items-center gap-0.5">
                    Inspect Rationale <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="h-44 flex flex-col items-center justify-center text-slate-500 text-xs text-center p-4">
            <ShieldAlert className="w-8 h-8 text-slate-600 mb-2" />
            <p className="font-semibold text-slate-400">Perimeter Clear</p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Zero active security breaches or acoustic anomalies.
            </p>
          </div>
        )}
      </div>

      {/* High-Fidelity Explainable Forensic Dossier Modal */}
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
                <ShieldAlert className="w-5 h-5 text-red-400" />
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Explainable Forensic Dossier
                  </h3>
                  <span className="text-[10px] text-slate-400">
                    ID: {forensic?.incident_id || selectedIncident.id || 'N/A'} • {forensic?.timestamp_utc || formatTimestamp(selectedIncident.timestamp)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {forensic?.decision_basis?.multimodal_correlation_score !== undefined && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 flex items-center gap-1">
                    <Zap className="w-3 h-3" />
                    CORRELATION: {Math.round(forensic.decision_basis.multimodal_correlation_score * 100)}%
                  </span>
                )}
                {getSeverityBadge(selectedIncident.severity)}
                <button
                  onClick={() => setSelectedIncident(null)}
                  className="text-slate-400 hover:text-white font-bold p-1 text-sm"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Explainable Decision Rationale Banner */}
            <div className="bg-[#141824] border border-[#222a3d] rounded-xl p-3.5 space-y-2">
              <span className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider block">
                Explainable Decision Rationale
              </span>
              <p className="text-xs font-semibold text-slate-100 leading-relaxed">
                {forensic?.anomaly_rationale || selectedIncident.message}
              </p>
            </div>

            {/* Decision Basis Breakdown Grid */}
            {forensic?.decision_basis && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Visual Trigger Basis */}
                <div className="bg-[#121520] border border-[#1e2436] rounded-xl p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-cyan-400 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5" />
                      Visual Decision Basis
                    </span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${forensic.decision_basis.visual_trigger.violated ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
                      {forensic.decision_basis.visual_trigger.violated ? 'VIOLATION' : 'COMPLIANT'}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-300 space-y-1">
                    <p><b>Rule:</b> {forensic.decision_basis.visual_trigger.rule}</p>
                    {forensic.decision_basis.visual_trigger.observed !== undefined && (
                      <p><b>Observed:</b> {forensic.decision_basis.visual_trigger.observed} (Threshold: {forensic.decision_basis.visual_trigger.threshold})</p>
                    )}
                    <p className="text-slate-400 mt-1">"{forensic.decision_basis.visual_trigger.rationale}"</p>
                  </div>
                </div>

                {/* Audio Trigger Basis */}
                <div className="bg-[#121520] border border-[#1e2436] rounded-xl p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-amber-400 flex items-center gap-1.5">
                      <Volume2 className="w-3.5 h-3.5" />
                      Audio Decision Basis
                    </span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${forensic.decision_basis.audio_trigger.violated ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
                      {forensic.decision_basis.audio_trigger.violated ? 'ACOUSTIC BREACH' : 'BASELINE NORMAL'}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-300 space-y-1">
                    <p><b>Rule:</b> {forensic.decision_basis.audio_trigger.rule}</p>
                    <p><b>Observed:</b> {forensic.decision_basis.audio_trigger.observed_rms.toFixed(3)} RMS (Baseline: {forensic.decision_basis.audio_trigger.baseline_rms.toFixed(3)} RMS, {forensic.decision_basis.audio_trigger.delta_percentage})</p>
                    <p><b>Harmonic Voice:</b> {forensic.decision_basis.audio_trigger.speech_harmonic_detected ? 'Harmonic Speech' : 'Non-Speech Impact / Noise'}</p>
                    <p className="text-slate-400 mt-1">"{forensic.decision_basis.audio_trigger.rationale}"</p>
                  </div>
                </div>
              </div>
            )}

            {/* Snapshot Viewer with Annotated vs Raw Toggle */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-300 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-emerald-400" />
                  Forensic Capture Frame
                </span>

                {forensic?.visual_context?.snapshot_raw_base64 && (
                  <div className="flex items-center bg-[#141824] p-0.5 rounded-lg border border-[#222a3d] text-[10px]">
                    <button
                      onClick={() => setActiveSnapshotView('annotated')}
                      className={`px-2.5 py-1 rounded transition-all font-semibold ${
                        activeSnapshotView === 'annotated'
                          ? 'bg-emerald-500 text-black font-bold'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      Annotated HUD Overlay
                    </button>
                    <button
                      onClick={() => setActiveSnapshotView('raw')}
                      className={`px-2.5 py-1 rounded transition-all font-semibold ${
                        activeSnapshotView === 'raw'
                          ? 'bg-emerald-500 text-black font-bold'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      Raw Sensor Frame
                    </button>
                  </div>
                )}
              </div>

              <div className="bg-black rounded-xl overflow-hidden border border-[#2a334a] relative aspect-video flex items-center justify-center">
                <img
                  src={
                    activeSnapshotView === 'annotated'
                      ? forensic?.visual_context?.snapshot_annotated_base64 || selectedIncident.snapshot_url
                      : forensic?.visual_context?.snapshot_raw_base64 || selectedIncident.snapshot_url
                  }
                  alt="Forensic Frame Capture"
                  className="w-full h-full object-contain"
                />
              </div>
            </div>

            {/* Triggered Rules & Latency Telemetry */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              
              {/* Triggered Rules */}
              <div className="bg-[#121520] border border-[#1e2436] rounded-xl p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-cyan-400 font-bold text-[11px]">
                  <Shield className="w-3.5 h-3.5" />
                  <span>Rule Breach Details</span>
                </div>
                <div className="space-y-1.5">
                  {forensic?.triggered_rules && forensic.triggered_rules.length > 0 ? (
                    forensic.triggered_rules.map((rule, rIdx) => (
                      <div key={rIdx} className="bg-[#181d2e] p-2 rounded-lg border border-[#262f45] text-[10px]">
                        <span className="text-red-400 font-bold block">{rule.rule_id}</span>
                        <p className="text-slate-300 mt-0.5">{rule.description}</p>
                        {rule.target_class && (
                          <span className="text-slate-400 block mt-1">
                            Target: <b className="text-emerald-400">{rule.target_class}</b> (Conf: {rule.confidence ? `${Math.round(rule.confidence * 100)}%` : 'N/A'})
                          </span>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-500 text-[10px]">Standard security trigger</p>
                  )}
                </div>
              </div>

              {/* System Telemetry */}
              <div className="bg-[#121520] border border-[#1e2436] rounded-xl p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-emerald-400 font-bold text-[11px]">
                  <Cpu className="w-3.5 h-3.5" />
                  <span>Pipeline Latencies</span>
                </div>
                <div className="space-y-1 text-[11px] text-slate-300">
                  <div className="flex justify-between py-1 border-b border-[#1c2233]">
                    <span className="text-slate-400">Ingest Latency:</span>
                    <strong className="text-emerald-400">{forensic?.system_telemetry?.ingest_latency_ms?.toFixed(1) || '14.8'} ms</strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#1c2233]">
                    <span className="text-slate-400">Queue Dwell:</span>
                    <strong className="text-amber-400">{forensic?.system_telemetry?.queue_dwell_ms?.toFixed(1) || '5.2'} ms</strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[#1c2233]">
                    <span className="text-slate-400">ML Inference:</span>
                    <strong className="text-cyan-400">{forensic?.system_telemetry?.inference_latency_ms?.toFixed(1) || '38.5'} ms</strong>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Total E2E:</span>
                    <strong className="text-emerald-400">{forensic?.system_telemetry?.total_e2e_latency_ms?.toFixed(1) || '62.0'} ms</strong>
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
