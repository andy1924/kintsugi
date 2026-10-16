import os
import uuid
from pathlib import Path
from .config import DATA

class Store:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET')
        self.local = DATA / 'objects'
        self.local.mkdir(parents=True, exist_ok=True)
        if self.bucket:
            import boto3
            self.client = boto3.client('s3', endpoint_url=os.getenv('S3_ENDPOINT_URL') or None)
    def put(self, data: bytes, suffix: str) -> str:
        key = f'{uuid.uuid4().hex}.{suffix}'
        if self.bucket:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption='AES256')
        else:
            target = self.local / key
            temp = target.with_suffix('.tmp')
            temp.write_bytes(data)
            temp.replace(target)
        return key
    def get(self, key: str) -> bytes:
        if '/' in key or '..' in key: raise ValueError('Invalid object key')
        if self.bucket: return self.client.get_object(Bucket=self.bucket, Key=key)['Body'].read()
        return (self.local / key).read_bytes()
    def delete(self, key: str):
        if self.bucket: self.client.delete_object(Bucket=self.bucket, Key=key)
        else: (self.local / key).unlink(missing_ok=True)

store = Store()
