#!/usr/bin/env python3
"""Verify MinIO backup."""

from minio import Minio

client = Minio("localhost:9000", "minioadmin", "minioadmin123", secure=False)

# 列出 copaw-default bucket 中的对象
objects = list(client.list_objects("copaw-default", recursive=True))
print(f"Total objects: {len(objects)}")

total_size = 0
for obj in objects[:30]:
    print(f"{obj.object_name}: {obj.size} bytes")
    total_size += obj.size or 0

print(f"\nTotal size: {total_size} bytes ({total_size/1024:.2f} KB)")