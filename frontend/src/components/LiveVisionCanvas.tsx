import React, { useRef, useEffect, useState, useCallback } from 'react';
import { RotateCcw, Eye, EyeOff } from 'lucide-react';
import { StreamTelemetryPayload, StreamROIConfig, ROINormalizedBox } from '../types';

interface LiveVisionCanvasProps {
  canvasRef: React.RefObject<HTMLCanvasElement>;
  latestTelemetry: StreamTelemetryPayload | null;
  confidenceThreshold: number;
  streamId: string;
  onRoiChange?: (roi: StreamROIConfig) => void;
}

type DragHandle = 'move' | 'nw' | 'ne' | 'se' | 'sw' | 'n' | 's' | 'e' | 'w' | null;

export const LiveVisionCanvas: React.FC<LiveVisionCanvasProps> = ({
  canvasRef,
  latestTelemetry,
  confidenceThreshold,
  streamId,
  onRoiChange,
}) => {
  // ---------------------------------------------------------------------------
  // Decoupled Mutable State Refs (Zero React Re-render Lag during active drag)
  // ---------------------------------------------------------------------------
  const roiRef = useRef<ROINormalizedBox>({
    x1: 0.20,
    y1: 0.30,
    x2: 0.70,
    y2: 0.80,
  });
  const roiEnabledRef = useRef<boolean>(true);
  const roiLabelRef = useRef<string>('Server Rack Perimeter');
  const isDraggingRef = useRef<boolean>(false);
  const dragHandleRef = useRef<DragHandle>(null);
  const dragStartRef = useRef<{
    startX: number;
    startY: number;
    initialBox: ROINormalizedBox;
  } | null>(null);
  const isBreachedRef = useRef<boolean>(false);
  const latestTelemetryRef = useRef<StreamTelemetryPayload | null>(latestTelemetry);
  const confidenceThresholdRef = useRef<number>(confidenceThreshold);

  // Static UI indicators
  const [uiRoiEnabled, setUiRoiEnabled] = useState<boolean>(true);
  const [uiRoiLabel, setUiRoiLabel] = useState<string>('Server Rack Perimeter');

  // Keep telemetry refs in sync immediately
  useEffect(() => {
    latestTelemetryRef.current = latestTelemetry;
    confidenceThresholdRef.current = confidenceThreshold;
  }, [latestTelemetry, confidenceThreshold]);

  // Sync external ROI updates from backend
  useEffect(() => {
    if (latestTelemetry?.stream_roi && !isDraggingRef.current) {
      const { roi_enabled, roi_normalized, roi_label } = latestTelemetry.stream_roi;
      roiEnabledRef.current = roi_enabled;
      setUiRoiEnabled(roi_enabled);
      if (roi_normalized) {
        roiRef.current = { ...roi_normalized };
      }
      if (roi_label) {
        roiLabelRef.current = roi_label;
        setUiRoiLabel(roi_label);
      }
    }
  }, [latestTelemetry?.stream_roi]);

  // Commit ROI update to Backend REST/WebSocket
  const commitRoiUpdate = useCallback(
    async (box: ROINormalizedBox, enabled: boolean, label: string) => {
      const payload: StreamROIConfig = {
        stream_id: streamId,
        roi_enabled: enabled,
        roi_normalized: {
          x1: Math.round(box.x1 * 1000) / 1000,
          y1: Math.round(box.y1 * 1000) / 1000,
          x2: Math.round(box.x2 * 1000) / 1000,
          y2: Math.round(box.y2 * 1000) / 1000,
        },
        roi_label: label,
      };

      if (onRoiChange) {
        onRoiChange(payload);
      }

      try {
        await fetch('http://localhost:8000/api/v1/stream/roi', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        console.warn('ROI update dispatch failed:', err);
      }
    },
    [streamId, onRoiChange]
  );

  // ---------------------------------------------------------------------------
  // Continuous 60 FPS Unified Canvas Animation Loop
  // (Renders YOLOv8 Detection Boxes + Interactive Draggable ROI directly onto canvas)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let animId: number;

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) {
        animId = requestAnimationFrame(render);
        return;
      }
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        animId = requestAnimationFrame(render);
        return;
      }

      const w = canvas.width;
      const h = canvas.height;

      // 1. Clear visible canvas completely on every animation frame
      ctx.clearRect(0, 0, w, h);

      const telemetry = latestTelemetryRef.current;
      const confThresh = confidenceThresholdRef.current;
      const roi = roiRef.current;
      const isRoiActive = roiEnabledRef.current;
      const label = roiLabelRef.current;

      let hasBreach = false;

      // 2. Render Interactive Draggable ROI Box
      if (isRoiActive) {
        const rx1 = roi.x1 * w;
        const ry1 = roi.y1 * h;
        const rw = (roi.x2 - roi.x1) * w;
        const rh = (roi.y2 - roi.y1) * h;

        ctx.save();

        if (isBreachedRef.current) {
          // Breached: Solid pulsing red with glow
          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = 3.5;
          ctx.shadowColor = '#ef4444';
          ctx.shadowBlur = 16;
          ctx.fillStyle = 'rgba(239, 68, 68, 0.18)';
          ctx.strokeRect(rx1, ry1, rw, rh);
          ctx.fillRect(rx1, ry1, rw, rh);

          // Corner Handles (Red)
          const handleSize = 12;
          ctx.fillStyle = '#ef4444';
          ctx.fillRect(rx1 - handleSize / 2, ry1 - handleSize / 2, handleSize, handleSize);
          ctx.fillRect(rx1 + rw - handleSize / 2, ry1 - handleSize / 2, handleSize, handleSize);
          ctx.fillRect(rx1 + rw - handleSize / 2, ry1 + rh - handleSize / 2, handleSize, handleSize);
          ctx.fillRect(rx1 - handleSize / 2, ry1 + rh - handleSize / 2, handleSize, handleSize);

          // Breach Label Pill
          const labelText = `⚠️ BREACH: Zone Occupied (${label})`;
          ctx.font = 'bold 12px monospace';
          const tw = ctx.measureText(labelText).width;
          ctx.fillStyle = '#dc2626';
          ctx.beginPath();
          ctx.roundRect(rx1, Math.max(0, ry1 - 24), tw + 18, 22, [4, 4, 0, 0]);
          ctx.fill();

          ctx.fillStyle = '#ffffff';
          ctx.shadowBlur = 0;
          ctx.fillText(labelText, rx1 + 8, Math.max(15, ry1 - 8));
        } else {
          // Normal: Dashed cyan borders
          ctx.strokeStyle = '#06b6d4';
          ctx.lineWidth = 2.5;
          ctx.setLineDash([8, 6]);
          ctx.shadowColor = '#06b6d4';
          ctx.shadowBlur = 8;
          ctx.strokeRect(rx1, ry1, rw, rh);

          ctx.fillStyle = isDraggingRef.current
            ? 'rgba(6, 182, 212, 0.14)'
            : 'rgba(6, 182, 212, 0.05)';
          ctx.fillRect(rx1, ry1, rw, rh);

          // Corner Handles (NW, NE, SE, SW)
          ctx.setLineDash([]);
          const cornerHandles = [
            [rx1, ry1],
            [rx1 + rw, ry1],
            [rx1 + rw, ry1 + rh],
            [rx1, ry1 + rh],
          ];

          cornerHandles.forEach(([hx, hy]) => {
            ctx.fillStyle = '#06b6d4';
            ctx.beginPath();
            ctx.arc(hx, hy, 6, 0, 2 * Math.PI);
            ctx.fill();
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(hx, hy, 3.5, 0, 2 * Math.PI);
            ctx.fill();
          });

          // Edge Midpoint Handles (N, S, E, W)
          const edgeHandles = [
            [rx1 + rw / 2, ry1],
            [rx1 + rw / 2, ry1 + rh],
            [rx1 + rw, ry1 + rh / 2],
            [rx1, ry1 + rh / 2],
          ];

          edgeHandles.forEach(([hx, hy]) => {
            ctx.fillStyle = '#0891b2';
            ctx.beginPath();
            ctx.arc(hx, hy, 4.5, 0, 2 * Math.PI);
            ctx.fill();
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(hx, hy, 2.5, 0, 2 * Math.PI);
            ctx.fill();
          });

          // Tactical Cyan Pill
          const labelText = `● RESTRICTED ROI [${label}]`;
          ctx.font = 'bold 12px monospace';
          const tw = ctx.measureText(labelText).width;
          ctx.fillStyle = '#0891b2';
          ctx.beginPath();
          ctx.roundRect(rx1, Math.max(0, ry1 - 22), tw + 16, 20, [4, 4, 0, 0]);
          ctx.fill();

          ctx.fillStyle = '#ffffff';
          ctx.shadowBlur = 0;
          ctx.fillText(labelText, rx1 + 8, Math.max(14, ry1 - 7));
        }

        ctx.restore();
      }

      // 3. Render Real Dynamic YOLOv8 Detections
      if (telemetry?.detections && telemetry.detections.length > 0) {
        telemetry.detections.forEach((det) => {
          if (det.confidence < confThresh) return;

          const [nx1, ny1, nx2, ny2] = det.normalized_box;
          const x1 = nx1 * w;
          const y1 = ny1 * h;
          const boxW = Math.max(10, (nx2 - nx1) * w);
          const boxH = Math.max(10, (ny2 - ny1) * h);

          const cx = (nx1 + nx2) / 2.0;
          const cy = (ny1 + ny2) / 2.0;

          // Check if detection centroid is inside custom ROI
          const insideRoi =
            isRoiActive &&
            cx >= roi.x1 &&
            cx <= roi.x2 &&
            cy >= roi.y1 &&
            cy <= roi.y2;

          if (insideRoi) {
            hasBreach = true;
          }

          const isProhibited = [
            'cell phone',
            'laptop',
            'knife',
            'scissors',
            'backpack',
          ].includes(det.label.toLowerCase());

          const isViolator =
            insideRoi || isProhibited || (det as any).is_violator;
          const boxColor = isViolator ? '#ef4444' : '#10b981';
          const labelBg = isViolator ? '#dc2626' : '#059669';

          // Draw Bounding Box with glow
          ctx.save();
          ctx.strokeStyle = boxColor;
          ctx.lineWidth = 2.5;
          ctx.shadowColor = boxColor;
          ctx.shadowBlur = isViolator ? 14 : 6;
          ctx.strokeRect(x1, y1, boxW, boxH);

          // Tactical Corner Brackets
          const cornerLen = Math.min(18, boxW / 4, boxH / 4);
          ctx.lineWidth = 4;
          // Top Left
          ctx.beginPath();
          ctx.moveTo(x1, y1 + cornerLen);
          ctx.lineTo(x1, y1);
          ctx.lineTo(x1 + cornerLen, y1);
          ctx.stroke();
          // Top Right
          ctx.beginPath();
          ctx.moveTo(x1 + boxW - cornerLen, y1);
          ctx.lineTo(x1 + boxW, y1);
          ctx.lineTo(x1 + boxW, y1 + cornerLen);
          ctx.stroke();
          // Bottom Left
          ctx.beginPath();
          ctx.moveTo(x1, y1 + boxH - cornerLen);
          ctx.lineTo(x1, y1 + boxH);
          ctx.lineTo(x1 + cornerLen, y1 + boxH);
          ctx.stroke();
          // Bottom Right
          ctx.beginPath();
          ctx.moveTo(x1 + boxW - cornerLen, y1 + boxH);
          ctx.lineTo(x1 + boxW, y1 + boxH);
          ctx.lineTo(x1 + boxW, y1 + boxH - cornerLen);
          ctx.stroke();

          // Crisp Label Pill Above Box
          const tagPrefix = isViolator ? '[ALERT] ' : '';
          const tagText = `${tagPrefix}${det.label.toUpperCase()} ${Math.round(
            det.confidence * 100
          )}% ${det.tracking_id ? `[#${det.tracking_id}]` : ''}`;

          ctx.font = 'bold 12px monospace';
          const textWidth = ctx.measureText(tagText).width;

          const pillX = x1;
          const pillY = Math.max(22, y1 - 6);
          const pillH = 22;
          const pillW = textWidth + 16;

          ctx.fillStyle = labelBg;
          ctx.beginPath();
          ctx.roundRect(pillX, pillY - pillH, pillW, pillH, [4, 4, 0, 0]);
          ctx.fill();

          ctx.fillStyle = '#ffffff';
          ctx.shadowBlur = 0;
          ctx.fillText(tagText, pillX + 8, pillY - 6);
          ctx.restore();
        });
      }

      isBreachedRef.current = hasBreach;

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [canvasRef]);

  // ---------------------------------------------------------------------------
  // Interactive Pointer Events for Dragging & Resizing ROI
  // ---------------------------------------------------------------------------
  const getNormalizedPointerPos = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    return { x, y };
  };

  const hitTestHandle = (nx: number, ny: number): DragHandle => {
    if (!roiEnabledRef.current) return null;
    const { x1, y1, x2, y2 } = roiRef.current;
    const tol = 0.035;

    // Corners
    if (Math.abs(nx - x1) < tol && Math.abs(ny - y1) < tol) return 'nw';
    if (Math.abs(nx - x2) < tol && Math.abs(ny - y1) < tol) return 'ne';
    if (Math.abs(nx - x2) < tol && Math.abs(ny - y2) < tol) return 'se';
    if (Math.abs(nx - x1) < tol && Math.abs(ny - y2) < tol) return 'sw';

    // Edges
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    if (Math.abs(nx - midX) < tol && Math.abs(ny - y1) < tol) return 'n';
    if (Math.abs(nx - midX) < tol && Math.abs(ny - y2) < tol) return 's';
    if (Math.abs(nx - x2) < tol && Math.abs(ny - midY) < tol) return 'e';
    if (Math.abs(nx - x1) < tol && Math.abs(ny - midY) < tol) return 'w';

    // Inside Box
    if (nx >= x1 && nx <= x2 && ny >= y1 && ny <= y2) return 'move';

    return null;
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!roiEnabledRef.current) return;
    const { x, y } = getNormalizedPointerPos(e);
    const handle = hitTestHandle(x, y);

    if (handle) {
      isDraggingRef.current = true;
      dragHandleRef.current = handle;
      dragStartRef.current = {
        startX: x,
        startY: y,
        initialBox: { ...roiRef.current },
      };

      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch (_) {}
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const { x, y } = getNormalizedPointerPos(e);

    if (!isDraggingRef.current) {
      const handle = hitTestHandle(x, y);
      switch (handle) {
        case 'nw':
        case 'se':
          canvas.style.cursor = 'nwse-resize';
          break;
        case 'ne':
        case 'sw':
          canvas.style.cursor = 'nesw-resize';
          break;
        case 'n':
        case 's':
          canvas.style.cursor = 'ns-resize';
          break;
        case 'e':
        case 'w':
          canvas.style.cursor = 'ew-resize';
          break;
        case 'move':
          canvas.style.cursor = 'grab';
          break;
        default:
          canvas.style.cursor = 'default';
      }
      return;
    }

    if (!dragStartRef.current || !dragHandleRef.current) return;

    const { startX, startY, initialBox } = dragStartRef.current;
    const dx = x - startX;
    const dy = y - startY;
    const minSize = 0.05;
    const handle = dragHandleRef.current;

    if (handle === 'move') {
      const width = initialBox.x2 - initialBox.x1;
      const height = initialBox.y2 - initialBox.y1;
      const newX1 = Math.max(0, Math.min(1 - width, initialBox.x1 + dx));
      const newY1 = Math.max(0, Math.min(1 - height, initialBox.y1 + dy));
      roiRef.current = {
        x1: newX1,
        y1: newY1,
        x2: newX1 + width,
        y2: newY1 + height,
      };
      canvas.style.cursor = 'grabbing';
    } else if (handle === 'nw') {
      roiRef.current.x1 = Math.max(0, Math.min(initialBox.x2 - minSize, initialBox.x1 + dx));
      roiRef.current.y1 = Math.max(0, Math.min(initialBox.y2 - minSize, initialBox.y1 + dy));
    } else if (handle === 'ne') {
      roiRef.current.x2 = Math.min(1, Math.max(initialBox.x1 + minSize, initialBox.x2 + dx));
      roiRef.current.y1 = Math.max(0, Math.min(initialBox.y2 - minSize, initialBox.y1 + dy));
    } else if (handle === 'se') {
      roiRef.current.x2 = Math.min(1, Math.max(initialBox.x1 + minSize, initialBox.x2 + dx));
      roiRef.current.y2 = Math.min(1, Math.max(initialBox.y1 + minSize, initialBox.y2 + dy));
    } else if (handle === 'sw') {
      roiRef.current.x1 = Math.max(0, Math.min(initialBox.x2 - minSize, initialBox.x1 + dx));
      roiRef.current.y2 = Math.min(1, Math.max(initialBox.y1 + minSize, initialBox.y2 + dy));
    } else if (handle === 'n') {
      roiRef.current.y1 = Math.max(0, Math.min(initialBox.y2 - minSize, initialBox.y1 + dy));
    } else if (handle === 's') {
      roiRef.current.y2 = Math.min(1, Math.max(initialBox.y1 + minSize, initialBox.y2 + dy));
    } else if (handle === 'e') {
      roiRef.current.x2 = Math.min(1, Math.max(initialBox.x1 + minSize, initialBox.x2 + dx));
    } else if (handle === 'w') {
      roiRef.current.x1 = Math.max(0, Math.min(initialBox.x2 - minSize, initialBox.x1 + dx));
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      dragHandleRef.current = null;
      dragStartRef.current = null;

      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch (_) {}

      const canvas = canvasRef.current;
      if (canvas) {
        canvas.style.cursor = 'default';
      }

      commitRoiUpdate(roiRef.current, roiEnabledRef.current, roiLabelRef.current);
    }
  };

  const applyPreset = (preset: { label: string; box: ROINormalizedBox }) => {
    roiRef.current = { ...preset.box };
    roiLabelRef.current = preset.label;
    setUiRoiLabel(preset.label);
    commitRoiUpdate(preset.box, roiEnabledRef.current, preset.label);
  };

  return (
    <div className="relative w-full h-full">
      {/* Primary Hardware-Accelerated Dynamic Vision & Interactive ROI Canvas */}
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        width={1280}
        height={720}
        className="w-full h-full object-cover pointer-events-auto touch-none"
      />

      {/* Floating ROI Controls Toolbar */}
      <div className="absolute bottom-3 left-3 right-3 bg-[#0e111acc]/95 backdrop-blur-md border border-[#222a3d] rounded-xl px-3 py-2 flex flex-wrap items-center justify-between gap-2 text-xs font-mono z-30 shadow-2xl">
        {/* Toggle ROI and Label */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const nextState = !roiEnabledRef.current;
              roiEnabledRef.current = nextState;
              setUiRoiEnabled(nextState);
              commitRoiUpdate(roiRef.current, nextState, roiLabelRef.current);
            }}
            className={`px-2.5 py-1 rounded-lg font-bold flex items-center gap-1.5 transition-all ${
              uiRoiEnabled
                ? 'bg-cyan-500 text-black shadow-sm'
                : 'bg-[#181d2e] text-slate-400 border border-[#262f45] hover:text-white'
            }`}
          >
            {uiRoiEnabled ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>ROI: {uiRoiEnabled ? 'ACTIVE' : 'DISABLED'}</span>
          </button>

          <span className="text-[11px] text-slate-300 font-semibold hidden sm:inline">
            Sector: <strong className="text-cyan-400">{uiRoiLabel}</strong>
          </span>
        </div>

        {/* Quick Presets */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() =>
              applyPreset({
                label: 'Center Stage',
                box: { x1: 0.25, y1: 0.20, x2: 0.75, y2: 0.80 },
              })
            }
            className="px-2 py-1 bg-[#141824] hover:bg-[#1c2233] text-slate-300 hover:text-cyan-400 border border-[#222a3d] rounded-md transition-colors text-[10px]"
          >
            Center Stage
          </button>

          <button
            onClick={() =>
              applyPreset({
                label: 'Right Perimeter',
                box: { x1: 0.60, y1: 0.15, x2: 0.95, y2: 0.85 },
              })
            }
            className="px-2 py-1 bg-[#141824] hover:bg-[#1c2233] text-slate-300 hover:text-cyan-400 border border-[#222a3d] rounded-md transition-colors text-[10px]"
          >
            Right Perimeter
          </button>

          <button
            onClick={() =>
              applyPreset({
                label: 'Full Field',
                box: { x1: 0.05, y1: 0.05, x2: 0.95, y2: 0.95 },
              })
            }
            className="px-2 py-1 bg-[#141824] hover:bg-[#1c2233] text-slate-300 hover:text-cyan-400 border border-[#222a3d] rounded-md transition-colors text-[10px]"
          >
            Full Frame
          </button>

          <button
            onClick={() =>
              applyPreset({
                label: 'Server Rack Perimeter',
                box: { x1: 0.20, y1: 0.30, x2: 0.70, y2: 0.80 },
              })
            }
            className="px-2 py-1 bg-[#141824] hover:bg-[#1c2233] text-slate-400 hover:text-white border border-[#222a3d] rounded-md transition-colors text-[10px] flex items-center gap-1"
          >
            <RotateCcw className="w-3 h-3" />
            Reset
          </button>
        </div>
      </div>
    </div>
  );
};
