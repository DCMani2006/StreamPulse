import React, { useState } from 'react';
import { Car, Factory, Building2, Check, Sparkles } from 'lucide-react';
import { IncidentCategory } from '../types';

interface PresetSelectorProps {
  currentPreset?: IncidentCategory;
  onPresetChange?: (preset: IncidentCategory) => void;
}

interface PresetOption {
  id: IncidentCategory;
  name: string;
  shortDesc: string;
  icon: React.ReactNode;
  accentColor: string;
  badge: string;
}

const PRESETS: PresetOption[] = [
  {
    id: 'TRAFFIC',
    name: 'Traffic & Highway Corridor',
    shortDesc: 'Collisions, wrong-way vehicles, stalled cars & lane blockages',
    icon: <Car className="w-4 h-4 text-cyan-400" />,
    accentColor: 'border-cyan-500/40 text-cyan-400 bg-cyan-500/10',
    badge: 'TRAFFIC VLM',
  },
  {
    id: 'INDUSTRIAL_SAFETY',
    name: 'Smart Warehouse & Logistics',
    shortDesc: 'Forklift proximity, PPE compliance, machinery hazards & spills',
    icon: <Factory className="w-4 h-4 text-amber-400" />,
    accentColor: 'border-amber-500/40 text-amber-400 bg-amber-500/10',
    badge: 'OSHA / SAFETY',
  },
  {
    id: 'FACILITY_SECURITY',
    name: 'Campus & Facility Security',
    shortDesc: 'After-hours intrusion, perimeter breaches, loitering & weapons',
    icon: <Building2 className="w-4 h-4 text-purple-400" />,
    accentColor: 'border-purple-500/40 text-purple-400 bg-purple-500/10',
    badge: 'SECURITY 24/7',
  },
];

export const PresetSelector: React.FC<PresetSelectorProps> = ({
  currentPreset = 'TRAFFIC',
  onPresetChange,
}) => {
  const [selected, setSelected] = useState<IncidentCategory>(currentPreset);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);

  const handleSelect = async (presetId: IncidentCategory) => {
    setSelected(presetId);
    if (onPresetChange) {
      onPresetChange(presetId);
    }

    setIsUpdating(true);
    try {
      await fetch('/api/v1/context/preset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset: presetId }),
      });
    } catch (e) {
      console.warn('Failed to update context preset on backend:', e);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 font-mono text-xs">
      <div className="flex items-center gap-1.5 text-slate-400 font-bold uppercase tracking-wider text-[10px] shrink-0 mr-1">
        <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
        <span>VLM Domain:</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 flex-1">
        {PRESETS.map((preset) => {
          const isCurrent = selected === preset.id;
          return (
            <button
              key={preset.id}
              disabled={isUpdating}
              onClick={() => handleSelect(preset.id)}
              className={`p-2.5 rounded-xl border transition-all text-left flex items-center justify-between gap-2 shadow-sm ${
                isCurrent
                  ? `${preset.accentColor} border-current ring-1 ring-emerald-500/40 font-bold`
                  : 'bg-[#121520] border-[#1e2436] text-slate-400 hover:text-slate-200 hover:border-[#2a334a]'
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="p-1 rounded-lg bg-black/40 shrink-0">
                  {preset.icon}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] font-bold truncate text-slate-100">
                      {preset.name}
                    </span>
                  </div>
                  <p className="text-[9px] text-slate-400 truncate mt-0.5">
                    {preset.shortDesc}
                  </p>
                </div>
              </div>

              {isCurrent && (
                <div className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center shrink-0">
                  <Check className="w-2.5 h-2.5" />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};
