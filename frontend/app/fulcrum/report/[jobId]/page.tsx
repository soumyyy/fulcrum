import { ReportRunWorkspace } from "./report-run-workspace";

export default async function ReportRunPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <ReportRunWorkspace jobId={jobId} />;
}
