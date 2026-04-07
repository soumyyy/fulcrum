import { NextRequest } from "next/server";

import { backendBaseUrl, proxyError, proxyJsonResponse } from "../_backend";

export type DecisioningRouteContext = {
  params: Promise<{ cin: string }>;
};

export async function proxyDecisioningGet(path: string, request?: NextRequest) {
  const backendUrl = backendBaseUrl();
  const url = new URL(`${backendUrl}${path}`);

  if (request) {
    const incomingUrl = new URL(request.url);
    incomingUrl.searchParams.forEach((value, key) => {
      url.searchParams.append(key, value);
    });
  }

  try {
    const response = await fetch(url, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    return proxyJsonResponse(response);
  } catch (error) {
    return proxyError(
      error instanceof Error ? error.message : `Failed to reach the Fulcrum backend ${path} endpoint`
    );
  }
}
