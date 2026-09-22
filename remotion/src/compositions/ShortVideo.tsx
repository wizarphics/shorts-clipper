import React from "react";
import { AbsoluteFill } from "remotion";
import { Video } from "@remotion/media";
import type { ShortVideoProps } from "../lib/types";
import { Subtitles } from "./Subtitles";
import { HookOverlay } from "./HookOverlay";
import { VideoEffects } from "./VideoEffects";
import { MotionGraphics } from "./MotionGraphics";

/**
 * Main composition that layers all post-processing on top of the base video:
 * 1. Base video with dynamic zoom/color grading
 * 2. Animated kinetic subtitles with word-by-word highlighting
 * 3. Opening hook banner with spring/slide physics
 * 4. Contextual Motion Graphics badges (glass, alert, cyber, sticker) with vector emojis
 */
export const ShortVideo: React.FC<Record<string, unknown>> = (rawProps) => {
  const { videoUrl, subtitles, hook, motionBadges, effects } =
    rawProps as unknown as ShortVideoProps;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Layer 1: Base video with optional zoom/color effects */}
      <VideoEffects config={effects}>
        <Video
          src={videoUrl}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </VideoEffects>

      {/* Layer 2: Contextual Motion Graphic Badges & Emojis with Spring Physics */}
      {motionBadges && motionBadges.length > 0 && (
        <MotionGraphics badges={motionBadges} />
      )}

      {/* Layer 3: Animated Subtitles */}
      {subtitles && <Subtitles config={subtitles} />}

      {/* Layer 4: Hook Text Overlay */}
      {hook && <HookOverlay config={hook} />}
    </AbsoluteFill>
  );
};
