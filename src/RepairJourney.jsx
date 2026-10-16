import React, { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Download,
  RefreshCw,
  Scissors,
  HandHeart,
} from "lucide-react";
import { api, asset, downloadPattern } from "./api";
import RepairPreview from "./RepairPreview";
import RepairTutorial from "./RepairTutorial";
import DamagePhoto from "./DamagePhoto";
import "./repair-journey.css";

export default function RepairJourney({ initial, onUpdate, onService }) {
  const [project, setProject] = useState(initial);
  const [health, setHealth] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [tutorial, setTutorial] = useState(false);
  const [editing, setEditing] = useState(false);
  const [box, setBox] = useState(
    initial.analysis?.box || initial.settings?.box || null,
  );
  const started = useRef(false);
  const analysis = project.analysis;
  const preview = project.preview;
  const previewPending = ["queued", "running"].includes(preview?.state);
  const processing = ["analyzing", "compiling"].includes(project.status);
  const conceptReady = preview?.state === "ready";
  const uncertain =
    analysis?.requires_manual_area || analysis?.damage_found === false;
  const hasCurrentPlan =
    !!project.plan &&
    (!conceptReady || project.plan.design_revision === preview.revision);
  const style = preview?.style || analysis?.recommended_style || "sashiko";

  function update(fresh) {
    setProject(fresh);
    onUpdate(fresh);
  }
  async function act(callback) {
    setBusy(true);
    setError("");
    try {
      const fresh = await callback();
      if (fresh?.id) update(fresh);
      return fresh;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    api("/health", { signal: controller.signal })
      .then(setHealth)
      .catch(() => {});
    return () => controller.abort();
  }, []);
  // Existing saved uploads also enter the suggestion-first flow automatically.
  useEffect(() => {
    if (project.category !== "textile" || started.current) return;
    const freshUpload = project.status === "uploaded" && !analysis;
    const legacyAnalysis =
      project.status === "needs_review" &&
      analysis?.provider === "local" &&
      analysis.detector_version !== 2 &&
      !preview;
    if (!freshUpload && !legacyAnalysis) return;
    started.current = true;
    act(() =>
      api(`/projects/${project.id}/analyze`, {
        method: "POST",
        body: legacyAnalysis ? project.settings || {} : {},
      }),
    );
  }, [project.id, project.status]);
  useEffect(() => {
    setConfirmed(false);
    if (analysis?.box) setBox(analysis.box);
  }, [project.revision, preview?.revision]);
  useEffect(() => {
    if (!processing && !previewPending) return;
    const controller = new AbortController();
    let timer;
    let active = true;
    const poll = async () => {
      try {
        const fresh = await api(`/projects/${project.id}`, {
          signal: controller.signal,
        });
        if (!active) return;
        update(fresh);
        setError("");
        if (
          ["analyzing", "compiling"].includes(fresh.status) ||
          ["queued", "running"].includes(fresh.preview?.state)
        )
          timer = setTimeout(poll, 1500);
      } catch (e) {
        if (active && e.name !== "AbortError") {
          setError("Your work is saved. Reconnecting to the studio…");
          timer = setTimeout(poll, 4000);
        }
      }
    };
    timer = setTimeout(poll, 1000);
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [project.id, project.status, preview?.state, preview?.revision]);

  async function beginDiy() {
    if (hasCurrentPlan || project.category === "ceramic") {
      setTutorial(true);
      return;
    }
    const fresh = await act(() =>
      api(`/projects/${project.id}/compile`, {
        method: "POST",
        body: { revision: project.revision, style, confirmed: true },
      }),
    );
    if (fresh) setTutorial(true);
  }
  if (tutorial && (hasCurrentPlan || project.category === "ceramic"))
    return (
      <RepairTutorial
        project={project}
        onClose={() => setTutorial(false)}
        onMaker={onService}
        onUpdate={update}
      />
    );

  return (
    <motion.div
      className="repair-journey"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <div className="journey-heading">
        <div>
          <span className="app-kicker">YOUR PIECE, REIMAGINED</span>
          <h1>{project.title}</h1>
        </div>
        <span className="journey-step">
          {processing || previewPending
            ? "Finding its next chapter"
            : "A new chapter, chosen for you"}
        </span>
      </div>
      {(error || project.error) && (
        <p className="app-error" role="alert">
          {error || project.error}
        </p>
      )}
      {(processing || previewPending) && (
        <div className="journey-processing" role="status">
          <RefreshCw className="spin" size={26} />
          <div>
            <h2>
              {project.status === "compiling"
                ? "Making your personal repair guide."
                : previewPending
                  ? "Imagining the finished piece."
                  : "Finding the tear, and its possibilities."}
            </h2>
            <p>
              We’ll suggest the look first. Then you can choose your hands, or a
              maker’s.
            </p>
            {health && !health.worker_available && (
              <p className="app-note">
                The worker is reconnecting. Your piece is saved and will
                continue when it returns.
              </p>
            )}
          </div>
        </div>
      )}

      {project.category === "textile" && (
        <RepairPreview
          project={project}
          available={health?.creative_preview_available}
          onUpdate={update}
          busy={busy}
          onRefresh={() =>
            act(() =>
              api(`/projects/${project.id}/preview`, {
                method: "POST",
                body: { request_id: crypto.randomUUID() },
              }),
            )
          }
        />
      )}
      {project.category === "ceramic" && (
        <div className="journey-ceramic">
          <img
            src={asset(`/projects/${project.id}/image`)}
            alt={project.title}
          />
          <div>
            <h2>A considered repair for a meaningful piece.</h2>
            <p>
              Decorative ceramics need a suitability assessment. Explore the
              ceramic guide, or request a specialist’s quote.
            </p>
          </div>
        </div>
      )}

      {!processing &&
        !previewPending &&
        !conceptReady &&
        project.category === "textile" && (
          <div className="journey-assessment">
            <DamagePhoto
              project={project}
              box={analysis?.box || box}
              analysis={analysis}
            />
            <div>
              <span className="app-kicker">
                LET’S GET THE STARTING POINT RIGHT
              </span>
              <h2>
                {uncertain
                  ? "This area needs a second look."
                  : "Let’s suggest a fresh repair."}
              </h2>
              <p>
                {uncertain
                  ? "We couldn’t confidently isolate the tear. Show us its two opposite corners, or let a maker assess your photo."
                  : "We’ll reassess the damage and put a proposed repair directly onto your photo."}
              </p>
              <button
                className="secondary"
                onClick={() => {
                  setBox(analysis?.box || null);
                  setEditing(true);
                }}
              >
                {uncertain ? "Adjust the damage area" : "Review the area"}
              </button>
              {!uncertain && (
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    act(() =>
                      api(`/projects/${project.id}/analyze`, {
                        method: "POST",
                        body: project.settings || {},
                      }),
                    )
                  }
                >
                  Suggest my repair <ArrowRight size={16} />
                </button>
              )}
            </div>
          </div>
        )}

      {(analysis || editing) && !processing && (
        <details
          className="journey-adjustments"
          open={editing || undefined}
          onToggle={(e) => {
            if (!e.currentTarget.open) setEditing(false);
          }}
        >
          <summary>Review the damage area or adjust the fit</summary>
          <div className="journey-adjust-grid">
            <DamagePhoto
              project={project}
              box={box}
              onPoint={setBox}
              analysis={analysis}
            />
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                const fresh = await act(() =>
                  api(`/projects/${project.id}/analyze`, {
                    method: "POST",
                    body: {
                      ...project.settings,
                      box,
                      width_mm: data.get("width_mm")
                        ? Number(data.get("width_mm"))
                        : null,
                      fabric: data.get("fabric") || null,
                    },
                  }),
                );
                if (fresh) {
                  setEditing(false);
                  setTutorial(false);
                }
              }}
            >
              <h3>Check the tear. Keep the rest.</h3>
              <p>
                Tap two opposite corners around all the frayed or missing
                fabric. A real measurement improves the print size.
              </p>
              <fieldset className="box-fields">
                <legend>Damage area · % of photo</legend>
                {["Left", "Top", "Right", "Bottom"].map((name, i) => (
                  <label key={name}>
                    {name}
                    <input
                      aria-label={`${name} boundary`}
                      type="number"
                      min=".5"
                      max="99.5"
                      step=".1"
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
                Measured damage width in millimetres · optional
                <input
                  type="number"
                  name="width_mm"
                  min="3"
                  max="150"
                  step=".1"
                  defaultValue={project.settings?.width_mm || ""}
                  placeholder="Measure on the real garment"
                />
              </label>
              <label>
                Fabric · optional
                <select
                  name="fabric"
                  defaultValue={project.settings?.fabric || ""}
                >
                  <option value="">Not sure</option>
                  {["Denim", "Cotton", "Linen", "Knit", "Other"].map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
              </label>
              <div className="journey-adjust-actions">
                <button
                  type="submit"
                  className="primary"
                  disabled={busy || !box}
                >
                  Update my proposal
                </button>
                <button
                  type="button"
                  className="text-link"
                  disabled={busy}
                  onClick={async () => {
                    const fresh = await act(() =>
                      api(`/projects/${project.id}/analyze`, {
                        method: "POST",
                        body: { ...project.settings, box: null },
                      }),
                    );
                    if (fresh) setEditing(false);
                  }}
                >
                  Try automatic detection again
                </button>
              </div>
            </form>
          </div>
        </details>
      )}

      {!processing && !previewPending && (
        <section className="journey-next">
          <span className="app-kicker">THE NEXT PART IS YOURS</span>
          <h2>
            {conceptReady
              ? "Like the look? Let’s bring it to life."
              : "A little guidance, or a skilled hand?"}
          </h2>
          <div className="journey-options">
            <article>
              <span className="journey-option-icon">
                <Scissors size={23} strokeWidth={1.3} />
              </span>
              <h3>I’ll make it myself.</h3>
              <p>
                Your suggested design, a printable template, materials, and six
                illustrated steps. Go at your own pace.
              </p>
              {project.category === "textile" && !hasCurrentPlan && (
                <label className="confirm-check">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  I’ve checked the damage area and will measure and check the
                  template fit before cutting.
                </label>
              )}
              <button
                className="primary"
                disabled={
                  busy ||
                  (project.category === "textile" &&
                    (uncertain || !analysis || (!hasCurrentPlan && !confirmed)))
                }
                onClick={beginDiy}
              >
                {hasCurrentPlan ? "Open my repair guide" : "Make my guide"}
                <ArrowRight size={17} />
              </button>
              {hasCurrentPlan && (
                <div className="journey-downloads">
                  {["pdf", "svg"].map((kind) => (
                    <button
                      className="text-link"
                      key={kind}
                      onClick={() => act(() => downloadPattern(project, kind))}
                    >
                      <Download size={14} />
                      Download {kind.toUpperCase()}
                    </button>
                  ))}
                </div>
              )}
            </article>
            <article>
              <span className="journey-option-icon">
                <HandHeart size={24} strokeWidth={1.3} />
              </span>
              <h3>Let a maker bring it to life.</h3>
              <p>
                Connect with an approved rural or community workroom, or an
                independent maker. They assess your piece and set their own
                price.
              </p>
              <dl className="journey-price-lines">
                <div>
                  <dt>Labour & materials</dt>
                  <dd>Quoted by your maker</dd>
                </div>
                <div>
                  <dt>Collection & return</dt>
                  <dd>Itemised before you accept</dd>
                </div>
                <div>
                  <dt>Studio coordination</dt>
                  <dd>
                    {health?.service_fee_bps != null
                      ? `${health.service_fee_bps / 100}% of craft work`
                      : "Shown in your full quote"}
                  </dd>
                </div>
              </dl>
              <button className="secondary" onClick={() => onService(project)}>
                Find a maker & get charges
                <ArrowUpRight size={17} />
              </button>
              <small>
                Requesting a quote is free. No payment or booking until you
                accept a full quote.
              </small>
            </article>
          </div>
        </section>
      )}
      {project.status === "completed" && (
        <p className="journey-completed">
          <Check size={18} />
          Your finished repair is saved to your worktable.
        </p>
      )}
    </motion.div>
  );
}
