# vitaldb-sevoflurane-ke0

Scripts that extract and process the data from VitalDB for the population pharmacodynamic analysis of sevoflurane effect-site equilibration (ke0) and the bispectral index (BIS):

> Yoo YM. Sevoflurane effect-site equilibration estimated from routine anaesthetic records, its external validation and the effects of age: a population pharmacodynamic analysis. Submitted to *BJA Open*.

## Contents

| File | Content |
|---|---|
| `data/caseids_derivation_n268.csv` | VitalDB `caseid` of the derivation cohort (gastrectomy, 268 patients) |
| `data/caseids_sensitivity_n213.csv` | `caseid` of the sensitivity subset of the derivation cohort (213 patients) |
| `data/caseids_external_n179.csv` | `caseid` of the external validation cohort (colorectal resection, 179 patients) |
| `data_build/rebuild_datasets.py` | Downloads the VitalDB case and track lists and the tracks of the listed cases, and writes the three NONMEM data sets |
| `data_build/build_sevo_ke0_dataset.py` | Builds the 30-s NONMEM records of the analysis window for a list of cases |
| `data_build/build_nonmem_dataset.py` | Track download from the VitalDB API and 1-s resampling |

The processed data sets are not included, because the VitalDB Data Use Agreement does not allow the data to be passed on without the provider's consent. The case lists define the cohorts; the selection criteria are given in the paper.

## Requirements

Python 3.12 with numpy, pandas and requests (tested with numpy 2.3, pandas 2.3, requests 2.34).

## Usage

```
python data_build/rebuild_datasets.py --work <empty working folder>
```

The script downloads about 2600 track files (end-tidal sevoflurane, BIS, signal quality index, end-tidal carbon dioxide, minute ventilation and remifentanil effect-site concentration; about 12 min) and writes to `data_build/output/`

- `sevo_ke0_maint_cov_30s_n268.csv` (derivation cohort; 268 patients, 113 752 records, 110 736 BIS observations)
- `sevo_ke0_maint_cov_30s_sens_n213.csv` (sensitivity subset; 213 patients, 92 171 records, 89 699 BIS observations)
- `sevo_ke0_ext_colorectal_30s.csv` (external cohort; 179 patients, 56 920 records, 50 748 BIS observations)

The analysis window starts 45 min after end-tidal sevoflurane first reached 0.3 vol% and ends at the last 0.3 vol% reading. Each 30-s record holds the median BIS (missing, `.`, when the minimum signal quality index in the interval was below 50), the last end-tidal sevoflurane value, interval medians of end-tidal carbon dioxide and minute ventilation, the last remifentanil effect-site concentration and patient covariates (age, sex, weight, height, BMI, ASA physical status, surgical approach, patient medians of remifentanil, carbon dioxide and minute ventilation, fat-free mass). In the external cohort, one isolated 30-s end-tidal value of 11.3 vol% (caseid 3128, 7.0 min) between 1.2 and 1.5 vol% is replaced by the linear interpolation 1.35 vol%, as in the analysed file.

A rebuild from a fresh download on 17 October 2026 gave files identical to those analysed in the paper.

## Licence

The code and the case ID lists are released under the MIT Licence (`LICENSE`). The VitalDB data are not covered by this licence; their use is governed by the VitalDB Data Use Agreement (https://vitaldb.net/dataset/).

## Citation

Please cite the paper above and VitalDB: Lee HC, Park Y, Yoon SB, Yang SM, Park D, Jung CW. VitalDB, a high-fidelity multi-parameter vital signs database in surgical patients. *Sci Data* 2022; 9: 279. https://doi.org/10.1038/s41597-022-01411-5
