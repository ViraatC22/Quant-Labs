"""Session desk endpoints: macro bias, sessions, news, calendar, and briefing.

Most of these are read-only market-context views shared by every user, so they
take no `user_id` dependency. `/briefing` is the exception: it records bias
snapshots per user in order to report genuine changes, so it is user-scoped.

A failure to load one instrument degrades that instrument (reported in
`unavailable`) rather than failing the whole desk — a dashboard with three of
four cards beats a 502.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import DeskReport
from app.schemas.desk import (
    BiasSignalRead,
    BriefingItemRead,
    BriefingRead,
    CalendarEventRead,
    CalendarRead,
    CalibrationBucketRead,
    CalibrationRead,
    CurrencyStrengthRead,
    DeskReportRead,
    DeskReportSummaryRead,
    FlowEntryRead,
    InstrumentBiasRead,
    MacroDeskRead,
    MarketMoodRead,
    MoodComponentRead,
    NewsFeedRead,
    NewsItemRead,
    SessionsRead,
    SessionStateRead,
    StrengthRead,
)
from app.services.desk import briefing as briefing_service
from app.services.desk import calendar as calendar_service
from app.services.desk import calibration as calibration_service
from app.services.desk import mood as mood_service
from app.services.desk import news as news_service
from app.services.desk import reports as reports_service
from app.services.desk import sessions as sessions_service
from app.services.desk import snapshots as snapshots_service
from app.services.desk import strength as strength_service
from app.services.desk.bias import InstrumentBias, build_bias
from app.services.market_data import (
    CHANGE_WINDOW_BARS,
    MarketContext,
    asset_class_for,
    fetch_market_context,
)

router = APIRouter()


# A cross-asset basket is dozens of upstream calls on a cold cache. Fetching
# them sequentially made the dashboard's first load several seconds; the market
# data layer is thread-safe (its cache is lock-guarded), so a small pool is
# safe and turns that into roughly one round trip.
_FETCH_WORKERS = 8


def _fetch_contexts(
    symbols: list[str],
) -> tuple[dict[str, MarketContext], dict[str, str]]:
    """Fetch market context for many symbols in parallel.

    Returns ``(contexts_by_symbol, unavailable_by_symbol)``. A failure degrades
    that one instrument rather than the whole request.
    """
    contexts: dict[str, MarketContext] = {}
    unavailable: dict[str, str] = {}

    def load(symbol: str) -> tuple[str, MarketContext | None, str | None]:
        try:
            return symbol, fetch_market_context(symbol), None
        except (OSError, TimeoutError, ValueError) as exc:
            return symbol, None, f"Market context unavailable ({type(exc).__name__})."

    if not symbols:
        return contexts, unavailable
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        for symbol, context, error in pool.map(load, symbols):
            if context is None:
                unavailable[symbol] = error or "Unavailable."
            else:
                contexts[symbol] = context
    return contexts, unavailable


def _current_price(symbol: str) -> float | None:
    try:
        return fetch_market_context(symbol).last_price
    except (OSError, TimeoutError, ValueError):
        return None


def _requested_symbols(symbols: str | None) -> list[str]:
    if not symbols:
        return list(settings.macro_desk_symbols)
    parsed = [item.strip().upper() for item in symbols.split(",") if item.strip()]
    # Bounded so a crafted query string cannot fan out into dozens of upstream
    # fetches; each symbol is a separate provider call.
    return parsed[:12] or list(settings.macro_desk_symbols)


def _collect_biases(
    symbols: list[str],
) -> tuple[list[InstrumentBias], dict[str, str], dict[str, list[NewsItemRead]]]:
    biases: list[InstrumentBias] = []
    news_by_symbol: dict[str, list[NewsItemRead]] = {}
    contexts, unavailable = _fetch_contexts(symbols)

    for symbol in symbols:
        context = contexts.get(symbol)
        if context is None:
            continue
        # Headlines are optional context: retrieved per instrument (cached),
        # handed to the explanation writer as the only news it may reference,
        # and returned as data so the card can list them verbatim.
        feed = news_service.fetch_symbol_news(symbol)
        headlines = tuple(item.title for item in feed.items)
        news_by_symbol[symbol.strip().upper().replace("/", "")] = [
            NewsItemRead(
                title=item.title,
                url=item.url,
                source=item.source,
                published_at=item.published_at,
                age_label=item.age_label,
                summary=item.summary,
                image_url=item.image_url,
                symbol=item.symbol,
            )
            for item in feed.items
        ]
        biases.append(build_bias(context, headlines))
    return biases, unavailable, news_by_symbol


def _bias_read(
    bias: InstrumentBias,
    news: list[NewsItemRead] | None = None,
    calibrated: calibration_service.CalibratedConfidence | None = None,
) -> InstrumentBiasRead:
    return InstrumentBiasRead(
        symbol=bias.symbol,
        asset_class=asset_class_for(bias.symbol),
        direction=bias.direction,
        confidence=calibrated.calibrated if calibrated else bias.confidence,
        strength=bias.strength,
        agreement=bias.agreement,
        coverage=bias.coverage,
        last_price=bias.last_price,
        change_percent=bias.change_percent,
        signals=[
            BiasSignalRead(
                label=signal.label,
                direction=signal.direction,
                value=round(signal.value, 4),
                weight=signal.weight,
                detail=signal.detail,
                role=signal.role,
            )
            for signal in bias.signals
        ],
        explanation=bias.explanation,
        explanation_mode=bias.explanation_mode,
        as_of=bias.as_of,
        provider=bias.provider,
        price_basis=bias.price_basis,
        sample_size=bias.sample_size,
        delayed=bias.delayed,
        stale=bias.stale,
        proxy_note=bias.proxy_note,
        limitations=list(bias.limitations),
        writer_provider_id=bias.writer_provider_id,
        writer_model=bias.writer_model,
        news=news or [],
        raw_confidence=bias.confidence,
        calibration_applied=bool(calibrated and calibrated.applied),
        calibration_sample=calibrated.sample if calibrated else 0,
        calibration_note=calibrated.note if calibrated else "",
    )


@router.get("/macro", response_model=MacroDeskRead)
def macro_desk(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    symbols: Annotated[str | None, Query(max_length=200)] = None,
) -> MacroDeskRead:
    biases, unavailable, news_by_symbol = _collect_biases(_requested_symbols(symbols))
    # Display-time calibration: the engine's raw confidence is blended toward
    # the measured hit rate of its bucket. Snapshots (written by /briefing)
    # store the raw value, so learning never feeds on its own output.
    stats = calibration_service.load_stats(db, user_id=user_id)
    return MacroDeskRead(
        instruments=[
            _bias_read(
                bias,
                news_by_symbol.get(bias.symbol),
                calibration_service.calibrate(bias.direction, bias.confidence, stats),
            )
            for bias in biases
        ],
        unavailable=unavailable,
        generated_at=datetime.now(UTC),
    )


@router.get("/sessions", response_model=SessionsRead)
def market_sessions() -> SessionsRead:
    now = datetime.now(UTC)
    return SessionsRead(
        sessions=[
            SessionStateRead(
                key=state.key,
                label=state.label,
                timezone=state.timezone,
                phase=state.phase,
                phase_label=state.phase_label,
                local_time=state.local_time,
                is_open=state.is_open,
                next_phase=state.next_phase,
                next_phase_label=state.next_phase_label,
                next_transition_at=state.next_transition_at,
                seconds_to_next=state.seconds_to_next,
                countdown=state.countdown,
            )
            for state in sessions_service.all_session_states(now)
        ],
        now_utc=now,
    )


@router.get("/news", response_model=NewsFeedRead)
def news(limit: Annotated[int, Query(ge=1, le=50)] = 12) -> NewsFeedRead:
    feed = news_service.fetch_news(limit=limit)
    return NewsFeedRead(
        items=[
            NewsItemRead(
                title=item.title,
                url=item.url,
                source=item.source,
                published_at=item.published_at,
                age_label=item.age_label,
                summary=item.summary,
                image_url=item.image_url,
                symbol=item.symbol,
            )
            for item in feed.items
        ],
        available=feed.available,
        stale=feed.stale,
        reason=feed.reason,
        provider=feed.provider,
    )


@router.get("/calibration", response_model=CalibrationRead)
def calibration(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> CalibrationRead:
    """The desk's graded track record, bucketed, with the luck baseline."""
    stats = calibration_service.load_stats(db, user_id=user_id)
    return CalibrationRead(
        buckets=[
            CalibrationBucketRead(
                bucket=item.bucket,
                graded=item.graded,
                correct=item.correct,
                hit_rate=item.hit_rate,
            )
            for item in stats.buckets.values()
        ],
        decisive_share=stats.decisive_share,
        luck_baseline=stats.luck_baseline,
        total_graded=stats.total_graded,
        min_sample=calibration_service.MIN_SAMPLE,
        generated_at=datetime.now(UTC),
    )


