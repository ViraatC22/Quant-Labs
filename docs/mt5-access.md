# Reaching MetaTrader 5 from macOS

Findings and a recommendation for connecting Quant Labs to an MT5 account from
an Apple Silicon Mac. Verified July 2026 against a Darwin 26.1 / arm64 host.

## The actual blocker

It is **not** that MT5 cannot run on a Mac. It can, and MetaQuotes ships an
official installer for it. The blocker is narrower and more specific:

> The `MetaTrader5` **Python package** ships only `win_amd64` wheels.

```
$ curl -s https://pypi.org/pypi/MetaTrader5/json   # 5.0.5735
metatrader5-5.0.5735-cp310-cp310-win_amd64.whl
metatrader5-5.0.5735-cp311-cp311-win_amd64.whl
...  (cp36 through cp314 — every one win_amd64)

$ pip install MetaTrader5
ERROR: Could not find a version that satisfies the requirement MetaTrader5
       (from versions: none)
```

Three things follow, and each matters:

1. There is **no macOS wheel** and **no source distribution**, so there is
   nothing for pip to fall back on and build. This is not fixable with flags.
2. There is **no `win_arm64` wheel either**. Even inside Windows-on-ARM, the
   package only runs under x64 emulation.
3. The package is a thin IPC client that talks to a *running MT5 terminal on
   the same machine*. It is not a network API, so it cannot simply be pointed
   at a terminal running elsewhere.

## What does work on macOS

MetaQuotes ships an official macOS installer that supports "all Apple
processors, from M1 to the latest released versions". It is **not a native
port** — the installer downloads and configures Wine, then installs the Windows
build inside it.

So the terminal runs fine on this machine. What you do not get is a Python
bridge: the `MetaTrader5` package would need Windows Python running inside that
same Wine prefix to see the terminal at all.

**That gap — terminal available, Python bridge not — is what the options below
are actually solving.**

---

## Options

### A. MQL5 Expert Advisor calling out over HTTP  ← recommended

Skip the Python package entirely. An Expert Advisor runs *inside* the terminal,
where it already has native access to quotes, positions, and order execution,
and pushes to the Quant Labs API with `WebRequest()`.

**Why this one:** it works wherever the terminal works, including the official
Wine build already supported on this Mac. No emulation stack, no third party
holding broker credentials, no subscription. It also solves the pricing problem
identified in `services/api/app/services/market_data.py` — prices arrive from
the venue the order will actually be routed to, which is the only way
`PRICE_BASIS_TOP_OF_BOOK` ever becomes truthful here.

**Constraints, all verified against the MQL5 docs:**

| Constraint | Consequence |
|---|---|
| Callable from **EAs and scripts only** — indicators get error 4014 | The bridge must be an EA |
| **Synchronous**; blocks the calling program until the server responds | Keep the API endpoint fast; never block a tick handler on a slow call |
| URL must be **whitelisted**: Tools → Options → Expert Advisors | Manual one-time setup on the terminal, per URL |
| **Does not run in the Strategy Tester** | Backtests cannot exercise the bridge |
| Port is implied by scheme (80 / 443) | Non-standard ports are not addressable |

**Shape:** EA pushes account state, positions, and fills to a new
`POST /api/v1/mt5/*` endpoint on a timer. For execution, the EA *polls* for
pending commands rather than accepting inbound connections — the terminal
cannot listen for requests, only make them. That polling direction is forced by
the platform, not a design preference.

### B. MetaApi (cloud REST API)

A hosted service that runs MT4/MT5 terminals for you and exposes a real REST
API plus a Python SDK that installs anywhere, macOS included. Broker-agnostic.

**Cost:** roughly **$10–850/month** per connected account depending on tier.

**The real trade-off is not price.** You hand your broker account credentials to
a third party who then holds standing authority to trade it. That may be
perfectly acceptable, but it should be a deliberate decision rather than a
convenience default.

### C. Docker + QEMU emulation (`silicon-metatrader5`)

Gets you the genuine `MetaTrader5` Python API on Apple Silicon by stacking
Colima + QEMU **full x86_64 emulation** → Linux → Wine → headless MT5, with a
socket IPC bridge to host Python. Notably the project uses QEMU rather than
Rosetta because Rosetta "proved unstable" for this.

Cost: free. Setup: 5–10 min build, **25–30 min first boot**, manual broker login
over VNC.

The author's own warning is the deciding factor:

> for live (production) trading that requires millisecond precision or involves
> high capital, using a physical PC or server with native Windows (no emulation
> layer) is strictly recommended.

**Verdict:** reasonable for research and historical data pulls. Not for
execution.

### D. Windows VM (Parallels + Windows 11 ARM)

The most conventionally "supported" arrangement, and still emulated: the
`win_amd64` wheel runs under Windows-on-ARM's x64 emulation layer. Costs a
Parallels licence plus a Windows licence, and leaves you administering a VM
whose uptime your trading now depends on.

### E. Use the broker's own REST API instead

**Check this before building any of the above.** Many brokers that offer MT5
also publish their own REST API — the account labelled *"IG MT5 Account"* in the
HybridTrader screenshots is an example, and IG has a documented public API.

Where it exists this dominates every other option: no emulation, no Wine, no
subscription, officially supported, and real executable bid/ask straight from
the venue.

---

## Recommendation

1. **Identify the broker first.** If they publish a REST API, take option E and
   stop. It removes the entire problem rather than working around it.
2. **Otherwise take option A.** The EA bridge is free, runs on the Mac you have,
   keeps credentials on your own machine, and delivers venue-accurate prices.
3. **Option B** if you specifically want Python-native access and are willing to
   both pay and delegate account authority.
4. **Option C** for research only. **Option D** only if you already run Windows.

## Scope note

Whichever path is chosen, execution stays manual. Quant Labs' README places live
autonomous trading out of scope, and nothing here changes that: the bridge
carries state *in* and, at most, carries commands you have explicitly authorised
*out*. The live order path should be built disabled and enabled deliberately.

## Sources

- [MetaTrader5 on PyPI](https://pypi.org/pypi/MetaTrader5/json) — wheel list, verified July 2026
- [MetaQuotes: Installation on Mac OS](https://www.metatrader5.com/en/terminal/help/start_advanced/install_mac)
- [MQL5 `WebRequest` documentation](https://www.mql5.com/en/docs/network/webrequest)
- [`silicon-metatrader5`](https://github.com/bahadirumutiscimen/silicon-metatrader5)
- [MetaApi](https://metaapi.cloud/) and [MetaApi Python SDK](https://github.com/metaapi/metaapi-python-sdk)
