import React, { useRef, useEffect, useState } from 'react';
import {
  Video,
  Upload,
  Link,
  Radio,
  Sliders,
  AlertTriangle,
  Camera,
  Play,
  Pause,
  Film,
  CameraOff,
  CheckCircle,
  Loader2,
  FileVideo,
  RefreshCw,
} from 'lucide-react';
import { StreamTelemetryPayload, StreamSourceType, PresetScenario } from '../types';
import { LiveVisionCanvas } from './LiveVisionCanvas';

interface VideoStageProps {
  videoRef: React.RefObject<HTMLVideoElement>;
  overlayCanvasRef: React.RefObject<HTMLCanvasElement>;
  streamSource: StreamSourceType;
  setStreamSource: (source: StreamSourceType) => void;
  loadVideoFile: (file: File) => void;
  loadVideoUrl: (url: string) => void;
  loadPresetScenario: (url: string) => void;
  startWebcam: () => void;
  latestTelemetry: StreamTelemetryPayload | null;
  currentFps: number;
  cameraActive: boolean;
  cameraError: string | null;
  isLoadingMedia?: boolean;
  confidenceThreshold: number;
  setConfidenceThreshold: (val: number) => void;
  streamId: string;
  isBackendConnected: boolean;
  onTakeSnapshot: () => void;
}

const PRESET_SCENARIOS: PresetScenario[] = [
  {
    id: 'traffic',
    title: 'Traffic Highway Feed',
    subtitle: 'Vehicle Collision & Accident Test',
    description: 'Real-time multi-vehicle tracking with autonomous high-impact crash and traffic collision detection.',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    zone: [0.0, 0.0, 1.0, 1.0],
    tags: ['Traffic Feed', 'Vehicle Collision', 'Crash Detection'],
  },
  {
    id: 'proctoring',
    title: 'Proctoring & Facility Cam',
    subtitle: 'Multi-Person & Prohibited Items',
    description: 'Autonomous monitoring detecting unauthorized persons, devices, and prohibited items.',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
    zone: [0.0, 0.0, 1.0, 1.0],
    tags: ['Facility', 'Device Detection', 'Prohibited Items'],
  },
  {
    id: 'night',
    title: 'Night Infrastructure',
    subtitle: 'Kinetic Motion & Transient Spikes',
    description: 'Surveillance feed with sub-300ms multi-modal incident trigger dispatch.',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
    zone: [0.0, 0.0, 1.0, 1.0],
    tags: ['Perimeter', 'Motion Spikes', 'Low Latency'],
  },
];

const QUICK_SAMPLE_URLS = [
  {
    name: 'Sample 1 (Blazes)',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
  },
  {
    name: 'Sample 2 (Bunny)',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
  },
  {
    name: 'Sample 3 (Elephants)',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
  },
];

