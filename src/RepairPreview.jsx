import React, { useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { asset } from "./api";
import "./repair-preview.css";
import GenerationHistory from "./GenerationHistory";

export default function RepairPreview({
  project,
  available,
  onRefresh,
  busy,
  onUpdate,
}) {
  const [view, setView] = useState("after");
  const preview = project.preview;
  const generating = ["queued", "running"].includes(preview?.state);
  const ready = preview?.state === "ready";
  const local = preview?.provider === "local";
  if (!project.analysis || project.category !== "textile") return null;
  const blocked =
    project.analysis.requires_manual_area ||
    project.analysis.damage_found === false;
  if (blocked) return null;
  return (
    <section className="repair-imagination">
      <div className="imagination-heading">
        <div>
          <span className="app-kicker">
            {local
              ? "A REPAIR PROPOSED FOR YOUR PIECE"
              : "A NEW CHAPTER, IN THREAD"}
          </span>
          <h2>
            {ready
              ? preview.design.name
              : generating
                ? "Imagining what it could become."
                : "See a different possibility."}
          </h2>
        </div>
        {available && project.status !== "completed" && (
          <button
            className="secondary"
            disabled={
              busy ||
              generating ||
              ["analyzing", "compiling"].includes(project.status)
            }
            onClick={() => {
              setView("after");
              onRefresh();
            }}
          >
            <RefreshCw size={15} className={generating ? "spin" : ""} />
            {generating
              ? "Creating your preview…"
              : ready
                ? "Another idea"
                : preview?.state === "failed"
                  ? "Try a new idea"
                  : "Imagine my repair"}
          </button>
        )}
      </div>
      {ready ? (
        <>
          <p className="imagination-story">{preview.design.story}</p>
          <div
            className="preview-view-tabs"
            role="group"
            aria-label="Compare original and imagined repair"
          >
            <button
              aria-pressed={view === "before"}
              onClick={() => setView("before")}
            >
              Your original
            </button>
            <button
              aria-pressed={view === "after"}
              onClick={() => setView("after")}
            >
              The imagined repair
            </button>
          </div>
          <div className="garment-preview">
            <img
              key={`${project.id}-${preview.revision}-${view}`}
              src={asset(
                view === "after"
                  ? `/projects/${project.id}/preview.png?v=${preview.revision}`
                  : `/projects/${project.id}/image`,
              )}
              alt={
                view === "after"
                  ? `${local ? "Illustrated proposal" : "AI visualisation"}: ${preview.design.name} on ${project.title}`
                  : `Original photograph of ${project.title}`
              }
            />
          </div>
          <p className="preview-caption">
            <Sparkles size={13} />
            {preview.disclaimer} The original photo is preserved outside the
            repair area.
          </p>
          <details className="preview-method">
            <summary>How to make this repair · 6 steps</summary>
            <p>
              <strong>Thread:</strong> {preview.design.thread_colour}
            </p>
            <ul>
              {preview.design.materials.map((material) => (
                <li key={material}>{material}</li>
              ))}
            </ul>
            <ol>
              {preview.design.steps.map((step, i) => (
                <li key={i}>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                  <small>{step.tip}</small>
                </li>
              ))}
            </ol>
          </details>
        </>
      ) : generating ? (
        <div className="preview-waiting" role="status">
          <RefreshCw className="spin" size={22} />
          <p>
            Designing a motif around the tear, then stitching it into a
            realistic preview of your own photograph. This can take a few
            minutes. You can leave and return.
          </p>
        </div>
      ) : ["failed", "limited", "cancelled"].includes(preview?.state) ? (
        <p className="map-feedback" role="alert">
          {preview.error} Your damage assessment and printable repair tools are
          still saved.
        </p>
      ) : !available ? (
        <p className="app-note">
          Creative photo previews aren’t enabled in this studio yet. You can
          still create a stitch pattern and follow the repair guide.
        </p>
      ) : (
        <p>
          Let the tear lead the design. We’ll keep your garment and photograph,
          and imagine a hand-sewn motif in the repair area.
        </p>
      )}
      <GenerationHistory
        project={project}
        available={available}
        onUpdate={onUpdate}
      />
    </section>
  );
}
