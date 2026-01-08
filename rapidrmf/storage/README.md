# Storage Backends

RapidRMF stores evidence in a vault per enclave. Two backends are supported:

- MinIO (on-prem/edge)
- S3 (GovCloud IL5/IL6)

## MinIO configuration example
```yaml
environments:
  edge:
    storage:
      type: minio
      endpoint: localhost:9000
      bucket: rapidrmf-evidence
      access_key: minioadmin
      secret_key: minioadmin
      secure: false
```
Run MinIO locally:
```powershell
docker run -d -p 9000:9000 -p 9001:9001 ^
  -e MINIO_ROOT_USER=minioadmin ^
  -e MINIO_ROOT_PASSWORD=minioadmin ^
  --name rapidrmf-minio minio/minio server /data --console-address ":9001"
```

## S3 configuration example
```yaml
environments:
  govcloud-il5:
    storage:
      type: s3
      region: us-gov-west-1
      bucket: govcloud-evidence
      profile: default  # or role-based access
```

## Path layout in vaults
```
<bucket>/
  terraform/...
  github/...
  gitlab/...
  argo/...
  azure/...
  manifests/{env}/<collector>-manifest.json
```

## Practices
- Use separate buckets or prefixes per enclave to avoid cross-enclave leakage
- Enable server-side encryption on S3; MinIO supports SSE if configured
- Keep credentials out of repos; prefer profiles or environment variables
- Periodically verify manifests with stored SHA256 hashes to detect tampering
