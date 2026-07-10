"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

import { askResearch } from "./api";
import type { ResearchAnswer } from "./types";

// "Ask my memory" — grounded Q&A over the trading vault (Lattice L3). Every
// answer is composed only from retrieved evidence; the trust meter shows the
// measured share backed by citations, and a zero-evidence question is refused
// rather than answered from thin air.
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
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <div>
        <h1 className="text-xl font-semibold">Ask your trading memory</h1>
        <p className="text-sm text-muted-foreground">
          Answers are assembled only from your saved sources and trades — every
          claim is cited, and it will say so when it has no evidence.
        </p>
      </div>

      <form onSubmit={ask} className="flex gap-2">
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

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {answer ? <AnswerCard answer={answer} /> : null}
    </div>
  );
}

function AnswerCard({ answer }: { answer: ResearchAnswer }) {
  const trustPct = Math.round(answer.trust_score * 100);
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>Answer</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline">route: {answer.route}</Badge>
            <TrustMeter pct={trustPct} />
          </div>
        </div>
        <CardDescription>
          {answer.citations.length} citation{answer.citations.length === 1 ? "" : "s"}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{answer.answer_markdown}</div>

        {answer.citations.length > 0 ? (
          <div className="flex flex-col gap-2">
            <h4 className="text-xs font-semibold uppercase text-muted-foreground">Evidence</h4>
            {answer.citations.map((c) => (
              <div key={c.ref} className="rounded-md border p-2 text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{c.kind}</Badge>
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

function TrustMeter({ pct }: { pct: number }) {
  const tone = pct >= 67 ? "bg-emerald-500" : pct >= 34 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2" title="Share of the answer backed by retrieved evidence">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-muted">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">{pct}% trust</span>
    </div>
  );
}
