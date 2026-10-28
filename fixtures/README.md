# Part 02 Provider Fixtures

Read-only, entirely synthetic fixtures used by `MockProvider` (mock mode), contract
tests and the demo seed. The Meta, Google and Shopify JSON files are generated locally by `scripts/generate_fixtures.py` from code literals and a seeded pseudorandom generator, without reading provider accounts or business exports. Scenario files:

- `healthy_growth` — normal 3-day growth data
- `zero_purchase_burn` — spend with no purchases
- `meta_creative_fatigue` — impressions up, CTR down
- `google_high_cpc` — high cost-per-click search data
- `shopify_refund_spike` — orders with heavy refunds
- `api_rate_limit` — provider returns rate-limit error
- `schema_drift` — provider returns unexpected schema

## Instagram Growth Intelligence

`instagram/growth_intelligence_v1.json` is a fixed, explicitly `DEMO`-mode
fixture for the Instagram V1 domain contract. It contains account and media
raw snapshots, capability reasons, and unsupported metrics represented as
`null`; it does not contain Ads, Shopify, revenue, ROAS, interest, or purchase
attribution data.
