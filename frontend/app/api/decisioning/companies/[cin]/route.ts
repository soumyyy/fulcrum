import { proxyDecisioningGet, type DecisioningRouteContext } from "../../_decisioningProxy";

export async function GET(_request: Request, context: DecisioningRouteContext) {
  const { cin } = await context.params;
  return proxyDecisioningGet(`/decisioning/companies/${encodeURIComponent(cin)}`);
}
