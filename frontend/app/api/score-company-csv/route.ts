import { NextRequest, NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  const backendUrl = process.env.NEXT_PUBLIC_FULCRUM_API_BASE ?? DEFAULT_BACKEND_URL;

  try {
    const incomingForm = await request.formData();
    const file = incomingForm.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        {
          status: "error",
          detail: "A CSV file is required under the 'file' field.",
        },
        { status: 400 }
      );
    }

    const outboundForm = new FormData();
    outboundForm.append("file", file, file.name);

    const response = await fetch(`${backendUrl}/score-company-csv`, {
      method: "POST",
      body: outboundForm,
      cache: "no-store",
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
            : "Failed to reach the Fulcrum backend /score-company-csv endpoint",
      },
      { status: 502 }
    );
  }
}
