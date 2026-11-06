# NJC Cabin Meal Allowance

**No affiliation with the National Joint Council (NJC) or the Government of Canada.**

A `nanoagent.plugin/v0001` plugin, version 0.2.0. An agent works out one Canadian public-service trip's
entitlement under a toy handbook paraphrased from the National Joint Council Travel Directive (version 326,
effective 2025-10-01, with Appendix C and D rates effective 2026-10-01). It reads the trip and the destination's
allowance row, then submits the cabin authorized on each outbound segment and the meal and incidental
allowances. A deterministic Python verifier, with no LLM, checks the answer against an oracle that it
computes itself, and gives partial credit per decision.

## Task

- **Input:** `ScenarioInput` with a single field, `scenario`, which names one of twelve bundled trips, for
  example `{"scenario": "tokyo-trade-talks"}`.
- **Tools:** the agent calls `get_trip_request`, then `get_allowance_rates`, then `submit`. This is three of
  the six hosted steps.
- **Output:** `NjcEntitlementOutput`, with these fields:
  - `segment_cabins`: one `{segment_id, cabin}` per outbound segment (economy, premium_economy or business);
  - `longest_continuous_air_minutes`;
  - `currency`;
  - `meal_allowance_minor`, `incidental_allowance_minor`, `total_minor`: integers in hundredths of the currency.
- **Success:** the answer equals the one entitlement that the handbook's rules give (`valid`); the `score`
  says how much of it is right.

The handbook is `src/plugin/data/handbook.md`. It is also the task's `instructions` in `nanoagent.yaml`, and
a test keeps the two identical. It holds the paraphrased in-scope rules, the "Clarifications (toy rules)"
C1–C10, the rules not in scope, the pinned sources with their drift, and the step plan.

Each scenario sets one trap, and the twelve pair up at the sharp edges: 540 vs 541 minutes (Paris vs London
and Berlin), an overnight stop that leaves 505 vs 1055 minutes (Nairobi crop vs Sydney), a qualifying leg that
sells premium economy vs only economy (Tokyo vs Berlin), Hawaii vs Alaska, and the meal clock one minute either
side of 07:00, 12:00 and 18:00 at the start and the end of status.

| Scenario | Trap | Correct entitlement |
|---|---|---|
| `paris-assembly` | 75 + 60 connection + 405 = exactly 540 continuous minutes, which is not more than nine hours. Status starts 12:01 and ends 17:59 | economy, economy; 540; EUR 20020 + 15704 = 35724 |
| `london-secondment` | 65 + 60 + 416 = 541 only when the connection counts (481 in the air). Private accommodation lowers the incidental. Status ends 18:00 | business, business; 541; GBP 31340 + 8836 = 40176 |
| `nairobi-crop-institute` | Decision 1575: the overnight stop in London cuts the journey into 410 and 505. Status ends 12:00 | economy, economy; 505; KES 3400500 + 2176320 = 5576820 |
| `nairobi-water-workshop` | A five-hour daytime wait is an ordinary connection: 400 + 300 + 505 = 1205. Status starts 18:00, ends 06:59 | business, business; 1205; KES 3197500 + 1813600 = 5011100 |
| `tokyo-trade-talks` | The long-haul flight sells no business, so premium economy; the short hop in the same block is business. Status starts 07:00; the date line | business, premium_economy; 950; JPY 4774000 + 2874880 = 7648880 |
| `washington-conference` | Continental USA is Module 3, economy; Canadian amounts paid in USD; status ends 11:59 | economy; 100; USD 18310 + 7500 = 25810 |
| `honolulu-science-meeting` | Hawaii is outside the continental USA, so Module 4 and business at 740 minutes | business, business; 740; USD 46285 + 12500 = 58785 |
| `whitehorse-site-review` | Domestic, so economy; Yukon has its own Appendix C column | economy, economy; 510; CAD 36800 + 7500 = 44300 |
| `sydney-reef-symposium` | Decision 1575 the other way: the overnight stop in Vancouver leaves 300 and 360 + 95 + 600 = 1055, so the two legs after it are business. Three segments; a full day spent mostly in the air; status ends 18:01 | economy, business, business; 1055; AUD 101035 + 47220 = 148255 |
| `berlin-standards-meeting` | 55 + 65 + 421 = 541 (476 in the air); the long leg sells only economy, so the short hop is business and the long leg economy. Status starts 07:01 (no breakfast) and ends 07:00 (breakfast) | business, economy; 541; EUR 40035 + 21350 = 61385 |
| `anchorage-port-study` | Alaska counts as continental USA: Module 3, economy at 620 minutes, Appendix C on the Yukon amounts in USD. Status ends 00:00 on a listed part day: one incidental, no meal | economy, economy; 620; USD 31405 + 10000 = 41405 |
| `mexico-city-census-exchange` | An Appendix D row paid in Canadian dollars, not pesos; private accommodation. Status starts 18:01 (no dinner) and ends 12:01 (lunch) | economy; 345; CAD 46400 + 18270 = 64670 |

