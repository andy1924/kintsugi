import React, { useState, useEffect, useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowRight,
  ArrowUpRight,
  Upload,
  ChevronLeft,
  Plus,
  LogOut,
  Lock,
  Eye,
  EyeOff,
} from "lucide-react";
import { api, asset } from "./api";
import "./studio.css";
import ServiceDesk from "./ServiceDesk";
import RepairJourney from "./RepairJourney";
import GoogleSignIn from "./GoogleSignIn";
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
    [error, setError] = useState(""),
    [showPassword, setShowPassword] = useState(false);
  return (
    <div className="auth-panel">
      <div className="auth-welcome">
        <span className="app-kicker">YOUR KINTSUGI WORKTABLE</span>
        <h1>
          A place for
          <br />
          <em>what you keep.</em>
        </h1>
        <p>
          A home for your favourite pieces. Mend them yourself, or find a
          skilled hand.
        </p>
        <div className="auth-fabric-study" aria-hidden="true">
          <img src="/mending-panorama.png" alt="" />
          <svg viewBox="0 0 360 150" fill="none">
            <path
              d="M10 109C83 23 150 147 231 81S321 29 350 55"
              stroke="#c5a363"
              strokeWidth="1.7"
              strokeDasharray="5 6"
            />
            <path d="m328 54 25-9-21 14Z" stroke="#e3d7b8" strokeWidth="1" />
          </svg>
          <span>A little more life.</span>
        </div>
      </div>
      <div className="auth-form-surface">
        <GoogleSignIn onSuccess={onSuccess} onError={setError} />
        <div className="auth-tabs">
          <button
            onClick={() => {
              setMode("register");
              setError("");
            }}
            className={mode === "register" ? "active" : ""}
            aria-pressed={mode === "register"}
            type="button"
          >
            {mode === "register" && (
              <motion.span
                className="auth-tab-indicator"
                layoutId="auth-tab-indicator"
                transition={{ type: "spring", stiffness: 380, damping: 34 }}
              />
            )}
            <span className="auth-tab-label">Create an account</span>
          </button>
          <button
            onClick={() => {
              setMode("login");
              setError("");
            }}
            className={mode === "login" ? "active" : ""}
            aria-pressed={mode === "login"}
            type="button"
          >
            {mode === "login" && (
              <motion.span
                className="auth-tab-indicator"
                layoutId="auth-tab-indicator"
                transition={{ type: "spring", stiffness: 380, damping: 34 }}
              />
            )}
            <span className="auth-tab-label">Sign in</span>
          </button>
        </div>
        <motion.form
          layout
          transition={{ duration: 0.3 }}
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
            <motion.label
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              Your name
              <input
                name="name"
                autoComplete="name"
                placeholder="What should we call you?"
                required
                maxLength={80}
              />
            </motion.label>
          )}
          <label>
            Email
            <input
              name="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
              maxLength={254}
            />
          </label>
          <label>
            Password
            <span className="auth-password">
              <input
                name="password"
                type={showPassword ? "text" : "password"}
                placeholder={
                  mode === "register"
                    ? "At least 10 characters"
                    : "Your password"
                }
                autoComplete={
                  mode === "register" ? "new-password" : "current-password"
                }
                minLength={10}
                maxLength={128}
                required
              />
              <button
                type="button"
                className="auth-password-toggle"
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <EyeOff size={18} strokeWidth={1.4} />
                ) : (
                  <Eye size={18} strokeWidth={1.4} />
                )}
              </button>
            </span>
          </label>
          <ErrorMessage message={error} />
          <button className="primary" disabled={busy}>
            {busy
              ? "Please wait…"
              : mode === "register"
                ? "Create my worktable"
                : "Sign in"}
            <ArrowRight size={16} />
          </button>
        </motion.form>
        <div className="auth-privacy">
          <Lock size={13} strokeWidth={1.5} />
          <span>Your photos stay private.</span>
        </div>
      </div>
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
export default function Studio({ onClose, initialView = "list" }) {
  const reduced = useReducedMotion();
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
    <main
      className={account === null ? "app-shell account-entry" : "app-shell"}
    >
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
      <motion.div
        key={`${account?.id || "guest"}-${view}`}
        initial={reduced ? false : { opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
      >
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
              <RepairJourney
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
                      Make a repair yourself, or commission an independent
                      maker. You get to keep something you love. They get paid
                      for the skill that makes it possible.
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
                    <button
                      className="text-link"
                      onClick={() => setView("new")}
                    >
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
      </motion.div>
    </main>
  );
}
