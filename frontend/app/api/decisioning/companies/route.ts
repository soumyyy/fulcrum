import { NextRequest } from "next/server";

import { proxyDecisioningGet } from "../_decisioningProxy";

export async function GET(request: NextRequest) {
  return proxyDecisioningGet("/decisioning/companies", request);
}