export const VideoStage: React.FC<VideoStageProps> = ({
  videoRef,
  overlayCanvasRef,
  streamSource,
  setStreamSource: _setStreamSource,
  loadVideoFile,
  loadVideoUrl,
  loadPresetScenario,
  startWebcam,
  latestTelemetry,
  currentFps,
  cameraActive,
  cameraError,
  isLoadingMedia,
  confidenceThreshold,
  setConfidenceThreshold,
  streamId,
  isBackendConnected: _isBackendConnected,
  onTakeSnapshot,
}) => {
  const [hudTime, setHudTime] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'source' | 'upload' | 'url' | 'presets'>('source');
  const [urlInput, setUrlInput] = useState<string>('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4');
  const [selectedPresetId, setSelectedPresetId] = useState<string>('campus');
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Live HUD Millisecond Clock
  useEffect(() => {
    const timer = setInterval(() => {
      const d = new Date();
      const timeStr = d.toLocaleTimeString([], {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      const ms = String(d.getMilliseconds()).padStart(3, '0');
      setHudTime(`${timeStr}.${ms}`);
    }, 50);
    return () => clearInterval(timer);
  }, []);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setUploadedFileName(file.name);
      loadVideoFile(file);
      setIsPlaying(true);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setUploadedFileName(file.name);
      loadVideoFile(file);
      setIsPlaying(true);
      e.target.value = '';
    }
  };

  const togglePlayback = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().then(() => setIsPlaying(true)).catch(console.warn);
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlInput && urlInput.trim()) {
      loadVideoUrl(urlInput.trim());
      setIsPlaying(true);
    }
  };

  const handlePresetSelect = (preset: PresetScenario) => {
    setSelectedPresetId(preset.id);
    loadPresetScenario(preset.videoUrl);
    setIsPlaying(true);
  };

  const isTriggerFired = Boolean(
    latestTelemetry?.trigger_fired ||
    (latestTelemetry?.alerts && latestTelemetry.alerts.length > 0) ||
    latestTelemetry?.forensic_incident
  );

  return (
    <div className="flex flex-col gap-3 font-mono">
      
      {/* Video Container Stage */}
      <div className={`relative bg-[#07090e] border ${
        isTriggerFired
          ? 'border-amber-400 ring-4 ring-amber-500/30 shadow-2xl shadow-amber-500/20'
          : 'border-[#1c2233]'
      } rounded-2xl overflow-hidden shadow-2xl aspect-[16/9] flex items-center justify-center transition-all duration-200 group`}>
        
        {/* Live Camera / Video Stream Element */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          loop
          className="w-full h-full object-cover"
        />

        {/* Loading Spinner Indicator */}
        {isLoadingMedia && (
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm flex flex-col items-center justify-center gap-2 z-30">
            <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
            <span className="text-xs text-emerald-400 font-bold">Loading Video Stream...</span>
          </div>
        )}

        {/* Camera Permission / Error Fallback Screen */}
        {((streamSource === 'webcam' && !cameraActive && !isLoadingMedia) || cameraError) && (
          <div className="absolute inset-0 bg-[#090b12]/95 flex flex-col items-center justify-center p-6 text-center z-10">
            <CameraOff className="w-12 h-12 text-slate-500 mb-3" />
            <h3 className="text-base font-bold text-slate-200 font-mono">
              Stream Source Initialization
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mt-1 mb-4 font-mono">
              {cameraError || 'Requesting browser camera access. Please allow camera permissions in your browser.'}
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              <button
                onClick={startWebcam}
                className="bg-emerald-600 hover:bg-emerald-500 text-black font-bold text-xs px-4 py-2 rounded-lg transition-all"
              >
                Retry Webcam
              </button>
              <button
                onClick={() => {
                  setActiveTab('url');
                  loadVideoUrl('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4');
                }}
                className="bg-[#141824] hover:bg-[#1d2334] text-emerald-400 border border-emerald-500/30 text-xs font-semibold px-4 py-2 rounded-lg transition-all"
              >
                Load Direct Stream URL
              </button>
              <button
                onClick={() => {
                  setActiveTab('presets');
                  handlePresetSelect(PRESET_SCENARIOS[0]);
                }}
                className="bg-[#141824] hover:bg-[#1d2334] text-white border border-[#262f45] text-xs font-semibold px-4 py-2 rounded-lg transition-all"
              >
                Load Preset Scenario
              </button>
            </div>
          </div>
        )}

        {/* Interactive Draggable ROI & Dynamic Detection Overlay */}
        <div className="absolute inset-0 w-full h-full z-20 pointer-events-auto">
          <LiveVisionCanvas
            canvasRef={overlayCanvasRef}
            latestTelemetry={latestTelemetry}
            confidenceThreshold={confidenceThreshold}
            streamId={streamId}
          />
        </div>

        {/* On-Screen HUD Overlay (Top-Left Source & Millisecond Clock) */}
        <div className="absolute top-3.5 left-3.5 z-30 flex items-center gap-2 pointer-events-none">
          <div className="bg-black/80 backdrop-blur-md border border-white/10 px-3 py-1 rounded-lg text-xs font-semibold text-slate-200 flex items-center gap-2 shadow-lg">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>
              CAM-01: {streamSource.toUpperCase()}
            </span>
            <span className="text-slate-500">|</span>
            <span className="text-emerald-400">{hudTime}</span>
          </div>

          {/* Edge Gatekeeper Active Status Pill */}
          <div className="hidden sm:flex items-center gap-1.5 bg-black/80 backdrop-blur-md border border-emerald-500/30 px-2.5 py-1 rounded-lg text-[10px] font-bold text-emerald-400 shadow-lg">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
            <span>
              {isTriggerFired
                ? '⚡ Candidate Event (VLM Dispatch)'
                : latestTelemetry?.is_static
                ? '🟢 Edge Gatekeeper: Static Filtered (<1.5ms)'
                : '🟢 Edge Gatekeeper: Active (Filtering >95%)'}
            </span>
          </div>
        </div>

        {/* On-Screen HUD Overlay (Top-Right FPS & Active Alert) */}
        <div className="absolute top-3.5 right-3.5 z-30 flex items-center gap-2 pointer-events-none">
          <div className="bg-black/80 backdrop-blur-md border border-white/10 px-2.5 py-1 rounded-lg text-xs font-semibold text-emerald-400 flex items-center gap-1.5 shadow-lg">
            <Radio className="w-3.5 h-3.5" />
            <span>{currentFps > 0 ? `${currentFps}.0` : '10.0'} FPS</span>
          </div>

          {latestTelemetry?.alerts && latestTelemetry.alerts.length > 0 && (
            <div className="bg-red-600/90 backdrop-blur-md text-white border border-red-400 px-3 py-1 rounded-lg text-xs font-bold animate-pulse shadow-lg flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>{latestTelemetry.vlm_synthesis?.title || latestTelemetry.alerts[0].message || '💥 ACTIVE INCIDENT DETECTED'}</span>
            </div>
          )}
        </div>

      </div>

      {/* Media Ingestion & Scenario Selection Bar */}
      <div className="bg-[#0e111a] border border-[#1c2233] rounded-xl p-3 flex flex-col gap-3 shadow-sm">
        
        {/* Source Navigation Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-[#1c2233]">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 text-[11px] font-bold uppercase tracking-wider">
              Ingest Source:
            </span>
            <div className="flex items-center bg-[#141824] p-1 rounded-lg border border-[#222a3d] text-xs">
              <button
                onClick={() => {
                  setActiveTab('source');
                  startWebcam();
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
                  streamSource === 'webcam' && activeTab === 'source'
                    ? 'bg-emerald-500 text-black font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Video className="w-3.5 h-3.5" />
                <span>Local Webcam</span>
              </button>

              <button
                onClick={() => setActiveTab('upload')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
                  streamSource === 'file' || activeTab === 'upload'
                    ? 'bg-emerald-500 text-black font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Video Upload</span>
              </button>

              <button
                onClick={() => setActiveTab('url')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
                  streamSource === 'url' && activeTab === 'url'
                    ? 'bg-emerald-500 text-black font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Link className="w-3.5 h-3.5" />
                <span>Direct URL</span>
              </button>

              <button
                onClick={() => setActiveTab('presets')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
                  streamSource === 'preset' || activeTab === 'presets'
                    ? 'bg-emerald-500 text-black font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Film className="w-3.5 h-3.5" />
                <span>Preset Scenarios</span>
              </button>
            </div>
          </div>

          {/* Confidence Slider */}
          <div className="flex items-center gap-3 bg-[#141824] px-3 py-1.5 rounded-lg border border-[#222a3d]">
            <Sliders className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400 text-xs font-semibold">Min Confidence:</span>
            <input
              type="range"
              min="0.10"
              max="0.95"
              step="0.05"
              value={confidenceThreshold}
              onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
              className="w-20 accent-emerald-500 cursor-pointer h-1.5 bg-slate-700 rounded-lg"
            />
            <span className="text-emerald-400 font-bold text-xs w-9 text-right">
              {Math.round(confidenceThreshold * 100)}%
            </span>
          </div>
        </div>

        {/* Tab 1: Local Webcam Info */}
        {activeTab === 'source' && (
          <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>Capturing live browser camera at 10 FPS with sub-10ms overlay rendering.</span>
            </div>
            <button
              onClick={onTakeSnapshot}
              className="bg-[#141824] hover:bg-[#1d2334] text-slate-200 border border-[#2a334a] px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-all text-xs"
            >
              <Camera className="w-3.5 h-3.5 text-emerald-400" />
              <span>Snapshot HUD</span>
            </button>
          </div>
        )}

        {/* Tab 2: Video File Drag-and-Drop Upload */}
        {activeTab === 'upload' && (
          <div className="flex flex-col gap-2.5 pt-1">
            {/* Hidden Single Persistent File Input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*,.mp4,.webm,.mov,.mkv,.avi"
              onChange={handleFileSelect}
              className="hidden"
            />

            {uploadedFileName && streamSource === 'file' ? (
              <div className="bg-[#121520] border border-[#262f45] rounded-xl p-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <FileVideo className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-200 truncate max-w-xs sm:max-w-md">
                      {uploadedFileName}
                    </h4>
                    <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      Local Video Ingestion Active (Streaming at 10 FPS)
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={togglePlayback}
                    className="bg-[#181d2e] hover:bg-[#222a3d] text-slate-200 border border-[#2e374f] px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-all text-xs"
                  >
                    {isPlaying ? <Pause className="w-3.5 h-3.5 text-amber-400" /> : <Play className="w-3.5 h-3.5 text-emerald-400 fill-current" />}
                    <span>{isPlaying ? 'Pause' : 'Play'}</span>
                  </button>

                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all text-xs shadow-sm"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Upload New Video</span>
                  </button>
                </div>
              </div>
            ) : (
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragOver(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragOver(false);
                }}
                onDrop={handleFileDrop}
                className={`border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer transition-all ${
                  isDragOver
                    ? 'border-emerald-400 bg-emerald-500/10'
                    : 'border-[#262f45] bg-[#121520] hover:border-emerald-500/50 hover:bg-[#151928]'
                }`}
              >
                <Upload className="w-8 h-8 text-emerald-400 mb-1" />
                <p className="text-xs font-bold text-slate-200">
                  Drag & Drop your video file here, or <span className="text-emerald-400 underline">Browse Local Files</span>
                </p>
                <span className="text-[10px] text-slate-500">
                  Supports MP4, WebM, QuickTime MOV, MKV up to 4K resolution.
                </span>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Direct Stream URL Input */}
        {activeTab === 'url' && (
          <form onSubmit={handleUrlSubmit} className="flex flex-col gap-2 pt-1">
            <div className="flex gap-2">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="Enter direct video URL (e.g. https://domain.com/feed.mp4)"
                className="flex-1 bg-[#121520] border border-[#262f45] focus:border-emerald-500 focus:outline-none rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500"
              />
              <button
                type="submit"
                className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs px-5 py-2 rounded-lg flex items-center gap-1.5 transition-all shadow-sm shrink-0"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Load URL</span>
              </button>
            </div>

            {/* Quick Sample Links */}
            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <span>Quick Test Samples:</span>
              {QUICK_SAMPLE_URLS.map((sample, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setUrlInput(sample.url);
                    loadVideoUrl(sample.url);
                  }}
                  className="text-emerald-400 hover:underline font-semibold"
                >
                  {sample.name}
                </button>
              ))}
            </div>
          </form>
        )}

        {/* Tab 4: Interactive Preset Scenarios */}
        {activeTab === 'presets' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 pt-1">
            {PRESET_SCENARIOS.map((preset) => {
              const isSelected = selectedPresetId === preset.id && streamSource === 'preset';
              return (
                <div
                  key={preset.id}
                  onClick={() => handlePresetSelect(preset)}
                  className={`border rounded-xl p-3 cursor-pointer transition-all flex flex-col justify-between gap-2 ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-500/10 shadow-sm'
                      : 'border-[#222a3d] bg-[#121520] hover:border-[#2e3a54] hover:bg-[#151928]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="text-xs font-bold text-slate-200">{preset.title}</h4>
                      <span className="text-[10px] text-emerald-400 font-semibold">{preset.subtitle}</span>
                    </div>
                    {isSelected && <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />}
                  </div>

                  <p className="text-[10px] text-slate-400 line-clamp-2 leading-relaxed">
                    {preset.description}
                  </p>

                  <div className="flex flex-wrap gap-1 mt-1">
                    {preset.tags.map((tag, tIdx) => (
                      <span
                        key={tIdx}
                        className="text-[9px] px-1.5 py-0.5 rounded bg-[#181d2e] text-slate-400 border border-[#262f45]"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

      </div>

    </div>
  );
};
