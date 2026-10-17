import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_nonmem_dataset as B

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

WANT = ['Primus/EXP_SEVO', 'BIS/BIS', 'BIS/SQI', 'Primus/ETCO2',
        'Solar8000/VENT_MV', 'Orchestra/RFTN20_CE']
WARMUP = 45.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--grid', type=int, default=30, help='격자 초')
    ap.add_argument('--sqi-min', type=float, default=50)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cache = os.path.join(a.work, 'cache')

    trks = pd.read_csv(os.path.join(a.work, 'trks.csv'))
    cases = pd.read_csv(os.path.join(a.work, 'cases.csv')).set_index('caseid')
    sel = pd.read_csv(os.path.join(os.path.dirname(a.out), 'sevo_ke0_analysis_set.csv'), index_col='caseid') \
        if os.path.exists(os.path.join(os.path.dirname(a.out), 'sevo_ke0_analysis_set.csv')) \
        else pd.read_csv('sevo_ke0_analysis_set.csv', index_col='caseid')
    ids = list(sel.index)
    print('cases:', len(ids), sel.approach.value_counts().to_dict(), flush=True)
    tid = {(r.caseid, r.tname): r.tid for r in trks.itertuples() if r.tname in WANT}
    G = a.grid

    parts, summ = [], []
    for cid in ids:
        c = cases.loc[cid]
        sv = B.fetch(tid[(cid, 'Primus/EXP_SEVO')], cache).dropna()
        tmax = int(sv.Time.max()) + 1
        et = pd.Series(B.sec_series(sv, tmax)).ffill().fillna(0).values
        on = et >= 0.3
        i0 = int(np.argmax(on)); i1 = len(on) - 1 - int(np.argmax(on[::-1]))
        start = i0 + int(WARMUP * 60)
        if i1 - start < 1800:
            continue
        sl = slice(start, i1 + 1)
        n = (i1 + 1 - start) // G
        if n < 60:
            continue

        def get(name, fill_zero=False, limit=None):
            if (cid, name) not in tid:
                return np.full(i1 + 1 - start, np.nan)
            s_ = pd.Series(B.sec_series(B.fetch(tid[(cid, name)], cache), tmax))
            s_ = s_.ffill(limit=limit) if limit else s_.ffill()
            v = s_.values[sl]
            return np.nan_to_num(v, nan=0.0) if fill_zero else v

        def bins(arr, fn):
            x = np.asarray(arr, dtype=float)[:n * G].reshape(n, G)
            with np.errstate(all='ignore'):
                return fn(x, axis=1)

        ets = et[sl]
        bis = get('BIS/BIS'); sqi = get('BIS/SQI')
        co2 = get('Primus/ETCO2'); mv = get('Solar8000/VENT_MV')
        remi = get('Orchestra/RFTN20_CE', fill_zero=True)

        df = pd.DataFrame({
            'ID': cid,
            'TIME': np.round((np.arange(n) * G + G) / 60.0, 3),
            'DV': np.round(bins(bis, np.nanmedian), 2),
            'SQI': np.round(bins(sqi, np.nanmin), 1),
            'ETSEVO': np.round(bins(ets, lambda x, axis: x[:, -1]), 4),
            'CEREMI': np.round(bins(remi, lambda x, axis: x[:, -1]), 3),
            'ETCO2': np.round(bins(co2, np.nanmedian), 1),
            'MV': np.round(bins(mv, np.nanmedian), 2),
        })
        df.loc[(df.DV <= 0) | (df.DV > 100) | ~(df.SQI >= a.sqi_min), 'DV'] = np.nan
        df['MDV'] = np.where(df.DV.notna(), 0, 1)
        df['EVID'] = 0
        df['ET0'] = float(ets[0])
        df['AGE'] = c.age; df['SEX'] = int(c.sex == 'M'); df['WT'] = c.weight; df['HT'] = c.height
        df['BMI'] = round(c.weight / (c.height / 100) ** 2, 2)
        df['ASA'] = c.asa if pd.notna(c.asa) else -99
        df['LAP'] = int(sel.loc[cid, 'approach'] == 'Laparoscopic')
        df['HASREMI'] = int((cid, 'Orchestra/RFTN20_CE') in tid)
        parts.append(df)
        summ.append(dict(caseid=cid, n_rows=len(df), n_obs=int((df.MDV == 0).sum()),
                         maint_min=len(df) * G / 60, et0=df.ET0.iloc[0],
                         et_min=df.ETSEVO.min(), et_max=df.ETSEVO.max(),
                         bis_median=df.DV.median(), lap=df.LAP.iloc[0], remi=df.HASREMI.iloc[0]))
        if len(parts) % 40 == 0:
            print('  processed', len(parts), flush=True)

    full = pd.concat(parts, ignore_index=True)
    cols = ['ID', 'TIME', 'DV', 'MDV', 'EVID', 'ETSEVO', 'ET0', 'SQI', 'CEREMI', 'ETCO2', 'MV',
            'AGE', 'SEX', 'WT', 'HT', 'BMI', 'ASA', 'LAP', 'HASREMI']
    full = full[cols].astype(object).where(pd.notna(full[cols]), '.')
    out = os.path.join(a.out, f'sevo_ke0_maintenance_{G}s.csv')
    full.to_csv(out, index=False)
    S = pd.DataFrame(summ).set_index('caseid')
    S.to_csv(os.path.join(a.out, 'sevo_ke0_case_summary.csv'), encoding='utf-8-sig')
    print('\nsaved', out)
    print('rows', len(full), 'cases', full.ID.nunique(), 'obs', int((full.MDV == 0).sum()))
    print('obs/case median %.0f, maint_min median %.0f' % (S.n_obs.median(), S.maint_min.median()))
    print('ET range: %.2f - %.2f, ET0 median %.2f' % (S.et_min.min(), S.et_max.max(), S.et0.median()))
    print('lap %d / open %d, remi %d' % (S.lap.sum(), (S.lap == 0).sum(), S.remi.sum()))


if __name__ == '__main__':
    main()