## Tools

| Tool | Does | Code |
|---|---|---|
| `get_trip_request` | Returns a scenario's trip: the traveller's words, the destination with its geography flag and allowance row id, the accommodation, the outbound segments (UTC and local times, in-air minutes, cabins sold, the connection after each with its minutes and overnight-stop flag) and every travel-status day with its status window and provided meals | `src/plugin/trip.py` |
| `get_allowance_rates` | Returns one Appendix C or D row (days 1–30) for both accommodation types, with its currency. It applies no policy | `src/plugin/rates.py` |
| `compute_njc_entitlement` | The answer key: the oracle (`rules.oracle`) over the bundled fixtures. It is the task's `reference`, never shown to the agent | `src/plugin/reference.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `njc-trip-entitlement` | Works out the cabin per outbound segment and the meal and incidental allowances for a trip under the toy NJC handbook | `agent`, with `get_trip_request` and `get_allowance_rates`; reference `compute_njc_entitlement` |

## Environment

- Offline and self-contained. It uses `hosts: []`, an empty `.env`, and `write: []`, and has no clock.
- Fixtures are in `src/plugin/data/`:
  - `rates.json`: 14 Appendix C and D rows, the printed amounts in hundredths, effective 2026-10-01;
  - `travellers.json` and `airports.json` (the time zones the generator used);
  - `scenarios/<id>.json`, twelve trips of one to three segments from Ottawa, Toronto and Vancouver, which hold
    facts only and never an answer; `request_text` is flavour, and every fact it mentions is also a typed field.
- Fixtures come from `src/plugin/tools_dev/generate.py`, which converts local times to UTC with `zoneinfo` once. A test checks the generator still reproduces the committed files byte for byte, and another recomputes every UTC time.
- The shared core is `src/plugin/world.py` (fixture schema, loader and checks, date, clock and minute arithmetic without `datetime`). The oracle is `src/plugin/rules.py`. Both are byte-identical in `verifier/`.
- Python 3.12 or later, with dependencies pinned by `uv.lock`.

### Sources and their drift

The handbook pins the Directive (v326) and the Appendix D print page by URL and sha256. Both pages changed
between the first capture (2026-11-02) and a re-capture on 2026-11-06: the Directive print page went from
`6fd931c9…` to `46cde1bb…`, and the Appendix D print page (`app_d/en?print=1&drv_id=0`) from `9a96123b…` to
`8f9772b3…`. The handbook records both hashes and both dates. On 2026-11-06 every bundled Appendix D row
(Paris, Berlin, London, Nairobi, Tokyo, Mexico City, Sydney and Hawaii, both accommodation types) was re-read
from the served page and matches `rates.json` to the cent. Appendix C is no longer served at `app_c/en` (HTTP
404), so the Canada, Yukon, Northwest Territories, Nunavut, continental USA and Alaska rows stay as typed from
the 2026-11-02 capture; `tests/test_fixtures.py` holds that typed copy independently of the generator.

## Verifier

