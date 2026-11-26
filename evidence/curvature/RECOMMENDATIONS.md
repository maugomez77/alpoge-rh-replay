# Recommendations from the Ollivier–Ricci graph analysis

Status: **analysis only — not applied**. These are hypotheses to validate with
delta-build measurements, not instructions to refactor now.

Source: full module import graph at `e497a6603e` (47,885 modules, 494,947 imports).
Full ORC pass on GitHub Actions (`maugomez77/rh-ricci`, run 45718931916),
20 shards, pairwise shortest paths. Reports in this directory.

## What the data says

- 90.9% of import edges have negative Ollivier–Ricci curvature (mean −0.266);
  the graph is broadly tree-like. That is structural, not a defect.
- Cross-namespace edges are more negative than same-namespace edges
  (−0.350 vs −0.251): namespace boundaries are the fragile links.
- Instance debt is essentially orthogonal to curvature
  (Spearman ρ = −0.044). Separate workstream.
- Compile cost correlates weakly with curvature (ρ = −0.109); degree weakly
  (ρ = −0.214). Curvature is an **interface detector**, not a cost model.
- Worst namespace pairs: `PositivityTheory–ReciprocityTheory` (−0.631),
  `Formalism–PositivityTheory` (−0.565), `Formalism–GroundTheory` (−0.534),
  `Formalism–ReciprocityTheory` (−0.478, n=605),
  `CompanionTheory–ReciprocityTheory` (−0.462).
- Sharpest module bridges: `DivisorProofs.Bundle* ↔ Divisors.Bundle0007`,
  `ThetaCorrespondence…EveryCharacterOfLiteratureOfVWin ↔ WeilBound…TheoremKOfMod`,
  `TemperedProductOfSquareIntegrable ↔ …DiscreteSeriesCoefficientsCuspidal`.

## Recommendations (deferred)

1. **Interface consolidation.** Replace the worst bundle-to-bundle bridges with
   a small explicit interface module. Start with
   `DivisorProofs ↔ Divisors.Bundle0007`, then
   `Formalism ↔ ReciprocityTheory/GroundTheory`.
   Measure the reverse-dependency cone before/after with `import-closure.py`.
2. **Invalidation reduction.** Split the ~4,208-import aggregator, remove
   `import all`, move instance providers into leaves. Target change cost, not
   compile cost.
3. **Instance debt via generator.** `scoped instance` / shared providers, gated
   by `hygiene-check.sh`; do not hand-edit 10k files.
4. **Dedupe via generator.** At most ~444 strict duplicates (cos≥.95, J≥.8);
   emit one shared module + aliases rather than deleting files.
5. **Throughput.** Artifact cache, more cores/second builder, olean-only
   defaults. `-j` tuning is not indicated (timeline shows ~19 busy lanes).

## Do not

- Do not optimize modules by curvature alone (hubs are cheap to compile).
- Do not merge duplicate files by hand (imports differ).
- Do not refactor before the green + certification path is stable.
