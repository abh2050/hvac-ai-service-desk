# Data and manual sources

All files were downloaded on 2026-10-22 with `curl`. The full SHA256 manifest for every file, including the 52 ORNL lab CSVs and the 25 simulated RTU CSVs inside the LBNL zip, is in `data/checksums.sha256`. Run `shasum -a 256 -c data/checksums.sha256` from `data/` to verify it. Raw files stay out of git.

## Datasets

| Dataset | URL | License note | Used in |
|---|---|---|---|
| LBNL "AHU and RTU" FDD data set (Figshare article 11752740, version 3) | https://figshare.com/articles/dataset/LBNLDataSynthesisInventory_pdf/11752740/3 (files via https://ndownloader.figshare.com/files/<id>) | CC0 1.0, as stated in the Figshare metadata. The Figshare MD5 for each file was checked on download. | Release 1 (lab files only) |
| LBNL "Roof top unit (RTU)" FDD data set, DOI 10.25984/1881324 | https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_RTU/ | The dataset page states no license. LBNL asks downloaders to submit a registration form (name, organization, email, purpose). We downloaded from the public file URLs without the form, by owner decision. Cite with the DOI. | Release 1 (lab and field), Release 2 (simulated) |

### Files and their source type

| File | SHA256 | Source type | Equipment | Release |
|---|---|---|---|---|
| figshare: LBNLDataSynthesisInventory.pdf | `0c241a4d1b125a54e8d73e29b59e316012aef722524c3ea531c2f71da79d7d4d` | documentation | n/a | label source |
| figshare: MZVAV-1.csv | `26037a166758763b985454b3e4dde7f4e478583478c27e899a18eef40a44dbf2` | simulated (PNNL EnergyPlus and Modelica) | multi-zone VAV AHU | 2 |
| figshare: MZVAV-2-1.csv | `ac69ac4cae8d18c852fe5aaa8b6c34113282bb56770bc72a398e2c430056ae76` | lab (ASHRAE RP-1312, Energy Resource Station, Ankeny, Iowa) | multi-zone VAV AHU-A | 1 |
| figshare: MZVAV-2-2.csv | `d754d7010078db94644b2bc2280d67bfbeab2f4d929af91bcb4a5a46ad9330a0` | simulated (RP-1312 model of the same AHU) | multi-zone VAV AHU-A | 2 |
| figshare: SZCAV.csv | `6bb116a7ac987a828f5d73e92bc1ead1b50f51374c7695db7396ed509c47d4e2` | lab (LBNL FLEXLAB test cell X3A) | single-zone constant volume AHU | 1 |
| figshare: SZVAV.csv | `512992155cb43c576a3ba1e45b37f20966f42c5b05980428fec8008bd054ee93` | lab (LBNL FLEXLAB test cell X3A) | single-zone VAV AHU (same unit as SZCAV) | 1 |
| figshare: RTU.csv | `90edc100e6fcf274230cce7b66f41861ab1ffbcd752a94eefb9876b4d7941e49` | lab (ORNL FRP #2) | Trane YCD150 12.5 ton RTU | 1 |
| lbnl-rtu: LBNL_FDD_Data_Sets_RTU.pdf | `6c9c173462467bc7662c60807d0879de11d66c1483f16d90b716b964fbd35457` | documentation | n/a | label source |
| lbnl-rtu: LBNL_FDD_Data_Sets_RTU_all_3.zip | `883cdd70f50e4cf55179c3ea793b8baec92dda60b55821e537fc4b5f92b251f8` | archive of the three parts below | n/a | n/a |
| zip: ORNL_RTU/*.csv (52 files) | per-file hashes in `checksums.sha256` | lab (ORNL FRP, Oak Ridge, TN) | Trane YCD150 12.5 ton RTU serving 10 VAV boxes | 1 |
| zip: Field RTU/Site1_Staging_Fault.csv | `beecd357268e02e6e8084ee267c0549e909302db4c6ff099c4fe88ec8c1f2d3f` | field measured | 7.5 ton RTU, restaurant, Milford, CT | 1 |
| zip: Field RTU/Site1_Unfaulted.csv | `30986a9b02ebdeb17b977a7831d50fc6963bd704dcecb4b9547971464bede6ba` | field measured | same unit | 1 |
| zip: Field RTU/Site2_Undercharged40.csv | `205d2069444804abfdb8a9096c34e41b6b0a34bb8d1b6c43ba93ab1c19d3ead7` | field measured | 10 ton RTU, distribution center, Colchester, CT | 1 |
| zip: Field RTU/Site2_Unfaulted.csv | `7e482f6bb6fb28f17ceb58a51a0426bc8028be9be9d90fb0231d074caa8d1f38` | field measured | same unit | 1 |
| zip: Simulated RTU/*.csv (25 files) | per-file hashes in `checksums.sha256` | simulated (NREL Modelica and EnergyPlus) | Trane Precedent 5 ton RTU model | 2 |
| lbnl-rtu: LBNL_FDD_Data_Sets_RTU_ttl.zip | `622978d1bd8c3efed40b5e705f73cb77be9202ae075cdffe6fce7fe36d77f5dc` | Brick models | see below | 1 |

The episode index with one row per labeled episode is in `data/episodes.csv`. `pipelines/build_episodes.py` builds it from the inventory tables.

### Label conflicts kept as published

We keep the original LBNL labels. When the inventory table and the per-minute "Fault Detection Ground Truth" flag disagree, `episodes.csv` keeps both and fills `label_conflict`. There are 16 such Release 1 rows.

1. In RTU.csv, the flag equals 1 on every day. That includes the 7 days that Table 4-3 lists as unfaulted.
2. In RTU.csv, Table 4-3 lists 2017-12-03 both as an "HVAC setback early termination" fault day and as an unfaulted day.
3. In RTU.csv, 2017-12-10 is in the file but not in Table 4-3. The days 2017-08-28, 2017-12-08, 2017-12-11, and 2018-02-06 each hold 1 row that spills over a day boundary.
4. In MZVAV-2-1.csv, Table 2-2 lists 2007-08-30 as a 2.0 GPM heating valve leak, but the flag is 0. The days 2009-05-30 and 2009-05-31 are in the file but not in the table.

Gate 1 decides how conflicting days are scored, and the gate report states that rule. It does not relabel any day.

### Brick models

`LBNL_FDD_Data_Sets_RTU_ttl.zip` holds two Brick 1.2 models.

1. `LBNL_FDD_Data_Sets_RTU_Exp.ttl` (SHA256 `0eb38c4a…13bd`, full hash in the manifest) models the ORNL lab RTU. It holds the RTU, its compressor and supply fan, 10 VAV boxes, 10 HVAC zones, and their points (23 `hasPoint` and 11 `feeds` relations). We use it for asset relationships of the ORNL lab RTU.
2. `LBNL_FDD_Data_Sets_RTU_Sim.ttl` models the simulated Precedent RTU. It is used only in Release 2.

No Brick model exists for the field RTUs or for any Figshare AHU or RTU file. Asset relationships for those units come from the inventory PDF descriptions and are entered as configuration.

## Manuals

All five manuals are public PDFs published by the equipment maker. The makers keep their copyright. We use the manuals for retrieval and quotation inside the app and do not redistribute them. They are stored in a private S3 bucket and opened only through short-lived presigned URLs for signed-in users.

| File | Title (from the PDF) | URL | Pages | SHA256 |
|---|---|---|---|---|
| trane-rt-svx26p-voyager-gas-electric-12-25t.pdf | Trane RT-SVX26P-EN (2017-02-28), Voyager Cooling, Gas/Electric 12½ to 25 Tons, models YS*150-300, YH*150-300, Installation, Operation, and Maintenance | https://www.trane.com/content/dam/Trane/Commercial/lar/es/product-systems/comercial/Rooftops/VoyagerII/iom/RT-SVX26P-EN%20-%20Voyager%20II%20FC%20Gas%20IOM%20(Ingl%C3%A9s).pdf | 56 | `d439eee42dc991632fb0c0fe499c00e1922e6e1901e5d0473e1c7a8b48fd6a7b` |
| trane-rt-svx21ad-precedent-gas-electric-3-10t.pdf | Trane RT-SVX21AD-EN (2022-06-17), Precedent Gas/Electric 3 to 10 Tons, Installation, Operation, and Maintenance | https://elibrary.tranetechnologies.com/public/commercial-hvac/Literature/Installation%20Operation%20and%20Maintenance/RT-SVX21AD-EN_06172022.pdf | 82 | `41ccb36b3054526744ceccd2155a9765526b79de90a4e1350adcda94d6df2382` |
| daikin-im672-vision-ahu.pdf | Daikin Applied IM 672-26, Vision Indoor Air Handler, Installation and Maintenance Manual | https://tahoeweb.daikinapplied.com/api/general/DownloadDocumentByName/media/IM%20672-26_pub%207%203%2025.pdf | 88 | `ce93b5df73ea295394b48b1703848dd594b9dfb119b9c06c4dbb8625fb19053b` |
| trane-clch-svx08f-csaa-ahu-gas-heat.pdf | Trane CLCH-SVX08F-EN (2025-09-30), Gas Heat Performance Climate Changer CSAA Air Handlers, Installation, Operation, and Maintenance | https://elibrary.tranetechnologies.com/public/trane-history/Literature/Installation%20Operation%20and%20Maintenance/CLCH-SVX08F-EN_09302025.pdf | 40 | `93fdd64b47db8e7be3272962aee9d3c7ddd1ed75c7981dad86977fefaaa883e8` |
| honeywell-jade-w7220-63-2700.pdf | Honeywell 63-2700, JADE Economizer Module (W7220) Specification and Installation Instructions | https://www.cochranesupply.com/media/assets/product/documents/Honeywell/Jade%20Install%20Sheet.pdf (Honeywell document hosted by a distributor) | 32 | `67050681867dd6a313a24206f73f47e32ff38713db0dbe921548ee51a6dd13bd` |

We also tried `CLCH-SVX07R-EN` (the general CSAA manual) at its listed eLibrary URL, and the server returned HTTP 404.

### Component manuals added after Gate 2 run 1 (downloaded 2026-10-23)

Gate 2 run 1 showed that 38 of 51 AI abstentions came from components that no manual covered. The most common were the supply air temperature sensor and the coil valves. The owner approved adding public documents for those components. All three are documents from the equipment maker, hosted by distributors.

| File | Title (from the PDF) | URL | Pages | SHA256 |
|---|---|---|---|---|
| siemens-duct-temperature-sensor-129-525.pdf | Siemens Document No. 129-525 (2008-10-27), Duct Temperature Sensor Installation Instructions | https://zotsupply.com/content/PDFs/Siemens/Temperature/Averaging/Duct%20Temperature%20Sensor%20Installation.pdf (Siemens document hosted by a distributor) | 3 | `7b58244bc91fd7da480f69f564169ca602e6e12a0a98e8e66ea495db61dd1772` |
| jci-te6300m-duct-averaging-sensor.pdf | Johnson Controls, TE-6300M Series Duct Averaging Temperature Sensors Installation Instructions | https://resource.gemaire.com/is/content/Watscocom/Gemaire/johnsoncontrols_te-6316m-1_article_1405423016904_en_ii.pdf?fmt=pdf (Johnson Controls document hosted by a distributor) | 2 | `84a5900ecadb7effca5744bbf912312976d1b2b90cee33ae8a5083e47e1aeee8` |
| honeywell-ml6984-ml7984-series4000.pdf | Honeywell 95C-10939-11, ML6984, ML7984 Series 4000 Direct Coupled Valve Actuators | https://fwwebbimage.fwwebb.com/ProductInfo/Honeywell_ML6984A4000_U_Specification_Sheet.pdf (Honeywell document hosted by a distributor) | 12 | `8d6fc3cd139555ed2ef265bce49caa8f4239972ed49d9a0e7614ec61766c3017` |

Tried and not used:
- The Trane support attachments that were expected to hold the ReliaTel service manual RT-SVD03M-EN both turned out to be the communications interface installer guide (ACC-SVN18). The article page returns HTTP 403.
- The Honeywell ML6984/ML7984 troubleshooting guide on kele.com returned HTTP 403.

Compatibility: LBNL does not name the sensor or valve actuator models for any unit. All three documents are component class matches, and they carry the "compatibility uncertain" flag like the other manuals.

## Manual compatibility table

An exact match means the manual covers the same maker and model series. A class match means the manual covers the same equipment class but a different or unknown model. The diagnosis step marks every class match "compatibility uncertain".

| LBNL unit | Equipment as documented by LBNL | Manual(s) | Match | Gap |
|---|---|---|---|---|
| ORNL FRP RTU (RTU.csv and ORNL_RTU/*) | Trane YCD150, 12.5 ton, gas/electric, VAV | RT-SVX26P (Voyager gas/electric 12½ to 25 ton) | class match | The YCD prefix is an older Voyager series. RT-SVX26P covers YS and YH models of the same size range. We did not find a public YCD150 IOM. |
| ORNL FRP RTU economizer | economizer with OA and RA dampers (controller model not stated) | Honeywell JADE 63-2700 | class match | LBNL does not name the economizer controller. JADE is a common RTU economizer controller, not the documented one. |
| Field Site 1 RTU | 7.5 ton, EER 9, maker not stated | RT-SVX21AD (Precedent 3 to 10 ton) | class match | The RTU maker is not given. The "Manufacturer" column in Table F1 names the FDD tool (ClimaCheck), not the RTU. |
| Field Site 2 RTU | 10 ton, EER 10.4, two refrigerant circuits, maker not stated | RT-SVX21AD (Precedent 3 to 10 ton) | class match | Same gap as Site 1. The FDD tool is Enerfit. |
| ERS AHU-A (MZVAV-2-1) | multi-zone VAV AHU with preheat, cooling and heating coils, supply and return fans, maker not stated | Daikin IM 672 Vision; Trane CLCH-SVX08F | class match | The AHU maker is not given. CLCH-SVX08F mainly covers gas heat sections, so it is weak for hot water valve faults. |
| FLEXLAB X3A AHU (SZCAV, SZVAV) | single-zone AHU with hot water heating and chilled water cooling coils and OA, RA, and EA dampers, maker not stated | Daikin IM 672 Vision; Trane CLCH-SVX08F | class match | Same gap as ERS AHU-A. |
| NREL simulated RTU (Release 2) | Trane Precedent 5 ton model | RT-SVX21AD | exact family | Simulated data. Release 2 only. |

No LBNL unit in Release 1 has an exact manual match. As a result, the policy "manual does not match the equipment" fires for every Release 1 diagnosis unless Gate 2 finds a closer manual. This is expected, and we report it, not hide it.
