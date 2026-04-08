#!/usr/bin/env python3
"""
Transform FishStatJ CSVs to compact JSON for global aquaculture visualization.
Run from project root: py scripts/transform_global.py
Output: data/global_aquaculture.json
"""
import csv, json, re, os

QTY_CSV = 'FishStatJ/Global aquaculture quantity.csv'
VAL_CSV = 'FishStatJ/Global aquaculture value.csv'
OUT     = 'data/global_aquaculture.json'

# Species group classification by keyword matching
PLANT_KW = ['seaweed','algae','nori','wakame','kombu','laminaria','undaria',
            'porphyra','gracilaria','eucheuma','kappaphycus','sargassum',
            'caulerpa','spirulina','chlorella','kelp','carrageen','dulse',
            'fucus','ascophyllum','macroalga','agar weed']
CRUST_KW = ['shrimp','prawn','crab','lobster','crayfish','crawfish',
            'crustacean','langoustine','scampi','kuruma','krill','barnacle']
MOLLU_KW = ['oyster','clam','mussel','scallop','abalone','squid','octopus',
            'cuttlefish','cockle','whelk','snail','periwinkle','conch',
            'mollusc','bivalve','geoduck','ark shell','razor','venus']
OTHER_KW = ['sea cucumber','trepang','sea urchin','echinoderm','holothurian',
            'frog','turtle','crocodile','alligator','caiman','sponge',
            'jellyfish','sea squirt','tunicate','beche']

def classify(name):
    n = name.lower()
    if any(k in n for k in PLANT_KW): return 3   # Aquatic plant
    if any(k in n for k in CRUST_KW): return 1   # Crustacean
    if any(k in n for k in MOLLU_KW): return 2   # Mollusc
    if any(k in n for k in OTHER_KW): return 4   # Other
    return 0                                        # Fish

def get_year_cols(header):
    cols = []
    for i, h in enumerate(header):
        m = re.match(r'\[(\d{4})\]', h)
        if m:
            cols.append((i, int(m.group(1))))
    return cols

def read_csv(path):
    with open(path, encoding='latin-1') as f:
        rdr = csv.reader(f)
        hdr = next(rdr)
        ycols = get_year_cols(hdr)
        years = [y for _, y in ycols]
        rows = []
        for row in rdr:
            if not row or len(row) < 6 or not row[0].strip():
                continue
            vals = []
            for idx, _ in ycols:
                v = row[idx].strip() if idx < len(row) else ''
                try:
                    vals.append(0.0 if not v or v == '...' else float(v))
                except:
                    vals.append(0.0)
            rows.append({
                'country': row[0].strip(),
                'species': row[1].strip(),
                'env':     row[3].strip(),
                'vals':    vals,
            })
        return years, rows

print('Reading quantity CSV...')
qty_years, qty_rows = read_csv(QTY_CSV)
print('Reading value CSV...')
val_years, val_rows = read_csv(VAL_CSV)
print(f'Qty: {len(qty_rows)} rows ({qty_years[0]}-{qty_years[-1]})')
print(f'Val: {len(val_rows)} rows ({val_years[0]}-{val_years[-1]})')

# Build value lookup: (country, species) -> values array
val_lut = {(r['country'], r['species']): r['vals'] for r in val_rows}

ENV_MAP = {'Freshwater': 0, 'Marine': 1, 'Brackishwater': 2}

countries = {}
skipped = 0

for row in qty_rows:
    c = row['country']
    s = row['species']
    if not c or not s:
        continue
    q = row['vals']
    if all(v == 0 for v in q):
        skipped += 1
        continue

    v = val_lut.get((c, s), [0.0] * len(val_years))

    if c not in countries:
        countries[c] = {'t': [0.0] * len(qty_years), 's': []}

    for i, val in enumerate(q):
        countries[c]['t'][i] += val

    countries[c]['s'].append({
        'n': s,
        'g': classify(s),
        'e': ENV_MAP.get(row['env'], 0),
        'q': [round(x) for x in q],
        'v': [round(x, 1) for x in v],
    })

# Round country totals
for cd in countries.values():
    cd['t'] = [round(x) for x in cd['t']]

result = {
    'qy': qty_years,   # quantity years (1950-2024)
    'vy': val_years,   # value years (1984-2024)
    'g': ['Fish', 'Crustacean', 'Mollusc', 'Aquatic plant', 'Other'],
    'e': ['Freshwater', 'Marine', 'Brackishwater'],
    'c': countries,
}

os.makedirs('data', exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(result, f, separators=(',', ':'))

sz = os.path.getsize(OUT) / 1024 / 1024
total_sp = sum(len(cd['s']) for cd in countries.values())
print(f'\nWritten: {OUT}')
print(f'Size: {sz:.2f} MB')
print(f'Countries with data: {len(countries)}')
print(f'Species entries: {total_sp}')
print(f'All-zero rows skipped: {skipped}')
