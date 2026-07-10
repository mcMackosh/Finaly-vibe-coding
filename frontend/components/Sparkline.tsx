"use client";

import { useEffect, useRef } from "react";
import type { PricePoint } from "@/lib/store";

/**
 * A compact canvas price trail. Draws the accumulated SSE points for one
 * ticker; colored by net direction over the window. Redraws on data change.
 */
export function Sparkline({
  points,
  width = 96,
  height = 28,
}: {
  points: PricePoint[];
  width?: number;
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    if (points.length < 2) return;

    const values = points.map((p) => p.price);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pad = 2;
    const stepX = (width - pad * 2) / (values.length - 1);
    const y = (v: number) =>
      height - pad - ((v - min) / range) * (height - pad * 2);

    const rising = values[values.length - 1] >= values[0];
    ctx.strokeStyle = rising ? "#10b981" : "#f43f5e";
    ctx.lineWidth = 1.75;
    ctx.lineJoin = "round";
    ctx.beginPath();
    values.forEach((v, i) => {
      const px = pad + i * stepX;
      const py = y(v);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();
  }, [points, width, height]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height }}
      className="block"
      aria-hidden
    />
  );
}
