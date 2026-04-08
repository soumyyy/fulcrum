import { ProcessingWorkspace } from "./processing-workspace";

export default async function ProcessingPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <ProcessingWorkspace jobId={jobId} />;
}
