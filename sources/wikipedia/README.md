# Source : Wikipedia

Script `wikipedia_wrecks.py` : extraction des épaves depuis
[Lists of shipwrecks](https://en.wikipedia.org/wiki/Lists_of_shipwrecks) (Wikipedia en).

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env   # puis renseigner les identifiants R2
```

## Étape 1 – liste synthétique (`data/wrecks.csv`)

```bash
python wikipedia_wrecks.py lists
python wikipedia_wrecks.py lists --max-pages 5   # test rapide
```

Le script part de *Lists of shipwrecks* et suit récursivement toutes les pages
« List(s) of shipwrecks … » : par année, par mois (1820‑1889, 1914‑1918, 1939‑1945)
et par région (Europe, Afrique…). Comptez environ 1 500 pages. Elles sont mises en cache
dans `cache/lists/`, donc une relance est quasi instantanée (`--refresh` pour forcer
le rechargement).

| Colonne | Contenu |
|---|---|
| `id` | Identifiant stable `WPW-xxxxxxxxxxxx` (hash de l'article + année, sinon nom + date + pavillon) |
| `name` | Nom du navire |
| `flag` | Pavillon / État / marine |
| `date` | Date ISO partielle (`1942-06-01`, `1942-06`, `1700`, `-0300` pour 300 av. J.‑C.) |
| `latitude`, `longitude` | Coordonnées décimales (WGS84) quand elles sont connues |
| `depth_m` | Profondeur en mètres quand elle est mentionnée (« in 85 feet of water », « at a depth of 60 m »…) |
| `note` | Description issue de la liste |
| `wikipedia_url` | Article de l'épave, s'il existe |
| `date_raw` | Date telle qu'écrite dans la source |
| `depth_source`, `coord_source` | `list` ou `article` |
| `source_lists` | Pages de liste où l'épave apparaît (séparées par ` \| `) |

Une épave présente dans plusieurs listes (par exemple chronologique et géographique)
est dédoublonnée, et ses informations sont fusionnées.

## Étape 2 – articles, textes et images → Cloudflare R2

```bash
python wikipedia_wrecks.py articles                     # envoi dans R2
python wikipedia_wrecks.py articles --limit 20 --storage local   # test en local (./export)
```

Pour chaque épave qui a un article, le script écrit dans le bucket :

```
wrecks/<id>/article.txt      texte brut de l'article
wrecks/<id>/article.html     HTML rendu
wrecks/<id>/metadata.json    titre, URL, révision, coordonnées, profondeur, images + licences/auteurs
wrecks/<id>/images/NN_<nom>.jpg
```

Les drapeaux, icônes, logos et SVG sont ignorés. Les images sont téléchargées en
1600 px de large au maximum (`--image-width`), avec 20 images au plus par article (`--max-images`).
La reprise est automatique grâce à `cache/articles_state.jsonl` (`--force` pour tout
retraiter). À la fin, les coordonnées et profondeurs manquantes dans le CSV sont
complétées à partir des articles.

Autres options : `--workers 4`, `--delay 0.2` (délai minimal entre requêtes), `--no-images`.

## Licences

Les textes Wikipedia sont publiés sous licence CC BY‑SA 4.0. Les licences des images varient :
l'auteur et la licence de chaque image sont conservés dans `metadata.json` et doivent
être affichés lors de toute réutilisation.

## Limites

- La profondeur est extraite du texte par expressions régulières. Elle n'est
  disponible que pour une minorité d'épaves et doit être vérifiée.
- La structure des tableaux varie d'une liste à l'autre. Les colonnes sont détectées
  d'après leurs en‑têtes (Ship/Name, Flag/State/Country, Date, Description/Notes,
  Coordinates). La date vient de la colonne Date si elle existe, sinon du titre de la
  section ou du tableau, sinon du titre de la page.
