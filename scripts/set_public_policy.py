#!/usr/bin/env python3
"""Set public policy for MinIO bucket (for testing preview)."""
import json
from minio import Minio

client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin123', secure=False)

# Set public read policy for testing
bucket = 'copaw-127-0-0-1-8085-default'

policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": "*"},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{bucket}/*"]
        }
    ]
}

try:
    client.set_bucket_policy(bucket, json.dumps(policy))
    print(f"Set public read policy for {bucket}")
except Exception as e:
    print(f"Error: {e}")

# Verify by downloading without auth
import urllib.request
url = f"http://localhost:9000/{bucket}/realtime/agent.json"
try:
    response = urllib.request.urlopen(url)
    print(f"\nPublic access works! Content length: {len(response.read())}")
except Exception as e:
    print(f"\nPublic access failed: {e}")