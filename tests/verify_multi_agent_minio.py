#!/usr/bin/env python3
"""Verify MinIO multi-agent backup."""

from minio import Minio

client = Minio("localhost:9000", "minioadmin", "minioadmin123", secure=False)

# 列出所有 copaw buckets
print("=== CoPaw Buckets ===")
for bucket in client.list_buckets():
    if bucket.name.startswith("copaw"):
        objects = list(client.list_objects(bucket.name, recursive=True))
        total_size = sum(o.size or 0 for o in objects)
        print(f"{bucket.name}: {len(objects)} objects, {total_size/1024:.1f} KB")

# 详细查看各 bucket 内容
print("\n=== Bucket Details ===")
for bucket_name in ["copaw-shared", "copaw-default", "copaw-ms7xfg"]:
    print(f"\n{bucket_name}:")
    try:
        objects = list(client.list_objects(bucket_name, recursive=True))
        for obj in objects[:15]:
            print(f"  {obj.object_name}: {obj.size} bytes")
        if len(objects) > 15:
            print(f"  ... and {len(objects) - 15} more")
    except Exception as e:
        print(f"  Error: {e}")