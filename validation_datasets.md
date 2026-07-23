# APSIM Strawberry Model — Validation Datasets

## Model structure (for reference)

**Phenology phases:** Transplanting → Established → VegetativeGrowth → FlowerInduction → Anthesis → FruitSet → GreenFruit → Maturity → Harvest

**Key sub-models:**
- Thermal time: TMin=5°C, TOpt=20°C, sub-daily interpolation
- Photoperiod gate: SD cultivars daylength <14h; DN cultivars always open unless Tmean >26°C
- Dormancy: Utah chilling model (`StrawberryChilling.cs`)

---

## Dataset 1 — McWhirt et al. 2023 *(best match for Anthesis→Harvest phases)*

**Citation:** McWhirt, A. (2023). Model Development of the Phenological Cycle from Flower to Fruit of Strawberries (*Fragaria × ananassa*). *Agronomy*, 13(10), 2489. https://doi.org/10.3390/agronomy13102489

**URL:** https://www.mdpi.com/2073-4395/13/10/2489

**Access:** Open access (CC BY)

**What it contains:**
- DN cultivars **Albion** and **San Andreas**
- Hydroponic drip system, greenhouse, Auburn Alabama (USA)
- 2022–2023 season; three production cycles:
  - Cycle 1: Oct 25 – Dec 16
  - Cycle 2: Dec 27 – Feb 21
  - Cycle 3: Feb 28 – Apr 16
- Daily tracking of 30 flowers per cultivar through six stages (floral bud → ripe fruit)
- In-situ weather station data available
- GDD base temperature: 3°C
- Days to maturity: **Albion** 51 / 56 / 47 days; **San Andreas** 43 / 54 / 46 days (cycles 1–3)
- Stage 5 (fruit formation) was the longest stage

**Phases validated:** FlowerInduction → Anthesis → FruitSet → GreenFruit → Maturity → Harvest

**Notes:** Weather data from an in-situ greenhouse station allows exact GDD reconstruction. Best quantitative dataset for the post-anthesis thermal time targets.

---

## Dataset 2 — Bethere et al. 2016 *(calibrated GDD model, bloom and harvest)*

**Citation:** Bethere, L., Sīle, T., Seņņikovs, J., & Bethers, U. (2016). Impact of climate change on the timing of strawberry phenological processes in the Baltic States. *Estonian Journal of Earth Sciences*, 65(1), 48–58. https://doi.org/10.3176/earth.2016.04

**URL:** https://kirj.ee/public/Estonian_Journal_of_Earth_Sciences/2016/issue_1/earth-2016-1-48-59.pdf

**Access:** Open access

**What it contains:**
- Latvia field observations 2010–2013, multiple locations
- BBCH-scale phenological observations (stages 61/65 = bloom; 85/87 = first harvest; 89 = second harvest)
- Iteratively calibrated GDD model parameters (modified sine wave diurnal interpolation):

| Phenological event | Tbase (°C) | GDD sum | n obs | RMSE (days) |
|--------------------|-----------|---------|-------|-------------|
| Bloom              | 0         | 586     | 19    | 4.3         |
| First harvest      | 6         | 284     | 16    | 7.3         |
| Second harvest     | 10        | 95      | 13    | 2.2         |

- GDD for bloom accumulated from 1 January; harvest GDD accumulated from bloom date

**Phases validated:** VegetativeGrowth → FlowerInduction (bloom); GreenFruit → Maturity (harvest)

**Notes:** Multi-year multi-location data. Tbase and GDD targets differ from the model's current TMin=5°C — worth comparing directly.

---

## Dataset 3 — Costa et al. 2021 *(SD vs DN photoperiodic comparison)*

**Citation:** Costa, R. C., Calvete, E. O., Spengler, N. C. L., Chiomento, J. L. T., Trentin, N. S., & Paula, J. E. C. (2021). Morpho-phenological and agronomic performance of strawberry cultivars with different photoperiodic flowering responses. *Acta Scientiarum. Agronomy*, 43, e45189. https://doi.org/10.4025/actasciagron.v43i1.45189

**URL:** https://pdfs.semanticscholar.org/366e/42a1ce326682061f51a2063ccc2b8fd7c3de.pdf

**Access:** Open access

**What it contains:**
- 6 cultivars: **Camarosa, Camino Real** (SD) and **Aromas, Albion, Monterey, San Andreas** (DN)
- Greenhouse, Rio Grande do Sul, Brazil (28°S, subtropical), 2016
- Transplant dates varied by cultivar (May–July 2016); experiment ran to October 2016
- Base temperature: 7°C (Arnold 1960 method)
- BBCH phenology (E11 to E87)

| Cultivar    | Type | Days to first flower | ATT to first flower (°C-day, Tbase=7°C) |
|-------------|------|----------------------|------------------------------------------|
| San Andreas | DN   | 39                   | ~327                                     |
| Camarosa    | SD   | 55                   | ~327                                     |
| Albion      | DN   | ~48 (ND mean)        | —                                        |
| Monterey    | DN   | 63                   | —                                        |
| Camino Real | SD   | 81                   | —                                        |

