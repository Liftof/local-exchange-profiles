# Audit indépendant du solveur C++ au rayon 8

Date de l'audit : 27 août 2026. Configuration auditée : le jeu public
`S_100` de 164 points, dans la grille `100 x 100`.

## Verdict

**Aucune faille de correction n'a été trouvée dans le calcul archivé.** Les
entrées critiques ont été régénérées par une chaîne standard-library
indépendante, les 2 071 630 paires ont été revérifiées, les principaux
algorithmes de pruning ont été relus et testés, et les exécutions ont été
reproduites depuis une nouvelle compilation.

Les éléments présents soutiennent le résultat expérimental exact

```text
e_{S_100}(8) = 6.
```

En effet :

- un échange `8 retraits -> 6 ajouts` est vérifié directement en géométrie
  entière ;
- la recherche `8 retraits -> 7 ajouts` retourne `UNSAT` ;
- plus fortement, elle retourne encore `UNSAT` après suppression de toutes les
  contraintes portant sur les triangles formés de trois outsiders et après
  désactivation du pruning par coloration. Cette dernière exécution explore
  un sur-ensemble nécessaire du vrai problème : son `UNSAT` implique donc
  l'absence de tout échange réel à sept ajouts.

Il s'agit d'un **calcul exhaustif reproductible et audité**, pas d'un certificat
statique portable : aucun DRAT/LRAT ni aucune preuve vérifiée par assistant de
preuve n'est produit par cette DFS.

## Réduction auditée

Pour chaque point extérieur `p`, les paires de points du record qui forment un
triangle isocèle avec `p` constituent un graphe de conflits `H_p`. Rendre `p`
admissible exige que les retraits contiennent une couverture de sommets de
`H_p`. Pour chaque paire d'outsiders `(p,q)`, tous les points du record formant
un triangle isocèle avec cette paire sont également forcés au retrait.

Pour un ensemble déjà sélectionné `A`, le solveur conserve l'antichaîne des
masques de retraits minimaux qui réalisent `A`. Lors de l'ajout de `p`, il
calcule exactement

```text
min_subset {
  old OR forced(p,A) OR cover
  : old dans M(A), cover couverture minimale de H_p,
    popcount(old OR forced(p,A) OR cover) <= r
}.
```

Éliminer un sur-ensemble d'un masque conservé est sûr : toute contrainte
ultérieure est monotone par ajout de retraits. Tout ensemble réalisable induit
en outre une clique dans le graphe de compatibilité par paires. La DFS énumère
canoniquement les sommets dans l'ordre relabellisé ; après le choix d'un sommet,
elle ne conserve que ses voisins encore ultérieurs. Chaque clique cible est
donc examinée une fois.

## Audit du code

### Binaire RPC1 et masques

- L'en-tête little-endian, les 2 036 coordonnées, les familles de couvertures
  et les 331 300 entrées forcées sont lus sans décalage ; aucune donnée finale
  n'est ignorée.
- Les retraits sont représentés par trois mots de 64 bits, donc 192 bits pour
  164 sommets. Les opérations `OR`, `popcount` et inclusion sont correctes mot
  par mot.
- Le checker indépendant impose que les 28 bits inutilisés soient nuls, que
  les familles et les clés forcées ne contiennent aucun doublon et que les
  indices restent dans `0..163`. L'entrée archivée passe tous ces contrôles.
- Le solveur C++ lui-même ne rejette pas explicitement un bit inutilisé dans un
  masque et `unordered_map::emplace` ignorerait silencieusement une seconde
  entrée forcée de même clé. Ce sont des durcissements recommandés du parseur,
  mais ils n'affectent pas l'entrée archivée, validée indépendamment et figée
  par SHA-256.

### Couvertures, masques forcés et cache de paires

Le programme `radius8_cpp_inputs_independent.py` n'importe aucun module de la
chaîne de production rayon 8. Il s'appuie sur la géométrie standard-library et
l'énumérateur alternatif `v-ou-tous-ses-voisins` de `independent_cnf.py`.

Contrôle exhaustif obtenu en 273,217 s avec six workers :

| Élément | Résultat indépendant |
|---|---:|
| candidats admissibles | 2 036 |
| couvertures minimales | 150 848 |
| masques forcés non vides | 331 300 |
| incidences de sommets forcés | 397 808 |
| paires testées | 2 071 630 |
| paires compatibles | 35 950 |
| divergences | 0 |

