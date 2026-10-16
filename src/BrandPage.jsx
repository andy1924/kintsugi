import React, { useRef } from "react";
import {
  motion,
  useScroll,
  useSpring,
  useTransform,
  useReducedMotion,
} from "motion/react";
import { ArrowUpRight, ArrowDown, Plus, Upload } from "lucide-react";
import StitchingStory from "./StitchingStory";

const ease = [0.22, 1, 0.36, 1];
function Reveal({ children, className = "", delay = 0 }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduced ? false : { opacity: 0, y: 32 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 1, ease, delay }}
    >
      {children}
    </motion.div>
  );
}
export default function BrandPage({ onBegin, onService = onBegin }) {
  const imageSection = useRef(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: imageSection,
    offset: ["start end", "end start"],
  });
  const progress = useSpring(scrollYProgress, {
    stiffness: 70,
    damping: 28,
    restDelta: 0.001,
  });
  const y = useTransform(progress, [0, 1], ["-12%", "12%"]);
  const scale = useTransform(progress, [0, 1], [1.12, 1]);
  return (
    <div className="atelier-page">
      <section className="atelier-intro" id="begin">
        <Reveal>
          <h1>
            Some things deserve
            <br />
            <em>another chapter.</em>
          </h1>
          <svg
            className="intro-stitch"
            viewBox="0 0 360 46"
            fill="none"
            aria-hidden="true"
          >
            <path
              className="intro-stitch-seam"
              d="M12 24C78 10 121 38 188 25S267 14 298 21"
            />
            <path
              className="intro-stitch-thread"
              d="M298 21c16 4 21 18 8 18s-10-15 5-20l16-6"
            />
            <path
              className="intro-stitch-needle"
              d="m319 16 28-12-24 17-4-5Z"
            />
            <path className="intro-stitch-eye" d="m324 16 7-3" />
          </svg>
          <motion.button
            className="stitched-upload"
            onClick={() => onBegin("new")}
            whileTap={reduced ? {} : { scale: 0.98 }}
          >
            <span className="stitched-upload-icon">
              <Upload size={21} strokeWidth={1.3} />
            </span>
            <span>Upload your piece</span>
            <ArrowUpRight
              className="stitched-upload-arrow"
              size={20}
              strokeWidth={1.4}
            />
          </motion.button>
        </Reveal>
      </section>
      <section
        className="cloth-story"
        ref={imageSection}
        aria-label="The beauty of visible repair"
      >
        <div className="cloth-window">
          <motion.img
            className="cloth-image"
            src="/mending-panorama.png"
            alt="Ivory linen and indigo denim repaired with delicate gold stitches on an atelier worktable"
            style={reduced ? {} : { y, scale }}
            fetchPriority="high"
          />
          <div className="cloth-shade" />
          <div className="cloth-topline">
            <span>01 / The art of keeping</span>
            <span>Worn with love. Mended with care.</span>
          </div>
          <div className="cloth-copy">
            <span>A new story, in every stitch.</span>
            <h2>
              Beautifully
              <br />
              <em>unfinished.</em>
            </h2>
            <a
              href="#philosophy"
              className="cloth-scroll"
              aria-label="Discover our philosophy"
            >
              <ArrowDown size={22} />
            </a>
          </div>
          <div className="cloth-bottomline">
            <span>Indigo, linen & a thread of possibility.</span>
            <span>Kintsugi atelier</span>
          </div>
        </div>
      </section>
      <section id="philosophy" className="atelier-belief">
        <Reveal>
          <span className="atelier-eyebrow">A different way to see it</span>
        </Reveal>
        <Reveal>
          <h2>
            Not worn out.
            <br />
            <em>Woven with memories.</em>
          </h2>
        </Reveal>
        <StitchingStory />
        <Reveal className="belief-copy">
          <p>
            A familiar fit. A particular summer. Someone who wore it before you.
            Some things hold more than their shape. Inspired by the Japanese art
            of repairing with gold, we turn the marks of living into something
            worth keeping. A tear becomes a line. A patch becomes a signature.
            And your piece becomes yours, all over again.
          </p>
        </Reveal>
        <Reveal>
          <button className="soft-link" onClick={() => onBegin("new")}>
            Find the possibility in your piece <ArrowUpRight size={18} />
          </button>
        </Reveal>
      </section>
      <section id="process" className="atelier-process">
        <Reveal className="process-heading">
          <span className="atelier-eyebrow">
            From a little wear, to a little wonder
          </span>
          <h2>
            A slower kind
            <br />
            of <em>transformation.</em>
          </h2>
        </Reveal>
        <div className="process-capsules">
          {[
            [
              "01",
              "Show us what you love.",
              "A photo of your piece is all it takes to begin. We’ll help you look at the damage in a new way.",
            ],
            [
              "02",
              "Find its next chapter.",
              "See a repair proposed for your piece. Then choose your own hands, or a skilled maker’s.",
            ],
            [
              "03",
              "Make a little more life.",
              "Follow your printable guide at your own pace, or put your piece in the hands of an independent maker.",
            ],
          ].map(([n, title, copy], i) => (
            <Reveal className="process-pill" key={n} delay={i * 0.1}>
              <span className="step-number">{n}</span>
              <div>
                <h3>{title}</h3>
                <p>{copy}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>
      <section id="possibilities" className="atelier-makers">
        <Reveal className="maker-image">
          <img
            src="/renaissance-atelier.png"
            alt="An engraved illustration of hands mending indigo cloth with golden thread"
            loading="lazy"
          />
        </Reveal>
        <Reveal className="maker-copy">
          <span className="atelier-eyebrow">
            Good things take a skilled hand
          </span>
          <h2>
            You keep a piece.
            <br />
            <em>
              Someone keeps
              <br />a craft alive.
            </em>
          </h2>
          <p>
            You don’t have to learn every stitch. Independent makers bring their
            skill; you bring something you love. We help coordinate the quote,
            collection, and journey home.
          </p>
          <button className="dark-pill" onClick={onService}>
            Find your maker <ArrowUpRight size={18} />
          </button>
        </Reveal>
      </section>
      <section className="atelier-questions">
        <Reveal>
          <span className="atelier-eyebrow">
            A few things, before you begin
          </span>
          <h2>
            A little <em>guidance.</em>
          </h2>
        </Reveal>
        <div>
          {[
            [
              "I’ve never mended anything. Is this for me?",
              "Absolutely. Start with a simple patch and running stitches. Your guide walks you through each step, and you can ask a maker to help whenever you need.",
            ],
            [
              "What should I photograph?",
              "Lay the piece flat in good light and capture the damaged area clearly. You can adjust the proposed boundary and optionally enter its measured width. Without a measurement, guides use a labelled suggested template size.",
            ],
            [
              "Can someone repair it for me?",
              "Yes. Request an itemised quote from an independent textile or decorative ceramic maker. Availability varies; collection, shipping and payment are coordinated by an operator.",
            ],
          ].map(([q, a]) => (
            <Reveal key={q}>
              <details>
                <summary>
                  {q}
                  <Plus size={18} />
                </summary>
                <p>{a}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </section>
      <section className="atelier-finale">
        <Reveal>
          <span className="atelier-eyebrow">
            Less replacing. More remembering.
          </span>
          <h2>
            There’s life
            <br />
            <em>in it yet.</em>
          </h2>
          <button className="dark-pill" onClick={() => onBegin("new")}>
            Let’s find it <ArrowUpRight size={19} />
          </button>
        </Reveal>
      </section>
      <footer className="atelier-footer">
        <a href="#begin">kintsugi.</a>
        <span>For the things we keep.</span>
        <a className="replay-opening" href="/?intro=1#begin">
          Watch the opening ↗
        </a>
        <span>© {new Date().getFullYear()} Kintsugi atelier</span>
      </footer>
    </div>
  );
}