- Yield data (total fresh fruit mass) by month for each cultivar
- Root morphology data also collected

**Phases validated:** Transplanting → VegetativeGrowth → FlowerInduction; photoperiod gate (SD vs DN responses)

**Notes:** Southern Hemisphere subtropical conditions — ND cultivars flowered autonomously (not cold-induced). Useful for testing photoperiod gate logic under warm conditions where SD gate stays closed but DN gate stays open.

---

## Dataset 4 — Tanino & Wang 2008 *(chilling model validation)*

**Citation:** Tanino, K., & Wang, M. (2008). Modeling chilling requirement and diurnal temperature differences on flowering and yield performance in strawberry crown production. *HortScience*, 43(7), 2060–2065.

**URL:** https://journals.ashs.org/view/journals/hortsci/43/7/article-p2060.xml *(paywalled — institutional access required)*

**Access:** Paywalled (ASHS)

**What it contains:**
- 6-year commercial field data across 5 geographically distinct locations
- Compared Utah Model vs. non-weighted ACU for predicting:
  - Time to flower
  - Fruit yield
- Best correlation for flowering time: quadratic function with ACU using effective temperatures –2 to 15°C
- Fruit yield correlated only with specific weighted accumulation models (not simple chilling hours)
- Daylength interaction with chilling also modelled

**Sub-model validated:** `StrawberryChilling.cs` Utah chilling model; ChillingComplete → FlowerInduction phase

**Notes:** Most directly relevant to the dormancy/chilling sub-model. The paper's multi-location multi-year structure is ideal for testing whether the Utah model outperforms simpler chilling hour counts.

---

## Dataset 5 — Verheul et al. 2006 *(photoperiod gate parameters)*

**Citation:** Verheul, M. J., Sønsteby, A., & Grimstad, S. O. (2006). Interactions of photoperiod, temperature, duration of short-day treatment and plant age on flowering of *Fragaria* × ananassa Duch. cv. Korona. *Scientia Horticulturae*, 107(2), 164–170. https://doi.org/10.1016/j.scienta.2005.07.004

*(Corrected 2026-07-23 — this dataset was previously misattributed to "Durner, E.F. (2005)"; the paper, URL, and findings below are unchanged, only the author/year/volume/DOI were wrong.)*

**URL:** https://www.sciencedirect.com/science/article/abs/pii/S030442380500258X *(paywalled)*

**Access:** Paywalled (Elsevier)

**What it contains:**
- Controlled-environment experiments varying photoperiod (10, 12, 16, 20, 24 h), day temperature (12–30°C), number of short days (14, 21, 28 d), and plant age
- SD cultivar cv. Korona
- Key result: all plants flowered under 10–12 h photoperiod after ≥21 short days at 12–18°C; no flowering at 16 h photoperiod
- DN cultivars (Tristar, Hecker): flowering suppressed only above ~26–28°C (day/night)

**Sub-model validated:** `StrawberryPhotoperiod.cs` — CriticalDayLength, MinInductiveDays, MinInductiveTemp/MaxInductiveTemp, HeatSuppressionThreshold

**Notes:** These results broadly support the default parameter values in the photoperiod script. Durner's 1984 paper (JASHS) is the original DN threshold work; the 2006 Korona paper (Verheul et al.) is most directly comparable to the SD gate logic.

---

## Summary — which phases each dataset covers

| Phase(s)                          | Dataset(s)                    |
|-----------------------------------|-------------------------------|
| Transplanting → Established       | Not well covered — use grower records |
| Established → VegetativeGrowth    | Not well covered              |
| VegetativeGrowth → FlowerInduction (bloom) | Bethere 2016, Costa 2021 |
| FlowerInduction → Anthesis        | McWhirt 2023, Verheul et al. 2006 |
| Anthesis → FruitSet               | McWhirt 2023                  |
| FruitSet → GreenFruit             | McWhirt 2023                  |
| GreenFruit → Maturity             | McWhirt 2023, Bethere 2016    |
| Maturity → Harvest                | Bethere 2016, Costa 2021      |
| Dormancy / Utah chilling          | Tanino & Wang 2008            |
| Photoperiod gate (SD)             | Verheul et al. 2006           |
| Photoperiod gate (DN)             | Costa 2021, Durner 1984       |

---

## Known gaps

- **Transplanting → Established and Established → VegetativeGrowth** phases are not documented in any of the papers above. These may need calibration from grower trial data or agronomic extension records.
- Most open-access datasets use base temperatures of 3°C or 7°C, whereas the current APSIM model uses a beta function with TMin=5°C, TOpt=20°C. Conversion/comparison will be needed.
- McWhirt 2023 is greenhouse/hydroponic — field validation data for DN cultivars under Australian conditions would strengthen the model.
