import io
import os
import time

import numpy as np
import pandas as pd
import requests

BASE = 'https://api.vitaldb.net'


def fetch(tid_, cache):
    p = os.path.join(cache, f'{tid_}.csv')
    if os.path.exists(p):
        return pd.read_csv(p)
    for k in range(4):
        try:
            r = requests.get(f'{BASE}/{tid_}', timeout=180)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.to_csv(p, index=False)
            return df
        except Exception:
            time.sleep(2 + 3 * k)
    raise RuntimeError(f'download failed {tid_}')


def sec_series(df, tmax):
    g = np.full(tmax, np.nan)
    d = df.dropna()
    if d.empty:
        return g
    t = d['Time'].values.astype(int)
    v = d.iloc[:, 1].values
    m = (t >= 0) & (t < tmax)
    g[t[m]] = v[m]
    return g
