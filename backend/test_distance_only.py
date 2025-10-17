#!/usr/bin/env python3
"""
Test distance-only sorting for Tokyo Station
"""
import subprocess
import json

result = subprocess.run([
    'curl', '-s', '-X', 'POST', 'http://localhost:8001/api/plateau/search-by-address',
    '-H', 'Content-Type: application/json',
    '-d', json.dumps({'query': '東京駅', 'radius': 0.001, 'limit': 5})
], capture_output=True, text=True)

data = json.loads(result.stdout)
if data.get('success'):
    print('Buildings near Tokyo Station (distance-only sorting):')
    print('='*70)
    for i, b in enumerate(data['buildings'], 1):
        h = b.get('measured_height') or b.get('height') or 0
        d = b.get('distance_meters', 0)
        u = b.get('usage') or 'N/A'
        gml_id = b.get('gml_id', 'N/A')[:40]
        print(f'{i}. {h:6.1f}m tall, {d:5.1f}m away, usage={u}')
        print(f'   ID: {gml_id}...')
else:
    print('Error:', data.get('error'))
