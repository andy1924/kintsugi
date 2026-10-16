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
    <button
      type="button"
      className={link ? "text-link" : "secondary"}
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
      {busy
        ? "Connecting to Google…"
        : linked
          ? "Google linked"
          : link
            ? "Link Google"
            : "Continue with Google"}
    </button>
  );
}