@router.get("/mood", response_model=MarketMoodRead)
def market_mood() -> MarketMoodRead:
    """Risk-on/off read from cross-asset moves. Descriptive, not predictive."""
    wanted = [symbol for symbol, _ in mood_service.RISK_ASSETS] + [
        symbol for symbol, _, _ in mood_service.HAVENS
    ]
    changes: dict[str, float] = {}
    unavailable: list[str] = []
    for symbol in wanted:
        try:
            changes[symbol] = fetch_market_context(symbol).change_percent
        except (OSError, TimeoutError, ValueError):
            unavailable.append(symbol)

    result = mood_service.derive_mood(changes, tuple(unavailable))
    return MarketMoodRead(
        mood=result.mood,
        spread=result.spread,
        risk_score=result.risk_score,
        haven_score=result.haven_score,
        components=[
            MoodComponentRead(
                symbol=item.symbol,
                label=item.label,
                role=item.role,
                change_percent=item.change_percent,
                contribution=item.contribution,
            )
            for item in result.components
        ],
        unavailable=list(result.unavailable),
        summary=result.summary,
        caveat=result.caveat,
        generated_at=datetime.now(UTC),
    )


@router.get("/strength", response_model=StrengthRead)
def strength(
    symbols: Annotated[str | None, Query(max_length=200)] = None,
) -> StrengthRead:
    """Currency strength plus a capital-flow ranking.

    Defaults to the FX majors, because currency strength is only meaningful
    when each currency appears in several pairs. Extra symbols still show up in
    the flow ranking even though non-FX names contribute no strength.
    """
    requested = (
        _requested_symbols(symbols) if symbols else list(strength_service.FLOW_BASKET)
    )
    contexts, unavailable = _fetch_contexts(requested)
    changes = {symbol: ctx.change_percent for symbol, ctx in contexts.items()}

    return StrengthRead(
        currencies=[
            CurrencyStrengthRead(
                currency=item.currency,
                score=item.score,
                pairs=item.pairs,
                contributions=list(item.contributions),
            )
            for item in strength_service.currency_strength(changes)
        ],
        flow=[
            FlowEntryRead(
                symbol=item.symbol,
                change_percent=item.change_percent,
                asset_class=asset_class_for(item.symbol),
            )
            for item in strength_service.capital_flow(changes)
        ],
        unavailable=unavailable,
        window=f"last {CHANGE_WINDOW_BARS} hourly bars",
        generated_at=datetime.now(UTC),
    )


