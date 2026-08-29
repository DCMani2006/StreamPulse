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
  // Continuous 60 FPS Dynamic Vision & Collision Anomaly Canvas Animation Loop
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

      // 1. Pairwise Vehicle Collision & Pedestrian Strike Analysis
      const VEHICLE_LABELS = new Set(['car', 'truck', 'bus', 'motorcycle', 'bicycle']);
      const collisionPairs: Array<{
        detA: any;
        detB: any;
        midX: number;
        midY: number;
        iou: number;
      }> = [];
      const collidingIndices = new Set<number>();

      if (telemetry?.detections && telemetry.detections.length > 1) {
        const dets = telemetry.detections;
        for (let i = 0; i < dets.length; i++) {
          if (dets[i].confidence < confThresh) continue;
          const isVehA = VEHICLE_LABELS.has(dets[i].label.toLowerCase());
          const isPersonA = dets[i].label.toLowerCase() === 'person';

          for (let j = i + 1; j < dets.length; j++) {
            if (dets[j].confidence < confThresh) continue;
            const isVehB = VEHICLE_LABELS.has(dets[j].label.toLowerCase());
            const isPersonB = dets[j].label.toLowerCase() === 'person';

            // Vehicle-to-Vehicle Collision OR Pedestrian-to-Vehicle Strike
            if ((isVehA && isVehB) || (isPersonA && isVehB) || (isVehA && isPersonB)) {
              const b1 = dets[i].normalized_box;
              const b2 = dets[j].normalized_box;

              const xL = Math.max(b1[0], b2[0]);
              const yT = Math.max(b1[1], b2[1]);
              const xR = Math.min(b1[2], b2[2]);
              const yB = Math.min(b1[3], b2[3]);

              if (xR > xL && yB > yT) {
                const inter = (xR - xL) * (yB - yT);
                const a1 = Math.max(1e-5, (b1[2] - b1[0]) * (b1[3] - b1[1]));
                const a2 = Math.max(1e-5, (b2[2] - b2[0]) * (b2[3] - b2[1]));
                const union = a1 + a2 - inter;
                const iou = inter / union;
                const ioa = inter / Math.min(a1, a2);

                const isPedStrike = isPersonA || isPersonB;
                const iouThresh = isPedStrike ? 0.10 : 0.18;
                const ioaThresh = isPedStrike ? 0.22 : 0.35;
                if (iou >= iouThresh || ioa >= ioaThresh) {
                  collidingIndices.add(i);
                  collidingIndices.add(j);
                  const cx1 = ((b1[0] + b1[2]) / 2.0) * w;
                  const cy1 = ((b1[1] + b1[3]) / 2.0) * h;
                  const cx2 = ((b2[0] + b2[2]) / 2.0) * w;
                  const cy2 = ((b2[1] + b2[3]) / 2.0) * h;
                  collisionPairs.push({
                    detA: dets[i],
                    detB: dets[j],
                    midX: (cx1 + cx2) / 2.0,
                    midY: (cy1 + cy2) / 2.0,
                    iou,
                  });
                }
              }
            }
          }
        }
      }

      // Draw Tactical Crash Connection Lines & Shockwaves
      if (collisionPairs.length > 0) {
        collisionPairs.forEach((pair) => {
          const b1 = pair.detA.normalized_box;
          const b2 = pair.detB.normalized_box;
          const cx1 = ((b1[0] + b1[2]) / 2.0) * w;
          const cy1 = ((b1[1] + b1[3]) / 2.0) * h;
          const cx2 = ((b2[0] + b2[2]) / 2.0) * w;
          const cy2 = ((b2[1] + b2[3]) / 2.0) * h;

          ctx.save();
          // Animated Red Shockwave Line
          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = 3;
          ctx.setLineDash([6, 4]);
          ctx.shadowColor = '#ef4444';
          ctx.shadowBlur = 16;
          ctx.beginPath();
          ctx.moveTo(cx1, cy1);
          ctx.lineTo(cx2, cy2);
          ctx.stroke();

          // Pulsing Collision Beacon at Midpoint
          ctx.fillStyle = '#dc2626';
          ctx.beginPath();
          ctx.arc(pair.midX, pair.midY, 14, 0, 2 * Math.PI);
          ctx.fill();
          ctx.fillStyle = '#fef08a';
          ctx.beginPath();
          ctx.arc(pair.midX, pair.midY, 7, 0, 2 * Math.PI);
          ctx.fill();

          // High-Impact Crash Badge
          const crashBadge = `💥 CRASH / COLLISION DETECTED [IoU: ${Math.round(pair.iou * 100)}%]`;
          ctx.font = 'bold 12px monospace';
          const badgeW = ctx.measureText(crashBadge).width + 20;
          ctx.fillStyle = '#b91c1c';
          ctx.beginPath();
          ctx.roundRect(pair.midX - badgeW / 2, pair.midY - 34, badgeW, 24, [6, 6, 6, 6]);
          ctx.fill();
          ctx.strokeStyle = '#fef08a';
          ctx.lineWidth = 1.5;
          ctx.stroke();

          ctx.fillStyle = '#ffffff';
          ctx.shadowBlur = 0;
          ctx.fillText(crashBadge, pair.midX - badgeW / 2 + 10, pair.midY - 18);
          ctx.restore();
        });
      }

      // 2. Render Dynamic YOLOv8 Detections
      if (telemetry?.detections && telemetry.detections.length > 0) {
        telemetry.detections.forEach((det, idx) => {
          if (det.confidence < confThresh) return;

          const [nx1, ny1, nx2, ny2] = det.normalized_box;
          const x1 = nx1 * w;
          const y1 = ny1 * h;
          const boxW = Math.max(10, (nx2 - nx1) * w);
          const boxH = Math.max(10, (ny2 - ny1) * h);

          const isProhibited = [
            'cell phone',
            'laptop',
            'knife',
            'scissors',
            'backpack',
          ].includes(det.label.toLowerCase());

          const isColliding = collidingIndices.has(idx);
          const isViolator = isColliding || isProhibited || (det as any).is_violator;

          const boxColor = isColliding
            ? '#ef4444'
            : isViolator
            ? '#f59e0b'
            : '#10b981';
          const labelBg = isColliding
            ? '#dc2626'
            : isViolator
            ? '#d97706'
            : '#059669';

          // Draw Bounding Box with glow
          ctx.save();
          ctx.strokeStyle = boxColor;
          ctx.lineWidth = isColliding ? 3.5 : 2.5;
          ctx.shadowColor = boxColor;
          ctx.shadowBlur = isColliding ? 18 : isViolator ? 12 : 6;
          ctx.strokeRect(x1, y1, boxW, boxH);

          // Tactical Corner Brackets
          const cornerLen = Math.min(18, boxW / 4, boxH / 4);
          ctx.lineWidth = isColliding ? 4.5 : 3.5;
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
          let tagPrefix = '';
          if (isColliding) tagPrefix = '💥 [CRASH] ';
          else if (isProhibited) tagPrefix = '🚫 [PROHIBITED] ';

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
