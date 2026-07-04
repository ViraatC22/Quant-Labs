# Provider Setup Requests

Provider integrations are later-phase work. This file will track exact founder
actions as provider adapters are implemented.

| Provider | Founder setup needed? | Priority | Notes |
| --- | --- | --- | --- |
| SEC EDGAR | none | Later | No API key expected; use official public APIs with provenance and rate courtesy. |
| Alpha Vantage | optional_key | Later | Useful equities/fundamentals fallback; document quota and license assumptions before adapter work. |
| FRED | optional_key | Later | Useful macro source; requires a distinct API key. |
| Twelve Data | optional_key | Later | Useful OHLCV fallback; track daily credits and rate limits. |
| Financial Modeling Prep | optional_key | Later | Useful fundamentals/news fallback; verify free tier scope. |
| CoinGecko | optional_key | Later | Useful crypto data; verify Demo API limits. |
| Alpaca | required_account | Later | Paper-only broker adapter after internal simulator is stable. |
| TradingView | required_account | Later | Webhook adapter only; alerts create events, not live orders. |
