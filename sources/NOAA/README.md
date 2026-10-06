# Source : NOAA – ENC Direct to GIS

Script `noaa_enc_wrecks.py` : récupère les épaves, obstructions et coques (hulks)
**à jour** dans les cartes marines électroniques (ENC) de la NOAA, via le service ArcGIS
[ENC Direct to GIS](https://encdirect.noaa.gov/arcgis/rest/services/encdirect).

L'ancienne base AWOIS n'est plus mise à jour, et sa copie MarineCadastre est figée depuis 2024.
Ce service, lui, reflète l'état actuel des cartes.

## Utilisation

```bash
pip install requests
python noaa_enc_wrecks.py                         # tout : épaves + obstructions + coques
python noaa_enc_wrecks.py --no-obstructions       # épaves et coques seulement
python noaa_enc_wrecks.py --bands harbour coastal # certaines bandes d'échelle
python noaa_enc_wrecks.py --refresh               # ignorer le cache data/raw/
```

## Fonctionnement

1. Pour chaque bande d'échelle (`berthing`, `harbour`, `approach`, `coastal`, `general`,
   `overview`), le script repère les couches `Wreck_*`, `Obstruction_*` et `Hulk_*`
   (point, ligne, surface).
2. Il télécharge tous les objets par lots de 500 (requêtes `objectIds`, en WGS 84)
   et les met en cache dans `data/raw/`.
3. Un même objet figure souvent dans plusieurs bandes. Le script garde la version de
   la bande la plus détaillée et fusionne les objets de même type situés à moins de
   100 m (`--merge-m`).
4. Il décode les codes S‑57 en libellés lisibles : CATWRK, CATOBS, WATLEV, QUASOU,
   TECSOU, EXPSOU, VERDAT.

## Sorties (`data/`)

| Fichier | Contenu |
|---|---|
| `noaa_wrecks.csv` | Un objet par ligne, au format du projet (point ou centroïde) |
| `noaa_wrecks.geojson` | Mêmes objets, avec leur géométrie complète (lignes et surfaces) |
| `raw/<bande>__<couche>.geojson` | Données brutes par couche |

| Colonne | Source S‑57 | Description |
|---|---|---|
| `id` | – | `NOAA-` suivi d'un hash du type, de la position arrondie et du nom (stable d'une exécution à l'autre) |
| `name` | OBJNAM | Nom du navire ou de l'objet |
| `latitude`, `longitude` | géométrie | WGS 84. Centroïde pour les lignes et les surfaces |
| `depth_m` | VALSOU | Profondeur minimale au‑dessus de l'objet (m) |
| `note` | INFORM | Information complémentaire |
| `kind` | couche | `wreck`, `obstruction`, `hulk` |
| `category` | CATWRK / CATOBS | Ex. *dangerous wreck*, *foul ground* |
| `water_level` | WATLEV | Ex. *always under water/submerged* |
| `depth_quality`, `depth_technique`, `depth_exposition` | QUASOU, TECSOU, EXPSOU | Qualité et méthode de la sonde |
| `vertical_datum` | VERDAT | Zéro de référence de la profondeur |
| `source_date`, `source_ind` | SORDAT, SORIND | Date et référence de la source |
| `enc_cell` | DSNM | Cellule ENC d'origine |
| `bands` | – | Bandes d'échelle où l'objet apparaît |

## Limites

- Les ENC ne donnent **ni date de naufrage ni pavillon**. Pour ces informations, il faut
  rapprocher les objets d'AWOIS/MarineCadastre (champ `yearsunk`, `history`) ou de Wikipedia.
- La couverture se limite aux eaux américaines (y compris l'Alaska, Hawaï, Porto Rico et
  les territoires du Pacifique).
- Le serveur limite chaque requête à 1 000 objets. Le script respecte une pause de
  0,3 s entre les requêtes (`--delay`).
- Licence : données du gouvernement fédéral américain (domaine public). Elles ne
  doivent pas servir à la navigation.
