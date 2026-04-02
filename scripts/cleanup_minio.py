#!/usr/bin/env python3
"""Clean up all CoPaw buckets from MinIO."""
from minio import Minio

client = Minio(
    'localhost:9000',
    access_key='minioadmin',
    secret_key='minioadmin123',
    secure=False
)

# List all buckets
buckets = list(client.list_buckets())
print(f'Found {len(buckets)} buckets')

# Delete all objects and buckets
for b in buckets:
    bucket_name = b.name
    print(f'\nDeleting bucket: {bucket_name}')
    
    # Remove all objects first
    objects = list(client.list_objects(bucket_name, recursive=True))
    for obj in objects:
        try:
            client.remove_object(bucket_name, obj.object_name)
            print(f'  Removed: {obj.object_name}')
        except Exception as e:
            print(f'  Error removing {obj.object_name}: {e}')
    
    # Remove bucket
    try:
        client.remove_bucket(bucket_name)
        print(f'  ✓ Bucket {bucket_name} deleted')
    except Exception as e:
        print(f'  Error deleting bucket {bucket_name}: {e}')

print('\n=== Cleanup complete ===')

# Verify
buckets = list(client.list_buckets())
print(f'Remaining buckets: {len(buckets)}')
for b in buckets:
    print(f'  {b.name}')