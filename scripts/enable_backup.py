#!/usr/bin/env python3
"""Enable backup in config.json for specified port."""
import json
import sys
from pathlib import Path

def get_config_path(port: int = None) -> Path:
    """Get config path for specified port."""
    if port is None:
        # Default config
        return Path.home() / '.copaw/config.json'
    
    # Port-specific config
    if port == 8085:
        return Path.home() / '.copaw_dev_server_8085/config.json'
    elif port == 8088:
        return Path.home() / '.copaw/config.json'
    elif port == 8089:
        return Path.home() / '.copaw_dev/config.json'
    elif port == 8090:
        return Path.home() / '.copaw_ops/config.json'
    elif port == 8091:
        return Path.home() / '.copaw_test/config.json'
    else:
        return Path.home() / f'.copaw_{port}/config.json'

def enable_backup(port: int = None) -> None:
    """Enable backup in config file."""
    config_path = get_config_path(port)
    
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return
    
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
    
    # Update last_api if port specified
    if port:
        config['last_api'] = {'host': '127.0.0.1', 'port': port}
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Updated {config_path}:")
    print(f"  - backup.enabled = True")
    if port:
        print(f"  - last_api = 127.0.0.1:{port}")

if __name__ == '__main__':
    port = None
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)
    
    enable_backup(port)
    
    if port:
        print(f"\nNow restart port {port} to apply changes:")
        print(f"  /Data/CodeBase/iflycode/CoPaw/restart_worker.sh restart {port}")