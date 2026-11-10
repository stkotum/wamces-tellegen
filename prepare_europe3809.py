#!/usr/bin/env python3
"""Prepare the European 3809-bus example case from its two Zenodo records.

The network and line ratings come from PanTaGruEl. The solved AC operating
point comes from WAMCES. SOURCE_DIR holds wamces_model.zip, raw_csv_data.zip
and pantagruel.zip. The script checks each zip against a pinned SHA-256. It
reads the zips as data and executes nothing from them.

OUT_DIR receives europe3809.m, europe3809_buses.csv and
europe3809_ATTRIBUTION.txt. Reading the stored solution needs scipy. If the
tellegen wheel is installed, the script also solves the case and compares.
"""
import argparse
import csv
import hashlib
import io
import math
from pathlib import Path
import re
import zipfile

from scipy.io import loadmat

SOURCES = {
    'wamces_model.zip': '251b046e842163d378ffeccaacd2238d5a7556d005d7b23472ad5dd72ffb48f8',
    'raw_csv_data.zip': '75bd40cd1f6293e97104504da266a3b37aed47e793c8d1d92810e0c269afad51',
    'pantagruel.zip': 'e0b38e1e62fea6fe9a2d962ab66a47146d69b6651d8d3c3033a92b423db04ce5',
}
REFERENCE_BUS = 355  # WAMCES has five slack buses. The other four become PV buses.
BASE_MVA = 100.0

ATTRIBUTION = """\
European 3809-bus example case for tellegen.

Derived from two datasets. Both are licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/).

1. R. Musca, "WAMCES - Wide-Area Monitoring and Control of the European power
   System". Zenodo record 18721887, https://doi.org/10.5281/zenodo.18721887.
   Companion paper: R. Musca, M. G. Ippolito, E. Riva Sanseverino,
   Electricity 7(2): 28, 2026, https://doi.org/10.3390/electricity7020028.
   Used: buses, lines, machine ratings and the stored power flow solution
   (powerflow_sol.mat).
2. L. Pagnier, P. Jacquod, "PanTaGruEl - a pan-European transmission grid and
   electricity generation model". Zenodo record 2642175,
   https://doi.org/10.5281/zenodo.2642175. Its authors ask for two citations:
   L. Pagnier, P. Jacquod, PLOS ONE 14(3): e0213550, 2019,
   https://doi.org/10.1371/journal.pone.0213550.
   M. Tyloo, L. Pagnier, P. Jacquod, Science Advances 5(11): eaaw8359, 2019,
   https://doi.org/10.1126/sciadv.aaw8359.
   Used: line ratings, generator costs, bus names and coordinates.
   PanTaGruEl builds on the GridKit extract of the ENTSO-E map by B. Wiegmans,
   https://doi.org/10.5281/zenodo.55853.

Changes made by prepare_europe3809.py
(https://github.com/stkotum/wamces-tellegen):
- Bus {ref} is the only reference bus. The other four WAMCES slack buses are
  PV buses at their solved output.
- A generator rating rises to the solved apparent power divided by 0.8 where
  that exceeds the stored rating. wamces_script.m does the same.
- Pmax and the Q limits come from the machine rating. Pmin is 0.
- The bus area field holds a country number. The case file header lists them.
- Line ratings, costs, names and coordinates are joined from PanTaGruEl by row
  order. The script checks that both records list the same buses, branches
  and generators in the same order.

This is a research test grid. It is not a validated model of the real
European grid. The creators of both records and ENTSO-E have not reviewed or
endorsed this derivative.
""".format(ref=REFERENCE_BUS)


def require(ok, message):
    if not ok:
        raise SystemExit(message)


def read_zip(path, digest):
    require(path.is_file(), f'{path}: not found. README.md lists the downloads.')
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == digest, f'{path.name}: SHA-256 does not match the pinned Zenodo file.')
    return zipfile.ZipFile(io.BytesIO(data))


def read_csv(archive, name):
    with archive.open(name) as handle:
        return list(csv.DictReader(io.TextIOWrapper(handle, 'utf-8'), skipinitialspace=True))


def matrix(text, name):
    body = re.search(r'mpc\.' + name + r'\s*=\s*\[(.*?)\];', text, re.S).group(1)
    lines = (line.split('%')[0] for line in body.replace(';', '\n').splitlines())
    return [[float(v) for v in line.split()] for line in lines if line.strip()]


def rows(values, ints):
    return '\n'.join(
        '\t' + '\t'.join(str(int(v)) if j in ints else repr(float(v)) for j, v in enumerate(row)) + ';'
        for row in values)


