import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { VideoStage } from './components/VideoStage';
import { TelemetryKPIs } from './components/TelemetryKPIs';
import { LatencyChart } from './components/LatencyChart';
import { AudioVisualizer } from './components/AudioVisualizer';
import { IncidentFeed } from './components/IncidentFeed';
import { useStreamPulse } from './hooks/useStreamPulse';

export const App: React.FC = () => {
  const [streamId] = useState<string>('cam_01');
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.35);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const {
    videoRef,
    overlayCanvasRef,
    streamSource,
    setStreamSource,
    loadVideoFile,
    loadVideoUrl,
    loadPresetScenario,
    startWebcam,
    isBackendConnected,
    currentFps,
    latestTelemetry,
    latencyHistory,
    incidents,
    audioLevel,
    audioVadActive,
    cameraActive,
    cameraError,
    triggerManualSnapshot,
  } = useStreamPulse({
    streamId,
    targetFps: 10,
    confidenceThreshold,
  });

  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(console.warn);
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(console.warn);
      setIsFullscreen(false);
    }
  };

  const handleSnapshotClick = () => {
    const success = triggerManualSnapshot();
    if (success) {
      triggerToast('Combined Frame Snapshot Captured & Saved');
    } else {
      triggerToast('Video stream frame not ready');
    }
  };

  return (
    <div className="min-h-screen bg-[#08090e] text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-black">
      
      {/* Top Enterprise Navigation Header */}
      <Navbar
        isBackendConnected={isBackendConnected}
        isFailsafeActive={!isBackendConnected}
        activeFeedName={`CAM-01 (${streamSource.toUpperCase()})`}
        isFullscreen={isFullscreen}
        onToggleFullscreen={handleToggleFullscreen}
        onTakeSnapshot={handleSnapshotClick}
        onOpenSettings={() => triggerToast('System Running in Autonomous AI Mode')}
      />

      {/* Main Command Center Stage */}
      <main className="flex-1 max-w-[1920px] w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5">
        
        {/* Left Column: Live Video + KPIs + Latency Timeline (8 cols) */}
        <div className="lg:col-span-8 flex flex-col gap-5">
          
          {/* Live Video Stage & Dynamic Canvas HUD Overlay */}
          <VideoStage
            videoRef={videoRef}
            overlayCanvasRef={overlayCanvasRef}
            streamSource={streamSource}
            setStreamSource={setStreamSource}
            loadVideoFile={loadVideoFile}
            loadVideoUrl={loadVideoUrl}
            loadPresetScenario={loadPresetScenario}
            startWebcam={startWebcam}
            latestTelemetry={latestTelemetry}
            currentFps={currentFps}
            cameraActive={cameraActive}
            cameraError={cameraError}
            confidenceThreshold={confidenceThreshold}
            setConfidenceThreshold={setConfidenceThreshold}
            streamId={streamId}
            isBackendConnected={isBackendConnected}
            onTakeSnapshot={handleSnapshotClick}
          />

          {/* 3 High-Impact KPI Cards */}
          <TelemetryKPIs latency={latestTelemetry?.latency} />

          {/* Recharts 30-Second Rolling Latency Spline Graph */}
          <LatencyChart data={latencyHistory} />

        </div>

        {/* Right Column: Audio VAD & Live Incident Feed (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-5">
          
          {/* Audio Energy & Voice Activity Monitor */}
          <AudioVisualizer
            audioLevel={audioLevel}
            vadActive={audioVadActive}
            audioAnalysis={latestTelemetry?.audio_analysis}
          />

          {/* Live Security & Incident Feed with Snapshots */}
          <div className="flex-1 min-h-[500px]">
            <IncidentFeed incidents={incidents} />
          </div>

        </div>

      </main>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 bg-[#121520] border border-emerald-500/40 text-emerald-400 font-mono text-xs font-bold px-4 py-2.5 rounded-xl shadow-2xl flex items-center gap-2 animate-bounce">
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          <span>{toastMessage}</span>
        </div>
      )}

    </div>
  );
};
