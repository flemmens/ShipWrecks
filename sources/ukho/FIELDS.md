# UKHO / ADMIRALTY – Wrecks and Obstructions : description des champs

Source : [ADMIRALTY Marine Data Portal – Global Wrecks](https://datahub.admiralty.co.uk/portal/apps/sites/#/marine-data-portal/items?tags=GlobalWrecks)
(94 000+ épaves et obstructions dans le monde, OGL v3, mise à jour trimestrielle).
Téléchargements : [Shapefile](https://datahub.admiralty.co.uk/portal/sharing/rest/content/items/4dbf2ace22bf4f9785fb445d0593bc2c/data) ·
[Texte](https://datahub.admiralty.co.uk/portal/sharing/rest/content/items/60c0908526b844a68494c038a457e1a7/data) ·
définitions officielles : [Wrecks Layers Definitions](https://datahub.admiralty.co.uk/portal/sharing/rest/content/items/44176cc106a948e0a4c14610bf3f9699/data),
[External Export File Format](https://datahub.admiralty.co.uk/portal/sharing/rest/content/items/1aa31582b285461f81518007eeed9963/data).

Les noms de colonnes du shapefile sont **tronqués à 10 caractères** (format DBF), d'où
`obstructio`, `original00`… Le fichier texte porte les noms complets.

Beaucoup d'attributs reprennent la norme hydrographique **IHO S‑57**, dont le code est
indiqué entre crochets, par exemple [CATWRK]. Les listes de valeurs ci‑dessous viennent
de S‑57 et des exemples observés dans les données. Elles sont **à confirmer** avec le
fichier « Wrecks Layers Definitions » de l'UKHO, qui n'a pas pu être lu ici (format Excel).

---

## 1. Identification et nature

| Champ | Description | Valeurs / exemple |
|---|---|---|
| `wreck_id` | Numéro unique de l'enregistrement dans la base UKHO. Il est stable d'une mise à jour à l'autre et sert de clé de jointure. | `1509`, `39355` |
| `wreck_cate` | Catégorie d'épave [CATWRK]. Vide pour une obstruction. | non‑dangerous wreck · dangerous wreck · distributed remains of wreck · wreck showing mast/masts · wreck showing any portion of hull or superstructure |
| `obstructio` | Catégorie d'obstruction [CATOBS]. Vide pour une épave. | foul ground · foul area · snag/stump · wellhead · diffuser · crib · fish haven · ground tackle · boom… |
| `status` | État de l'enregistrement. **live** : l'objet est toujours considéré comme présent. **dead** : il n'a pas été retrouvé lors de levés successifs et reste en base pour mémoire. (D'autres valeurs comme *lifted*, pour un objet renfloué ou enlevé, sont possibles, à confirmer.) | live · dead |
| `classifica` | Classification complémentaire de l'enregistrement (à confirmer). | souvent vide |
| `type` | Type d'objet ou de navire. | tanker · cargo · trawler · submarine · aircraft · **Fisherman's Fastener** (accroche signalée par des pêcheurs : objet non identifié) |
| `name` | Nom du navire ou de l'objet, si connu. | `EL IMAM ALI`, vide → épave non identifiée |
| `flag` | Pavillon, en code pays ISO à 2 lettres. | `GB`, `EG`, `NO` |

## 2. Position

| Champ | Description | Valeurs / exemple |
|---|---|---|
| `position` | Position complète, au format texte « degrés minutes.décimales ». | `58 18.03 N,1 44.421 W` |
| `latitude` | Latitude en **texte**, degrés et minutes décimales. Pour une carte, il faut la convertir en degrés décimaux. | `58 18.03 N` → 58.3005 |
| `longitude` | Longitude, même format. Ouest et sud donnent une valeur négative. | `1 44.421 W` → −1.74035 |
| `horizontal` | Système géodésique horizontal [HORDAT]. `WGD 2` = WGS 84. | WGD 2 |
| `limits` | Limites ou étendue de la zone, pour un objet étendu ou un champ de débris (à confirmer). | souvent vide |
| `position_m` | Méthode de positionnement [POSMTH]. Elle renseigne sur la précision : DECCA et sextant sont peu précis, DGPS précis. | DECCA navigator · GPS · DGPS · radar · sextant · Loran‑C |

## 3. Profondeur et hauteur d'eau

> **Pour un plongeur ou une carte**, `depth` est la profondeur **au‑dessus** de l'épave
> (son point le plus haut), tandis que `water_dept` est la profondeur du **fond** sur
> lequel elle repose.

| Champ | Description | Valeurs / exemple |
|---|---|---|
| `depth` | Profondeur minimale au‑dessus de l'objet, en mètres, mesurée depuis le zéro vertical (`vertical_d`) [VALSOU]. | `12.4` |
| `height` | Hauteur de l'objet au‑dessus du fond, en mètres (à confirmer). | |
| `depth_meth` | Technique de sondage [TECSOU]. | found by echo‑sounder · side scan sonar · multibeam · found by diver · swept by wire‑drag · lead line · found by laser |
| `depth_qual` | Qualité de la profondeur [QUASOU]. | depth known · **depth unknown** · doubtful sounding · unreliable sounding · least depth known · least depth unknown, safe clearance at value shown · value reported (not surveyed) · value reported (not confirmed) |
| `depth_accu` | Précision de la profondeur, en mètres. | |
| `water_dept` | Profondeur d'eau générale autour de l'objet, en mètres : le fond marin. | `90`, `40`, `3` |
| `water_leve` | Effet du niveau de l'eau [WATLEV]. | always under water/submerged · covers and uncovers · awash · partly submerged at high water · always dry · floating |
| `vertical_d` | Zéro de référence des profondeurs [VERDAT]. | Lowest Astronomical Tide · Approximate Lowest Astronomical Tide · Mean Lower Low Water Springs · Chart Datum |
| `reported_y` | Année du signalement (à confirmer). | |

## 4. Caractéristiques du navire et de l'épave

| Champ | Description | Unité / exemple |
|---|---|---|
| `length` | Longueur du navire. | m · `79.2` |
| `width` | Largeur (maître‑bau). | m · `10.4` |
| `draught` | Tirant d'eau. | m · `5.5` |
| `tonnage` | Tonnage. | `1532` |
| `tonnage_ty` | Type de tonnage. | gross · net · deadweight · displacement |
| `cargo` | Cargaison au moment de la perte. | ballast · coal · general… |
| `sonar_leng` | Longueur de l'épave mesurée au sonar. | m |
| `sonar_widt` | Largeur de l'épave mesurée au sonar. | m |
| `shadow_hei` | Hauteur de l'épave déduite de l'ombre acoustique du sonar. | m |
| `orientatio` | Orientation de l'axe de l'épave. | degrés |
| `bottom_tex` | Nature du fond. | sand · mud · rock · gravel |
| `scour_dime` | Dimensions de l'affouillement (creux d'érosion) autour de l'épave. | |
| `debris_fie` | Description ou étendue du champ de débris. | |
| `non_sub_co` | « Non‑submarine contact » : contact sonar classé comme n'étant pas un sous‑marin (terme naval, à confirmer). | |

## 5. Visibilité et balisage

| Champ | Description | Valeurs |
|---|---|---|
| `conspic_vi` | Visibilité de jour [CONVIS]. | visually conspicuous · not visually conspicuous |
| `conspic_ra` | Visibilité au radar [CONRAD]. | radar conspicuous · not radar conspicuous |
| `markers` | Balisage de l'épave : bouées, feux. | |

## 6. Historique de la perte et des détections

| Champ | Description | Valeurs / exemple |
|---|---|---|
| `date_sunk` | Date du naufrage, au format `AAAAMMJJ` (parfois partielle). | `19820226` |
| `circumstan` | Circonstances de la perte : construction, armateur, cause du naufrage… (texte libre). | « BUILT IN 1928 BY W DOXFORD & SONS… » |
| `original_s` | Capteur de la première détection. | Reported Sinking · side scan sonar · echo‑sounder · video sensor · None reported |
| `last_senso` | Capteur de la dernière détection. | idem |
| `original_d` | Année de la première détection ou du premier signalement. | `1966` |
| `last_detec` | Année de la dernière détection ou vérification. | `2019` |
| `original00` | Source d'origine de l'information (nom tronqué de *original source*). | national HO/authority charts · Lloyd's and Marine Underwriter's reports · ship visit/hydrographic note report |
| `surveying_` | Historique des levés : références `H…`, dates, observations (texte libre). | « H2526/83. 14.4.83. STILL AGROUND… » |
| `general_co` | Commentaires généraux. | `UK NM 5003/21` (Notice to Mariners) · `Mast` |
| `last_amend` | Date de dernière modification de l'enregistrement, au format `AAAAMMJJ`. | `20231004` |

---

## Correspondance avec le CSV synthétique du projet

| CSV ShipWrecks | Champ UKHO | Transformation |
|---|---|---|
| `id` | `wreck_id` | préfixe `UKHO-` |
| `name` | `name` | vide → « Unnamed wreck » |
| `flag` | `flag` | code ISO 2 lettres → nom du pays |
| `date` | `date_sunk` | `AAAAMMJJ` → `AAAA-MM-JJ` (ou partiel) |
| `latitude`, `longitude` | `latitude`, `longitude` | « DD MM.mmm H » → degrés décimaux |
| `depth_m` | `water_dept` (fond) ; `depth` = sommet de l'épave | à garder dans deux colonnes distinctes |
| `note` | `circumstan` (+ `type`, `cargo`) | |
| statut | `status`, `wreck_cate` / `obstructio` | filtrer `dead` et les obstructions selon l'usage |

**Points d'attention**

- **Obstructions.** Les lignes avec `obstructio` renseigné et `wreck_cate` vide ne sont pas des épaves : *foul ground*, accroches de pêcheurs… Elles représentent l'écart entre les 94 000 enregistrements UKHO et les 67 000 republiés par EMODnet.
- **Enregistrements « dead ».** Ils ne sont plus détectés, donc leur position est incertaine. À exclure de la carte, ou à afficher à part.
- **Positions.** Leur précision dépend de `position_m` : une position DECCA peut être fausse de plusieurs centaines de mètres.
- **Valeurs vides.** Elles sont codées `NULL` ou `n/a` selon le format d'export.
