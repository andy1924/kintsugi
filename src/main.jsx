import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { motion, AnimatePresence, MotionConfig } from "motion/react";
import { ArrowUpRight, Menu } from "lucide-react";
import BrandPage from "./BrandPage";
import Studio from "./Studio";
import "./style.css";
import "./brand.css";
function App() {
  const [studio, setStudio] = useState(false),
    [menu, setMenu] = useState(false),
    [entry, setEntry] = useState("list");
  function open(destination = "list") {
    setEntry(typeof destination === "string" ? destination : "list");
    setStudio(true);
    setMenu(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  function close() {
    setStudio(false);
    setMenu(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  return (
    <>
      <header>
        <a className="logo" href="#" onClick={close}>
          Kintsugi<span className="logo-stitch">.</span>
        </a>
        <nav className={menu ? "open" : ""}>
          <a href="#philosophy" onClick={close}>
            Our story
          </a>
          <a href="#process" onClick={close}>
            The process
          </a>
          <a href="#possibilities" onClick={close}>
            The worktable <span>↗</span>
          </a>
        </nav>
        <button className="nav-cta" onClick={open}>
          My studio <ArrowUpRight size={15} />
        </button>
        <button
          aria-label="Toggle menu"
          className="menu"
          onClick={() => setMenu(!menu)}
        >
          <Menu />
        </button>
      </header>
      <AnimatePresence mode="wait">
        {studio ? (
          <motion.div
            key="studio"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Studio onClose={close} initialView={entry} />
          </motion.div>
        ) : (
          <motion.main
            key="home"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
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
