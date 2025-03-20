# IT Assets Kubernetes Kustomize overlay configuration

Declarative management of IT Assets Kubernetes resources using Kustomize.

## How to use

Within an overlay directory, create a `.env` file to contain required secret
values in the format KEY=value (i.e. `overlays/uat/.env`). Required keys:

    DATABASE_URL
    SECRET_KEY
    ADMIN_EMAILS
    EMAIL_HOST
    AZURE_CONNECTION_STRING
    AZURE_TENANT_ID
    MS_GRAPH_API_CLIENT_ID
    MS_GRAPH_API_CLIENT_SECRET
    ASCENDER_DEACTIVATE_EXPIRED
    ASCENDER_CREATE_AZURE_AD
    ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS
    FOREIGN_DB_HOST
    FOREIGN_DB_PORT
    FOREIGN_DB_NAME
    FOREIGN_DB_USERNAME
    FOREIGN_DB_PASSWORD
    FOREIGN_SCHEMA
    FOREIGN_SERVER
    FOREIGN_TABLE
    FOREIGN_TABLE_CC_MANAGER
    FRESHSERVICE_ENDPOINT
    FRESHSERVICE_API_KEY
    AZURE_ACCOUNT_NAME
    AZURE_ACCOUNT_KEY
    AZURE_CONTAINER
    ASCENDER_SFTP_HOSTNAME
    ASCENDER_SFTP_PORT
    ASCENDER_SFTP_USERNAME
    ASCENDER_SFTP_PASSWORD
    ASCENDER_SFTP_DIRECTORY
    POSTGRES_PASSWORD
    GEOSERVER_URL
    REDIS_CACHE_HOST
    API_RESPONSE_CACHE_SECONDS
    SENTRY_DSN
    SENTRY_ENVIRONMENT
    SENTRY_SAMPLE_RATE
    SENTRY_TRANSACTION_SAMPLE_RATE
    SENTRY_PROFILES_SAMPLE_RATE
    SENTRY_CRON_CHECK_ASCENDER
    SENTRY_CRON_CHECK_AZURE
    SENTRY_CRON_CHECK_ONPREM

Review the built resource output using `kustomize`:

```bash
kustomize build kustomize/overlays/uat/ | less
```

Run `kubectl` with the `-k` flag to generate resources for a given overlay:

```bash
kubectl apply -k kustomize/overlays/uat --namespace sss --dry-run=client
```

## References

- <https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/>
- <https://github.com/kubernetes-sigs/kustomize>
- <https://github.com/kubernetes-sigs/kustomize/tree/master/examples>
