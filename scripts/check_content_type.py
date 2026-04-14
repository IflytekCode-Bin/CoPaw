#!/usr/bin/env python3
"""Check MinIO object metadata."""
from minio import Minio

client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin123', secure=False)

# Check content-type of objects
objects = [
    ('copaw-127-0-0-1-8085-default', 'realtime/agent.json'),
    ('copaw-127-0-0-1-8085-default', 'realtime/MEMORY.md'),
    ('copaw-127-0-0-1-8085-default', 'change/chats.json'),
    ('copaw-127-0-0-1-8085-shared', 'config/process_config.json'),
]

for bucket, obj in objects:
    try:
        stat = client.stat_object(bucket, obj)
        print(f'{obj}:')
        print(f'  content-type: {stat.content_type}')
        print(f'  size: {stat.size}')
    except Exception as e:
        print(f'{obj}: ERROR - {e}')