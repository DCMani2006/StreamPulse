import React, { useRef, useEffect } from 'react';
import { StreamTelemetryPayload } from '../types';

interface LiveVisionCanvasProps {
  canvasRef: React.RefObject<HTMLCanvasElement>;
  videoRef?: React.RefObject<HTMLVideoElement>;
  latestTelemetry: StreamTelemetryPayload | null;
  confidenceThreshold: number;
  streamId: string;
}

export const LiveVisionCanvas: React.FC<LiveVisionCanvasProps> = ({
  canvasRef,
  videoRef,
  latestTelemetry,
  confidenceThreshold,
  streamId,
}) => {
  const latestTelemetryRef = useRef<StreamTelemetryPayload | null>(latestTelemetry);
  const confidenceThresholdRef = useRef<number>(confidenceThreshold);
  const videoRefInternal = useRef<React.RefObject<HTMLVideoElement> | undefined>(videoRef);
  const frameCountRef = useRef<number>(0);

  // Keep telemetry refs in sync immediately
  useEffect(() => {
    latestTelemetryRef.current = latestTelemetry;
    confidenceThresholdRef.current = confidenceThreshold;
    videoRefInternal.current = videoRef;
  }, [latestTelemetry, confidenceThreshold, videoRef]);

  // ---------------------------------------------------------------------------
  // Option C: High-Contrast Enterprise Command Dynamic Vision Canvas
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
      frameCountRef.current++;

      const video = videoRefInternal.current?.current;
      const isVideoPlaying = Boolean(
        video &&
        video.readyState >= 2 &&
        video.videoWidth > 0 &&
        !video.paused &&
        !video.error
      );

      // Clear canvas
      ctx.clearRect(0, 0, w, h);

      // If video cannot decode frames (e.g. VIRAT raw H.264), render a realistic dynamic surveillance scene!
      if (!isVideoPlaying) {
        // 1. High-Contrast Pitch Black CCTV pavement background
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, '#050508');
        grad.addColorStop(0.5, '#0b0b12');
        grad.addColorStop(1, '#050508');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);

        // 2. Perspective Surveillance Ground Grid & Parking Bay Lines
        ctx.save();
        ctx.strokeStyle = 'rgba(39, 39, 58, 0.45)';
        ctx.lineWidth = 1;

        // Horizontal perspective lines
        for (let y = h * 0.35; y < h; y += 45) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(w, y);
          ctx.stroke();
        }

        // Converging perspective lines
        const vanishingX = w * 0.5;
        const vanishingY = h * 0.2;
        for (let x = -w * 0.2; x <= w * 1.2; x += 120) {
          ctx.beginPath();
          ctx.moveTo(vanishingX, vanishingY);
          ctx.lineTo(x, h);
          ctx.stroke();
        }

        // Roadway / Facility Markings
        ctx.strokeStyle = 'rgba(34, 197, 94, 0.20)';
        ctx.setLineDash([15, 15]);
        ctx.beginPath();
        ctx.moveTo(w * 0.2, h);
        ctx.lineTo(vanishingX, vanishingY + 60);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(w * 0.8, h);
        ctx.lineTo(vanishingX, vanishingY + 60);
        ctx.stroke();
        ctx.setLineDash([]);

        // Surveillance Watermark & Tactical Crosshairs
        ctx.fillStyle = 'rgba(161, 161, 170, 0.50)';
        ctx.font = '10px monospace';
        ctx.fillText(`CCTV FEED: ${streamId.toUpperCase()} [ENTERPRISE COMMAND]`, 25, h - 25);
        ctx.fillText(`OPTICAL SENSOR: 1080P WIDE-ANGLE FOV`, 25, h - 12);

        // Center Optical Crosshair
        ctx.strokeStyle = 'rgba(139, 92, 246, 0.35)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(w / 2 - 20, h / 2);
        ctx.lineTo(w / 2 + 20, h / 2);
        ctx.moveTo(w / 2, h / 2 - 20);
        ctx.lineTo(w / 2, h / 2 + 20);
        ctx.stroke();
        ctx.restore();
      }

      const telemetry = latestTelemetryRef.current;
      const confThresh = confidenceThresholdRef.current;

      const isStreamAnomaly = Boolean(
        telemetry?.trigger_fired ||
        (telemetry?.alerts && telemetry.alerts.length > 0) ||
        telemetry?.forensic_incident ||
        (telemetry?.audio_db !== undefined && telemetry.audio_db > -28.0)
      );

      // 1. Draw Pulsing Pure Red Highlight Border Around Canvas Frame During Anomalies
      if (isStreamAnomaly) {
        ctx.save();
        ctx.strokeStyle = 'rgba(220, 38, 38, 0.85)';
        ctx.lineWidth = 6;
        ctx.shadowColor = '#DC2626';
        ctx.shadowBlur = 20;
        ctx.strokeRect(3, 3, w - 6, h - 6);
        ctx.restore();
      }

      // 2. Render YOLOv8 Detected Object Bounding Boxes with Option C High-Contrast Colors
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

          // Option C Color Scheme: Pure Red (#DC2626) for anomaly, Tactical Green (#22C55E) for normal
          const isAnomaly = det.is_violator || (det as any).is_anomaly || isStreamAnomaly || isProhibited;
          const boxColor = isAnomaly ? '#DC2626' : '#22C55E';
          const labelBg = isAnomaly ? 'rgba(220, 38, 38, 0.95)' : 'rgba(34, 197, 94, 0.90)';
          const boxLineWidth = isAnomaly ? 3.0 : 2.0;

          // If synthetic background is active, draw stylized entity visual inside box!
          if (!isVideoPlaying) {
            ctx.save();
            ctx.fillStyle = isAnomaly ? 'rgba(220, 38, 38, 0.20)' : 'rgba(34, 197, 94, 0.15)';
            ctx.fillRect(x1, y1, boxW, boxH);

            // Draw entity silhouette
            const cx = x1 + boxW / 2;
            ctx.fillStyle = isAnomaly ? 'rgba(220, 38, 38, 0.50)' : 'rgba(34, 197, 94, 0.45)';
            if (det.label.toLowerCase().includes('person')) {
              // Person silhouette (head + body)
              const headR = Math.min(boxW, boxH) * 0.18;
              ctx.beginPath();
              ctx.arc(cx, y1 + headR + 8, headR, 0, Math.PI * 2);
              ctx.fill();
              ctx.beginPath();
              ctx.roundRect(cx - boxW * 0.25, y1 + headR * 2 + 10, boxW * 0.5, boxH * 0.55, [6, 6, 0, 0]);
              ctx.fill();
            } else {
              // Vehicle / object chassis silhouette
              ctx.beginPath();
              ctx.roundRect(x1 + 6, y1 + boxH * 0.3, boxW - 12, boxH * 0.55, [8, 8, 4, 4]);
              ctx.fill();
            }
            ctx.restore();
          }

          // Draw Bounding Box with high-contrast glow
          ctx.save();
          ctx.strokeStyle = boxColor;
          ctx.lineWidth = boxLineWidth;
          ctx.shadowColor = boxColor;
          ctx.shadowBlur = isAnomaly ? 16 : 4;
          ctx.strokeRect(x1, y1, boxW, boxH);

          // Tactical Corner Brackets
          const cornerLen = Math.min(16, boxW / 4, boxH / 4);
          ctx.lineWidth = isAnomaly ? 4.0 : 3.0;
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

          // Crisp High-Contrast Label Pill
          let tagPrefix = '';
          if (isProhibited) tagPrefix = '🚫 [PROHIBITED] ';
          else if (isAnomaly && isStreamAnomaly) tagPrefix = '⚠️ [ANOMALY] ';

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
