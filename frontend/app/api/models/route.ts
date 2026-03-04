import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export async function GET() {
  const backendUrl = process.env.NEXT_PUBLIC_FULCRUM_API_BASE ?? DEFAULT_BACKEND_URL;

  try {
    const response = await fetch(`${backendUrl}/models`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};

    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        detail:
          error instanceof Error
            ? error.message
            : "Failed to reach the Fulcrum backend /models endpoint",
      },
      { status: 502 }
    );
  }
}
