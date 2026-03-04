import { ScorePanel } from "../components/score-panel";

export default function ScorePage() {
  return (
    <main className="min-h-screen px-14 py-12">
      <section className="mx-auto max-w-[1560px]">
        <header className="rounded-[2.4rem] border border-[var(--line)] bg-[linear-gradient(135deg,rgba(255,255,255,0.025),rgba(255,255,255,0.01))] px-10 py-8 shadow-[0_32px_120px_rgba(0,0,0,0.42)]">
          <p className="text-[0.68rem] uppercase tracking-[0.3em] text-[var(--muted)]">Fulcrum / Score</p>
          <h1 className="mt-5 text-[5.4rem] font-semibold leading-none tracking-[-0.08em] text-white">
            Score Registry
          </h1>
        </header>

        <div className="mt-10">
          <ScorePanel />
        </div>
      </section>
    </main>
  );
}
