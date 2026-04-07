import { NextResponse } from "next/server";

import { backendBaseUrl, proxyError, proxyJsonResponse } from "../../_backend";

export type ReportRouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function proxyReportGet(context: ReportRouteContext, suffix = "") {
  const { jobId } = await context.params;
  const backendUrl = backendBaseUrl();

  try {
    const response = await fetch(`${backendUrl}/reports/${encodeURIComponent(jobId)}${suffix}`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    return proxyJsonResponse(response);
  } catch (error) {
    return proxyError(
      error instanceof Error
        ? error.message
        : `Failed to reach the Fulcrum backend /reports/${jobId}${suffix} endpoint`
    );
  }
}

export async function proxyReportDelete(context: ReportRouteContext) {
  const { jobId } = await context.params;
  const backendUrl = backendBaseUrl();

  try {
    const response = await fetch(`${backendUrl}/reports/${encodeURIComponent(jobId)}`, {
      method: "DELETE",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    return proxyJsonResponse(response);
  } catch (error) {
    return proxyError(
      error instanceof Error ? error.message : `Failed to reach the Fulcrum backend /reports/${jobId} endpoint`
    );
  }
}

export async function proxyReportEvents(context: ReportRouteContext) {
  const { jobId } = await context.params;
  const backendUrl = backendBaseUrl();

  try {
    const response = await fetch(`${backendUrl}/reports/${encodeURIComponent(jobId)}/events`, {
      cache: "no-store",
      headers: {
        Accept: "text/event-stream",
      },
    });

    if (!response.ok || !response.body) {
      return proxyJsonResponse(response);
    }

    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "text/event-stream",
        "Cache-Control": "no-cache",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        detail:
          error instanceof Error
            ? error.message
            : `Failed to reach the Fulcrum backend /reports/${jobId}/events endpoint`,
      },
      { status: 502 }
    );
  }
}
