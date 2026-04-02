#!/usr/bin/env python3
"""Enable backup in config.json."""
import json
from pathlib import Path

config_path = Path.home() / '.copaw/config.json'
with open(config_path) as f:
    config = json.load(f)

# Add storage configuration
config['storage'] = {
    'backup': {
        'enabled': True,
        'endpoint': 'localhost:9000',
        'secure': False,
        'retention_days': 30,
        'dedup_enabled': True
    }
}

# Update last_api to current port (8085)
config['last_api'] = {'host': '127.0.0.1', 'port': 8085}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print('Updated config.json:')
print('  - backup.enabled = True')
print('  - last_api = 127.0.0.1:8085')
print(f'  - Config path: {config_path}')