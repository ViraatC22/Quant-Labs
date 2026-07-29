"use client";

import { MessageCircleQuestion } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

import { askResearch } from "./api";
import type { ResearchAnswer } from "./types";

// "Ask my memory" — grounded Q&A over the trading vault (Lattice L3). Every
// answer is composed only from retrieved evidence; the coverage meter shows the
// measured share backed by citations, and a zero-evidence question is refused.
export function ResearchPanel() {
  const [question, setQuestion] = React.useState("");
  const [answer, setAnswer] = React.useState<ResearchAnswer | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setAnswer(await askResearch(question.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-lg border border-line bg-card/86 p-4 shadow-panel">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Ask your trading memory</h2>
          <p className="mt-1 text-sm text-ink/58">
            Answers are assembled only from your saved sources and trades — every
            claim is cited, and it will say so when it has no evidence.
          </p>
        </div>
        <MessageCircleQuestion aria-hidden="true" className="text-signal" size={21} strokeWidth={2.1} />
      </div>

      <form onSubmit={ask} className="mt-4 flex gap-2">
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. When does the opening range breakout work?"
          aria-label="Research question"
        />
        <Button type="submit" disabled={loading}>
          {loading ? "Thinking…" : "Ask"}
        </Button>
      </form>

      {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}

      {answer ? (
        <div className="mt-4">
          <AnswerCard answer={answer} />
        </div>
      ) : null}
    </section>
  );
}

function AnswerCard({ answer }: { answer: ResearchAnswer }) {
  const coveragePct = Math.round(answer.trust_score * 100);
  const citationNumbers = new Map(answer.citations.map((citation, index) => [citation.ref, index + 1]));
  const readableAnswer = answer.answer_markdown.replace(
    /\[((?:trade|chunk|claim):[0-9a-fA-F-]+)\]/g,
    (original, ref: string) => citationNumbers.has(ref) ? `[${citationNumbers.get(ref)}]` : original,
  );
  const generationLabel = answer.generation_mode === "ai"
    ? `AI · ${answer.writer_provider_id ?? "provider"}/${answer.writer_model ?? "model"}`
    : answer.generation_mode === "computed"
      ? "computed from trades"
      : "local grounded fallback";
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Answer</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={answer.generation_mode === "ai" ? "default" : "secondary"}>
              {generationLabel}
            </Badge>
            <Badge variant="outline">route: {answer.route}</Badge>
            <EvidenceCoverageMeter pct={coveragePct} />
          </div>
        </div>
        <CardDescription>
          {answer.citations.length} citation{answer.citations.length === 1 ? "" : "s"}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{readableAnswer}</div>

        {answer.citations.length > 0 ? (
          <div className="flex flex-col gap-2">
            <h4 className="text-xs font-semibold uppercase text-muted-foreground">Evidence</h4>
            {answer.citations.map((c, index) => (
              <div key={c.ref} className="rounded-md border p-2 text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">#{index + 1} {c.kind}</Badge>
                  <span className="font-medium">{c.source_title}</span>
                </div>
                <p className="mt-1 text-muted-foreground">{c.snippet}</p>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function EvidenceCoverageMeter({ pct }: { pct: number }) {
  const tone = pct >= 67 ? "bg-emerald-500" : pct >= 34 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2" title="Share of factual answer lines with a validated evidence citation">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-muted">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">{pct}% evidence coverage</span>
    </div>
  );
}
