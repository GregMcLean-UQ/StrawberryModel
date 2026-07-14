import sqlite3

con = sqlite3.connect('Strawberry.db')
cur = con.cursor()
for simname in ['Cycle1_Oct25_Albion', 'Cycle1_Oct25_SanAndreas', 'Cycle2_Dec27_Albion', 'Cycle2_Dec27_SanAndreas',
                 'Cycle3_Feb28_Albion', 'Cycle3_Feb28_SanAndreas', 'AusQld_Nambour_2023', 'AusQld_Nambour_2024']:
    cur.execute('select ID from _Simulations where Name=?', (simname,))
    row = cur.fetchone()
    if not row:
        print(f"{simname}: NOT FOUND")
        continue
    simid = row[0]
    cur.execute('select DAS, Phase from DailyReport where SimulationID=? order by DAS', (simid,))
    rows = cur.fetchall()
    prev = None
    mat_das = None
    for das, phase in rows:
        if phase != prev:
            prev = phase
            if phase == 'Maturity to Harvest' and mat_das is None:
                mat_das = das
    print(f"{simname}: Maturity at DAS={mat_das}")
