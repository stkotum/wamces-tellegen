# WAMCES for tellegen: a European grid case with a solved operating point

This repository builds a MATPOWER case of the continental European transmission
grid for [tellegen](https://github.com/eigenergy/tellegen). The case has 3809
buses, 7343 branches and 618 generators in 25 countries. Most buses are at
220 kV or 380 kV. Every bus has a latitude and longitude. The case comes with a
solved AC operating point.

The case joins two open datasets. The network, line ratings, generator costs
and coordinates come from PanTaGruEl
([Zenodo 2642175](https://doi.org/10.5281/zenodo.2642175)). The operating point
comes from WAMCES ([Zenodo 18721887](https://doi.org/10.5281/zenodo.18721887)).
WAMCES is a dynamic model built on the PanTaGruEl network.

Both records use [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
This repository does not copy them. The converter is MIT licensed.

## Building the Case

Download three files into one folder:

```sh
mkdir sources
curl -L -o sources/wamces_model.zip https://zenodo.org/api/records/18721887/files/wamces_model.zip/content
curl -L -o sources/raw_csv_data.zip https://zenodo.org/api/records/18721887/files/raw_csv_data.zip/content
curl -L -o sources/pantagruel.zip https://zenodo.org/api/records/2642175/files/pantagruel.zip/content
```

Then run the converter. It needs Python 3.10 or newer with scipy.

```sh
python3 -m pip install scipy tellegen
python3 prepare_europe3809.py sources out
```

The script checks each zip against a pinned SHA-256. It reads the zips as data
and runs nothing from them. It writes three files:

| File | Content |
|---|---|
| `europe3809.m` | MATPOWER case with the solved operating point, ratings, costs and bus names |
| `europe3809_buses.csv` | `bus_i,lat,lon` for every bus |
| `europe3809_ATTRIBUTION.txt` | Sources, licenses, citations and the list of changes |

Keep the attribution file with the case when you share it.

If the `tellegen` wheel is installed, the script also solves an AC power flow
from a flat start. The result must match the stored WAMCES solution to 1e-6.
The observed difference is about 1e-13. The GitHub workflow repeats this check
on every push.

## Loading the Case in tellegen

In the browser, open [tellegen.dev](https://tellegen.dev). Drop `europe3809.m`
together with `europe3809_buses.csv`. The coordinate file places every bus. The
browser solves a DC OPF first.

In Python:

```python
import tellegen

case = tellegen.load("out/europe3809.m")
case.formulation = "acpf"
power_flow = case.solve()   # the WAMCES operating point
case.formulation = "dcopf"
dispatch = case.solve()     # PanTaGruEl costs and line ratings
```

## What the Case Shows

All results are static. Each one is a single steady-state operating point.

The AC power flow reproduces the WAMCES operating point:

- The voltage angles spread over 152 degrees. Spain, Portugal and Italy have
  the lowest angles.
- Power flows into both peninsulas. France exports about 3.6 GW to Spain. Italy
  imports about 7.4 GW, mostly from Switzerland and France.
- The largest angle steps lie inside Spain around Madrid. Only one of the ten
  largest crosses a border. It is the Baixas to Vic line across the Pyrenees.
- Four branches exceed their PanTaGruEl rating. They form two corridors. One
  leaves Gravelines in northern France at about 220 percent. Three parallel
  circuits into Neurath in western Germany carry 103 percent. Both Gravelines
  and Neurath are WAMCES slack buses.

The DC OPF redispatches the generators within the line ratings:

- 55 lines reach their rating.
- The prices vary from bus to bus. Spain, Italy and Portugal have the highest
  median prices. France has the lowest.
- The costs are in arbitrary units. Only the price pattern carries meaning.

## Limits

This is a research test grid. It is not a validated model of the real European
grid.

- The topology comes from the GridKit extract of the ENTSO-E interactive map
  ([Zenodo 55853](https://doi.org/10.5281/zenodo.55853)). The extract is
  unofficial. It dates from May 2016.
- PanTaGruEl compared its line ratings with known values for a few lines. The
  rest of the static data has no published check against operator data.
- WAMCES scales the loads to 70 percent of the PanTaGruEl demand. It gives
  every load a capacitive power factor of 0.99. The case has no line charging
  and no shunts. The WAMCES paper explains neither choice.
- The dispatch is synthetic. No demand year is stated.
- 83 buses lie below 0.9 pu. All are 220 kV buses around Madrid.
- The model covers 25 countries of the continental synchronous area. Turkey,
  Ukraine and Moldova are missing. Eastern Denmark is missing too. Kosovo
  buses carry the Serbian country code.

## Changes to the Source Data

The converter keeps one reference bus (bus 355, Cattenom 380, France). The
other four WAMCES slack buses become PV buses at their solved output. A
generator rating rises where the solved output exceeds 80 percent of it. The
WAMCES script does the same. The converter joins ratings, costs, names and
coordinates from PanTaGruEl by row order. It checks that both records list the
same buses, branches and generators in the same order.
`europe3809_ATTRIBUTION.txt` lists every change.

## Citation

Cite both records when you publish results. WAMCES accompanies this article:

> R. Musca, M. G. Ippolito, E. Riva Sanseverino, "Dynamic Model of the European
> Power System for Wide-Area Monitoring and Control Applications", *Electricity*,
> vol. 7, no. 2, art. 28, 2026.
> [doi:10.3390/electricity7020028](https://doi.org/10.3390/electricity7020028)

PanTaGruEl asks for two papers:

> L. Pagnier, P. Jacquod, "Inertia location and slow network modes determine
> disturbance propagation in large-scale power grids", *PLOS ONE* 14(3):
> e0213550, 2019. [doi:10.1371/journal.pone.0213550](https://doi.org/10.1371/journal.pone.0213550)

> M. Tyloo, L. Pagnier, P. Jacquod, "The key player problem in complex
> oscillator networks and electric power grids: Resistance centralities
> identify local vulnerabilities", *Science Advances* 5(11): eaaw8359, 2019.
> [doi:10.1126/sciadv.aaw8359](https://doi.org/10.1126/sciadv.aaw8359)

`CITATION.cff` lists the same sources for GitHub's citation button.

## Related

[wamces-python](https://github.com/stkotum/wamces-python) is a Python port of
the WAMCES dynamic model. It covers the dynamics that this static case leaves
out.