`verifier/entitlement.py` reads the fixtures through `Path(__file__)` (`verifier/checks.py`), computes the oracle
with the shared `rules.py`, and checks the submission against eleven constraints in four stages. Each check has a
stable reason code. Every constraint is checked, and the message names the first failing one in stage order with
the rule and the numbers (for example "S1 YYZ-YUL is business instead of economy: its continuous block is 540 min,
not > 540, so economy") and how many more fail.

1. **Answer key:** `reference-matches-oracle`.
2. **Referential integrity:** `segments-match-journey` (every outbound segment exactly once).
3. **Internal consistency:** `cabins-are-sold`, `amounts-non-negative`, `total-is-sum`.
4. **Decision against the oracle:** `longest-block-correct`, `cabins-correct`, `currency-correct`, `meals-correct`, `incidentals-correct`, `total-correct`.

How it scores:

- `valid` is strict: true only when every constraint holds, and then `score` is 1.0.
- Otherwise `score` is partial credit for the stage-4 decisions, in hundredths that sum to 100: cabins 15
  (shared out per outbound segment, each earning its share when it is named exactly once with the oracle's
  cabin), longest block 20, currency 5, meals 30, incidentals 20, total 10. A right decision earns its weight;
  a wrong one earns nothing, whichever way it is wrong. `details.score_parts` shows the split.
- Two caps, documented here: a submission that fails `segments-match-journey` (a missing, repeated or unknown
  segment id) scores at most 0.25, however right its amounts; a broken answer key scores 0.0.
- What lazy answers earn: an empty, all-zero slip at most 0.05 (the currency, when CAD happens to be right);
  economy everywhere with zero amounts at most 0.20; another scenario's answer at most 0.275 in the bundled set
  (London's answer on Berlin, whose blocks are both 541 by design and which share one cabin), and 0.25 or less
  for every other pair. Every amount is specific to the trip.
- `details` also holds every constraint and the expected answer, as plain JSON.
- Shape errors never reach the verifier, because NanoAgent's `build_output` refuses them first: a wrong type, an unknown Enum value, a missing or extra field, or `null` for a required field.
- The verifier is pure stdlib and never raises. An unknown task or tool id, an unknown scenario, a malformed, deeply nested or cyclic value, or a broken fixture becomes a `verifier-error` verdict.
- Tool outputs are also checked against the fixtures (`verify_output`), and the rates tool's input against the tables (`verify_input`).

## Validation

`tests/` covers the brief's whole test matrix:

- correct, incorrect, missing and malformed outputs, with malformed cases as `build_output` rejections;
- boundaries: 540/541 continuous minutes (and a connection minute tipping it), connections counted, an ordinary connection of 0–720 minutes never cutting a block, an overnight stop always cutting it, per-segment cabins in a divided journey, business not sold, Module 3 vs 4, every meal's clock minute and one minute either side at the start and the end of status, provided meals, part days, the accommodation row;
- the corrected §11 sanity row: 360 + 90 + 420 gives 870 continuous minutes and business; with an overnight stop instead, economy;
- uniqueness: any other cabin, currency, or amount or minute count one off fails;
- partial credit: the gold answer scores 1.0 with parts summing to 100; each wrong decision costs its weight; too high and too low cost the same; lazy and cross-scenario answers stay low; the integrity cap and the broken-key zero;
- oracle == the hand-written `tests/cases/<scenario>.json` for every scenario, each with broken variants that together lead with every reason code except `reference-matches-oracle` (tested with a wrong pinned key) and `total-correct`, which can never fail first (when the meals and the incidentals are right and `total-is-sum` holds, the total is right too);
- the bundled scenarios cover every rule branch: Module 3 and 4, a block of exactly 540 and of 541, an overnight stop that does and does not leave a qualifying block, business sold, premium economy only and economy only on a qualifying leg, Appendix C (Canada, Yukon, Alaska) and D (six currencies, one paid in CAD), both accommodation rows, provided meals, and the meal clock at 07:00/07:01, 11:59/12:00/12:01, 17:59/18:00/18:01 and 00:00/06:59;
- `rules.py` and `world.py` identity, handbook == `instructions`, every rate row against the source's printed amounts (Alaska as Appendix C on the Yukon amounts, Hawaii as Appendix D on the USA amounts), the generator, UTC times, leap days and year rollover, and the loader refusing inconsistent fixtures (a status window that is open at the wrong end included);
- the verifier returning a `verifier-error` verdict, never an exception, for a fixture it cannot trust: a stay over 30 days or a destination row the tables do not hold;
- structured input and output (`tests/test_contract.py`), `request_text` as flavour only, and neutral scenario ids (`tests/test_scenario_ids.py`);
- a real MCP server round trip and tool-output sizes under about 1k tokens;
- a scripted, no-LLM end-to-end run per scenario: an agent written from the handbook alone follows the step plan, its gold answer passes, and broken answers fail with the expected reason code.

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions, tools, the njc-trip-entitlement task and its handbook instructions
├── contract.py      # typed inputs and outputs of every tool and the task (Enums, int minutes and hundredths)
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # empty: the plugin needs no environment variables
├── src/plugin/      # MCP server (__main__.py), tools, world.py (shared core), rules.py (oracle), fixtures
│   ├── data/        # handbook.md, rates.json, travellers.json, airports.json and scenarios/
│   └── tools_dev/   # the fixture generator (development only)
├── tests/           # verifier matrix, oracle cases, scripted agent, rules, tools, fixtures, contract, scenario ids
├── ui/              # renderers.js and renderers.css: outputs drawn from their JSON Schema
├── product/         # product.yaml and icon.svg
└── verifier/        # deterministic verifier: entitlement.py (task), trip_request.py, rates.py, rules.py, world.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run python -m plugin.tools_dev.generate   # rewrite the fixtures; the tests then check them
```

To run the agent, use `nanoagent plugin agent config=agent.yaml home=<run folder>` with `arguments` set to a
JSON file such as `{"scenario": "tokyo-trade-talks"}`. It needs `OPENROUTER_API_KEY` in the environment, not
in this repo.
