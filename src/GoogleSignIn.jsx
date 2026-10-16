import React, { useEffect, useState } from "react";
import { api } from "./api";
import { googleIdToken, googleError } from "./firebase-auth";

export default function GoogleSignIn({ onSuccess, onError, link = false }) {
  const [configuration, setConfiguration] = useState(null);
  const [busy, setBusy] = useState(false);
  const [linked, setLinked] = useState(false);
  useEffect(() => {
    let active = true;
    api("/auth/firebase/config")
      .then((value) => {
        if (active) setConfiguration(value);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  if (!configuration?.enabled) return null;
  return (
    <>
      <button
        type="button"
        className={link ? "text-link" : "secondary auth-google-button"}
        disabled={busy || linked}
        onClick={async () => {
          setBusy(true);
          onError?.("");
          try {
            const response = await googleIdToken(
              configuration.config,
              (id_token) =>
                api("/auth/firebase/" + (link ? "link" : "session"), {
                  method: "POST",
                  body: { id_token },
                }),
            );
            if (link) setLinked(true);
            else onSuccess(response);
          } catch (error) {
            onError?.(googleError(error));
          } finally {
            setBusy(false);
          }
        }}
      >
        {!link && (
          <svg width="19" height="19" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.32 2.98-7.36ZM12 22c2.7 0 4.96-.9 6.62-2.41l-3.24-2.51c-.9.6-2.05.97-3.38.97-2.61 0-4.83-1.76-5.62-4.13H3.04v2.59A10 10 0 0 0 12 22ZM6.38 13.92a6 6 0 0 1 0-3.84V7.49H3.04a10 10 0 0 0 0 9.02l3.34-2.59ZM12 5.95c1.47 0 2.79.51 3.82 1.51l2.87-2.87A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.96 5.49l3.34 2.59C7.17 7.71 9.39 5.95 12 5.95Z"
            />
          </svg>
        )}
        {busy
          ? "Connecting to Google…"
          : linked
            ? "Google linked"
            : link
              ? "Link Google"
              : "Continue with Google"}
      </button>
      {!link && (
        <div className="auth-email-divider">
          <span>or with email</span>
        </div>
      )}
    </>
  );
}
