import React, { useEffect, useState } from "react";
import { motion, useReducedMotion } from "motion/react";

export default function ClothUnveiling() {
  const reduced = useReducedMotion();
  const [visible, setVisible] = useState(true);
  const [unveil, setUnveil] = useState(false);
  function finish() {
    setVisible(false);
  }
  useEffect(() => {
    if (!visible) return;
    if (reduced) {
      finish();
      return;
    }
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const timer = window.setTimeout(() => setUnveil(true), 2500);
    return () => {
      window.clearTimeout(timer);
      document.body.style.overflow = previous;
    };
  }, [visible, reduced]);
  if (!visible || reduced) return null;
  return (
    <motion.div
      className="cloth-unveiling"
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to Kintsugi"
      onKeyDown={(event) => {
        if (event.key === "Escape") finish();
        if (event.key === "Tab") {
          event.preventDefault();
          event.currentTarget.querySelector("button")?.focus();
        }
      }}
      initial={{ opacity: 1 }}
      animate={{ opacity: unveil ? 0 : 1 }}
      transition={{ delay: unveil ? 0.8 : 0, duration: 0.5 }}
      onAnimationComplete={() => unveil && finish()}
    >
      <motion.div
        className="unveiling-backdrop"
        animate={{ opacity: unveil ? 0 : 1 }}
        transition={{ duration: 0.3 }}
      />
      <motion.div
        className="unveiling-cloth unveiling-cloth-left"
        initial={{ x: "-14%", rotate: -3 }}
        animate={
          unveil
            ? { x: "-108%", rotate: -8, borderBottomRightRadius: "48%" }
            : { x: 0, rotate: 0 }
        }
        transition={{ duration: unveil ? 1.1 : 0.85, ease: [0.65, 0, 0.25, 1] }}
      >
        <div className="unveiling-patch patch-indigo" />
        <div className="unveiling-patch patch-forest" />
      </motion.div>
      <motion.div
        className="unveiling-cloth unveiling-cloth-right"
        initial={{ x: "14%", rotate: 3 }}
        animate={
          unveil
            ? { x: "108%", rotate: 8, borderTopLeftRadius: "48%" }
            : { x: 0, rotate: 0 }
        }
        transition={{ duration: unveil ? 1.1 : 0.85, ease: [0.65, 0, 0.25, 1] }}
      >
        <div className="unveiling-patch patch-wine" />
        <div className="unveiling-patch patch-earth" />
      </motion.div>
      <motion.svg
        className="unveiling-thread"
        viewBox="0 0 80 800"
        preserveAspectRatio="none"
        aria-hidden="true"
        animate={{ opacity: unveil ? 0 : 1 }}
        transition={{ duration: 0.2 }}
      >
        <defs>
          <clipPath id="unveiling-seam-clip">
            <motion.rect
              x="0"
              y="0"
              width="80"
              initial={{ height: 0 }}
              animate={{ height: 800 }}
              transition={{ delay: 0.65, duration: 1.6, ease: "easeInOut" }}
            />
          </clipPath>
        </defs>
        <g clipPath="url(#unveiling-seam-clip)">
          <path
            d="M40 0V800"
            fill="none"
            stroke="#100e0b"
            strokeWidth="5"
            opacity=".6"
          />
          {Array.from({ length: 33 }, (_, i) => (
            <path
              key={i}
              d={`M24 ${i * 25 - 5}l32 18m-32 3 32-18`}
              fill="none"
              stroke="#d49d57"
              strokeWidth="2.2"
              strokeLinecap="round"
            />
          ))}
        </g>
        <motion.circle
          cx="40"
          r="4"
          fill="#f2d39a"
          initial={{ cy: 0 }}
          animate={{ cy: 800 }}
          transition={{ delay: 0.65, duration: 1.6, ease: "easeInOut" }}
        />
      </motion.svg>
      <motion.div
        className="unveiling-title"
        initial={{ opacity: 0 }}
        animate={{ opacity: unveil ? 0 : 1 }}
        transition={{ duration: 0.5, delay: unveil ? 0 : 0.4 }}
      >
        <span>kintsugi.</span>
        <p>A little care. A new beginning.</p>
      </motion.div>
      <button className="unveiling-skip" onClick={finish} autoFocus>
        Skip intro <span aria-hidden="true">↗</span>
      </button>
    </motion.div>
  );
}
