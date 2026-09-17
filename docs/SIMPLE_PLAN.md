# AirPriceX — Simple Plan v2

| Phase | Goal | Status |
|-------|------|--------|
| 0 | 10-second story on home | done |
| 1 | Remapped UI/UX (Story / Prices / Proof) | done |
| 2 | Live SpiceJet on 8 routes + fixture fallback | done |
| 3 | Honest live board (airline-direct vs market vs sample) | done |
| 4 | Daily GitHub Action → `run_live_day` | done |
| 5 | Judge script + Vercel deploy | done |

## Hard rules

- OTA ≠ CPI
- Missing ≠ 0
- No captcha bypass
- **No Google proxy rows counted as IndiGo / Air India / Vistara “live”** — those airlines show sample when blocked; market live is under Google Flights / Ixigo / Cleartrip

## Live collectors (honest)

| Source | Live board | CPI? |
|--------|------------|------|
| SpiceJet | Direct | Yes |
| Akasa | Direct | Yes |
| IndiGo / Air India / Vistara | Sample when blocked | Only if airline-direct someday |
| Google Flights / Ixigo / Cleartrip | Market live | No |

## Run a day

```powershell
$env:ALLOW_LIVE_HTTP="true"
$env:LIVE_AIRLINES="SG,QP"
$env:LIVE_MARKET="true"
python scripts/run_live_day.py
```
