import React, { useState, useRef } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  ChevronLeft,
  Check,
  Upload,
  Play,
} from "lucide-react";
import { api, asset } from "./api";
import "./tutorial.css";
const clothSteps = [
  {
    title: "Set up your piece.",
    short: "Prepare",
    body: "Lay the garment flat in good light. Keep the repair area relaxed, without stretching it. Gather a needle, thread, scissors, compatible backing fabric and a ruler.",
    tip: "If you have a printed pattern, measure its 20 mm bar. It must measure 20 mm before you use the template.",
  },
  {
    title: "Give the damage a backing.",
    short: "Back the tear",
    body: "Cut the backing to the dimensions in your repair plan. Place it behind the tear so the healthy fabric around every damaged edge has support.",
    tip: "Choose backing with similar weight and stretch. A stiff patch on a stretchy garment can pull at the edges.",
  },
  {
    title: "Hold it gently in place.",
    short: "Baste",
    body: "Pin the backing without stretching the garment. Use a few long, loose temporary stitches to keep the layers together. Keep them away from your final stitch line.",
    tip: "Check that your needle is only passing through the layers you intend to join. Keep the other side of a sleeve or pocket out of the way.",
  },
  {
    title: "Learn the running stitch.",
    short: "Practise the stitch",
    body: "Bring the needle up from the back. Move a short distance along the line and take it down through both layers. Come up again, leaving a small gap. Repeat with relaxed tension.",
    tip: "Practise on a scrap first. Aim for short, evenly spaced stitches, roughly 3 mm apart. If the fabric gathers, loosen the thread rather than pulling harder.",
  },
  {
    title: "Follow your own pattern.",
    short: "Follow the design",
    body: "Secure the patch perimeter in healthy fabric first. Then follow the motif from your plan, using the running stitch you practised. Work one short section at a time.",
    tip: "You can choose a simpler finish. The backing and secure edges matter more than making every decorative stitch identical.",
  },
  {
    title: "Finish, then try it on.",
    short: "Finish",
    body: "Secure the thread on the back and remove the temporary basting. Check for loose edges, then gently test the garment’s movement. Follow the fabric’s normal care instructions.",
    tip: "If the patch pulls or a new tear forms, stop and get help. A maker can assess the fabric and finish the repair.",
  },
];
const ceramicSteps = [
  {
    title: "Check whether this is a DIY repair.",
    short: "Assess",
    body: "This guide is for a simple decorative ceramic with a few clean-fitting pieces. Keep sharp fragments away from children and protect your hands while handling them.",
    tip: "Use a specialist for valuable pieces, many missing fragments, or objects intended for food, hot liquids, heat or structural use. A decorative repair is not a safety certification.",
  },
  {
    title: "Prepare a quiet work surface.",
    short: "Prepare",
    body: "Use a stable, protected surface and collect the fragments. Remove loose dirt gently and let the surfaces dry. Follow the preparation and ventilation instructions for the adhesive you intend to use.",
    tip: "Keep small fragments in a labelled container. Avoid aggressive cleaning that could damage a glaze or finish.",
  },
  {
    title: "Fit the pieces without adhesive.",
    short: "Dry-fit",
    body: "Check how the pieces meet without forcing them. Work out the order of assembly and a way to support each piece. If edges do not fit cleanly, stop and ask a ceramic restorer.",
    tip: "Take a photo of the dry fit. It can help a maker understand the repair if you decide to hand it over.",
  },
  {
    title: "Follow the adhesive’s own instructions.",
    short: "Join",
    body: "Select an adhesive explicitly suitable for the ceramic and its intended decorative use. Follow its label for application, alignment, protective equipment and excess removal. Use the manufacturer’s instructions rather than a guessed amount or mix ratio.",
    tip: "Do not add decorative powders or coatings unless the adhesive manufacturer permits them. The product determines what is compatible.",
  },
  {
    title: "Let the joint fully cure.",
    short: "Cure",
    body: "Support the pieces as directed and leave them undisturbed for the manufacturer’s full cure time. Setting time and full cure time can be different. Do not fill the vase or test its strength early.",
    tip: "There is no universal cure time. Read the instructions for the exact product and conditions you are using.",
  },
  {
    title: "Inspect the decorative finish.",
    short: "Inspect",
    body: "Inspect the join without stressing it. Keep the object for the decorative use supported by the adhesive and repair. If it feels unstable, stop using it and ask a specialist.",
    tip: "Food contact, hot liquids, water resistance and heat resistance need separate confirmation. A good-looking join does not prove any of these.",
  },
];
function StitchDiagram({ step, stitch, onStitch, ceramic }) {
  if (ceramic)
    return (
      <div className="tutorial-diagram">
        <svg
          viewBox="0 0 460 300"
          role="img"
          aria-label="A decorative vase with separated fragments and a repair seam"
        >
          <path
            d="M160 45h90l-10 65q70 42 42 135-45 24-135 0-28-93 42-135z"
            fill="#e4d8bf"
            stroke="#8b7a5a"
            strokeWidth="2"
          />
          <path
            d="m213 54-10 49 25 29-18 42 19 38-12 36"
            stroke="#ad8137"
            strokeWidth="4"
            fill="none"
            strokeDasharray={step < 3 ? "5 6" : undefined}
          />
          <path d="M183 55h44" stroke="#75664b" strokeWidth="2" />
          <path
            d="m304 118 27 15-8 29-26-12z"
            fill="#e4d8bf"
            stroke="#8b7a5a"
            strokeWidth="2"
          />
          <path
            d="M289 153h-37"
            stroke="#ad8137"
            strokeWidth="1.5"
            strokeDasharray="3 4"
          />
          <text
            x="230"
            y="282"
            textAnchor="middle"
            fill="#8b7a5a"
            fontSize="10"
            fontFamily="sans-serif"
            letterSpacing="1.5"
          >
            DRY-FIT FIRST. FOLLOW YOUR ADHESIVE LABEL.
          </text>
        </svg>
      </div>
    );
  return (
    <div className="tutorial-diagram">
      <svg
        viewBox="0 0 460 300"
        role="img"
        aria-label={
          step === 3
            ? "Running stitch demonstration: solid thread is visible, dashed thread passes beneath the fabric."
            : "Fabric backing and stitch placement illustration"
        }
      >
        <defs>
          <pattern
            id="tutorial-weave"
            width="5"
            height="5"
            patternUnits="userSpaceOnUse"
          >
            <rect width="5" height="5" fill="#384248" />
            <path
              d="M0 0h5M0 0v5"
              stroke="#74858d"
              strokeOpacity=".23"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect
          x="45"
          y="43"
          width="370"
          height="200"
          fill="url(#tutorial-weave)"
        />
        {step === 0 ? (
          <>
            <rect x="80" y="205" width="300" height="25" fill="#d9c995" />
            {Array.from({ length: 30 }, (_, i) => (
              <path
                key={i}
                d={`M${85 + i * 10} 205v${i % 5 === 0 ? 15 : 8}`}
                stroke="#75664b"
              />
            ))}
          </>
        ) : (
          <>
            <rect
              x="110"
              y="79"
              width="240"
              height="130"
              fill="#d4c5a2"
              fillOpacity=".8"
              stroke="#e5d4a5"
              strokeDasharray={step < 3 ? "5 7" : undefined}
            />
            <path
              d="m215 99 12 26-14 25 18 31"
              stroke="#32383c"
              strokeWidth="12"
              fill="none"
            />
            {step === 2 && (
              <path
                d="M122 91h216v106H122z"
                stroke="#f1ead7"
                strokeWidth="2"
                strokeDasharray="15 12"
                fill="none"
              />
            )}
          </>
        )}
        {step === 3 && (
          <>
            <rect x="75" y="106" width="310" height="65" fill="#c4c2b8" />
            <path
              d="M82 138h298"
              stroke="#c4ab78"
              strokeWidth="1"
              strokeDasharray="2 3"
            />
            {Array.from({ length: Math.min(6, stitch) }, (_, i) => (
              <path
                key={i}
                d={`M${90 + i * 45} 138h${i % 2 === 0 ? 28 : 22}`}
                stroke={i % 2 === 0 ? "#a47120" : "#786c54"}
                strokeWidth="3"
                strokeDasharray={i % 2 === 0 ? undefined : "4 3"}
              />
            ))}
            <path
              d={`M${Math.min(365, 90 + stitch * 45)} 138l22-38`}
              stroke="#f5f1e5"
              strokeWidth="4"
            />
            <text
              x="230"
              y="220"
              textAnchor="middle"
              fill="#dacda9"
              fontSize="11"
              fontFamily="sans-serif"
            >
              Solid: visible thread · Dashed: beneath the fabric
            </text>
          </>
        )}
        {step >= 4 && (
          <path
            d="m228 202-4-27 12-30-13-22 5-25m-4 78-35-15m47-16 32-22"
            stroke="#d0a24c"
            strokeWidth="3"
            fill="none"
          />
        )}
        <text
          x="230"
          y="278"
          textAnchor="middle"
          fill="#8b7a5a"
          fontSize="10"
          fontFamily="sans-serif"
          letterSpacing="1.5"
        >
          {step === 3
            ? "UP. ALONG. DOWN. REPEAT."
            : "BACKING BEHIND. STITCH INTO HEALTHY FABRIC."}
        </text>
      </svg>
      {step === 3 && (
        <button className="secondary" onClick={onStitch}>
          <Play size={13} />
          {stitch >= 6
            ? "Replay the stitch"
            : `Next stitch · ${stitch + 1} / 6`}
        </button>
      )}
    </div>
  );
}
export default function RepairTutorial({
  project,
  onClose,
  onMaker,
  onUpdate,
  practice = false,
}) {
  const ceramic = project.category === "ceramic";
  const steps = ceramic
    ? ceramicSteps
    : clothSteps.map((step, index) => ({
        ...step,
        ...(project.plan?.creative_steps?.[index] || {}),
      }));
  const [index, setIndex] = useState(() =>
      Math.min(5, (project.tutorial_steps || []).length),
    ),
    [completed, setCompleted] = useState(project.tutorial_steps || []),
    [stitch, setStitch] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const after = useRef();
  const step = steps[index];
  const canSave = !practice && (ceramic || project.plan);
  async function mark() {
    const next = completed.includes(index)
      ? completed.filter((i) => i !== index)
      : [...completed, index].sort();
    if (!canSave) {
      setCompleted(next);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const fresh = await api(`/projects/${project.id}/tutorial`, {
        method: "POST",
        body: { completed: next },
      });
      setCompleted(fresh.tutorial_steps);
      onUpdate(fresh);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="repair-tutorial">
      <button className="text-link" onClick={onClose}>
        <ChevronLeft size={15} />
        {practice ? "Back to marking" : "Back to your piece"}
      </button>
      <div className="tutorial-heading">
        <div>
          <span className="app-kicker">
            {practice ? "PRACTISE BEFORE YOU BEGIN" : "A GUIDE AT YOUR PACE"} ·{" "}
            {ceramic ? "DECORATIVE CERAMIC" : "VISIBLE MENDING"}
          </span>
          <h1>{project.title}</h1>
        </div>
        <span>{completed.length} / 6 steps checked</span>
      </div>
      {error && (
        <div className="app-error" role="alert">
          {error}
        </div>
      )}
      <div className="tutorial-layout">
        <nav className="tutorial-index" aria-label="Repair tutorial steps">
          {steps.map((s, i) => (
            <button
              key={s.short}
              className={index === i ? "active" : ""}
              onClick={() => {
                setIndex(i);
                setStitch(0);
              }}
            >
              <span>
                {completed.includes(i) ? (
                  <Check size={12} />
                ) : (
                  String(i + 1).padStart(2, "0")
                )}
              </span>
              {s.short}
            </button>
          ))}
        </nav>
        <div className="tutorial-current">
          <StitchDiagram
            step={index}
            stitch={stitch}
            onStitch={() => setStitch(stitch >= 6 ? 0 : stitch + 1)}
            ceramic={ceramic}
          />
          <span className="app-kicker">STEP {index + 1} OF 6</span>
          <h2>{step.title}</h2>
          <p>{step.body}</p>
          <div className="tutorial-tip">{step.tip}</div>
          {!ceramic && index === 4 && project.plan && (
            <a
              className="text-link"
              href={asset(`/projects/${project.id}/pattern.pdf`)}
              download
            >
              Open your measured pattern <ArrowUpRight size={15} />
            </a>
          )}
          {ceramic && index === 3 && (
            <a
              className="text-link"
              href="https://www.loctiteproducts.com/ideas/fix-stuff/how-to-fix-broken-ceramic-tips-for-breaks-cracks-and-chinks.html"
              target="_blank"
              rel="noreferrer"
            >
              Read the adhesive manufacturer’s repair guide{" "}
              <ArrowUpRight size={14} />
            </a>
          )}
          <div className="tutorial-actions">
            <button className="secondary" disabled={busy} onClick={mark}>
              {completed.includes(index) ? <Check size={14} /> : null}
              {completed.includes(index)
                ? "Step checked"
                : "Mark this step done"}
            </button>
            {index < 5 ? (
              <button
                className="primary"
                onClick={() => {
                  setIndex(index + 1);
                  setStitch(0);
                }}
              >
                Next step <ArrowRight size={15} />
              </button>
            ) : (
              <button className="primary" onClick={onClose}>
                Return to my piece <ArrowRight size={15} />
              </button>
            )}
          </div>
          {practice && (
            <p className="app-note">
              This is a practice guide. Create your measured repair pattern
              before saving progress on the final repair.
            </p>
          )}
          {completed.length === 6 &&
            canSave &&
            project.status !== "completed" && (
              <div className="tutorial-finish">
                <h3>Your last step: keep the finished story.</h3>
                <p>
                  Add a fresh after-photo to record the repair on your
                  worktable.
                </p>
                <input
                  ref={after}
                  hidden
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={async (e) => {
                    const file = e.target.files[0];
                    if (!file) return;
                    setBusy(true);
                    setError("");
                    try {
                      const data = new FormData();
                      data.append("image", file);
                      const result = await api(
                        `/projects/${project.id}/complete`,
                        { method: "POST", body: data },
                      );
                      onUpdate(result.project);
                    } catch (e) {
                      setError(e.message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => after.current.click()}
                >
                  <Upload size={14} />
                  Save my after-photo
                </button>
              </div>
            )}
          {project.status === "completed" && (
            <p className="tutorial-recorded">
              <Check size={15} /> Finished repair recorded.
            </p>
          )}
        </div>
        <aside className="tutorial-help">
          <span className="app-kicker">YOU CAN CHANGE YOUR MIND</span>
          <h3>
            It’s okay to
            <br />
            pass the needle.
          </h3>
          <p>
            {ceramic
              ? "If the pieces are difficult to align, or you are unsure about the intended use, a ceramic restorer can assess the job."
              : "If the stitch or finish feels beyond your skills, an independent maker can take over."}
          </p>
          <button
            className="secondary"
            onClick={() => onMaker({ ...project, tutorial_steps: completed })}
          >
            Let a maker help <ArrowUpRight size={15} />
          </button>
          <p className="app-note">
            Your saved design and completed steps go with the request. You’ll
            review their price before accepting.
          </p>
          {project.plan && (
            <div className="tutorial-materials">
              <h4>Before you begin</h4>
              <ul>
                {project.plan.materials.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
