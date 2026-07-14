import json, sys

total_sum = float(sys.argv[1])

BASE_RATIOS = {
    'FlowerInduction to Anthesis': 195.0/440.0,
    'Anthesis to FruitSet': 45.0/440.0,
    'FruitSet to GreenFruit': 80.0/440.0,
    'GreenFruit to Maturity': 120.0/440.0,
}

def find_path(node, name):
    if node.get('Name') == name:
        return node
    for c in node.get('Children', []) or []:
        r = find_path(c, name)
        if r:
            return r
    return None

d = json.load(open('Strawberry.apsimx.bak', encoding='utf-8'))
phen = find_path(d, 'Phenology')
for name, ratio in BASE_RATIOS.items():
    phase = find_path(phen, name)
    for c in phase['Children']:
        if c.get('Name') == 'Target':
            c['FixedValue'] = round(total_sum * ratio, 2)
            print(name, '->', c['FixedValue'])
json.dump(d, open('Strawberry.apsimx.bak', 'w', encoding='utf-8'), indent=2)
