# Audit strict de l'échange local au rayon 7

Date : 27 août 2026  
Construction : record public AlphaEvolve de 164 points dans la grille `100 x 100`  
Verdict : **le DFS est complet et correct ; un résultat plus fort, `e_S(7)=5`, possède désormais un certificat DRAT vérifié**

## Résultat final

Notons `e_S(r)` le maximum de points extérieurs qui peuvent être ajoutés **simultanément** après la suppression de exactement `r` points de `S`. Supprimer des points supplémentaires ne peut créer un triangle interdit, donc la convention « exactement `r` » est équivalente à « au plus `r` » après remplissage jusqu'à `r`.

Le résultat exact nouvellement établi est :

```text
e_S(7) = 5.
```

La borne inférieure est le témoin vérifié :

```text
R = {(92,51), (96,97), (7,51), (8,93), (26,40), (73,40), (77,95)}
A = {(95,98), (89,56), (75,81), (10,56), (77,99)}
|S \ R| + |A| = 162
```

`verify_radius7_witness.py` reconstruit ces 162 points depuis le notebook, contrôle les appartenances et les cardinalités, puis vérifie directement l'unicité de toutes les distances depuis chaque sommet. Il retourne :

```text
radius7_lower_bound_witness_verified=true removals=7 additions=5 final_size=162
```

La borne supérieure vient d'une CNF sans bris de symétrie demandant sept retraits et six ajouts simultanés. CaDiCaL conclut `UNSAT`, et sa preuve DRAT est acceptée par `drat-trim`.

Conséquence : toute amélioration de taille 165 doit retirer au moins huit points du record. Si `|T|=165`, alors `|T \ S|=|S \ T|+1`, donc :

```text
|S △ T| >= 8 + 9 = 17.
```

## 1. Réduction géométrique utilisée par le DFS

Pour chaque candidat extérieur `p`, le graphe `H_p` relie deux points du record `a,b` lorsque `{p,a,b}` est isocèle. Un ensemble de retraits `R` rend `p` admissible contre les points conservés si et seulement si `R` couvre toutes les arêtes de `H_p`.

Pour deux candidats `p,q`, un point du record `a` est forcé dans `R` dès que `{p,q,a}` est isocèle. Les trois possibilités sont contrôlées :

- `d(p,a)=d(q,a)` : sommet `a` ;
- `d(p,q)=d(p,a)` : sommet `p` ;
- `d(p,q)=d(q,a)` : sommet `q`.

Une sélection simultanée doit donc contenir :

1. une couverture de chaque `H_p` ;
2. tous les points du record forcés par chaque paire de candidats ;
3. aucun triple isocèle composé uniquement de candidats extérieurs.

## 2. Complétude de la famille de masques

À chaque nœud, `family` est l'antichaîne des masques d'inclusion minimaux qui satisfont toutes les contraintes de la sélection courante.

Lorsqu'un nouveau candidat `v` est ajouté, `extend_family` forme exactement :

```text
old_mask OR forced_pairs_with_v OR one_minimal_cover_of_H_v.
```

Les unions dépassant le rayon sont supprimées, puis les surensembles sont dominés.

Cette domination est sûre. Si `M` est contenu dans `M'`, toute extension monotone possible depuis `M'` est également possible depuis `M`, car les contraintes futures ne font qu'ajouter des bits par union. De même, il suffit d'énumérer les couvertures minimales : toute couverture arbitraire contient une couverture minimale.

Preuve inductive de complétude : si un ensemble global de retraits `R` réalise la sélection courante, la famille contient un masque `M ⊆ R`. Pour un nouveau candidat réalisable, une de ses couvertures minimales `C` et tous ses bits forcés `F` sont contenus dans `R`. L'extension `M OR C OR F` est donc générée et reste contenue dans `R`. Sa minimisation éventuelle ne fait que la remplacer par un sous-ensemble encore contenu dans `R`.

Contrôle automatisé : `extend_family` et `minimize_masks` ont été comparés à l'énumération brute de tous les masques sur des univers allant jusqu'à neuf sommets, pour 27 000 cas pseudo-aléatoires. Résultat :

```text
antichain_extend_property_tests=PASS cases=27000
```

## 3. Complétude du parcours DFS

Après relabellisation, le parcours énumère les sélections par indices strictement croissants.

