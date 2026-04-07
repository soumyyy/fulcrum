import { proxyReportDelete, proxyReportGet, type ReportRouteContext } from "./_reportProxy";

export async function GET(_request: Request, context: ReportRouteContext) {
  return proxyReportGet(context);
}

export async function DELETE(_request: Request, context: ReportRouteContext) {
  return proxyReportDelete(context);
}
