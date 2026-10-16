const BASE = (import.meta.env?.VITE_API_BASE_URL || "").replace(/\/$/, "");
let csrf = "";
export const asset = (path) => BASE + "/api/v1" + path;
export async function api(path, { method = "GET", body, signal } = {}) {
  const headers = {};
  if (body && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  let response;
  try {
    response = await fetch(asset(path), {
      method,
      headers,
      credentials: "include",
      body:
        body instanceof FormData
          ? body
          : body
            ? JSON.stringify(body)
            : undefined,
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      "The studio service is unavailable. Please try again shortly.",
    );
  }
  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail =
        "The studio service is not connected. Start the Kintsugi backend to continue.";
    }
    const error = new Error(
      Array.isArray(detail)
        ? detail.map((d) => d.msg).join(" ")
        : detail || "The request could not be completed.",
    );
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => {
    throw new Error(
      "The studio service is not connected. Start the Kintsugi backend to continue.",
    );
  });
  if (data?.csrf) csrf = data.csrf;
  return data;
}
export async function downloadPattern(project, kind) {
  const response = await fetch(
    asset(`/projects/${project.id}/pattern.${kind}`),
    { credentials: "include" },
  );
  if (!response.ok)
    throw new Error(
      "Could not download the pattern. Please sign in and try again.",
    );
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `kintsugi-${project.id.slice(0, 8)}.${kind}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
