# Domain types

Not a preset: a catalogue of functional types that depend on the product's domain. `/pb:init` asks about the domain and proposes the ones that fit (section **D** of the init skill); `/pb:schema` can add one later. A chosen type is copied into `brain/.pb/schema/types/` and adapted like any other type.

Every type here points at what it governs with `applies_to` (features, concepts, roles, modules): context packs follow that field, so a rule or a regulation reaches the agents working on the features it applies to.

| Type | What it holds | Signals in the repo, the docs and the interview | Fits |
|---|---|---|---|
| `rule` | A business rule valid across features: a calculation, a validation, a constraint, with its basis (law, contract, policy, convention) | calculation engines, `rules/`, `validators/`, rounding or tax code; docs full of "must", "only if", formulas | ERP, accounting, payroll, tax, insurance, pricing |
| `regulation` | An external norm the product must comply with (law, decree, authority circular, standard), what it imposes and how the product complies | e-invoicing, GDPR, PSD2, accessibility, fiscal deadlines; authority names in docs and code (AdE, SDI, INPS) | regulated domains: tax, finance, health, public sector |
| `metric` | A product or business KPI with its exact definition, the source of truth and how it is computed | analytics events, dashboards, `metrics/`, docs with targets and OKRs | data-driven products, SaaS growth teams |
| `edition` | A commercial package of the product (edition, plan, licence tier, add-on): what it includes, limits, who buys it | licensing or entitlement code, feature flags per plan, price lists, "available in Premium" in docs | commercial software sold in editions or plans |

## Interview

Ask these in one round (the answers decide which types to propose; facts first, never ask what the repo or the docs already say):

1. **Who and what for**: who uses the product and for which job (accounting firms keeping books, HR offices running payroll, shops selling online…).
2. **Rules**: does the product compute or validate things by rules the business owns (taxes, prices, deadlines, eligibility)? Do the same rules apply in several features?
3. **Regulation**: must it follow external norms that change over time? Which authorities or standards?
4. **Commercial shape**: is it sold in editions, plans or add-ons that change what users can do?
5. **Measures**: does the team steer by product KPIs whose exact definition matters?

Propose a type only on a clear recurring need: a "no" or a vague answer leaves it out (it can be added later with `/pb:schema`). When the domain needs something the catalogue lacks (e.g. `channel` for an omnichannel product, `document-template` for a document generator), design it in the same format: area, folder, fields with `applies_to`, budget, prose with create / do not create / body structure.
