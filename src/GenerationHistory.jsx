import React, { useEffect, useState } from "react";
import { api, asset } from "./api";
import { ArrowUpRight } from "lucide-react";

export default function GenerationHistory({ project, available, onUpdate }) {
  const [history, setHistory] = useState([]);
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (
      !available &&
      (!project.preview || project.preview.provider === "local")
    )
      return;
    const controller = new AbortController();
    setNotice("");
    setError("");
    Promise.all([
      api(`/projects/${project.id}/generations`, { signal: controller.signal }),
      api("/generation-usage", { signal: controller.signal }),
    ])
      .then(([rows, allowance]) => {
        if (controller.signal.aborted) return;
        setHistory(rows);
        setMore(rows.length === 50);
        setUsage(allowance);
      })
      .catch((e) => {
        if (e.name !== "AbortError" && !controller.signal.aborted)
          setError(e.message);
      });
    return () => controller.abort();
  }, [
    project.id,
    project.preview?.state,
    project.preview?.revision,
    available,
  ]);
  async function cancel() {
    setBusy(true);
    setError("");
    try {
      const generation = await api(
        `/projects/${project.id}/generations/${project.preview.revision}/cancel`,
        { method: "POST" },
      );
      const fresh = await api(`/projects/${project.id}`);
      onUpdate(fresh);
      setNotice(generation.error);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function loadMore() {
    setBusy(true);
    setError("");
    try {
      const rows = await api(
        `/projects/${project.id}/generations?offset=${history.length}`,
      );
      setHistory((previous) => [...previous, ...rows]);
      setMore(rows.length === 50);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const generating = ["queued", "running"].includes(project.preview?.state);
  if (!available && project.preview?.provider === "local") return null;
  return (
    <div className="generation-library">
      <div className="generation-allowance">
        {usage && (
          <span>
            {usage.remaining} of {usage.limit} creative attempts left today
          </span>
        )}
        {generating && (
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={cancel}
          >
            {busy ? "Stopping…" : "Stop this idea"}
          </button>
        )}
      </div>
      {notice && (
        <p className="app-note" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="app-error" role="alert">
          {error}
        </p>
      )}
      {history.length > 0 && (
        <details className="generation-history">
          <summary>
            Your ideas so far · {history.length}
            {more ? "+" : ""}
          </summary>
          <ul>
            {history.map((generation) => (
              <li key={generation.id}>
                <div>
                  <strong>
                    {generation.design?.name || `Idea ${generation.version}`}
                  </strong>
                  <span>
                    Idea {generation.version} · {generation.state}
                    {generation.state === "running"
                      ? ` · ${generation.stage === "image" ? "sewing the preview" : "designing"}`
                      : ""}
                  </span>
                </div>
                {generation.has_image && generation.state === "ready" && (
                  <a
                    className="text-link"
                    href={asset(
                      `/projects/${project.id}/generations/${generation.version}/image`,
                    )}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View idea <ArrowUpRight size={14} />
                  </a>
                )}
                {generation.error && (
                  <p className="app-note">{generation.error}</p>
                )}
              </li>
            ))}
          </ul>
          {more && (
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={loadMore}
            >
              Load earlier ideas
            </button>
          )}
        </details>
      )}
    </div>
  );
}
