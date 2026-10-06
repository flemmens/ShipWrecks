# ShipWrecks
List and map of ship wrecks

## Sources de données

Recensement des sites qui répertorient les épaves de navires et d'autres objets sous-marins (avions, munitions, obstructions).
★ = source prioritaire (coordonnées + téléchargement libre). « ? » = volume inconnu ou non vérifié.

### Bases mondiales

| Source | Contenu | Volume | Accès / licence |
|---|---|---|---|
| ★ [EMODnet – Worldwide wrecks (UKHO)](https://emodnet.ec.europa.eu/geonetwork/srv/api/records/108ef240-fa6e-4b83-8569-09b509e2959d) | Épaves cartographiées ou non, dans le monde entier : position, profondeur, longueur, largeur, tonnage, circonstances du naufrage | 67 000+ (fiche) à 94 000+ ([annonce](https://emodnet.ec.europa.eu/en/extensive-wreck-data-set-now-available-emodnet)) | CC BY 4.0 / OGL v3. [ZIP](https://ows.emodnet-humanactivities.eu/geonetwork/srv/api/records/108ef240-fa6e-4b83-8569-09b509e2959d/attachments/EMODnet_HA_Heritage_WW_Wrecks_20241226.zip) (shapefile, gdb) ; WFS `https://ows.emodnet-humanactivities.eu/wfs`, couche `emodnet:wwshipwrecks` |
| ★ [EMODnet – Cultural Heritage, Ship wrecks](https://emodnet.ec.europa.eu/geonetwork/srv/api/records/e965088b-a265-4517-84df-c49b156af8a7) | Europe : agrège SHOM, Irlande (NMS), Historic England, OxREP | ? | CC BY 4.0. [ZIP](https://ows.emodnet-humanactivities.eu/geonetwork/srv/api/records/e965088b-a265-4517-84df-c49b156af8a7/attachments/EMODnet_HA_Heritage_Shipwrecks_20250409.zip) ; WFS couche `emodnet:heritageshipwrecks` |
| [UKHO / ADMIRALTY Marine Data](https://admiralty.co.uk/access-data/marine-data) | Source d'origine des données ci-dessus (épaves et obstructions) | idem | Portail ADMIRALTY |
| [Wrecksite.eu](https://wrecksite.eu) | Plus grande base communautaire : épaves, positions, photos, cartes | ~187 000 (2019) à 214 000 | Freemium, pas de réutilisation libre. Lien possible via Wikidata P9135 |
| [ShipwreckMap](https://www.shipwreckmap.ca/) | Agrège UKHO, NOAA AWOIS/ENC, Wikidata, OSM ; inclut des avions | 87 000+ | Export CSV payant |
| [Wikidata](https://codethecity.org/2020/12/08/nautical-wrecks/) | Éléments « shipwreck » avec coordonnées (SPARQL) | Dizaines de milliers | CC0 |
| [OpenStreetMap / OpenSeaMap](https://wiki.openstreetmap.org/wiki/Tag:historic=wreck) | `historic=wreck`, `seamark:type=wreck`, `wreck:depth`, `wreck:date_sunk`, `wreck:type` | Variable | ODbL, via l'API Overpass |
| [Wikipedia – Lists of shipwrecks](https://en.wikipedia.org/wiki/Lists_of_shipwrecks) | Listes chronologiques et géographiques (voir `sources/wikipedia`) | Dizaines de milliers | CC BY-SA |
| [Worldwide Shipwreck Database](http://users.accesscomm.ca/shipwreck/), [ShipwreckWorld](https://www.shipwreckworld.com/maps/) | Sites d'amateurs | ? | Consultation seulement |

### Bases nationales – Europe

| Source | Zone | Volume | Accès / licence |
|---|---|---|---|
| ★ [SHOM – Épaves et obstructions](https://services.data.shom.fr:/geonetwork/WS/api/records/BDML_EPAVES.xml) | ZEE française (navires, avions, conteneurs, ancres) | ? | CC BY-SA 4.0 ; SHP/GPKG/CSV ([7z](https://services.data.shom.fr/INSPIRE/telechargement/prepackageGroup/EPAVES-PACK_DL/prepackage/EPAVES_PACK/file/EPAVES_PACK.7z)) + WFS |
| [DRASSM](https://www.culture.gouv.fr/espace-documentation/Repertoire-des-ressources-documentaires/Centres-de-recherches/departement-des-recherches-archeologiques-subaquatiques-et-sous-marines-drassm) | France, archéologie sous-marine | ? | Pas de base publique en libre accès trouvée |
| ★ [Wreck Inventory of Ireland](https://data.gov.ie/dataset/national-monuments-service-wreck-inventory-of-ireland) / [Wreck Viewer](https://www.archaeology.ie/underwater-archaeology/wreck-viewer) | Irlande | 18 000+ | CC BY 4.0, CSV |
| ★ [Canmore – Historic Environment Scotland](https://marine.gov.scot/node/12750) | Écosse : épaves, obstructions, naufrages documentés | ~24 000 | Données ouvertes (Marine Scotland) |
| [Historic England – Protected wreck sites](https://planning.data.gov.uk/dataset/protected-wreck-site) | Angleterre | Quelques dizaines protégées | planning.data.gov.uk |
| [RBINS – Belgian MSP wrecks](https://metadata.naturalsciences.be/geonetwork/srv/api/records/c5f1f8a0-3626-4396-9795-ad07d98e8bdb) | Belgique : 7 zones d'épaves protégées | 7 | CC BY 4.0, WFS |
| [Hydrographie flamande / VLIZ](https://www.belganewsagency.eu/flemish-hydrography-team-has-mapped-most-shipwrecks-of-coast-using-sonar) | Belgique : épaves relevées au sonar | ~300 | Téléchargement public à vérifier |
| [RCE – Wrakkentelling / MaSS](https://www.cultureelerfgoed.nl/binaries/cultureelerfgoed/documenten/publicaties/2022/01/01/wrakkentelling-2022/73923_RCE_Publicatie-Wrakkentelling_uitgave+2022_TG_PDFA.pdf), [épaves VOC 1595–1795](https://maritiemportal.nl/database-wrecks-in-documents-1595-1795-rijksdienst-voor-het-cultureel-erfgoed) | Pays-Bas | ? | Rapports, accès partiel |
| [Museovirasto](https://museovirasto.fi/en/cultural-environment/archaeological-cultural-heritage/underwater-cultural-heritage-in-finland) | Finlande | ? | [WFS ouvert](https://avoindata.suomi.fi/data/en/dataset/activity/museoviraston-kulttuuriymparistoaineistot-suojellut-kohteet-wfs-palvelu) |
| [Fornsök (RAÄ)](https://databaser.ub.gu.se/fornsok/100190) | Suède | ? | Recherche en ligne |
| Slots- og Kulturstyrelsen / Fund og Fortidsminder | Danemark | ? | À vérifier |
| [HELCOM](https://helcom.fi/wp-content/uploads/2025/06/Thematic-assessment-on-hazardous-submerged-objects-in-the-Baltic-Sea-potentially-polluting-shipwrecks.pdf), [War Log](https://divernet.com/scuba-news/wrecks/war-log-maps-out-1000-baltic-shipwrecks/) | Baltique : épaves polluantes et de guerre | 1 000+ | Rapports |
| BSH | Allemagne (mer du Nord, Baltique) | ? | Pas de base publique trouvée |

### Bases nationales – hors Europe

| Source | Zone | Volume | Accès |
|---|---|---|---|
| ★ [NOAA – Wrecks & Obstructions (AWOIS + ENC)](https://fisheries.noaa.gov/inport/item/39988) | Eaux américaines : position, profondeur, année, historique | Plusieurs milliers | Domaine public ; KML, Excel, WMS, ESRI REST |
| [NOAA – épaves potentiellement polluantes](https://response.restoration.noaa.gov/node/4511) | États-Unis | ~87 prioritaires | Rapport |
| [BOEM – Atlantic OCS](https://www.boem.gov/sites/default/files/uploadedFiles/BOEM/BOEM_Newsroom/Library/Publications/2012/PowerPoint_Source_Files/2A_1035_Holland_PPT.pdf) | Plateau atlantique des États-Unis | ? | Sur demande |
| [Maritime History of the Great Lakes](https://maritimehistoryofthegreatlakes.ca/Documents/DT86/default.asp), [Save Ontario Shipwrecks](https://saveontarioshipwrecks.ca/resources/marine-heritage-database/) | Grands Lacs | Plusieurs milliers | Consultation |
| [Northern Maritime Research](https://northernmaritimeresearch.com/) | Canada atlantique | ? | Consultation |
| ★ [Australasian Underwater Cultural Heritage Database](https://en.wikipedia.org/wiki/Australasian_Underwater_Cultural_Heritage_Database) | Australie : épaves, avions immergés, artefacts (registre officiel) | Plusieurs milliers | Recherche publique ; données en partie sur [data.gov.au](https://data.gov.au/data/dataset/e2e1b526-da90-438b-a897-0760de8a01d7) |
| [Western Australian Museum](https://museum.wa.gov.au/maritime-archaeology-db/wrecks) | Australie-Occidentale | 1 650+ | Consultation |
| [SAHRIS (SAHRA)](https://sahris.sahra.org.za/about/news/preserving-underwater-heritage) | Afrique du Sud | ? | Consultation |
| [National Shipwreck Database](https://nsd.ccf.gov.lk/) | Sri Lanka | 115 | Carte interactive |

### Sources spécialisées

| Source | Sujet | Accès |
|---|---|---|
| ★ [OxREP Shipwrecks Database](https://oxrep.web.ox.ac.uk/shipwrecks-database) | Épaves antiques de Méditerranée jusqu'en 1500 : coordonnées (volontairement imprécises), profondeur, datation, cargaison | Excel gratuit |
| [uboat.net](https://uboat.net/allies/merchants) | Navires touchés par les U-boote (1914–18, 1939–45), avec positions | Consultation |
| [Pacific Wrecks](https://pacificwrecks.com/) | Avions et navires de la guerre du Pacifique | Consultation |
| [EMODnet – Dumped munitions](https://emodnet.ec.europa.eu/geonetwork/srv/api/records/661aa259-8ea9-49ae-a39d-49685057b013) | Munitions immergées dans les mers européennes | Ouvert, WFS |
| [Heritage Victoria – Submerged aircraft](https://www.heritage.vic.gov.au/about-us/news/news-stories/submerged-aircraft-wrecks-program) | Avions immergés | Programme ponctuel |

### Priorités d'intégration

1. **EMODnet / UKHO** : base mondiale de départ (67 000 à 94 000 épaves, avec profondeur), complétée par la couche européenne EMODnet Cultural Heritage.
2. **NOAA**, **SHOM**, **Irlande**, **Canmore** : bases officielles ouvertes avec coordonnées.
3. **Wikipedia / Wikidata** : textes et images, avec l'identifiant Wrecksite pour faire le lien.
4. **OxREP** (Antiquité), **EMODnet munitions** et **OSM** (autres objets immergés).

Les bases payantes ou sous abonnement (Wrecksite, ShipwreckMap) ne peuvent pas être aspirées librement. Les volumes et licences sont à revérifier avant chaque intégration.
