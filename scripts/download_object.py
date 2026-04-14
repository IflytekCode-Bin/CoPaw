#!/usr/bin/env python3
"""Download and display MinIO object content."""
from minio import Minio

client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin123', secure=False)

# Download and show first 500 chars
bucket = 'copaw-127-0-0-1-8085-default'
obj = 'realtime/agent.json'

try:
    response = client.get_object(bucket, obj)
    content = response.read().decode('utf-8')
    print(f'=== {obj} (first 500 chars) ===')
    print(content[:500])
    print('...')
except Exception as e:
    print(f'ERROR: {e}')