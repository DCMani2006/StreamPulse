import React, { useState } from 'react';
import { X, Save, Sliders, ShieldCheck } from 'lucide-react';
import { AlertRuleConfig } from '../types';

interface ZoneConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: AlertRuleConfig;
  onSave: (newConfig: AlertRuleConfig) => void;
}

export const ZoneConfigModal: React.FC<ZoneConfigModalProps> = ({
  isOpen,
  onClose,
  config,
  onSave,
}) => {
  if (!isOpen) return null;

  const [maxPersons, setMaxPersons] = useState<number>(config.max_persons ?? 1);
  const [audioThreshold, setAudioThreshold] = useState<number>(
    config.audio_energy_threshold ?? 0.05
  );
  const [enablePerson, setEnablePerson] = useState<boolean>(
    config.enable_person_alert ?? true
  );
  const [enableZone, setEnableZone] = useState<boolean>(
    config.enable_zone_alert ?? true
  );
  const [enableAudio, setEnableAudio] = useState<boolean>(
    config.enable_audio_alert ?? true
  );

  // Restricted Zone [x1, y1, x2, y2] in percentages
  const defaultZone = config.restricted_zone || [0.2, 0.2, 0.8, 0.8];
  const [zx1, setZx1] = useState<number>(Math.round(defaultZone[0] * 100));
  const [zy1, setZy1] = useState<number>(Math.round(defaultZone[1] * 100));
  const [zx2, setZx2] = useState<number>(Math.round(defaultZone[2] * 100));
  const [zy2, setZy2] = useState<number>(Math.round(defaultZone[3] * 100));

  const handleSave = () => {
    onSave({
      ...config,
      max_persons: maxPersons,
      audio_energy_threshold: audioThreshold,
      enable_person_alert: enablePerson,
      enable_zone_alert: enableZone,
      enable_audio_alert: enableAudio,
      restricted_zone: [zx1 / 100, zy1 / 100, zx2 / 100, zy2 / 100],
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#0e111a] border border-[#222a3d] rounded-2xl p-6 max-w-xl w-full shadow-2xl font-mono text-xs text-slate-200">
        
        {/* Modal Header */}
        <div className="flex justify-between items-center pb-3 border-b border-[#1c2233] mb-4">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-100">
              Sector & Zone Configuration
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-4">
          
          {/* Rule 1: Max Persons */}
          <div className="bg-[#121520] p-3.5 rounded-xl border border-[#1e2436] space-y-2">
            <div className="flex items-center justify-between">
              <label className="font-bold text-slate-300">Max Person Threshold</label>
              <input
                type="checkbox"
                checked={enablePerson}
                onChange={(e) => setEnablePerson(e.target.checked)}
                className="accent-emerald-500 w-4 h-4"
              />
            </div>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="1"
                max="20"
                value={maxPersons}
                disabled={!enablePerson}
                onChange={(e) => setMaxPersons(parseInt(e.target.value))}
                className="flex-1 accent-emerald-500"
              />
              <span className="font-bold text-emerald-400 w-8 text-right">
                {maxPersons}
              </span>
            </div>
          </div>

          {/* Rule 2: Audio Energy Threshold */}
          <div className="bg-[#121520] p-3.5 rounded-xl border border-[#1e2436] space-y-2">
            <div className="flex items-center justify-between">
              <label className="font-bold text-slate-300">Acoustic Energy Spike Threshold (RMS)</label>
              <input
                type="checkbox"
                checked={enableAudio}
                onChange={(e) => setEnableAudio(e.target.checked)}
                className="accent-emerald-500 w-4 h-4"
              />
            </div>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="0.01"
                max="0.50"
                step="0.01"
                value={audioThreshold}
                disabled={!enableAudio}
                onChange={(e) => setAudioThreshold(parseFloat(e.target.value))}
                className="flex-1 accent-emerald-500"
              />
              <span className="font-bold text-amber-400 w-12 text-right">
                {audioThreshold.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Rule 3: Restricted Zone Bounds */}
          <div className="bg-[#121520] p-3.5 rounded-xl border border-[#1e2436] space-y-3">
            <div className="flex items-center justify-between">
              <label className="font-bold text-slate-300 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Default Perimeter ROI (%)
              </label>
              <input
                type="checkbox"
                checked={enableZone}
                onChange={(e) => setEnableZone(e.target.checked)}
                className="accent-emerald-500 w-4 h-4"
              />
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <span className="text-slate-400 block mb-1">X1 (Left): {zx1}%</span>
                <input
                  type="range"
                  min="0"
                  max={zx2 - 5}
                  value={zx1}
                  disabled={!enableZone}
                  onChange={(e) => setZx1(parseInt(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <span className="text-slate-400 block mb-1">X2 (Right): {zx2}%</span>
                <input
                  type="range"
                  min={zx1 + 5}
                  max="100"
                  value={zx2}
                  disabled={!enableZone}
                  onChange={(e) => setZx2(parseInt(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <span className="text-slate-400 block mb-1">Y1 (Top): {zy1}%</span>
                <input
                  type="range"
                  min="0"
                  max={zy2 - 5}
                  value={zy1}
                  disabled={!enableZone}
                  onChange={(e) => setZy1(parseInt(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <span className="text-slate-400 block mb-1">Y2 (Bottom): {zy2}%</span>
                <input
                  type="range"
                  min={zy1 + 5}
                  max="100"
                  value={zy2}
                  disabled={!enableZone}
                  onChange={(e) => setZy2(parseInt(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>
            </div>
          </div>

        </div>

        {/* Modal Actions */}
        <div className="flex justify-end gap-2 mt-6 pt-3 border-t border-[#1c2233]">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-5 py-2 bg-emerald-500 hover:bg-emerald-400 text-black font-bold rounded-lg flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Configuration</span>
          </button>
        </div>

      </div>
    </div>
  );
};