Chaque masque forcé a été recalculé directement en testant les trois égalités
possibles entre les longueurs au carré du triangle. Chaque paire a ensuite été
réévaluée à partir de la définition : existence de deux couvertures dont
l'union avec le masque forcé contient au plus huit sommets. Cette vérification
écarte le principal risque de faux `UNSAT`, à savoir une paire compatible omise
du cache.

### Relabellisation, graphe et coloration

- `degeneracy_order` renvoie une permutation complète ; `old_to_new` transpose
  chaque arête dans les deux sens.
- `Candidate::old_index` survit au déplacement et permet de retrouver la bonne
  clé du masque forcé après relabellisation.
- Le graphe est symétrique et les doublons du JSON sont rejetés.
- La coloration gloutonne partitionne les sommets possibles en ensembles
  indépendants. Le nombre de couleurs est donc une borne supérieure valide de
  la taille d'une clique.
- Un harness sous ASan/UBSan a comparé cette borne au nombre de clique exact sur
  1 400 graphes aléatoires de 1 à 14 sommets ; aucune sous-estimation n'a été
  observée.
- Le résultat décisif `r=8,k=7` a aussi été reproduit avec la coloration
  entièrement désactivée. La conclusion ne dépend donc pas de ce pruning.

### Récurrence d'antichaîne

Les deux branches optimisées de `extend_family` sont sûres :

- si un masque partiel a déjà huit bits, seule une couverture incluse dans ce
  masque peut survivre et le masque reste inchangé ;
- sinon, toutes les unions dans le budget sont produites, triées par cardinalité
  puis minimisées par inclusion.

Un harness sous ASan/UBSan a comparé la fonction C++ à l'énumération brute sur
5 000 instances aléatoires de masques utilisant jusqu'aux 164 bits. Résultat :
`VERIFIED`, aucune divergence ni erreur de sanitizer.

### Triangles d'outsiders

La version exacte pré-calcule, pour chaque arête compatible, les troisièmes
outsiders formant un triangle isocèle avec arithmétique entière 64 bits. La DFS
teste les triples déjà constitués et filtre les candidats futurs.

Le compteur `pruned_outside_triples=0` ne compte pas les suppressions réalisées
par le filtre anticipé ; il ne suffirait donc pas, seul, à prouver que ce code
est sans effet. En revanche, la compilation
`R8CPP_RELAX_OUTSIDE_TRIPLES + R8CPP_NO_COLOR_PRUNING` supprime effectivement
les deux usages du filtre. Son `UNSAT` rend toute erreur éventuelle dans ce
module non pertinente pour la borne supérieure finale.

### Timeout et statut

`SAT` n'est émis qu'après conservation d'une famille non vide de retraits ;
`UNSAT` n'est émis que si la DFS s'épuise sans que le drapeau de timeout soit
levé ; sinon le statut est `UNKNOWN`. Une sonde avec une limite de 0,001 s a
retourné `UNKNOWN`, `exit=0`, et zéro extension.

Le prétraitement des triples n'est pas interruptible et peut donc dépasser une
très petite limite murale avant le premier contrôle. Il s'agit d'une limite
opérationnelle, pas d'une faille de correction. Les exécutions utilisées pour
la conclusion se sont terminées normalement avec `exit=20`, très avant leur
limite de 160 s.

## Reproductions

Compilation : `g++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0`, `x86_64`, options
`-O3 -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic`. Aucun warning.

| Instance | Variante | Statut | Nœuds | Extensions |
|---|---|---:|---:|---:|
| `r=7,k=5` | exacte + coloration | SAT | 4 507 | 423 940 |
| `r=7,k=6` | exacte + coloration | UNSAT | 11 817 | 996 023 |
| `r=7,k=6` | sans triples, sans coloration | UNSAT | 15 239 | 1 016 576 |
| `r=8,k=6` | exacte + coloration | SAT | 21 139 | 3 900 970 |
| `r=8,k=7` | exacte + coloration | UNSAT | 63 206 | 9 883 499 |
| `r=8,k=7` | sans triples, sans coloration | UNSAT | 78 031 | 10 009 190 |
| `r=8,k=9` | exacte + coloration | UNSAT | 59 660 | 9 628 112 |
| `r=8,k=9` | sans triples, sans coloration | UNSAT | 73 398 | 9 855 657 |

