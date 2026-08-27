# Audit indépendant du résultat local au rayon 6

Date : 27 août 2026  
Périmètre : réduction mathématique, géométrie discrète, filtrage des candidats, encodages SAT et certificat d'insatisfaisabilité  
Verdict : **aucune faille trouvée ; résultat confirmé par une chaîne indépendante et par un certificat DRAT vérifié**

## Verdict scientifique

Pour la construction publique `S` de 164 points, le maximum exact du nombre de points extérieurs rendus **individuellement** admissibles après exactement six suppressions est 4.

La borne inférieure est donnée par le témoin :

```text
R = {(26,59), (7,48), (73,59), (92,48), (96,2), (3,2)}
U(R) = {(4,1), (10,43), (89,43), (95,1)}
```

Le générateur géométrique indépendant confirme directement que ce témoin ouvre exactement ces quatre points. La borne supérieure est l'insatisfaisabilité de l'instance « six retraits et au moins cinq points individuellement admissibles ».

## Justification mathématique

Pour chaque point extérieur `p`, soit `H_p` le graphe dont les sommets sont les points de `S` et dont une arête `{a,b}` signifie que `{p,a,b}` est isocèle. Comme `S` est déjà valide, `p` devient admissible dans `S \ R` si et seulement si `R` rencontre chaque arête de `H_p`, c'est-à-dire si `R` est une couverture par sommets de `H_p`.

L'instance SAT utilise :

- une variable `x_a` par point du record, vraie quand `a` est retiré ;
- une variable `y_p` par candidat retenu, vraie quand on demande que `p` soit admissible ;
- `sum(x_a) = 6` ;
- `sum(y_p) >= 5` ;
- pour toute arête `{a,b}` de `H_p`, la clause `not y_p or x_a or x_b`.

Ces contraintes sont satisfaisables si et seulement s'il existe six retraits qui ouvrent au moins cinq candidats. Une valuation SAT fournit directement un tel ensemble. Réciproquement, cinq candidats réellement ouverts permettent de mettre leurs cinq variables `y_p` à vrai.

Si `T` est une construction valide quelconque, avec `R = S \ T` et `A = T \ S`, chaque `p` de `A` appartient nécessairement à `U(R)`. Les incompatibilités possibles entre nouveaux points ne fragilisent donc pas la borne : `|A| <= |U(R)|` est une borne supérieure sûre.

## Audit du code existant

### Géométrie

Le masque de `research/solve_removal_radius_cpsat.py` couvre exactement les trois égalités possibles entre les distances au carré de `{p,a,b}`. Les coordonnées sont dans `[0,99]`, donc la valeur maximale `19 602` reste très loin de tout débordement `int32`. Les indices convertis en `int16` sont dans `[0,163]`.

### Énumération des couvertures

La récursion existante choisit une arête et explore ses deux extrémités. C'est exhaustif puisque toute couverture d'une arête contient au moins une de ses extrémités. La taille d'un matching glouton est employée seulement comme borne inférieure ; cette coupure est sûre. La minimisation finale ne peut créer ni faux positif ni perte d'une couverture minimale.

### Encodages SAT

- L'encodage `edge` impose `y_p ->` couverture de chaque arête. L'implication inverse n'est pas nécessaire pour la décision `sum(y) >= target`.
- L'encodage `dnf` rend chaque variable de couverture équivalente à la conjonction de ses retraits, puis `y_p` équivalente à la disjonction des couvertures.
- Le bris de symétrie optionnel est valide : le record est invariant par les deux réflexions axiales et la rotation de 180 degrés. Le résultat `UNSAT` principal existe aussi sans bris de symétrie.

Risque identifié : les deux encodages initiaux partageaient le même générateur de conflits et le même préfiltre `enumerate_minimal_covers`. Ce n'était donc pas deux chaînes de preuve indépendantes. Le nouvel audit élimine ce point commun.

## Générateur indépendant

`independent_cnf.py` n'importe aucun module de recherche existant, NumPy, OR-Tools ou PySAT. Il :

1. extrait `sol_100` par analyse AST du notebook public ;
2. valide les 164 points en contrôlant l'unicité des distances depuis chaque sommet ;
3. reconstruit les conflits par anneaux autour des sommets, et non par le balayage NumPy des paires ;
4. emploie, pour le contrôle des comptes, la dichotomie indépendante « prendre `v` ou prendre tous ses voisins » ;
5. encode les cardinalités avec une récurrence booléenne écrite localement et testée exhaustivement sur tous les petits cas jusqu'à huit variables.

Résultats reproduits indépendamment :

```text
record_size=164
outside_candidates=9836
conflict_edges=154440
candidates_with_covers_at_radius_6=692
minimal_covers=16048
covers_by_size={2:24, 3:212, 4:656, 5:2932, 6:12224}
```

Une première CNF indépendante fondée sur ces 692 candidats conclut `UNSAT` avec Glucose 4.2 en 138,551 secondes : 5 433 variables et 23 355 clauses.

Les rayons inférieurs ont aussi été recroisés avec ce générateur :

| Rayon | Cible impossible | Candidats retenus | Résultat | Temps solveur |
|---:|---:|---:|---|---:|
| 2 | 2 | 16 | `UNSAT` | 0,001934 s |
| 3 | 2 | 56 | `UNSAT` | 0,058607 s |
| 4 | 3 | 128 | `UNSAT` | 1,192248 s |
| 5 | 4 | 316 | `UNSAT` | 12,709264 s |
| 6 | 5 | 692 | `UNSAT` | 138,551 s |

## Préfiltre certifiable par matchings

Pour réduire la confiance à placer dans l'énumération de couvertures, une seconde instance indépendante n'écarte un candidat que si elle produit sept arêtes de conflit deux à deux disjointes. Six sommets ne peuvent pas rencontrer sept arêtes disjointes ; le candidat est donc incontestablement impossible au rayon 6.

