// Session desk API client. Self-contained (not routed through lib/api.ts) so
// the dashboard feature stays isolated, matching features/research/api.ts.

import type {
  Briefing,
  BriefingItem,
  InstrumentBias,
  MacroDesk,
  NewsFeed,
  NewsItem,
  CalibrationStats,
  SessionState,
  StrengthSnapshot
} from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!response.ok) {
    throw new Error(`API ${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

type BiasDto = {
  symbol: string;
  asset_class: string;
  direction: string;
  confidence: number;
  strength: number;
  agreement: number;
  coverage: number;
  last_price: number;
  change_percent: number;
  signals: Array<{
    label: string;
    direction: string;
    value: number;
    weight: number;
    detail: string;
    role: string;
  }>;
  explanation: string;
  explanation_mode: string;
  as_of: string;
  provider: string;
  price_basis: string;
  sample_size: number;
  delayed: boolean;
  stale: boolean;
  proxy_note: string | null;
  limitations: string[];
  writer_provider_id: string | null;
  writer_model: string | null;
  news: Array<{
    title: string;
    url: string;
    source: string;
    published_at: string | null;
    age_label: string | null;
    summary: string | null;
    image_url: string | null;
    symbol: string | null;
  }>;
  raw_confidence: number;
  calibration_applied: boolean;
  calibration_sample: number;
  calibration_note: string;
};

function biasFromDto(dto: BiasDto): InstrumentBias {
  return {
    symbol: dto.symbol,
    assetClass: dto.asset_class ?? "equity",
    direction: dto.direction as InstrumentBias["direction"],
    confidence: dto.confidence,
    strength: dto.strength,
    agreement: dto.agreement,
    coverage: dto.coverage,
    lastPrice: dto.last_price,
    changePercent: dto.change_percent,
    signals: dto.signals.map((signal) => ({
      label: signal.label,
      direction: signal.direction,
      value: signal.value,
      weight: signal.weight,
      detail: signal.detail,
      role: signal.role
    })),
    explanation: dto.explanation,
    explanationMode: dto.explanation_mode,
    asOf: dto.as_of,
    provider: dto.provider,
    priceBasis: dto.price_basis,
    sampleSize: dto.sample_size,
    delayed: dto.delayed,
    stale: dto.stale,
    proxyNote: dto.proxy_note,
    limitations: dto.limitations ?? [],
    writerProviderId: dto.writer_provider_id,
    writerModel: dto.writer_model,
    news: (dto.news ?? []).map((item) => ({
      title: item.title,
      url: item.url,
      source: item.source,
      publishedAt: item.published_at,
      ageLabel: item.age_label,
      summary: item.summary,
      imageUrl: item.image_url,
      symbol: item.symbol
    })),
    rawConfidence: dto.raw_confidence ?? dto.confidence,
    calibrationApplied: dto.calibration_applied ?? false,
    calibrationSample: dto.calibration_sample ?? 0,
    calibrationNote: dto.calibration_note ?? ""
  };
}

export async function fetchCalibration(): Promise<CalibrationStats> {
  const dto = await json<{
    buckets: Array<{ bucket: string; graded: number; correct: number; hit_rate: number | null }>;
    decisive_share: number | null;
    luck_baseline: number | null;
    total_graded: number;
    min_sample: number;
  }>("/api/v1/desk/calibration");
  return {
    buckets: dto.buckets.map((bucket) => ({
      bucket: bucket.bucket,
      graded: bucket.graded,
      correct: bucket.correct,
      hitRate: bucket.hit_rate
    })),
    decisiveShare: dto.decisive_share,
    luckBaseline: dto.luck_baseline,
    totalGraded: dto.total_graded,
    minSample: dto.min_sample
  };
}

function symbolQuery(symbols?: string[]): string {
  if (!symbols?.length) return "";
  return `?symbols=${encodeURIComponent(symbols.join(","))}`;
}

export async function fetchMacroDesk(symbols?: string[]): Promise<MacroDesk> {
  const dto = await json<{
    instruments: BiasDto[];
    unavailable: Record<string, string>;
    generated_at: string;
  }>(`/api/v1/desk/macro${symbolQuery(symbols)}`);
  return {
    instruments: dto.instruments.map(biasFromDto),
    unavailable: dto.unavailable ?? {},
    generatedAt: dto.generated_at
  };
}

export async function fetchSessions(): Promise<SessionState[]> {
  const dto = await json<{
    sessions: Array<{
      key: string;
      label: string;
      timezone: string;
      phase: string;
      phase_label: string;
      local_time: string;
      is_open: boolean;
      next_phase: string;
      next_phase_label: string;
      next_transition_at: string;
      seconds_to_next: number;
      countdown: string;
    }>;
  }>("/api/v1/desk/sessions");
  return dto.sessions.map((session) => ({
    key: session.key,
    label: session.label,
    timezone: session.timezone,
    phase: session.phase as SessionState["phase"],
    phaseLabel: session.phase_label,
    localTime: session.local_time,
    isOpen: session.is_open,
    nextPhase: session.next_phase as SessionState["phase"],
    nextPhaseLabel: session.next_phase_label,
    nextTransitionAt: session.next_transition_at,
    secondsToNext: session.seconds_to_next,
    countdown: session.countdown
  }));
}

export async function fetchNews(limit = 12): Promise<NewsFeed> {
  const dto = await json<{
    items: Array<{
      title: string;
      url: string;
      source: string;
      published_at: string | null;
      age_label: string | null;
      summary: string | null;
      image_url: string | null;
      symbol: string | null;
    }>;
    available: boolean;
    stale: boolean;
    reason: string | null;
    provider: string;
  }>(`/api/v1/desk/news?limit=${limit}`);
  const items: NewsItem[] = dto.items.map((item) => ({
    title: item.title,
    url: item.url,
    source: item.source,
    publishedAt: item.published_at,
    ageLabel: item.age_label,
    summary: item.summary,
    imageUrl: item.image_url,
    symbol: item.symbol
  }));
  return {
    items,
    available: dto.available,
    stale: dto.stale,
    reason: dto.reason,
    provider: dto.provider
  };
}

export async function fetchStrength(): Promise<StrengthSnapshot> {
  const dto = await json<{
    currencies: Array<{
      currency: string;
      score: number;
      pairs: number;
      contributions: Array<[string, number]>;
    }>;
    flow: Array<{ symbol: string; change_percent: number; asset_class: string }>;
    unavailable: Record<string, string>;
    window: string;
    generated_at: string;
  }>("/api/v1/desk/strength");
  return {
    currencies: dto.currencies.map((item) => ({
      currency: item.currency,
      score: item.score,
      pairs: item.pairs,
      contributions: item.contributions ?? []
    })),
    flow: dto.flow.map((item) => ({
      symbol: item.symbol,
      changePercent: item.change_percent,
      assetClass: item.asset_class ?? "equity"
    })),
    unavailable: dto.unavailable ?? {},
    window: dto.window,
    generatedAt: dto.generated_at
  };
}

export type MarketMood = {
  mood: "risk_on" | "risk_off" | "mixed" | string;
  spread: number;
  riskScore: number;
  havenScore: number;
  components: Array<{
    symbol: string;
    label: string;
    role: string;
    changePercent: number;
    contribution: number;
  }>;
  unavailable: string[];
  summary: string;
  caveat: string;
};

export async function fetchMood(): Promise<MarketMood> {
  const dto = await json<{
    mood: string;
    spread: number;
    risk_score: number;
    haven_score: number;
    components: Array<{
      symbol: string;
      label: string;
      role: string;
      change_percent: number;
      contribution: number;
    }>;
    unavailable: string[];
    summary: string;
    caveat: string;
  }>("/api/v1/desk/mood");
  return {
    mood: dto.mood,
    spread: dto.spread,
    riskScore: dto.risk_score,
    havenScore: dto.haven_score,
    components: dto.components.map((item) => ({
      symbol: item.symbol,
      label: item.label,
      role: item.role,
      changePercent: item.change_percent,
      contribution: item.contribution
    })),
    unavailable: dto.unavailable ?? [],
    summary: dto.summary,
    caveat: dto.caveat
  };
}

export async function fetchBriefing(symbols?: string[]): Promise<Briefing> {
  const dto = await json<{
    headline: string;
    summary: string;
    regime: string;
    tone: string;
    items: Array<{
      symbol: string;
      direction: string;
      confidence: number;
      band: string;
      text: string;
      as_of: string;
    }>;
    generated_at: string;
    caveats: string[];
    changes: string[];
  }>(`/api/v1/desk/briefing${symbolQuery(symbols)}`);
  const items: BriefingItem[] = dto.items.map((item) => ({
    symbol: item.symbol,
    direction: item.direction as BriefingItem["direction"],
    confidence: item.confidence,
    band: item.band,
    text: item.text,
    asOf: item.as_of
  }));
  return {
    headline: dto.headline,
    summary: dto.summary,
    regime: dto.regime,
    tone: dto.tone,
    items,
    generatedAt: dto.generated_at,
    caveats: dto.caveats ?? [],
    changes: dto.changes ?? []
  };
}