- La boucle conserve dans `remaining` tous les candidats postérieurs non encore traités.
- Le fils reçoit `remaining AND adjacency[v]` ; par induction, ce masque est l'intersection des voisinages de tous les sommets sélectionnés.
- Continuer la boucle représente l'exclusion de `v`; descendre représente son inclusion. Chaque sous-ensemble candidat apparaît donc exactement une fois.
- Une solution globale est nécessairement une clique du graphe de compatibilité par paires. Éliminer un non-voisin ne peut donc perdre aucune solution.
- Les tests de cardinalité comparent seulement le nombre maximal de sommets encore disponibles au nombre nécessaire ; ils sont sûrs.
- L'ordre « smallest-last » est uniquement une permutation heuristique et ne modifie ni les arêtes ni les familles.

Le contrôle de délai est grossier — une fois tous les 4 096 nœuds et non toutes les extensions de famille — mais cela ne peut pas produire un faux `UNSAT`. Si le contrôle déclenche, `timed_out` se propage et le statut devient `UNKNOWN`. Sinon le programme peut seulement dépasser la durée demandée avant de terminer exactement.

## 4. Audit indépendant des candidats et du cache de paires

Le script `radius7_pair_cache_independent.py` n'importe aucun module de production du rayon 7. Il emploie :

- le générateur géométrique standard-library indépendant du premier audit ;
- l'algorithme de couvertures « prendre le sommet ou tous ses voisins » ;
- pour chaque paire de candidats et chacun des 164 points du record, le test direct des trois distances au carré.

Il a balayé les 875 826 paires et retrouve exactement, dans le même ordre, le cache SHA-256 :

```text
ceb308448dde48c205fa7ca9c8a1c9a2c382b84da993d09d1fe5dc7bf055dca1
```

Comptes indépendants :

```text
eligible_candidates=1324
minimal_covers=55528
pairs_tested=875826
compatible_pairs=11942
forced_pair_masks_nonempty=138156
forced_record_entries=167364
status=VERIFIED
```

Ainsi, aucune paire globalement réalisable n'est absente de l'adjacence utilisée par le DFS.

## 5. Triples de candidats extérieurs

Le test géométrique direct au moment d'ajouter un candidat est correct. Le filtrage anticipé retire un futur sommet seulement lorsqu'il forme un triple isocèle avec le nouveau sommet et un sommet déjà sélectionné.

Défaut mineur de télémétrie : `pruned_outside_triples` est incrémenté pour le rejet direct aux lignes 173–183, mais pas pour les retraits anticipés aux lignes 198–208. La valeur zéro affichée ne prouve donc pas, à elle seule, que ce filtrage était inutilisé.

Ce point est sans incidence sur la preuve. En remplaçant `is_isosceles` par une fonction toujours fausse — donc en autorisant tous les triples de nouveaux points — les deux relaxations restent `UNSAT` :

```text
target=8: nodes=14232, elapsed=41.753014 s, status=UNSAT
target=6: nodes=15239, elapsed=43.960801 s, status=UNSAT
```

La borne supérieure `e_S(7)<=5` découle donc déjà des couvertures individuelles et des retraits forcés par paires. Le code des triples extérieurs n'est pas nécessaire à cette conclusion.

## 6. Validation du DFS sur des frontières connues

Le même moteur reproduit les cas positifs et négatifs déjà établis :

| Rayon | Cible | Résultat | Contrôle |
|---:|---:|---|---|
| 2 | 1 | `SAT` | construction finale vérifiée géométriquement |
| 2 | 2 | `UNSAT` | conforme au maximum individuel 1 |
| 6 | 4 | `SAT` | construction finale vérifiée géométriquement |
| 6 | 5 | `UNSAT` | conforme au certificat rayon 6 |
| 7 | 5 | `SAT` | témoin de `e_S(7)>=5` |
| 7 | 6 | `UNSAT` | DFS relaxé et CNF certifiée |
| 7 | 8 | `UNSAT` | DFS initial, désormais impliqué par la ligne précédente |

## 7. Confirmation indépendante par `5`-core et no-goods triples

Toute sélection de six candidats est une clique `K_6` du graphe de compatibilité. Chacun de ses sommets conserve ses cinq voisins internes pendant l'épluchage ; toute `K_6` est donc contenue dans le `5`-core.

Le `5`-core de production a été comparé à un épluchage indépendant par file de degrés. Les comptes coïncident :

```text
core_candidates=392
core_compatible_edges=11054
one_outsider_clauses=2932
two_outsider_forced_entries=13844
```

Chaque triangle du graphe de cœur est ensuite classé. Une triple sélection est réalisable si et seulement si :

