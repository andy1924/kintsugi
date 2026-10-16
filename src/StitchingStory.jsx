import React, { useRef } from "react";
import {
  motion,
  useScroll,
  useSpring,
  useTransform,
  useReducedMotion,
} from "motion/react";

const stitchCount = 39;
const seamY = (t) => 220 + Math.sin(t * Math.PI * 2) * 12;

function Stitch({ index, progress, reduced }) {
  const t = index / (stitchCount - 1);
  const opacity = useTransform(
    progress,
    [Math.max(0, t - 0.025), Math.max(0.01, t)],
    [0, 1],
  );
  const x = 110 + t * 520;
  const y = seamY(t);
  return (
    <motion.path
      d={`M${x - 3} ${y - 8}l6 16`}
      style={{ opacity: reduced ? 1 : opacity }}
    />
  );
}

export default function StitchingStory() {
  const target = useRef(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target,
    offset: ["start 0.9", "end 0.4"],
  });
  const progress = useSpring(scrollYProgress, { stiffness: 85, damping: 28 });
  const x = useTransform(progress, [0, 1], [110, 630]);
  const y = useTransform(
    progress,
    (t) => seamY(t) - Math.sin(t * Math.PI * 26) * 7,
  );
  const opacity = useTransform(progress, [0, 0.09], [0, 1]);
  const rotate = useTransform(progress, (t) => Math.sin(t * Math.PI * 26) * 3);
  return (
    <div className="memory-stitch-scene" ref={target}>
      <svg
        viewBox="0 0 900 340"
        role="img"
        aria-label="A hand guides a needle across two pieces of fabric, leaving golden stitches as you scroll"
      >
        <defs>
          <pattern
            id="memory-weave"
            width="5"
            height="5"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M0 1h5M1 0v5"
              stroke="#a69c7f"
              strokeWidth=".45"
              opacity=".18"
            />
          </pattern>
          <linearGradient id="memory-fabric" x2="0" y2="1">
            <stop stopColor="#e7e4d7" />
            <stop offset="1" stopColor="#eeece2" />
          </linearGradient>
        </defs>
        <path
          d="M58 162Q234 137 406 166T748 159L775 275Q595 291 405 271T71 283Z"
          fill="url(#memory-fabric)"
        />
        <path
          d="M58 162Q234 137 406 166T748 159L775 275Q595 291 405 271T71 283Z"
          fill="url(#memory-weave)"
        />
        <path
          d="M91 220q66 20 139 7t132-14 135 8 152-1"
          fill="none"
          stroke="#b7ad93"
          strokeWidth="1.2"
          strokeDasharray="2 3"
        />
        <g fill="none" stroke="#ac7b3f" strokeWidth="2.4" strokeLinecap="round">
          {Array.from({ length: stitchCount }, (_, index) => (
            <Stitch
              key={index}
              index={index}
              progress={progress}
              reduced={reduced}
            />
          ))}
        </g>
        <motion.g
          style={reduced ? { x: 630, y: 220 } : { x, y, opacity, rotate }}
        >
          <path
            d="M1 0Q-27-42-5-63C11-78 28-60 13-48S-9-25 39-42"
            fill="none"
            stroke="#b78b48"
            strokeWidth="1.2"
          />
          <image
            href="/sewing-hand.png"
            x="-25"
            y="-218"
            width="240"
            height="240"
          />
        </motion.g>
      </svg>
    </div>
  );
}
