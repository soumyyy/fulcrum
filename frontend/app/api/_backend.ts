import { NextResponse } from "next/server";

export const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export function backendBaseUrl() {
  return process.env.NEXT_PUBLIC_FULCRUM_API_BASE ?? DEFAULT_BACKEND_URL;
}

export async function proxyJsonResponse(response: Response) {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  return NextResponse.json(payload, { status: response.status });
}

export function proxyError(detail: string, status = 502) {
  return NextResponse.json({ status: "error", detail }, { status });
}
