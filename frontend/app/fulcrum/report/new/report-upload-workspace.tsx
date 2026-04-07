"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { uploadReport } from "../../api";

export function ReportUploadWorkspace() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Select an annual report PDF first.");
      return;
    }
    setSubmitting(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file, file.name);

    try {
      const upload = await uploadReport(formData);
      router.push(`/fulcrum/report/${encodeURIComponent(upload.job_id)}`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Upload failed.");
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#08090b] text-[#f7f0df]">
      <div className="pointer-events-none fixed inset-0 [background:radial-gradient(circle_at_18%_18%,rgba(255,107,53,0.18),transparent_25%),radial-gradient(circle_at_80%_18%,rgba(245,230,200,0.12),transparent_25%),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(rgba(255,255,255,0.025)_1px,transparent_1px)] [background-size:auto,auto,56px_56px,56px_56px]" />
      <section className="relative mx-auto grid min-h-screen w-full max-w-[1720px] place-items-center gap-5 px-5 py-5 lg:grid-cols-[minmax(0,760px)] lg:px-7">
        <aside className="w-full rounded-[2rem] border border-white/10 bg-[#101216]/92 p-5 shadow-2xl shadow-black/45">
          <Link className="text-xs uppercase tracking-[0.24em] text-[#ffb38f]" href="/fulcrum">
            ← Portfolio
          </Link>
          <div className="mt-8">
            <p className="text-[0.65rem] uppercase tracking-[0.32em] text-[#9ba1ad]">Annual report run</p>
            <h1 className="mt-3 text-5xl font-semibold leading-[0.9] tracking-[-0.08em] text-white">
              Upload the report. Fulcrum does the rest.
            </h1>
            <p className="mt-4 text-sm leading-6 text-[#cfc5b1]">
              No manual company name, CIN, sector, year, or basis entry. The extraction pipeline infers those from the annual report and then runs the Tier 1A risk stack.
            </p>
          </div>
          <form className="mt-8 space-y-3" onSubmit={submit}>
            <label className="block rounded-[1.5rem] border border-dashed border-[#ff6b35]/50 bg-[#ff6b35]/8 p-5 text-sm text-[#f5e6c8]">
              <span className="block text-[0.65rem] uppercase tracking-[0.28em] text-[#ffb38f]">Annual report PDF</span>
              <input
                accept="application/pdf"
                className="mt-3 w-full text-sm text-[#f5e6c8] file:mr-4 file:rounded-full file:border-0 file:bg-[#ff6b35] file:px-4 file:py-2 file:text-xs file:font-semibold file:text-black"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                type="file"
              />
              <span className="mt-3 block truncate font-mono text-xs text-[#b9b1a2]">{file?.name ?? "No report selected"}</span>
            </label>
            <button
              className="h-[52px] w-full rounded-2xl bg-[#ff6b35] px-5 py-4 text-sm font-semibold text-black shadow-[0_0_32px_rgba(255,107,53,0.22)] transition hover:bg-[#ff8458] disabled:cursor-not-allowed disabled:opacity-50"
              disabled={submitting}
              type="submit"
            >
              {submitting ? "Creating analysis run" : "Start report analysis"}
            </button>
          </form>
          {error ? <div className="mt-4 rounded-2xl border border-[#ff6b35]/40 bg-[#ff6b35]/10 p-4 text-sm text-[#ffd8c5]">{error}</div> : null}
        </aside>
      </section>
    </main>
  );
}
