# Ricci-flow vs spectral vs namespace partitions

- Clusters: 316
- Import edges: 146,337
- Ricci resolution: 1.5; spectral k: 8

| partition | k | mod (topology) | cut (topology) | mod (imports) | cut (imports) |
|---|---:|---:|---:|---:|---:|
| ricci | 10 | 0.3083 | 0.5779 | -0.1098 | 0.8943 |
| spectral | 8 | 0.3823 | 0.3726 | 0.0277 | 0.2711 |
| namespace | 10 | 0.0669 | 0.5941 | -0.0024 | 0.4938 |

## Pairwise agreement

- ricci__spectral: ARI 0.4096, NMI 0.5056
- ricci__namespace: ARI 0.052, NMI 0.1679
- spectral__namespace: ARI 0.0354, NMI 0.206

## Ricci community composition

- size 60, purity 0.583 — {'Lemmata': 35, 'Formalism': 21, 'ReciprocityTheory': 4}
- size 53, purity 0.642 — {'Lemmata': 34, 'ReciprocityTheory': 7, 'Formalism': 4, 'CompanionTheory': 4, 'GroundTheory': 3}
- size 45, purity 0.667 — {'Lemmata': 30, 'Formalism': 11, 'ReciprocityTheory': 2, 'PositivityTheory': 1, 'GroundTheory': 1}
- size 42, purity 0.595 — {'Lemmata': 25, 'Formalism': 17}
- size 25, purity 0.44 — {'Formalism': 11, 'GroundTheory': 6, 'Development': 3, 'ReciprocityTheory': 1, 'Supplements': 1}
- size 23, purity 0.522 — {'Lemmata': 12, 'Formalism': 4, 'ReciprocityTheory': 3, 'PositivityTheory': 2, 'Development': 2}
- size 22, purity 0.545 — {'Formalism': 12, 'Lemmata': 3, 'CompanionTheory': 2, 'ReciprocityTheory': 2, 'GroundTheory': 2}
- size 19, purity 0.684 — {'Formalism': 13, 'Lemmata': 6}
- size 18, purity 0.556 — {'Formalism': 10, 'Lemmata': 8}
- size 9, purity 0.556 — {'ReciprocityTheory': 5, 'Lemmata': 4}

## Spectral community composition

- size 84, purity 0.393 — {'Lemmata': 33, 'ReciprocityTheory': 16, 'GroundTheory': 12, 'Development': 7, 'Formalism': 7}
- size 78, purity 0.641 — {'Lemmata': 50, 'Formalism': 28}
- size 75, purity 0.48 — {'Lemmata': 36, 'Formalism': 34, 'ReciprocityTheory': 5}
- size 37, purity 0.514 — {'Lemmata': 19, 'Formalism': 17, 'ReciprocityTheory': 1}
- size 16, purity 0.875 — {'Formalism': 14, 'Lemmata': 2}
- size 13, purity 0.846 — {'Lemmata': 11, 'ReciprocityTheory': 2}
- size 10, purity 0.7 — {'Lemmata': 7, 'Formalism': 3}
- size 3, purity 0.333 — {'Main': 1, 'Statements': 1, 'Supplements': 1}

## Heaviest cross-community imports (Ricci)

- 41,787 — Development.AbelianVarietyTheory -- Development.AutomorphicArithmetic
- 17,122 — ReciprocityTheory.ReductiveGroups -- Development.AbelianVarietyTheory
- 14,516 — Development.AbelianVarietyTheory -- Formalism.LocalToGlobal
- 5,882 — Development.AbelianVarietyTheory -- Formalism.SharpRestriction
- 5,578 — Development.AbelianVarietyTheory -- Development.WeilBound
- 5,573 — Development.AbelianVarietyTheory -- Development.AutomorphicSpectrum
- 2,898 — ReciprocityTheory.ReductiveGroups -- Development.AutomorphicSpectrum
- 2,398 — Formalism.LocalToGlobal -- Development.AutomorphicArithmetic
- 2,196 — GroundTheory.HeightsAndTheta -- Development.AutomorphicSpectrum
- 2,180 — Development.AbelianVarietyTheory -- Formalism.LocalRingCardinality
