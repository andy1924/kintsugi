import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { motion, AnimatePresence, MotionConfig } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import BrandPage from "./BrandPage";
import Studio from "./Studio";
import ClothUnveiling from "./ClothUnveiling";
import "./style.css";
import "./brand.css";
import "./atelier.css";
function App() {
  const [studio, setStudio] = useState(false);
  const [entry, setEntry] = useState("list");
  function open(destination = "list") {
    setEntry(typeof destination === "string" ? destination : "list");
    setStudio(true);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  function close() {
    setStudio(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  function visit(event, id) {
    event.preventDefault();
    setStudio(false);
    window.history.replaceState(null, "", `#${id}`);
    // The destination is mounted after the studio exit transition.
    pendingSection.current = id;
    if (!studio) scrollToSection();
  }
  const pendingSection = React.useRef(null);
  function scrollToSection() {
    const id = pendingSection.current;
    if (!id) return;
    requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
      pendingSection.current = null;
    });
  }
  return (
    <>
      <ClothUnveiling />
      <header className="atelier-masthead">
        <a className="logo" href="#begin" onClick={close}>
          kintsugi<span className="logo-stitch">.</span>
        </a>
        <span className="masthead-note">For the things we keep.</span>
        <button className="masthead-studio" onClick={() => open()}>
          My studio <ArrowUpRight size={15} />
        </button>
      </header>
      <nav className="floating-nav" aria-label="Main navigation">
        <a href="#begin" onClick={(e) => visit(e, "begin")}>
          The atelier
        </a>
        <a href="#philosophy" onClick={(e) => visit(e, "philosophy")}>
          Our story
        </a>
        <a href="#process" onClick={(e) => visit(e, "process")}>
          The process
        </a>
        <button onClick={() => open("services")}>Find a maker</button>
        <button
          className="nav-begin"
          aria-current={studio && entry === "new" ? "page" : undefined}
          onClick={() => open("new")}
        >
          Begin a repair <ArrowUpRight size={14} />
        </button>
      </nav>
      <AnimatePresence mode="wait">
        {studio ? (
          <motion.div
            key="studio"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Studio key={entry} onClose={close} initialView={entry} />
          </motion.div>
        ) : (
          <motion.main
            key="home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onAnimationComplete={scrollToSection}
            transition={{ duration: 0.3 }}
          >
            <BrandPage onBegin={open} onService={() => open("services")} />
          </motion.main>
        )}
      </AnimatePresence>
    </>
  );
}
createRoot(document.getElementById("root")).render(
  <MotionConfig reducedMotion="user">
    <App />
  </MotionConfig>,
);