@router.get("/calendar", response_model=CalendarRead)
def calendar(
    impact: Annotated[str | None, Query(max_length=60)] = None,
    currencies: Annotated[str | None, Query(max_length=120)] = None,
) -> CalendarRead:
    """This week's economic events, optionally filtered.

    `impact` and `currencies` are comma-separated (e.g. `impact=high,medium`).
    Filtering happens here rather than client-side so the timeline can request
    only what it renders.
    """
    feed = calendar_service.fetch_calendar()
    events = list(feed.events)

    if impact:
        wanted = {item.strip().lower() for item in impact.split(",") if item.strip()}
        events = [event for event in events if event.impact in wanted]
    if currencies:
        wanted = {item.strip().upper() for item in currencies.split(",") if item.strip()}
        events = [event for event in events if event.currency in wanted]

    return CalendarRead(
        events=[
            CalendarEventRead(
                title=event.title,
                currency=event.currency,
                impact=event.impact,
                scheduled_at=event.scheduled_at,
                date_label=event.date_label,
                all_day=event.all_day,
                tentative=event.tentative,
                forecast=event.forecast,
                previous=event.previous,
                actual=event.actual,
                url=event.url,
            )
            for event in events
        ],
        available=feed.available,
        stale=feed.stale,
        reason=feed.reason,
        source=feed.source,
        now_utc=datetime.now(UTC),
    )


