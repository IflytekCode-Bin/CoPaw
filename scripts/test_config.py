#!/usr/bin/env python3
"""Test config loading for backup."""
import sys
sys.path.insert(0, '/Data/CodeBase/iflycode/CoPaw/src')

from copaw.config.utils import load_config

config = load_config()
print('config.storage:', config.storage)
print('config.storage.backup:', config.storage.backup)
print('config.storage.backup.enabled:', config.storage.backup.enabled)
print('config.last_api:', config.last_api)