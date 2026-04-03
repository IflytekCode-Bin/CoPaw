#!/usr/bin/env python3
"""Set public policy for all CoPaw buckets."""
import json
from minio import Minio

client = Minio('localhost:9000', access_key='minioadmin', secret_key='minioadmin123', secure=False)

buckets = [
    'copaw-127-0-0-1-8085-default',
    'copaw-127-0-0-1-8085-copaw-qa-agent-0-1beta1',
    'copaw-127-0-0-1-8085-shared',
]

for bucket in buckets:
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
        print(f"✓ {bucket}")
    except Exception as e:
        print(f"✗ {bucket}: {e}")

print("\nDirect access URLs:")
print("http://localhost:9000/copaw-127-0-0-1-8085-default/realtime/agent.json")
print("http://localhost:9000/copaw-127-0-0-1-8085-default/change/chats.json")
print("http://localhost:9000/copaw-127-0-0-1-8085-shared/config/process_config.json")