- 9 099 candidats possèdent ce témoin élémentaire ;
- leurs 63 693 arêtes sont consignées dans `r6_matching_witnesses.json` ;
- `verify_matching_certificate.py` vérifie indépendamment les coordonnées, chaque égalité isocèle et la disjonction des 14 extrémités ;
- les 737 autres candidats sont tous conservés dans la CNF, y compris 45 qui sont en réalité impossibles ;
- l'instance contient 5 703 variables et 24 775 clauses.

Sortie du vérificateur :

```text
verified=true matching_witnesses=9099 remaining_candidates=737 matching_size=7
```

Cette instance conclut également `UNSAT` avec Glucose 4.2 en 162,663 secondes avant la production de la preuve archivable.

## Certificat DRAT archivable

Instance :

```text
research/audit/r6_t5_matching.cnf
381497 octets
SHA-256 f72229bacc773b19bf78209134cc666496854e60d1a515b4809ae2deeca23651
```

Génération, avec CaDiCaL 1.9.5 au commit `146207318796f094dcded87349a64f0c6927309e` :

```bash
ulimit -f 921600
timeout 300s research/audit/tools/cadical/build/cadical \
  --quiet --unsat \
  research/audit/r6_t5_matching.cnf \
  research/audit/r6_t5_matching.drat
```

Résultat exact :

```text
s UNSATISFIABLE
exit=20
proof_bytes=291778586
proof_sha256=149d3592fe5a2d6afccc05905b45ddc638947d537df6bc99865b9d190b20be9a
```

Vérification indépendante avec `drat-trim` au commit `2e3b2dc0ecf938addbd779d42877b6ed69d9a985` :

```bash
timeout 300s research/audit/tools/drat-trim/drat-trim \
  research/audit/r6_t5_matching.cnf \
  research/audit/r6_t5_matching.drat
```

Sortie exacte pertinente :

```text
c 20177 of 24775 clauses in core
c 464404 of 1002419 lemmas in core using 275153070 resolution steps
c 0 RAT lemmas in core; 834501 redundant literals in core lemmas
s VERIFIED
c verification time: 228.846 seconds
exit=0
```

Le fichier DRAT est donc une preuve d'insatisfaisabilité archivable et rejouable, pas un simple journal de solveur.

## Pourquoi LRAT n'a pas été généré ici

`cake_lpr`, vérificateur LRAT/LPR produit avec CakeML, a été compilé au commit `a36874a8b750b43fe4b385b8ddbf5b033e46a3fa`. Les deux chaînes suivantes ont passé une micro-instance :

```bash
cadical tiny_unsat.cnf tiny_direct.lrat --lrat
cake_lpr tiny_unsat.cnf tiny_direct.lrat

cadical tiny_unsat.cnf tiny.drat
drat-trim tiny_unsat.cnf tiny.drat -L tiny_converted.lrat
cake_lpr tiny_unsat.cnf tiny_converted.lrat
```

Dans les deux cas, `cake_lpr` affiche exactement `s VERIFIED UNSAT`.

La preuve réelle emploie 275 153 070 étapes de résolution. En LRAT binaire, la majorité des identifiants proches du million requiert trois octets, soit environ 825 Mo pour les seuls indices, avant clauses et suppressions. Une projection prudente est de 0,8 à 1,2 Go. Avec seulement 1,7 Go libres et le DRAT de 292 Mo déjà présent, la conversion n'a volontairement pas été lancée.

Sur une machine disposant d'au moins 5 Go de stockage temporaire :

```bash
research/audit/tools/drat-trim/drat-trim \
  research/audit/r6_t5_matching.cnf \
  research/audit/r6_t5_matching.drat \
  -C -L research/audit/r6_t5_matching.lrat

research/audit/tools/cake_lpr/cake_lpr \
  --CML_HEAP_SIZE=8000 --CML_STACK_SIZE=2000 \
  research/audit/r6_t5_matching.cnf \
  research/audit/r6_t5_matching.lrat
```

La publication doit exiger la ligne exacte `s VERIFIED UNSAT`, car le code de retour seul de certains emballages de vérificateurs ne suffit pas.

## Relecture en une commande

Depuis la racine du dossier :

```bash
research/audit/verify_certificate.sh
```

Le script contrôle tous les SHA-256, les 9 099 témoins de matching, le certificat DRAT et la présence exacte de `s VERIFIED`.

## Risques résiduels avant publication

1. **Nouveauté bibliographique** : cet audit ne démontre pas la priorité académique.
2. **Confiance dans la traduction géométrie-CNF** : fortement réduite par deux générateurs géométriques, deux algorithmes de couverture, les témoins élémentaires et les tests de cardinalité, mais une preuve SAT certifie la CNF, pas automatiquement le code qui l'a générée.
3. **Vérification formelle** : le DRAT est validé par un vérificateur C indépendant. Pour la couche de confiance maximale, convertir sur une machine mieux dotée et obtenir `cake_lpr: s VERIFIED UNSAT`.
4. **Provenance** : archiver ensemble le notebook, son commit, le record canonique, les sources, la CNF, les témoins, le DRAT, ce rapport et `proof_manifest.json` ; publier leurs empreintes dans l'article.

## Conclusion

Le résultat local au rayon 6 est mathématiquement bien réduit, logiciellement recroisé et désormais accompagné d'un certificat indépendant vérifié. Le niveau de confiance est suffisant pour rédiger une note scientifique sérieuse, sous réserve d'une recherche de priorité, d'une relecture humaine externe et, idéalement, de la dernière conversion LRAT/CakeML hors de cette machine contrainte en disque.
