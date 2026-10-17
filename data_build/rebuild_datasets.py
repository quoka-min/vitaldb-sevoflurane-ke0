import argparse
import io
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'data')
BASE = 'https://api.vitaldb.net'
COHORTS = {
    'derivation': ('caseids_derivation_n268.csv', 'sevo_ke0_maint_cov_30s_n268.csv', dict(mremi_digits=3, ffm_bmi='unrounded')),
    'external': ('caseids_external_n179.csv', 'sevo_ke0_ext_colorectal_30s.csv', dict(mremi_digits=4, ffm_bmi='column')),
}
CORRECTIONS = [
    ('external', 3128, '7.0', 'ETSEVO', '11.3', '1.35'),
]
SUBSETS = {
    'sensitivity': ('derivation', 'caseids_sensitivity_n213.csv', 'sevo_ke0_maint_cov_30s_sens_n213.csv'),
}
COLS = ['ID', 'TIME', 'DV', 'MDV', 'EVID', 'ETSEVO', 'ET0', 'SQI', 'CEREMI', 'ETCO2', 'MV', 'AGE', 'SEX', 'WT', 'HT', 'BMI',
        'ASA', 'LAP', 'HASREMI', 'MREMI', 'MCO2', 'MMV', 'FFM']


def get_list(name, work):
    p = os.path.join(work, name + '.csv')
    if not os.path.exists(p):
        r = requests.get(f'{BASE}/{name}', timeout=600)
        r.raise_for_status()
        pd.read_csv(io.StringIO(r.text)).to_csv(p, index=False)
    return p


def add_covariates(d, mremi_digits, ffm_bmi):
    x = d.replace('.', np.nan)
    for c in ['CEREMI', 'ETCO2', 'MV', 'WT', 'HT', 'BMI', 'SEX', 'HASREMI']:
        x[c] = pd.to_numeric(x[c])
    g = x.groupby('ID')
    mre = g.CEREMI.median().fillna(0); mre[g.HASREMI.first() == 0] = 0
    f = g.first()
    bmi = f.BMI if ffm_bmi == 'column' else f.WT / (f.HT / 100) ** 2
    ffm = np.where(f.SEX == 1, 9.27e3 * f.WT / (6.68e3 + 216 * bmi), 9.27e3 * f.WT / (8.78e3 + 244 * bmi))
    add = pd.DataFrame({'MREMI': mre.round(mremi_digits), 'MCO2': g.ETCO2.median().round(2), 'MMV': g.MV.median().round(3), 'FFM': np.round(ffm, 2)}, index=f.index)
    d = d.merge(add, left_on='ID', right_index=True, how='left')
    d = d[COLS].astype(object).where(lambda z: z.notna(), '.')
    return d


def main():
    ap = argparse.ArgumentParser(description='Rebuild the analysis data sets from the VitalDB API.')
    ap.add_argument('--work', required=True, help='working folder for downloaded track lists and tracks')
    ap.add_argument('--out', default=os.path.join(HERE, 'output'), help='folder for the rebuilt CSV files')
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    os.makedirs(a.out, exist_ok=True)
    cases_csv = get_list('cases', a.work)
    trks_csv = get_list('trks', a.work)
    cases = pd.read_csv(cases_csv).set_index('caseid')

    built = {}
    for name, (idfile, outfile, cov) in COHORTS.items():
        ids = pd.read_csv(os.path.join(DATA, idfile)).caseid.tolist()
        w = os.path.join(a.work, name)
        os.makedirs(os.path.join(w, 'cache'), exist_ok=True)
        os.makedirs(os.path.join(w, 'out'), exist_ok=True)
        shutil.copy(cases_csv, os.path.join(w, 'cases.csv'))
        shutil.copy(trks_csv, os.path.join(w, 'trks.csv'))
        approach = np.where(cases.loc[ids, 'approach'].values == 'Open', 'Open', 'Laparoscopic')
        pd.DataFrame({'caseid': ids, 'approach': approach}).to_csv(os.path.join(w, 'sevo_ke0_analysis_set.csv'), index=False)
        print('[%s] %d cases: downloading tracks and building the 30-s file' % (name, len(ids)), flush=True)
        subprocess.run([sys.executable, os.path.join(HERE, 'build_sevo_ke0_dataset.py'), '--work', w,
                        '--out', os.path.join(w, 'out'), '--grid', '30'], check=True)
        d = pd.read_csv(os.path.join(w, 'out', 'sevo_ke0_maintenance_30s.csv'), dtype=str, keep_default_na=False)
        missing = sorted(set(ids) - set(d.ID.astype(int)))
        if missing:
            sys.exit('[%s] not built: %s' % (name, missing))
        d = d[d.ID.astype(int).isin(ids)].reset_index(drop=True)
        for cohort, cid, t, col, old, new in CORRECTIONS:
            if cohort == name:
                m = (d.ID.astype(int) == cid) & (d.TIME == t) & (d[col] == old)
                print('[%s] correction ID %d TIME %s %s %s -> %s: %d row' % (name, cid, t, col, old, new, m.sum()))
                d.loc[m, col] = new
        d = add_covariates(d, **cov)
        d.to_csv(os.path.join(a.out, outfile), index=False)
        built[name] = d

    for name, (parent, idfile, outfile) in SUBSETS.items():
        ids = set(pd.read_csv(os.path.join(DATA, idfile)).caseid)
        d = built[parent]
        d[d.ID.astype(int).isin(ids)].to_csv(os.path.join(a.out, outfile), index=False)

    for outfile in [c[1] for c in COHORTS.values()] + [s[2] for s in SUBSETS.values()]:
        d = pd.read_csv(os.path.join(a.out, outfile), usecols=['ID', 'MDV'])
        print('%-40s %d patients, %d rows, %d BIS observations' % (outfile, d.ID.nunique(), len(d), (d.MDV == 0).sum()))


if __name__ == '__main__':
    main()
