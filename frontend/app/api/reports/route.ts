import { backendBaseUrl, proxyError, proxyJsonResponse } from "../_backend";

export async function GET(request: Request) {
  const backendUrl = backendBaseUrl();
  const url = new URL(request.url);
  const query = url.searchParams.toString();

  try {
    const response = await fetch(`${backendUrl}/reports${query ? `?${query}` : ""}`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    return proxyJsonResponse(response);
  } catch (error) {
    return proxyError(error instanceof Error ? error.message : "Failed to reach the Fulcrum backend /reports endpoint");
  }
}
