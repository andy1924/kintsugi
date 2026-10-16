// Only public Firebase web configuration enters this module. Tokens stay in memory.
export async function googleIdToken(config, consume) {
  const [
    { initializeApp, getApps },
    {
      getAuth,
      GoogleAuthProvider,
      inMemoryPersistence,
      setPersistence,
      signInWithPopup,
      signOut,
    },
  ] = await Promise.all([import("firebase/app"), import("firebase/auth")]);
  const app =
    getApps().find((entry) => entry.name === "kintsugi") ||
    initializeApp(config, "kintsugi");
  const auth = getAuth(app);
  await setPersistence(auth, inMemoryPersistence);
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  try {
    const result = await signInWithPopup(auth, provider);
    return await consume(await result.user.getIdToken());
  } finally {
    await signOut(auth);
  }
}

export function googleError(error) {
  const messages = {
    "auth/popup-closed-by-user":
      "Google sign-in was closed. You can try again.",
    "auth/cancelled-popup-request": "Another sign-in window is already open.",
    "auth/popup-blocked":
      "Allow the Google sign-in popup in your browser and try again.",
    "auth/unauthorized-domain":
      "This website is not yet authorised for Google sign-in.",
    "auth/operation-not-allowed":
      "Google sign-in is not enabled for this Firebase project.",
    "auth/network-request-failed":
      "Google could not connect. Please try again.",
  };
  return error.code
    ? messages[error.code] ||
        "Google sign-in could not finish. Please try again."
    : error.message;
}
