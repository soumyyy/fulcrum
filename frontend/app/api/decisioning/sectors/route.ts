import { proxyDecisioningGet } from "../_decisioningProxy";

export async function GET() {
  return proxyDecisioningGet("/decisioning/sectors");
}