def _report_read(report: DeskReport) -> DeskReportRead:
    return DeskReportRead(
        id=report.id,
        report_date=report.report_date,
        title=report.title,
        payload=report.payload or {},
        read_at=report.read_at,
        created_at=report.created_at,
    )


@router.post("/reports/generate", response_model=DeskReportRead)
def generate_report(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> DeskReportRead:
    """Return today's report, generating it on first call (idempotent)."""
    now = datetime.now(UTC)
    today = now.date()

    def build() -> tuple[str, dict]:
        biases, unavailable, _news = _collect_biases(_requested_symbols(None))
        reports_service.persist_due_grades(
            db, user_id=user_id, now=now, price_lookup=_current_price
        )
        graded = reports_service.graded_calls_for_report(db, user_id=user_id, now=now)
        calendar_feed = calendar_service.fetch_calendar()
        strength_inputs: dict[str, float] = {}
        for symbol in strength_service.FX_MAJORS:
            try:
                strength_inputs[symbol] = fetch_market_context(symbol).change_percent
            except (OSError, TimeoutError, ValueError):
                continue
        return reports_service.compose_report(
            report_date=today,
            biases=biases,
            graded=graded,
            events=list(calendar_feed.events),
            strength=strength_service.currency_strength(strength_inputs),
            sessions=sessions_service.all_session_states(now),
            unavailable=unavailable,
        )

    report, _created = reports_service.get_or_create_report(
        db, user_id=user_id, report_date=today, builder=build
    )
    return _report_read(report)


@router.get("/reports", response_model=list[DeskReportSummaryRead])
def list_reports(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[DeskReportSummaryRead]:
    rows = db.scalars(
        select(DeskReport)
        .where(DeskReport.user_id == user_id)
        .order_by(DeskReport.report_date.desc())
        .limit(limit)
    ).all()
    out = []
    for row in rows:
        payload = row.payload or {}
        out.append(
            DeskReportSummaryRead(
                id=row.id,
                report_date=row.report_date,
                title=row.title,
                read_at=row.read_at,
                created_at=row.created_at,
                assets_analyzed=int(payload.get("assets_analyzed") or 0),
                high_impact_events=sum(
                    1 for e in payload.get("events", []) if e.get("impact") == "high"
                ),
            )
        )
    return out


@router.get("/reports/{report_id}", response_model=DeskReportRead)
def get_report(
    report_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> DeskReportRead:
    report = db.get(DeskReport, report_id)
    if report is None or report.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )
    return _report_read(report)


@router.patch("/reports/{report_id}/read", response_model=DeskReportRead)
def mark_report_read(
    report_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> DeskReportRead:
    report = db.get(DeskReport, report_id)
    if report is None or report.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )
    if report.read_at is None:
        report.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(report)
    return _report_read(report)


@router.get("/briefing", response_model=BriefingRead)
def briefing(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    symbols: Annotated[str | None, Query(max_length=200)] = None,
) -> BriefingRead:
    now = datetime.now(UTC)
    biases, _, _news = _collect_biases(_requested_symbols(symbols))
    # Recording here is what lets the briefing report a real transition rather
    # than restate the current reading. Only material changes are stored.
    changes = snapshots_service.record_all(db, user_id=user_id, biases=biases)
    # Grade anything that has aged into the window while we are here — the
    # briefing is the endpoint that runs most often, so verdicts accrue without
    # a scheduler.
    reports_service.persist_due_grades(
        db, user_id=user_id, now=now, price_lookup=_current_price
    )
    result = briefing_service.build_briefing(
        biases, sessions_service.all_session_states(now), now, changes
    )
    return BriefingRead(
        headline=result.headline,
        summary=result.summary,
        regime=result.regime,
        tone=result.tone,
        items=[
            BriefingItemRead(
                symbol=item.symbol,
                direction=item.direction,
                confidence=item.confidence,
                band=item.band,
                text=item.text,
                as_of=item.as_of,
            )
            for item in result.items
        ],
        generated_at=result.generated_at,
        caveats=list(result.caveats),
        changes=list(result.changes),
    )
