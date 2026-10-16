import React, { useState, useEffect, useRef } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Upload,
  ChevronLeft,
  Check,
  Download,
  RefreshCw,
  Plus,
  LogOut,
  Lock,
  Heart,
} from "lucide-react";
import { api, asset, downloadPattern } from "./api";
import "./studio.css";
import ServiceDesk from "./ServiceDesk";
import RepairTutorial from "./RepairTutorial";
import RepairPreview from "./RepairPreview";
import GoogleSignIn from "./GoogleSignIn";
const styles = [
  ["sashiko", "Running stitch", "A simple woven grid."],
  ["branch", "Golden branch", "A branching line in gold."],
  ["constellation", "Constellation", "Connect the marks."],
  ["waves", "Seigaiha waves", "A repeating wave pattern."],
];
const labels = {
  uploaded: "Ready to analyse",
  analyzing: "Analysing",
  needs_review: "Review boundary",
  compiling: "Making pattern",
  ready: "Ready to mend",
  completed: "Repaired",
  failed: "Needs attention",
};
const readableError = (e) =>
  e.message || "Something went wrong. Please try again.";
function ErrorMessage({ message }) {
  return message ? (
    <div className="app-error" role="alert">
      {message}
    </div>
  ) : null;
}
function Auth({ onSuccess }) {
  const [mode, setMode] = useState("register"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="auth-panel">
      <span className="app-kicker">YOUR KINTSUGI WORKTABLE</span>
      <h1>
        A place for
        <br />
        <em>what you keep.</em>
      </h1>
      <p>
        Save your pieces, make a repair yourself, or put the work in the hands
        of an independent maker.
      </p>
      <GoogleSignIn onSuccess={onSuccess} onError={setError} />
      <div className="auth-tabs">
        <button
          onClick={() => {
            setMode("register");
            setError("");
          }}
          className={mode === "register" ? "active" : ""}
        >
          Create an account
        </button>
        <button
          onClick={() => {
            setMode("login");
            setError("");
          }}
          className={mode === "login" ? "active" : ""}
        >
          Sign in
        </button>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const d = new FormData(e.currentTarget);
          try {
            onSuccess(
              await api("/auth/" + mode, {
                method: "POST",
                body: Object.fromEntries(d),
              }),
            );
          } catch (e) {
            setError(readableError(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {mode === "register" && (
          <label>
            Your name
            <input name="name" autoComplete="name" required maxLength={80} />
          </label>
        )}
        <label>
          Email
          <input
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
          />
        </label>
        <label>
          Password
          <input
            name="password"
            type="password"
            autoComplete={
              mode === "register" ? "new-password" : "current-password"
            }
            minLength={10}
            maxLength={128}
            required
          />
        </label>
        {mode === "register" && (
          <small>
            At least 10 characters. Your photos stay private to your account.
          </small>
        )}
        <ErrorMessage message={error} />
        <button className="primary" disabled={busy}>
          {busy
            ? "Please wait…"
            : mode === "register"
              ? "Create my worktable"
              : "Sign in"}
          <ArrowRight size={16} />
        </button>
      </form>
    </div>
  );
}
function DamagePhoto({ project, box, onPoint, analysis }) {
  const image = useRef();
  const [first, setFirst] = useState(null);
  useEffect(() => setFirst(null), [project.id, analysis]);
  const click = (e) => {
    if (!onPoint) return;
    const r = e.currentTarget.getBoundingClientRect();
    const point = [
      Math.max(0.01, Math.min(0.99, (e.clientX - r.left) / r.width)),
      Math.max(0.01, Math.min(0.99, (e.clientY - r.top) / r.height)),
    ];
    if (!first) {
      setFirst(point);
      onPoint(null);
    } else {
      onPoint([
        Math.min(first[0], point[0]),
        Math.min(first[1], point[1]),
        Math.max(first[0], point[0]),
        Math.max(first[1], point[1]),
      ]);
      setFirst(null);
    }
  };
  return (
    <div
      className={"damage-photo " + (onPoint ? "editable" : "")}
      onClick={click}
    >
      <img
        ref={image}
        src={asset(`/projects/${project.id}/image`)}
        alt={project.title}
      />
      <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
        {box && (
          <rect
            x={box[0]}
            y={box[1]}
            width={box[2] - box[0]}
            height={box[3] - box[1]}
            fill="#b99a4133"
            stroke="#d4a744"
            strokeWidth=".004"
          />
        )}
        {first && (
          <circle cx={first[0]} cy={first[1]} r=".012" fill="#e1bb5d" />
        )}
        {analysis?.outlines.map((line, i) => (
          <polygon
            key={i}
            points={line.map((p) => p.join(",")).join(" ")}
            fill="#c2554833"
            stroke="#d16354"
            strokeWidth=".002"
          />
        ))}
      </svg>
      {onPoint && (
        <span className="photo-hint">
          {first
            ? "Now click the opposite corner"
            : "Click two opposite corners around the damage"}
        </span>
      )}
    </div>
  );
}
function UploadPiece({ onCreated }) {
  const [analysisService, setAnalysisService] = useState(null);
  useEffect(() => {
    api("/health")
      .then(setAnalysisService)
      .catch(() => {});
  }, []);
  const [file, setFile] = useState(null),
    [preview, setPreview] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const input = useRef();
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  function choose(f) {
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) {
      setError("Choose a JPG, PNG or WebP photo.");
      return;
    }
    if (f.size > 12 * 1024 * 1024) {
      setError("Choose a photo smaller than 12 MB.");
      return;
    }
    setError("");
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }
  return (
    <div className="new-piece">
      <span className="app-kicker">A PIECE WORTH KEEPING</span>
      <h1>
        What’s on
        <br />
        <em>your worktable?</em>
      </h1>
      <p>
        Photograph your piece flat, in good light. Include healthy fabric around
        the damaged area.
      </p>
      <p className="app-note">
        {analysisService?.damage_analysis === "openai"
          ? "Your textile photo is sent securely to OpenAI to find the tear, design a creative repair and generate a realistic preview. You can review the result and request another idea."
          : "Your photo is analysed locally to suggest a damage area. You can review and adjust the result."}
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!file) return;
          setBusy(true);
          setError("");
          const data = new FormData(e.currentTarget);
          data.set("image", file);
          try {
            let p = await api("/projects", { method: "POST", body: data });
            if (p.category === "textile") {
              try {
                p = await api(`/projects/${p.id}/analyze`, {
                  method: "POST",
                  body: {},
                });
              } catch {
                /* Saved uploads can retry detection from their repair page. */
              }
            }
            onCreated(p);
          } catch (e) {
            setError(readableError(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Kind of piece
          <select name="category">
            <option value="textile">Clothing or textile</option>
            <option value="ceramic">Vase or decorative ceramic</option>
          </select>
        </label>
        <label>
          Name your piece
          <input
            name="title"
            placeholder="My old denim jacket"
            required
            maxLength={100}
          />
        </label>
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(e) => choose(e.target.files[0])}
        />
        <button
          className="upload-area"
          type="button"
          onClick={() => input.current.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            choose(e.dataTransfer.files[0]);
          }}
        >
          {preview ? (
            <img
              className="upload-preview"
              src={preview}
              alt="Your selected piece"
            />
          ) : (
            <>
              <Upload size={26} />
              <strong>Choose a photograph</strong>
              <span>or drop it here · JPG, PNG, WebP · up to 12 MB</span>
            </>
          )}
        </button>
        <ErrorMessage message={error} />
        <button className="primary" disabled={!file || busy}>
          {busy ? "Saving your piece…" : "Upload and detect damage"}
          <ArrowRight size={16} />
        </button>
      </form>
    </div>
  );
}
function Repair({ initial, onUpdate, onService }) {
  const [project, setProject] = useState(initial),
    [box, setBox] = useState(
      initial.analysis?.box || initial.settings?.box || null,
    ),
    [style, setStyle] = useState(
      initial.analysis?.recommended_style || "sashiko",
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [health, setHealth] = useState(null),
    [choice, setChoice] = useState(
      ["ready", "needs_review", "analyzing", "compiling", "completed"].includes(
        initial.status,
      )
        ? "diy"
        : null,
    ),
    [showTutorial, setShowTutorial] = useState(false);
  const after = useRef();
  useEffect(() => {
    if (project.status === "needs_review") {
      setStyle(
        project.preview?.style ||
          project.analysis?.recommended_style ||
          "sashiko",
      );
    }
  }, [
    project.revision,
    project.status,
    project.preview?.revision,
    project.preview?.style,
  ]);
  useEffect(() => {
    api("/health")
      .then(setHealth)
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (
      !["analyzing", "compiling"].includes(project.status) &&
      !["queued", "running"].includes(project.preview?.state)
    )
      return;
    const controller = new AbortController();
    let timer;
    let active = true;
    const poll = async () => {
      try {
        const fresh = await api(`/projects/${project.id}`, {
          signal: controller.signal,
        });
        if (active) {
          setProject(fresh);
          onUpdate(fresh);
          setError("");
          if (
            ["analyzing", "compiling"].includes(fresh.status) ||
            ["queued", "running"].includes(fresh.preview?.state)
          )
            timer = setTimeout(poll, 2000);
        }
      } catch (e) {
        if (e.name !== "AbortError" && active) {
          setError(
            "Connection interrupted. Your work is saved; retrying shortly.",
          );
          timer = setTimeout(poll, 5000);
        }
      }
    };
    timer = setTimeout(poll, 1500);
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    project.id,
    project.status,
    project.preview?.state,
    project.preview?.revision,
  ]);
  async function act(fn) {
    setBusy(true);
    setError("");
    try {
      const p = await fn();
      if (p?.id) {
        setProject(p);
        onUpdate(p);
      }
    } catch (e) {
      setError(readableError(e));
    } finally {
      setBusy(false);
    }
  }
  const updateTutorial = (fresh) => {
    setProject(fresh);
    onUpdate(fresh);
  };
  if (!choice)
    return (
      <section className="repair-choice">
        <span className="app-kicker">{project.title}</span>
        <h1>
          How would you
          <br />
          <em>like to keep it?</em>
        </h1>
        <p>
          You can learn the repair at your own pace, or put it in the hands of
          someone who does this for a living.
        </p>
        <div className="repair-choice-grid">
          <button onClick={() => setChoice("diy")}>
            <span>MAKE IT YOURSELF</span>
            <h2>Guide me through it.</h2>
            <p>
              {project.category === "ceramic"
                ? "Start with a visual guide for simple decorative ceramic repairs. Check whether the job is suitable before you begin."
                : "Mark and measure the damage, get a repair pattern, and follow an illustrated tutorial one stitch at a time."}
            </p>
            <strong>
              Show me how <ArrowRight size={17} />
            </strong>
          </button>
          <button onClick={() => onService(project)}>
            <span>COMMISSION A MAKER</span>
            <h2>A skilled hand, instead.</h2>
            <p>
              Share the piece with an independent maker. Review their repair
              price and both shipping legs before accepting.
            </p>
            <strong>
              Find a maker <ArrowUpRight size={17} />
            </strong>
          </button>
        </div>
      </section>
    );
  if (showTutorial || project.category === "ceramic")
    return (
      <RepairTutorial
        project={project}
        practice={project.category === "textile" && !project.plan}
        onClose={() => {
          setShowTutorial(false);
          if (project.category === "ceramic") setChoice(null);
        }}
        onMaker={onService}
        onUpdate={updateTutorial}
      />
    );
  const marking = project.status === "uploaded" || project.status === "failed";
  const previewPending = ["queued", "running"].includes(project.preview?.state);
  const reviewing =
    project.status === "needs_review" ||
    (project.status === "ready" &&
      project.preview &&
      project.plan?.design_revision !== project.preview.revision);
  const refreshConcept = (direction = null) => {
    setConfirmed(false);
    act(() =>
      api(`/projects/${project.id}/preview`, {
        method: "POST",
        body: { style: direction },
      }),
    );
  };
  return (
    <>
      <div className="repair-heading">
        <div>
          <span className="app-kicker">
            {labels[project.status]?.toUpperCase()}
          </span>
          <h1>{project.title}</h1>
        </div>
        <span className="repair-ref">
          NO. {project.id.slice(0, 8).toUpperCase()}
        </span>
      </div>
      <ErrorMessage message={error || project.error} />
      <RepairPreview
        project={project}
        available={health?.creative_preview_available}
        onRefresh={() => refreshConcept()}
        busy={busy}
      />
      <div className="maker-help-banner">
        <div>
          <strong>A design you love, but not the skills to make it?</strong>
          <p>
            An independent maker can take it from here. Get a quote with
            round-trip shipping.
          </p>
        </div>
        <button className="secondary" onClick={() => onService(project)}>
          Find a maker <ArrowUpRight size={15} />
        </button>
      </div>
      {marking && (
        <button
          className="text-link practice-link"
          onClick={() => setShowTutorial(true)}
        >
          New to mending? Try the illustrated basics <ArrowUpRight size={15} />
        </button>
      )}
      <div className="repair-layout">
        <div>
          {project.plan && !reviewing ? (
            <img
              className="pattern-preview"
              src={asset(`/projects/${project.id}/pattern.svg`)}
              alt={project.plan.name + " printable pattern"}
            />
          ) : (
            <DamagePhoto
              project={project}
              box={marking ? box : project.analysis?.box}
              onPoint={marking ? setBox : undefined}
              analysis={reviewing ? project.analysis : null}
            />
          )}
          <p className="photo-caption">
            {project.plan && !reviewing
              ? `Pattern at ${project.plan.width_mm} × ${project.plan.height_mm} mm`
              : "Your photo stays private. Review the detected damage and adjust it if needed."}
          </p>
        </div>
        <div className="repair-controls">
          {marking ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const d = new FormData(e.currentTarget);
                act(() =>
                  api(`/projects/${project.id}/analyze`, {
                    method: "POST",
                    body: {
                      box,
                      width_mm: d.get("width_mm")
                        ? Number(d.get("width_mm"))
                        : null,
                      fabric: d.get("fabric") || null,
                      memory: d.get("memory"),
                    },
                  }),
                );
              }}
            >
              <h2>Let’s find the damage.</h2>
              <p>
                We’ll suggest a damage boundary and pattern size from your
                photo. You can adjust either, or leave these controls untouched
                for automatic detection.
              </p>
              <fieldset className="box-fields">
                <legend>Damage area (optional; % of photo)</legend>
                {["Left", "Top", "Right", "Bottom"].map((label, i) => (
                  <label key={label}>
                    {label}
                    <input
                      aria-label={label + " boundary"}
                      type="number"
                      step=".1"
                      min=".5"
                      max="99.5"
                      value={box ? Math.round(box[i] * 1000) / 10 : ""}
                      onChange={(e) => {
                        const next = [...(box || [0.2, 0.2, 0.8, 0.8])];
                        next[i] = Number(e.target.value) / 100;
                        setBox(next);
                      }}
                    />
                  </label>
                ))}
              </fieldset>
              <label>
                Adjust size in millimetres <span>optional</span>
                <input
                  name="width_mm"
                  type="number"
                  min="3"
                  max="150"
                  step=".1"
                  defaultValue={project.settings?.width_mm || ""}
                  placeholder={
                    project.analysis?.width_mm
                      ? `Suggested: ${project.analysis.width_mm} mm`
                      : "Use suggested template size"
                  }
                />
              </label>
              <label>
                Fabric
                <select
                  name="fabric"
                  defaultValue={project.settings?.fabric || ""}
                >
                  <option value="">Let analysis suggest the fabric</option>
                  {["Denim", "Cotton", "Linen", "Knit", "Other"].map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
              </label>
              <label>
                What makes this piece yours? <span>optional</span>
                <textarea
                  name="memory"
                  maxLength={500}
                  defaultValue={project.settings?.memory || ""}
                  placeholder="A memory, or simply the way it fits."
                />
              </label>
              <button className="primary" disabled={busy}>
                {busy
                  ? "Saving…"
                  : box
                    ? "Apply adjustments"
                    : "Detect damage automatically"}
                <ArrowRight size={16} />
              </button>
            </form>
          ) : ["analyzing", "compiling"].includes(project.status) ? (
            <div className="processing" role="status">
              <RefreshCw className="spin" size={27} />
              <h2>
                {project.status === "analyzing"
                  ? "Reading the damage."
                  : "Drawing your pattern."}
              </h2>
              <p>
                Your job is saved in the queue. You can leave and return to it.
              </p>
              {health && !health.worker_available && (
                <p className="app-note">
                  The processing worker is offline. Your repair will continue
                  when it reconnects.
                </p>
              )}
            </div>
          ) : reviewing ? (
            <>
              <span className="app-kicker">{project.analysis.engine}</span>
              <h2>Here’s what we found.</h2>
              <p>{project.analysis.assessment || "Damage area"}</p>
              {project.analysis.provider === "openai" && (
                <div className="vision-assessment">
                  <p className="app-kicker">
                    AI assessment · {project.analysis.confidence} confidence
                  </p>
                  <p>
                    {project.analysis.severity} damage · likely{" "}
                    {project.analysis.fabric.toLowerCase()}
                  </p>
                  <h3>A repair approach for this piece</h3>
                  <p>{project.analysis.repair_advice}</p>
                </div>
              )}
              <p>
                The proposed boundary is red; the gold rectangle shows the full
                area the backing will cover, plus a {project.analysis.margin_mm}{" "}
                mm anchoring margin.
              </p>
              <div className="measure-summary">
                <span>
                  {project.analysis.width_mm} × {project.analysis.height_mm} mm{" "}
                  {project.analysis.scale_source === "suggested"
                    ? "suggested template size"
                    : "damage area"}
                </span>
                <span>
                  {project.analysis.margin_mm} mm anchoring margin on every side
                </span>
              </div>
              <div className="analysis-notes">
                {project.analysis.warnings.map((n) => (
                  <p key={n}>{n}</p>
                ))}
              </div>
              <h3>
                {project.preview?.state === "ready"
                  ? "Your design’s stitch direction"
                  : "Choose your stitch direction"}
              </h3>
              <div className="style-options">
                {styles.map(([id, title, desc], i) => (
                  <button
                    key={id}
                    className={style === id ? "selected" : ""}
                    onClick={() => setStyle(id)}
                  >
                    <span>
                      {title}
                      {project.analysis.recommended_style === id
                        ? " · Suggested"
                        : ""}
                    </span>
                    <small>{desc}</small>
                  </button>
                ))}
              </div>
              {project.preview?.state === "ready" &&
                style !== project.preview.style && (
                  <button
                    className="secondary"
                    disabled={busy || previewPending}
                    onClick={() => refreshConcept(style)}
                  >
                    Visualise this direction <RefreshCw size={15} />
                  </button>
                )}
              <label className="confirm-check">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                The highlighted area covers the damage. I’ve reviewed the
                suggested size and will check the fit before cutting.
              </label>
              <button
                className="primary"
                disabled={
                  !confirmed ||
                  busy ||
                  previewPending ||
                  (project.preview?.state === "ready" &&
                    style !== project.preview.style) ||
                  project.analysis.requires_manual_area
                }
                onClick={() =>
                  act(() =>
                    api(`/projects/${project.id}/compile`, {
                      method: "POST",
                      body: {
                        revision: project.revision,
                        confirmed: true,
                        style,
                      },
                    }),
                  )
                }
              >
                {project.preview?.state === "ready"
                  ? "Make this design"
                  : "Create my pattern"}{" "}
                <ArrowRight size={16} />
              </button>
              <button
                className="text-link reset-analysis"
                onClick={() => {
                  setBox(
                    project.analysis?.box || project.settings?.box || null,
                  );
                  setProject({ ...project, status: "uploaded" });
                  setConfirmed(false);
                }}
              >
                Adjust damage or size
              </button>
            </>
          ) : (
            <>
              <span className="app-kicker">
                {project.plan?.estimated_minutes} MINUTES ·{" "}
                {(
                  project.settings.fabric ||
                  project.analysis?.fabric ||
                  "Other"
                ).toUpperCase()}
              </span>
              <h2>{project.plan?.name}</h2>
              <p>
                Your backing and stitch plan is ready. Check the printed
                calibration bar before you sew.
              </p>
              <div className="tutorial-start">
                <button
                  className="primary"
                  onClick={() => {
                    setShowTutorial(true);
                    window.scrollTo({ top: 0, behavior: "instant" });
                  }}
                >
                  Start the guided repair <ArrowRight size={16} />
                </button>
                <p>
                  Illustrated steps. Practise the stitch. Save your progress.
                </p>
              </div>
              <div className="download-row">
                {["pdf", "svg"].map((kind) => (
                  <button
                    className={kind === "pdf" ? "primary" : "secondary"}
                    key={kind}
                    onClick={() =>
                      act(async () => {
                        await downloadPattern(project, kind);
                      })
                    }
                  >
                    <Download size={15} />
                    {kind === "pdf" ? "Print guide" : "SVG pattern"}
                  </button>
                ))}
              </div>
              <h3>On your worktable</h3>
              <ul className="materials">
                {project.plan?.materials.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
              <p className="app-note">{project.plan?.disclaimer}</p>
              {project.status === "completed" ? (
                <div className="completion-panel">
                  <Check size={22} />
                  <h3>Another piece kept.</h3>
                  <p>Your finished repair is saved to your worktable.</p>
                </div>
              ) : (
                <div className="completion-panel">
                  <h3>Finished your repair?</h3>
                  <p>
                    Add a clear after-photo to save the finished piece to your
                    worktable.
                  </p>
                  <input
                    ref={after}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    hidden
                    onChange={(e) => {
                      const f = e.target.files[0];
                      if (!f) return;
                      act(async () => {
                        const d = new FormData();
                        d.append("image", f);
                        const result = await api(
                          `/projects/${project.id}/complete`,
                          { method: "POST", body: d },
                        );
                        return result.project;
                      });
                      e.target.value = "";
                    }}
                  />
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => after.current.click()}
                  >
                    <Upload size={14} />
                    {busy ? "Recording…" : "Add after-photo"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      {project.plan && (
        <section className="repair-method">
          <span className="app-kicker">ONE STITCH AT A TIME</span>
          <h2>Your method</h2>
          <ol>
            {project.plan.instructions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
        </section>
      )}
    </>
  );
}
export default function Studio({ onClose, initialView = "list" }) {
  const [account, setAccount] = useState(undefined),
    [projects, setProjects] = useState([]),
    [view, setView] = useState(initialView),
    [current, setCurrent] = useState(null),
    [serviceProject, setServiceProject] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [hasMore, setHasMore] = useState(false);
  useEffect(() => {
    let active = true;
    api("/auth/me")
      .then((data) => active && setAccount(data.user))
      .catch(() => active && setAccount(null));
    return () => {
      active = false;
    };
  }, []);
  async function refresh() {
    try {
      const p = await api("/projects");
      setProjects(p);
      setHasMore(p.length === 25);
    } catch (e) {
      setError(readableError(e));
    }
  }
  useEffect(() => {
    if (account) refresh();
  }, [account?.id]);
  function changed(p) {
    setProjects((old) =>
      [p, ...old.filter((x) => x.id !== p.id)].sort(
        (a, b) => b.created_at - a.created_at,
      ),
    );
  }
  function help(project = null) {
    setServiceProject(project);
    setView("services");
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  async function loadMore() {
    setBusy(true);
    try {
      const p = await api(`/projects?offset=${projects.length}`);
      setProjects((old) => [...old, ...p]);
      setHasMore(p.length === 25);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-shell">
      <div className="app-top">
        <button
          className="text-link"
          onClick={
            view === "list" || !account
              ? onClose
              : () => {
                  setView("list");
                  setServiceProject(null);
                  refresh();
                }
          }
        >
          <ChevronLeft size={15} />
          {view === "list" || !account ? "Back to the story" : "My worktable"}
        </button>
        {account && (
          <div>
            <button className="text-link" onClick={() => help()}>
              Repair services <ArrowUpRight size={13} />
            </button>
            <span>{account.name}</span>
            <GoogleSignIn link onError={setError} />
            <button
              className="text-link"
              onClick={async () => {
                try {
                  await api("/auth/logout", { method: "POST" });
                  setAccount(null);
                  setProjects([]);
                  setView("list");
                } catch (e) {
                  setError(e.message);
                }
              }}
            >
              Sign out <LogOut size={13} />
            </button>
          </div>
        )}
      </div>
      {account === undefined ? (
        <p className="loading" role="status">
          Opening your worktable…
        </p>
      ) : !account ? (
        <Auth onSuccess={(data) => setAccount(data.user)} />
      ) : (
        <>
          <ErrorMessage message={error} />
          {view === "services" ? (
            <ServiceDesk
              account={account}
              project={serviceProject}
              projects={projects}
              onStartUpload={() => setView("new")}
            />
          ) : view === "new" ? (
            <UploadPiece
              onCreated={(p) => {
                changed(p);
                setCurrent(p);
                setView("repair");
              }}
            />
          ) : view === "repair" ? (
            <Repair
              key={current.id}
              initial={current}
              onUpdate={changed}
              onService={help}
            />
          ) : (
            <>
              <div className="dashboard-heading">
                <div>
                  <span className="app-kicker">YOUR KINTSUGI WORKTABLE</span>
                  <h1>
                    Things worth
                    <br />
                    <em>keeping.</em>
                  </h1>
                </div>
                <button className="primary" onClick={() => setView("new")}>
                  <Plus size={16} />
                  Add a piece
                </button>
              </div>
              <div className="service-intro">
                <div>
                  <h2>
                    Your hands.
                    <br />
                    Or someone else's craft.
                  </h2>
                  <p>
                    Make a repair yourself, or commission an independent maker.
                    You get to keep something you love. They get paid for the
                    skill that makes it possible.
                  </p>
                </div>
                <button className="secondary" onClick={() => help()}>
                  Explore repair services <ArrowUpRight size={16} />
                </button>
              </div>
              {projects.length === 0 ? (
                <div className="empty-studio">
                  <h2>Your first piece belongs here.</h2>
                  <p>
                    A worn jacket, a torn bag, a chipped vase. Start with a
                    photo and we’ll help you find its next step.
                  </p>
                  <button className="text-link" onClick={() => setView("new")}>
                    Bring your piece <ArrowUpRight size={15} />
                  </button>
                </div>
              ) : (
                <div className="project-grid standalone">
                  {projects.map((p) => (
                    <button
                      key={p.id}
                      className="project-card"
                      onClick={() => {
                        setCurrent(p);
                        setView("repair");
                      }}
                    >
                      <img
                        src={asset(`/projects/${p.id}/image`)}
                        alt={p.title}
                      />
                      <div>
                        <span className={"status " + p.status}>
                          {p.category === "ceramic"
                            ? "Ceramic · specialist repair"
                            : labels[p.status]}
                        </span>
                        <h3>{p.title}</h3>
                        <span>
                          Open piece <ArrowUpRight size={13} />
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {hasMore && (
                <button
                  className="secondary load-more"
                  disabled={busy}
                  onClick={loadMore}
                >
                  Load more pieces
                </button>
              )}
            </>
          )}
        </>
      )}
    </main>
  );
}