def main(source, out):
    model = read_zip(source / 'wamces_model.zip', SOURCES['wamces_model.zip'])
    raw = read_zip(source / 'raw_csv_data.zip', SOURCES['raw_csv_data.zip'])
    pan = read_zip(source / 'pantagruel.zip', SOURCES['pantagruel.zip'])

    pf = loadmat(io.BytesIO(model.read('powerflow_sol.mat')))['bus_results']
    buses = read_csv(raw, 'data_bus.csv')
    lines = read_csv(raw, 'data_lin.csv')
    machines = read_csv(raw, 'data_sm.csv')
    places = read_csv(pan, 'pantagruel_csv/buses.csv')
    case = pan.read('pantagruel_case.m').decode('utf-8')
    pan_gen, pan_branch, gencost = (matrix(case, n) for n in ('gen', 'branch', 'gencost'))

    ids = [int(b['ID']) for b in buses]
    require(ids == list(range(1, len(ids) + 1)) == [int(r[0]) for r in pf] == [int(p['ID']) for p in places],
            'The records list different buses.')
    require([int(m['BusID']) for m in machines] == [int(g[0]) for g in pan_gen] and len(gencost) == len(machines),
            'The records list different generators.')
    require([(int(l['ID1']), int(l['ID2']), float(l['R']), float(l['X'])) for l in lines]
            == [(int(r[0]), int(r[1]), r[2], r[3]) for r in pan_branch],
            'The records list different branches.')
    require(all(r[4] == 0 and r[5] == 0 for r in pf if r[1] == 3), 'The solution has generation at a PQ bus.')

    countries = sorted({b['Country'] for b in buses})
    bus_rows = []
    for b, r in zip(buses, pf):
        kind = {1: 3, 2: 2, 3: 1}[int(r[1])]  # WAMCES 1 slack, 2 PV, 3 PQ
        if kind == 3 and int(b['ID']) != REFERENCE_BUS:
            kind = 2
        bus_rows.append([b['ID'], kind, r[6] * BASE_MVA, r[7] * BASE_MVA, b['Gshu'], b['Bshu'],
                         countries.index(b['Country']) + 1, r[2], math.degrees(r[3]),
                         b['Vr'], 1, 1.1, 0.9])
    require(sum(row[1] == 3 for row in bus_rows) == 1, f'Bus {REFERENCE_BUS} is not a WAMCES slack bus.')

    gen_rows = []
    for m in machines:
        r = pf[int(m['BusID']) - 1]
        pg, qg = r[4] * BASE_MVA, r[5] * BASE_MVA
        rating = max(float(m['Sr']), math.hypot(pg, qg) / 0.8)
        gen_rows.append([m['BusID'], pg, qg, rating, -rating, r[2], rating, 1, rating, 0])
    branch_rows = [[l['ID1'], l['ID2'], l['R'], l['X'], l['B'], p[5], 0, 0, l['Tap'], l['PhaseShift'], 1, -360, 360]
                   for l, p in zip(lines, pan_branch)]

    area_names = ', '.join(f'{i} {c}' for i, c in enumerate(countries, 1))
    names = '\n'.join("\t'" + p['Name'].replace("'", "''") + "';" for p in places)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'europe3809.m').write_text(
        'function mpc = europe3809\n'
        + ''.join('% ' + line + '\n' if line else '%\n' for line in ATTRIBUTION.splitlines())
        + f'%\n% Bus areas: {area_names}.\n\n'
        + f"mpc.version = '2';\nmpc.baseMVA = {BASE_MVA:g};\n"
        + 'mpc.bus = [\n' + rows(bus_rows, {0, 1, 6, 10}) + '\n];\n'
        + 'mpc.gen = [\n' + rows(gen_rows, {0, 7}) + '\n];\n'
        + 'mpc.branch = [\n' + rows(branch_rows, {0, 1, 10}) + '\n];\n'
        + 'mpc.gencost = [\n' + rows(gencost, {0, 3}) + '\n];\n'
        + 'mpc.bus_name = {\n' + names + '\n};\n', encoding='utf-8', newline='\n')
    with open(out / 'europe3809_buses.csv', 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(['bus_i', 'lat', 'lon'])
        writer.writerows([p['ID'], p['Latitude'], p['Longitude']] for p in places)
    (out / 'europe3809_ATTRIBUTION.txt').write_text(ATTRIBUTION, encoding='utf-8', newline='\n')
    print(f'wrote {len(bus_rows)} buses, {len(branch_rows)} branches, {len(gen_rows)} generators to {out}')
    check(out / 'europe3809.m', pf)


def check(path, pf):
    """Solve the written case from a flat start and compare with the stored WAMCES solution."""
    try:
        import tellegen
    except ImportError:
        print('tellegen is not installed. The power flow check was skipped.')
        return
    case = tellegen.load(path)
    case.formulation = 'acpf'
    result = case.solve()
    dvm = max(abs(x['value'] - r[2]) for x, r in zip(result['vm'], pf))
    dva = max(abs(x['value'] - r[3]) for x, r in zip(result['va'], pf))
    print(f'AC power flow: {result["status"]}, max |dVm| {dvm:.1e} pu, max |dVa| {dva:.1e} rad')
    require(result['status'] == 'feasible' and dvm < 1e-6 and dva < 1e-6,
            'The AC power flow does not match the stored WAMCES solution. The written files are unverified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path, metavar='SOURCE_DIR')
    parser.add_argument('out', type=Path, metavar='OUT_DIR')
    args = parser.parse_args()
    main(args.source, args.out)
