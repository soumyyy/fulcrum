import { NextRequest, NextResponse } from "next/server";

import { backendBaseUrl, proxyError, proxyJsonResponse } from "../../_backend";

export async function POST(request: NextRequest) {
  const backendUrl = backendBaseUrl();

  try {
    const incomingForm = await request.formData();
    const file = incomingForm.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        {
          status: "error",
          detail: "A PDF file is required under the 'file' field.",
        },
        { status: 400 }
      );
    }

    const outboundForm = new FormData();
    outboundForm.append("file", file, file.name);

    for (const key of ["company_name", "cin", "sector", "financial_year", "basis_preference"]) {
      const value = incomingForm.get(key);
      if (typeof value === "string" && value.trim() !== "") {
        outboundForm.append(key, value);
      }
    }

    const response = await fetch(`${backendUrl}/reports/upload`, {
      method: "POST",
      body: outboundForm,
      cache: "no-store",
    });

    return proxyJsonResponse(response);
  } catch (error) {
    return proxyError(
      error instanceof Error ? error.message : "Failed to reach the Fulcrum backend /reports/upload endpoint"
    );
  }
}
