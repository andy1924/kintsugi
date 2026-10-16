import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import { api } from "./api.js";
const original = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = original;
});
test("nullable maker profile is a valid response", async () => {
  globalThis.fetch = async () => Response.json(null);
  assert.equal(await api("/network/profile"), null);
});
test("session CSRF is sent only on mutations", async () => {
  globalThis.fetch = async () =>
    Response.json({ csrf: "session-csrf", user: { id: "owner" } });
  await api("/auth/me");
  let sent;
  globalThis.fetch = async (url, options) => {
    sent = options;
    return Response.json({ ok: true });
  };
  await api("/network/requests", {
    method: "POST",
    body: { project_id: "piece" },
  });
  assert.equal(sent.headers["X-CSRF-Token"], "session-csrf");
  assert.equal(sent.credentials, "include");
  assert.equal(sent.headers["Content-Type"], "application/json");
});
test("validation errors are readable", async () => {
  globalThis.fetch = async () =>
    Response.json(
      { detail: [{ msg: "A measurement is required." }] },
      { status: 422 },
    );
  await assert.rejects(api("/projects"), /A measurement is required/);
});
test("network errors have a user-facing message", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("fetch failed");
  };
  await assert.rejects(
    api("/network/requests"),
    /studio service is unavailable/,
  );
});
test("an unavailable HTML backend does not pretend to return app data", async () => {
  globalThis.fetch = async () =>
    new Response("<html>offline</html>", { status: 503 });
  await assert.rejects(
    api("/network/profile"),
    /studio service is not connected/,
  );
});
test("empty mutation responses are supported", async () => {
  globalThis.fetch = async () => new Response(null, { status: 204 });
  assert.equal(await api("/auth/logout", { method: "POST" }), null);
});
test("an aborted poll stays aborted", async () => {
  globalThis.fetch = async () => {
    throw new DOMException("aborted", "AbortError");
  };
  await assert.rejects(api("/projects"), (e) => e.name === "AbortError");
});
