# Prior art

| reference | what it does | reusable? | differentiator of psd2-kpi-es |
|---|---|---|---|
| Open Banking (UK) — `standards.openbanking.org.uk/operational-guidelines/availability-and-performance` | Operational guidelines for UK ASPSP stats publication; format expectations & per-interface reporting rules | Conceptual: comparability cautions, per-interface reporting | OB-UK numbers come from regulated APIs/FCA reporting; we ingest *published* Spanish docs, not regulatory feeds |
| EBA Single Rulebook Q&A (eba.europa.eu) | Authoritative interpretations of Art. 32(4) | Regulatory citations only | — |
| enablebanking.com / openbankingtracker.com | Commercial API-availability tracking (self-measured) | No | We publish *self-reported* stats with provenance, not probe-based measurement |
| Downdetector / isitdown* | Real-time user-reported outage tracking | No | Orthogonal signal; not regulatory statistics |
| datos.gob.es | Spanish open data catalogue | No dataset on PSD2 KPIs found | — |

No comparable open dataset of *published* Spanish ASPSP PSD2 statistics was
found (searched GitHub and the open-banking tooling space, Oct 2026). The
closest work is the UK Open Banking standard documentation, which informed
the comparability model but provides no code or data we reuse.
