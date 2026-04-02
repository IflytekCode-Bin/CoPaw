#!/usr/bin/env python3
"""Clean up MinIO buckets and show current state."""
from minio import Minio

client = Minio(
    'localhost:9000',
    access_key='minioadmin',
    secret_key='minioadmin123',
    secure=False
)

# List all buckets
print('=== Current Buckets ===')
buckets = list(client.list_buckets())
for b in buckets:
    print(f'  {b.name}')

# Show objects in each bucket
for b in buckets:
    print(f'\n=== {b.name} ===')
    objects = list(client.list_objects(b.name, recursive=True))
    for obj in objects[:5]:  # Show first 5
        print(f'  {obj.object_name} ({obj.size} bytes)')
    if len(objects) > 5:
        print(f'  ... and {len(objects) - 5} more objects')
    print(f'  Total: {len(objects)} objects')