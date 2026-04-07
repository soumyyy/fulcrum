import { backendBaseUrl, proxyError, proxyJsonResponse } from "../_backend";

export async function GET() {
  const backendUrl = backendBaseUrl();

  try {
    const response = await fetch(`${backendUrl}/models`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    return proxyJsonResponse(response);
  } catch (error) {
    return proxyError(
      error instanceof Error ? error.message : "Failed to reach the Fulcrum backend /models endpoint"
    );
  }
}
