import { proxyReportGet, type ReportRouteContext } from "../_reportProxy";

export async function GET(_request: Request, context: ReportRouteContext) {
  return proxyReportGet(context, "/sections");
}