- elle n'est pas elle-même isocèle ;
- une famille minimale réalisant la première paire peut être unie aux retraits forcés des deux autres paires et à une couverture minimale du troisième candidat sans dépasser sept bits.

Le vérificateur indépendant retrouve exactement :

```text
triangles_tested=211856
triple_incompatibilities=200796
geometry_incompatible=188
removal_incompatible=200608
status=VERIFIED
```

Les clauses de no-good sont donc des conséquences nécessaires, jamais des hypothèses heuristiques.

La CNF a aussi été résolue sans les trois lex-leaders de symétrie :

```text
variables=7386
clauses=308590
symmetry_break=False
solver=glucose42
status=UNSAT
solve_seconds=12.468170
```

Les contrôles positifs du même encodage retrouvent `r=2,k=1` et `r=6,k=4` avec vérification géométrique des modèles. Le contrôle `r=6,k=5` est `UNSAT`.

## 8. CNF et certificat DRAT sans symétrie

Instance exacte :

```text
path=research/audit/radius7_core_r7_k6_nosym.cnf
bytes=4855298
variables=7386
clauses=308590
sha256=2461ee72b797a636de8154422544c2c3673e43d9c83e069f41a1c434eef26bba
```

Avant toute trace, CaDiCaL 1.9.5 a été exécuté sans preuve : `UNSAT` en 20,83 secondes, 118 244 conflits, 11 865 889 littéraux appris et 74,45 Mo de mémoire maximale.

Production bornée de la preuve :

```bash
ulimit -f 819200
timeout 180s research/audit/tools/cadical/build/cadical \
  --quiet --unsat \
  research/audit/radius7_core_r7_k6_nosym.cnf \
  research/audit/radius7_core_r7_k6_nosym.drat
```

Résultat :

```text
s UNSATISFIABLE
exit=20
proof_bytes=25282853
proof_sha256=6a845c1af080a63661599f9633910b170293502c9319688cf55829ca1ba37c3b
```

Vérification indépendante :

```bash
timeout 300s research/audit/tools/drat-trim/drat-trim \
  research/audit/radius7_core_r7_k6_nosym.cnf \
  research/audit/radius7_core_r7_k6_nosym.drat
```

Sortie exacte pertinente :

```text
c 252110 of 308590 clauses in core
c 106745 of 427108 lemmas in core using 22191309 resolution steps
c 0 RAT lemmas in core; 57610 redundant literals in core lemmas
s VERIFIED
c verification time: 26.669 seconds
exit=0
```

Aucune conversion LRAT n'a été lancée.

## 9. Reproduction

Contrôle complet des empreintes, reconstruction indépendante du cache et du cœur, puis relecture DRAT :

```bash
research/audit/verify_radius7_certificate.sh
```

Contrôle successif des certificats rayon 6 puis rayon 7, sans modifier les deux vérificateurs spécialisés :

```bash
research/audit/verify_all_certificates.sh
```

Artefacts principaux :

- `research/audit/radius7_proof_manifest.json` ;
- `research/audit/radius7_certificate_checksums.sha256` ;
- `research/audit/radius7_pair_cache_independent.py` ;
- `research/audit/radius7_core_independent.py` ;
- `research/audit/verify_radius7_witness.py` ;
- `research/audit/radius7_core_r7_k6_nosym.cnf` ;
- `research/audit/radius7_core_r7_k6_nosym.drat`.

## 10. Limites résiduelles

1. Le DRAT est vérifié par un programme C indépendant, pas encore par un noyau formel CakeML/Lean.
2. Comme pour toute preuve SAT computationnelle, le certificat porte sur la CNF ; la fidélité de la traduction géométrique est soutenue ici par deux générateurs, deux algorithmes de couvertures, un balayage direct de toutes les paires et la recomputation indépendante de tous les no-goods.
3. La nouveauté bibliographique reste à établir par recherche spécialisée et contact avec les auteurs antérieurs.
4. Le compteur `pruned_outside_triples` devrait être corrigé ou renommé avant publication, bien qu'il ne participe pas au résultat.

## Conclusion

Le DFS rayon 7 est complet. Surtout, la nouvelle CNF certifie un énoncé plus fort que la cible initiale : sept retraits ne permettent même pas six ajouts simultanés, tandis qu'un témoin en permet cinq. Le profil exact au rayon 7 vaut donc 5, et toute construction de 165 points doit être distante du record d'au moins 17 modifications.
