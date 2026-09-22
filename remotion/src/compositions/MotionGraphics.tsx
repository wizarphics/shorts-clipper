import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import type { MotionBadgeConfig } from "../lib/types";

interface MotionGraphicsProps {
  badges: MotionBadgeConfig[];
}

export const MotionGraphics: React.FC<MotionGraphicsProps> = ({ badges }) => {
  const { fps } = useVideoConfig();

  if (!badges || badges.length === 0) return null;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {badges.map((badge, idx) => {
        const startFrame = Math.round(badge.startSec * fps);
        const durationFrames = Math.max(1, Math.round(badge.durationSec * fps));

        return (
          <Sequence
            key={idx}
            from={startFrame}
            durationInFrames={durationFrames}
            layout="none"
          >
            <BadgeItem badge={badge} durationFrames={durationFrames} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

interface BadgeItemProps {
  badge: MotionBadgeConfig;
  durationFrames: number;
}

const BadgeItem: React.FC<BadgeItemProps> = ({ badge, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 1. Spring entrance animation with physics bounce
  const enterSpring = spring({
    frame,
    fps,
    config: {
      mass: 0.6,
      damping: 11,
      stiffness: 180,
    },
    durationInFrames: 18,
  });

  const scale = interpolate(enterSpring, [0, 1], [0.35, 1]);
  const translateY = interpolate(enterSpring, [0, 1], [60, 0]);
  let opacity = interpolate(enterSpring, [0, 1], [0, 1]);

  // Subtle breathing pulse while active
  const pulse = Math.sin((frame / fps) * Math.PI * 2) * 0.02;

  // 2. Smooth fade out on exit (last 12 frames)
  const exitFrames = 12;
  const exitStart = durationFrames - exitFrames;
  if (frame > exitStart) {
    const exitProgress = (frame - exitStart) / exitFrames;
    opacity *= 1 - exitProgress;
  }

  const accentColor = badge.accentColor || "#38bdf8";
  const styleType = badge.style || "glass";

  // Emoji pulse scale
  const emojiSpring = spring({
    frame: frame - 2,
    fps,
    config: { mass: 0.4, damping: 8, stiffness: 220 },
  });
  const emojiScale = interpolate(emojiSpring, [0, 1], [0.5, 1.15]);

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: badge.positionY ? `${badge.positionY}%` : "48%",
        transform: "translateY(-50%)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        opacity,
      }}
    >
      <div
        style={{
          transform: `scale(${scale + pulse}) translateY(${translateY}px)`,
          transformOrigin: "center center",
          willChange: "transform, opacity",
        }}
      >
        {renderBadgeStyle(styleType, badge, accentColor, emojiScale)}
      </div>
    </div>
  );
};

function renderBadgeStyle(
  styleType: string,
  badge: MotionBadgeConfig,
  accentColor: string,
  emojiScale: number
) {
  const title = (badge.title || "MUST WATCH").toUpperCase();
  const emoji = badge.emoji || "🔥";

  if (styleType === "alert") {
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 16,
          padding: "16px 36px",
          borderRadius: 24,
          backgroundColor: accentColor,
          border: "4px solid #ffffff",
          boxShadow: `0 12px 36px rgba(0,0,0,0.6), 0 0 25px ${accentColor}80`,
        }}
      >
        <span
          style={{
            fontSize: 48,
            transform: `scale(${emojiScale})`,
            display: "inline-block",
            filter: "drop-shadow(0 2px 6px rgba(0,0,0,0.4))",
          }}
        >
          {emoji}
        </span>
        <span
          style={{
            fontFamily: "system-ui, -apple-system, sans-serif",
            fontWeight: 900,
            fontSize: 34,
            letterSpacing: "1px",
            color: "#0f172a",
            textShadow: "0 1px 2px rgba(255,255,255,0.4)",
          }}
        >
          {title}
        </span>
      </div>
    );
  }

  if (styleType === "cyber") {
    return (
      <div
        style={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          gap: 18,
          padding: "18px 42px",
          backgroundColor: "rgba(10, 15, 30, 0.95)",
          border: `2px solid ${accentColor}`,
          clipPath: "polygon(24px 0%, 100% 0%, calc(100% - 24px) 100%, 0% 100%)",
          boxShadow: `0 0 30px ${accentColor}60, inset 0 0 15px ${accentColor}30`,
        }}
      >
        <span
          style={{
            fontSize: 46,
            transform: `scale(${emojiScale})`,
            display: "inline-block",
            filter: `drop-shadow(0 0 10px ${accentColor})`,
          }}
        >
          {emoji}
        </span>
        <span
          style={{
            fontFamily: "'Courier New', monospace, system-ui",
            fontWeight: 900,
            fontSize: 34,
            letterSpacing: "2.5px",
            color: "#ffffff",
            textShadow: `0 0 10px ${accentColor}, 0 0 20px ${accentColor}`,
          }}
        >
          {title}
        </span>
      </div>
    );
  }

  if (styleType === "sticker") {
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 16,
          padding: "18px 36px",
          borderRadius: 30,
          backgroundColor: "#ffffff",
          border: `6px solid ${accentColor}`,
          boxShadow: "0 16px 0px rgba(0, 0, 0, 0.9), 0 24px 30px rgba(0,0,0,0.5)",
        }}
      >
        <span
          style={{
            fontSize: 50,
            transform: `scale(${emojiScale})`,
            display: "inline-block",
          }}
        >
          {emoji}
        </span>
        <span
          style={{
            fontFamily: "Impact, system-ui, sans-serif",
            fontWeight: 900,
            fontSize: 38,
            letterSpacing: "1.5px",
            color: accentColor,
            textShadow: "1px 1px 0 #000, -1px -1px 0 #000",
          }}
        >
          {title}
        </span>
      </div>
    );
  }

  // Default: Glassmorphism (Opus Clip / Klap premier style)
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 18,
        padding: "18px 38px",
        borderRadius: 28,
        backgroundColor: "rgba(15, 23, 42, 0.88)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: `3px solid ${accentColor}`,
        boxShadow: `0 20px 45px rgba(0, 0, 0, 0.7), 0 0 25px ${accentColor}55`,
      }}
    >
      <span
        style={{
          fontSize: 48,
          transform: `scale(${emojiScale})`,
          display: "inline-block",
          filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.5))",
        }}
      >
        {emoji}
      </span>
      <span
        style={{
          fontFamily: "system-ui, -apple-system, sans-serif",
          fontWeight: 800,
          fontSize: 34,
          letterSpacing: "1px",
          color: "#ffffff",
          textShadow: "0 2px 10px rgba(0,0,0,0.8)",
        }}
      >
        {title}
      </span>
    </div>
  );
}
