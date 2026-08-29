import React, { useRef, useEffect } from 'react';
import { StreamTelemetryPayload } from '../types';

interface LiveVisionCanvasProps {
  canvasRef: React.RefObject<HTMLCanvasElement>;
  latestTelemetry: StreamTelemetryPayload | null;
  confidenceThreshold: number;
  streamId: string;
}

export const LiveVisionCanvas: React.FC<LiveVisionCanvasProps> = ({
  canvasRef,
  latestTelemetry,
  confidenceThreshold,
}) => {
  const latestTelemetryRef = useRef<StreamTelemetryPayload | null>(latestTelemetry);
  const confidenceThresholdRef = useRef<number>(confidenceThreshold);

  // Keep telemetry refs in sync immediately
  useEffect(() => {
    latestTelemetryRef.current = latestTelemetry;
    confidenceThresholdRef.current = confidenceThreshold;
  }, [latestTelemetry, confidenceThreshold]);

  // ---------------------------------------------------------------------------
  // Clean, Low-Latency Hardware-Accelerated Dynamic Vision Canvas Loop
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

      // Clear visible canvas completely on every animation frame
      ctx.clearRect(0, 0, w, h);

      const telemetry = latestTelemetryRef.current;
      const confThresh = confidenceThresholdRef.current;

      // 1. Render Clean YOLOv8 Detected Object Bounding Boxes
      if (telemetry?.detections && telemetry.detections.length > 0) {
        telemetry.detections.forEach((det) => {
          if (det.confidence < confThresh) return;

          const [nx1, ny1, nx2, ny2] = det.normalized_box;
          const x1 = nx1 * w;
          const y1 = ny1 * h;
          const boxW = Math.max(10, (nx2 - nx1) * w);
          const boxH = Math.max(10, (ny2 - ny1) * h);

          const isProhibited = [
            'knife',
            'scissors',
            'gun',
            'weapon',
          ].includes(det.label.toLowerCase());

          const isViolator = isProhibited || (det as any).is_violator;
          const boxColor = isViolator ? '#f59e0b' : '#10b981';
          const labelBg = isViolator ? '#d97706' : '#059669';

          // Draw Bounding Box with subtle glow
          ctx.save();
          ctx.strokeStyle = boxColor;
          ctx.lineWidth = isViolator ? 3.0 : 2.0;
          ctx.shadowColor = boxColor;
          ctx.shadowBlur = isViolator ? 12 : 4;
          ctx.strokeRect(x1, y1, boxW, boxH);

          // Tactical Corner Brackets
          const cornerLen = Math.min(16, boxW / 4, boxH / 4);
          ctx.lineWidth = 3.0;
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

          // Crisp Label Pill
          const tagPrefix = isProhibited ? '🚫 [PROHIBITED] ' : '';
          const tagText = `${tagPrefix}${det.label.toUpperCase()} ${Math.round(
            det.confidence * 100
          )}% ${det.tracking_id ? `[#${det.tracking_id}]` : ''}`;

          ctx.font = 'bold 11px monospace';
          const textWidth = ctx.measureText(tagText).width;

          const pillX = x1;
          const pillY = Math.max(20, y1 - 4);
          const pillH = 20;
          const pillW = textWidth + 14;

          ctx.fillStyle = labelBg;
          ctx.beginPath();
          ctx.roundRect(pillX, pillY - pillH, pillW, pillH, [4, 4, 0, 0]);
          ctx.fill();

          ctx.fillStyle = '#ffffff';
          ctx.shadowBlur = 0;
          ctx.fillText(tagText, pillX + 7, pillY - 5);
          ctx.restore();
        });
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [canvasRef]);

  return (
    <div className="relative w-full h-full">
      {/* Primary Hardware-Accelerated Dynamic Vision Canvas */}
      <canvas
        ref={canvasRef}
        width={1280}
        height={720}
        className="w-full h-full object-cover pointer-events-none"
      />
    </div>
  );
};