Les compteurs `r=7,k=6` sans triples et sans coloration coïncident exactement
avec la DFS Python antérieure : 15 239 nœuds, 1 016 576 extensions, 475 616
masques produits, 24 208 prunings de cardinalité et 992 361 prunings de
retraits. Cette égalité fournit un recoupement particulièrement fort entre les
deux implémentations.

Le témoin `r=7,k=5` reproduit a passé une vérification cubique directe. Le
témoin indépendant `r=8,k=6` a été reconstruit depuis le record et vérifié par
`independent_cnf.validate_record` : huit retraits, six ajouts, 162 points et
aucun triangle isocèle.

## Commandes principales

```bash
# Validation indépendante complète de l'entrée et du cache
research/.venv/bin/python research/audit/radius8_cpp_inputs_independent.py \
  research/radius7_pair_input_n100_r8.bin \
  research/radius7_paircompat_n100_r8.json \
  --workers 6 --rows-per-task 8 \
  --output research/radius8_cpp_input_audit.json

# Variante décisive : relaxation sans triples d'outsiders ni coloration
g++ -O3 -DNDEBUG -DR8CPP_RELAX_OUTSIDE_TRIPLES \
  -DR8CPP_NO_COLOR_PRUNING -std=c++20 \
  research/radius8_cpp_antichain_dfs.cpp -o /tmp/r8-relaxed
/tmp/r8-relaxed research/radius7_pair_input_n100_r8.bin \
  research/radius7_paircompat_n100_r8.json 7 160 \
  /tmp/r8-k7-relaxed.json

# Tests aléatoires + sanitizers
g++ -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -std=c++20 research/audit/radius8_cpp_unit_harness.cpp \
  -o /tmp/r8-unit
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 \
  UBSAN_OPTIONS=halt_on_error=1 /tmp/r8-unit

# Témoin positif indépendant
research/.venv/bin/python research/audit/verify_exchange_witness.py \
  research/radius8_exchange_n100_r8_k6_witness.txt
```

## Empreintes figées

```text
3829813c9faef533fc13c97c0a48323e6a686fa9802250b5aa6ba8b5102900d6  research/radius8_cpp_antichain_dfs.cpp
31d4606f6f878ce6ddf4fc9cb48fbaeecd4380b11b478c456ec5ea2e040f295e  research/radius7_pair_input_n100_r8.bin
30e257b34af3a05a193023e3005fd46a933794fcd4ce429812b540724fe784d7  research/radius7_paircompat_n100_r8.json
4264586e20211a9b88c628e6192897dde035f770d1124dabdb8829e0e3ec3e92  research/audit/radius8_cpp_inputs_independent.py
b06a8eabb366fde4b60f12e88d9a27c636e4dd24523821af0ab09f0ccfde9340  research/radius8_cpp_input_audit.json
17a51584d6cde095f1aa70230c18e8e222fee2bb50be5aba5c44c1e14f076a9f  research/audit/radius8_cpp_unit_harness.cpp
9bacb1e56856425a99acfe50bd4c7747b475515de805a788c68b537bed91deb8  research/radius8_exchange_n100_r8_k6_witness.txt
ff5bb9771663ea239e7dfa6c6f6b0e8c1a4697d6d135e850e77b85467968fbab  research/radius8_cpp_n100_r8_k7_relaxed_nocolor.json
```

## Limites et formulation publiable

- Le résultat est local au record fixé `S_100`. Il ne prouve ni l'optimalité
  globale de 164 points ni une borne générale pour toutes les configurations.
- La borne `e_{S_100}(8)=6` est une recherche exhaustive machine-checkable,
  auditée par une seconde génération des données. Elle ne dispose pas encore
  d'un certificat UNSAT portable vérifiable par un petit checker de preuve.
- Pour une publication, la formulation prudente est : « exhaustive search,
  independently regenerated inputs and cross-checked implementation ». Éviter
  « formally verified » ou « proof certificate » tant qu'aucune trace
  DRAT/LRAT ou formalisation équivalente n'existe.
- Un lecteur externe doit pouvoir reconstruire l'environnement, rejouer le
  checker d'entrée, recompiler le solveur depuis l'empreinte annoncée et
  reproduire la variante relaxée avant que le calcul soit traité comme figé.
