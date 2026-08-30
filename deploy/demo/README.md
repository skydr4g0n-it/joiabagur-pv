# Demo environment — runbook

Everything needed to stand the isolated demonstration environment up from a
brand-new AWS account, populate it with the corpus, and hand out a public URL.

> **This environment is not production and cannot reach it.** It lives in a
> different AWS account, with its own Terraform state, its own image
> repositories, its own parameter prefix and its own deployment workflow. The
> shop's account is not referenced anywhere in it. See
> [`openspec/changes/add-ai-service-deployment/design.md`](../../openspec/changes/add-ai-service-deployment/design.md).

| Piece | Where |
|---|---|
| Infrastructure | [`terraform/demo/`](../../terraform/demo/) |
| Composition, four services | [`compose.demo.yaml`](../../compose.demo.yaml) |
| Reverse proxy | [`Caddyfile`](./Caddyfile) |
| Deployment script, runs on the host | [`deploy.sh`](./deploy.sh) |
| Workflow | [`.github/workflows/deploy-demo.yml`](../../.github/workflows/deploy-demo.yml) |
| Images | `backend/src/JoiabagurPV.API/Dockerfile.demo`, `ai-service/Dockerfile` |

---

## Two warnings, before anything else

**Never run `docker compose down -v` on this host.** The `-v` destroys named
volumes, and two of them matter:

- `jbg-demo-caddy-data` holds the **issued TLS certificate**. Let's Encrypt
  rate-limits *duplicate* certificates to **five per week** for the same set of
  names. Two careless redeployments in one week leave the demo without valid
  TLS until the limit resets — with no way to hurry it.
- `jbg-demo-pgdata` holds the **catalog and the vector index**. Recoverable
  from the dump, but that is an hour you did not plan for.

`deploy.sh` uses `up -d`, which recreates containers in place and leaves volumes
alone. Keep it that way.

**A deployed environment with an empty index passes every test.** It answers
200s, it serves a valid certificate, and assisted search finds nothing. That is
why the data path (§5 below) is part of the deployment and not an afterthought,
and why post-deployment verification fails on a document count of zero.

---

## 1. Account and prerequisites

> Account identifiers, the Identity Center portal URL and the state bucket name
> are **not written here**: this repository is public. Keep them in your own
> notes; `terraform output` reprints everything the workflow needs.

### 1.1 A dedicated member account

The demo runs in its **own AWS account**, created under AWS Organizations from
your management account. The specification only requires an account distinct
from the shop's, which a personal account already satisfies — so this is a
judgement call, made for three reasons:

- The demo publishes **a web server on the open Internet**, with a database
  holding real catalog prices and a GitHub-federated role that can create and
  destroy compute. In a dedicated account, an incident stays inside it.
- **Cost attribution is exact** with no tagging discipline: one filter by
  account in Cost Explorer. §12 of the design commits to reporting what this
  costs.
- The **OIDC provider is a singleton per account** (see [`iam.tf`](../../terraform/demo/iam.tf)).
  A virgin account is the case the module is written for.

The account itself is free; the ~20-25 USD/month is instance, disk and address.

```bash
aws organizations create-account \
  --email "<unique-root-email>" --account-name "<name>" \
  --iam-user-access-to-billing ALLOW

aws organizations list-create-account-status \
  --query 'CreateAccountStatuses[].[AccountName,State,AccountId,FailureReason]' \
  --output table
```

Asynchronous; poll until `SUCCEEDED` and keep the account id. **Closing an AWS
account takes 90 days**, so do not create one to try it out.

### 1.2 Access, without long-lived keys

Use **IAM Identity Center**, not IAM users: the credentials expire on their own,
and nothing lands on disk — the same principle the deployment follows for
secrets.

> **The trap that costs an hour.** An organization may already show an Identity
> Center instance that is an **account instance** — the kind an AWS managed
> application creates for itself. It looks identical in `list-instances` and is
> useless here. The tell is unambiguous:
>
> ```bash
> aws sso-admin list-permission-sets --instance-arn "$INSTANCE" --region <region>
> # ValidationException: Permission Sets are not enabled for this instance
> ```
>
> Permission sets are exactly what account instances lack. If it has no users
> and no applications, delete it with `aws sso-admin delete-instance` and enable
> an organization instance from the console.

In the management account, in the region you want:

1. **IAM Identity Center → Enable.** Choose **single-region**. Multi-region
   replicates your identity data to a second region and requires a
   customer-managed KMS key billed monthly — resilience nobody here needs. The
   primary region **cannot** be changed later; additional regions can be added.
2. **Users → Add user.** MFA is registered on first sign-in.
3. **Permission sets → Predefined → `AdministratorAccess`**, session duration
   **8 hours** — one hour turns a long `terraform apply` into a login loop.
   Total administrator is proportionate precisely because the account is
   dedicated and disposable.
4. **Assign the user to BOTH accounts** — the demo account to work in, and the
   management account so that organization tasks never need the root user again.

### 1.3 Local profiles

```ini
[sso-session jbg]
sso_start_url = https://<portal>.awsapps.com/start
sso_region = <identity-center-region>
sso_registration_scopes = sso:account:access

[profile jbg-demo]
sso_session = jbg
sso_account_id = <demo-account-id>
sso_role_name = <permission-set-name>
region = eu-west-1
output = json
ca_bundle = C:\Users\<you>\.aws\ca-bundle-norton.pem
```

`sso_region` and `region` are **independent**: the first is where Identity
Center lives, the second where the resources run. A portal in one region
managing workloads in another is ordinary.

> **`ca_bundle` is mandatory on the development machine used for C17.** Norton
> intercepts TLS with its own root CA, which sits in the Windows store but not
> in the CLI's bundled `certifi`. Without that line even `aws sso login` fails
> with `CERTIFICATE_VERIFY_FAILED`. It is the same cause that makes `uv` need
> `--system-certs` (see `CLAUDE.md`). Go-based tools — Terraform, Docker — read
> the Windows store and are unaffected. This is why `aws configure sso` is the
> wrong way to create these profiles: it does not write `ca_bundle`.

Then `aws sso login --profile jbg-demo`, and confirm with
`aws sts get-caller-identity --profile jbg-demo`.

### 1.4 State bucket

In the **demo** account, before `terraform init`:

```bash
aws s3api create-bucket --bucket <state-bucket> --region eu-west-1 \
  --create-bucket-configuration LocationConstraint=eu-west-1 --profile jbg-demo
aws s3api put-bucket-versioning --bucket <state-bucket> \
  --versioning-configuration Status=Enabled --profile jbg-demo
aws s3api put-public-access-block --bucket <state-bucket> --profile jbg-demo \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

Bucket names are **globally unique**; if the one in
[`backend.tf`](../../terraform/demo/backend.tf) is taken, suffix it with the
account id and update that file.

### 1.5 Local tooling

AWS CLI v2, Terraform ≥ 1.5, Docker, and `psql`/`pg_dump` from PostgreSQL 15
client tools.

## 2. Infrastructure

```bash
cd terraform/demo
cp terraform.tfvars.example terraform.tfvars   # fill in github_repo
terraform init
terraform plan
```

**Verify the plan explicitly**: every resource it lists must belong to this
module. No production instance, security group, role, repository, parameter or
database may appear — and it cannot, because this state has never read theirs.
Read the plan anyway; the check is cheap and the failure it prevents is not.

```bash
terraform apply
terraform output          # role ARN, instance id, elastic IP, demo URL
```

> Reusing this module in an account that **already** deploys from GitHub
> Actions: the OpenID Connect provider registration is a singleton per account
> and issuer. Convert `aws_iam_openid_connect_provider.github` into a data
> source first, or the apply fails with `EntityAlreadyExists`. The comment in
> [`iam.tf`](../../terraform/demo/iam.tf) spells out the change.

Then confirm the host has registered with Systems Manager — until it does, every
deployment times out on a command nobody can collect:

```bash
aws ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=$(terraform output -raw instance_id)" \
  --query 'InstanceInformationList[0].PingStatus' --output text     # Online
```

## 3. Parameters

Terraform creates the three non-secret parameters (`DEMO_HOSTNAME`,
`ECR_REGISTRY`, `IMAGE_TAG`). **The six secrets are created here, by hand, on
purpose**: a value passed to Terraform is written to its state file in clear,
which would move them out of the encrypted store and into a file.

```bash
REGION=eu-west-1
put() { aws ssm put-parameter --region "$REGION" --name "/jbg-demo/$1" \
          --type SecureString --value "$2" --overwrite; }

put POSTGRES_PASSWORD        "$(openssl rand -base64 24 | tr -d '/+=')"
put AI_DB_PASSWORD           "$(openssl rand -base64 24 | tr -d '/+=')"
put JWT_SIGNING_KEY          "$(openssl rand -base64 48 | tr -d '/+=')"
put AI_SERVICE_SHARED_SECRET "$(openssl rand -base64 48 | tr -d '/+=')"
put INDEX_FEED_SHARED_KEY    "$(openssl rand -base64 32 | tr -d '/+=')"
put EMBEDDING_API_KEY        "sk-..."      # the provider key, pasted
```

| Parameter | Injected as | Into |
|---|---|---|
| `POSTGRES_PASSWORD` | `POSTGRES_PASSWORD`, and the API connection string | database, API |
| `AI_DB_PASSWORD` | `DATABASE_URL` of the AI service | AI service |
| `JWT_SIGNING_KEY` | `Jwt__SecretKey` | API |
| **`AI_SERVICE_SHARED_SECRET`** | `JWT_SECRET` **and** `AiGateway__JwtSecret` | **both** |
| **`INDEX_FEED_SHARED_KEY`** | `JPV_INDEX_FEED_API_KEY` **and** `IndexFeed__ApiKey` | **both** |
| `EMBEDDING_API_KEY` | `JPV_EMBEDDING_API_KEY` | AI service |

The two rows in bold are **one parameter read twice**, never two parameters. Two
would be free to drift, and a drifted pair produces a 401 whose cause the AI
service is specified not to disclose — a failure with no message pointing at it.

What is **not** here, and must not be added: the embedding model, the retrieval
distance threshold, and stub mode. Those are versioned literals in
`compose.demo.yaml`. Changing what the system computes belongs in a commit, not
in a parameter anyone can edit.

## 4. First deployment

Create the `demo` branch and the GitHub Environment of the same name, and set
the environment's secrets from `terraform output`:

| Secret | Value |
|---|---|
| `DEMO_DEPLOY_ROLE_ARN` | `terraform output -raw deploy_role_arn` |
| `DEMO_INSTANCE_ID` | `terraform output -raw instance_id` |

Run the workflow **manually first** (`workflow_dispatch`), before pushing
anything to `demo`. A first run on a push is a first run you cannot repeat
cheaply.

```bash
gh workflow run deploy-demo.yml
gh run watch
```

**The first run will fail, and it fails earlier than you would guess.** Not at
verification for an empty index — it never gets that far. It fails at
`alembic upgrade head`, with:

```
FATAL: password authentication failed for user "jbg_ai"
```

The `jbg_ai` role and the `ai` schema do not exist until `bootstrap.sql` runs,
and `bootstrap.sql` needs the Postgres container that this very deployment is
what creates. The chicken and egg is inherent, not a mistake: **deploy first,
provision second, redeploy third.**

Everything before that step does succeed, and two of those things matter: the
containers come up, and **Caddy obtains the TLS certificate** — so the failed
run does not cost you a certificate issuance when you re-run it.

### One-off schema provisioning

Before the AI service can migrate, the database needs the extension, the `ai`
schema and the `jbg_ai` role — a privileged, once-per-environment step that
migrations deliberately do not perform:

```bash
INSTANCE=$(cd terraform/demo && terraform output -raw instance_id)
AI_PWD=$(aws ssm get-parameter --name /jbg-demo/AI_DB_PASSWORD \
           --with-decryption --query Parameter.Value --output text)

aws ssm start-session --target "$INSTANCE"
# on the host:
sudo docker exec -i jbg-demo-postgres psql -U postgres -d joiabagur_pv \
  -v ai_password="$AI_PWD" < /opt/jbg-demo/ai-service/migrations/bootstrap.sql
```

> Pass the password **raw**. `psql`'s `:'var'` already renders it as a quoted
> literal; pre-quoting produces a password containing apostrophes that then
> fails to authenticate.

Re-run the workflow afterwards: `alembic upgrade head` now succeeds.

## 5. The data path

The corpus does not exist outside a laptop. It travels as a dump — **not
recomputed** — so that the published index is, row for row, the one the reported
figures describe. Recomputing would produce a *different* index and make those
figures describe a different system.

### 5.1 Measure the source

Before dumping, record what you expect to find on the other side: products,
collections, points of sale, inventory rows, approved AI profiles, indexed
documents, **and the embedding model recorded on the index**:

```bash
docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv <<'SQL'
SELECT 'products', count(*) FROM "Products"
UNION ALL SELECT 'collections',   count(*) FROM "Collections"
UNION ALL SELECT 'points_of_sale',count(*) FROM "PointOfSales"
UNION ALL SELECT 'inventory',     count(*) FROM "Inventories"
UNION ALL SELECT 'profiles_approved', count(*) FROM "ProductAiProfiles" WHERE "Status" = 1
UNION ALL SELECT 'documents',     count(*) FROM ai.product_document;
SELECT DISTINCT embedding_model FROM ai.product_document;
SQL
```

The distinct model **must** be `openai/text-embedding-3-small`, the literal in
`compose.demo.yaml`. If it is not, stop: the environment would answer 200s with
meaningless results, which is exactly what `/health` now reports as
`model_mismatch`.

### 5.2 Dump both schemas

```bash
docker exec jpv-pv-postgres pg_dump -U postgres -d joiabagur_pv \
  --schema=public --no-owner --no-acl > /tmp/demo-public.sql
docker exec jpv-pv-postgres pg_dump -U postgres -d joiabagur_pv \
  --schema=ai --no-owner --no-acl > /tmp/demo-ai.sql
```

### 5.3 Replace the shop's staff — mandatory

The dump carries the jewellery's real employees and their e-mail addresses. In a
publicly reachable environment they are replaced by two demonstration accounts,
one of each role, so both dashboards and the administrator-only diagnostics
block can be shown.

The catalog itself — real SKUs and real prices — **is** published: a business
decision taken explicitly.

After restoring, on the demo database:

```sql
-- Keep nothing of the real staff.
DELETE FROM "Users";
-- Then create exactly two accounts through the API's own registration path,
-- so the password hashing matches what the application expects:
--   demo.admin@joiabagur.example    role Administrator
--   demo.operador@joiabagur.example role Operator, assigned to one point of sale
```

Verify afterwards that **no** real address can authenticate:

```sql
SELECT "Email" FROM "Users";     -- exactly the two demonstration addresses
```

### 5.4 Restore and check the counts

```bash
aws ssm start-session --target "$INSTANCE"
# on the host, after bootstrap.sql and `alembic upgrade head`:
sudo docker exec -i jbg-demo-postgres psql -U postgres -d joiabagur_pv < demo-public.sql
sudo docker exec -i jbg-demo-postgres psql -U postgres -d joiabagur_pv < demo-ai.sql
```

Re-run the count query of §5.1 against the demo database and compare, number by
number, against what you recorded.

### 5.5 One reconciliation sync

The dump proves the data arrived. It does **not** prove the path that keeps it
up to date is wired. One synchronisation does:

```bash
# from the host, with an internal token signed by AI_SERVICE_SHARED_SECRET
sudo docker exec jbg-demo-ai python - <<'PY'
# POST /v1/index/sync, then GET /v1/index/status
PY
```

Expected: `drift_count = 0`. Anything else means the feed and the index disagree
about the catalog, and the environment must not be shown until it does not.

### 5.5b Three traps a wipe-and-restore sets, all found the hard way in C17

**The API reseeds `admin` / `Admin123!` on every start.** Its seeder's only guard
is "does any user named `admin` exist?", and after a truncate none does — so a
restart creates an administrator whose password is a constant in a **public**
repository, on a host open to the Internet. Deleting the row does not help: the
next restart recreates it. Leave one **disabled** row named `admin` with an
unusable hash: the seeder finds it and skips, and login rejects it on `IsActive`
before it ever checks the password.

**Password hashes minted outside .NET must use the `$2a$` prefix.** Python's
`bcrypt` emits `$2b$` by default, and the BCrypt.Net version here answers
`SaltParseException: Invalid salt version` — which escapes uncaught and turns a
login into a **500, not a 401**. Use `bcrypt.gensalt(12, prefix=b"2a")`. Do this
for the disabled accounts too: their hash never has to verify, but it does have
to *parse*.

**Do not read a hash file with `source`.** A line like `H=$2a$12$...` is an
unquoted assignment, and the shell eats `$2a` and `$12` as positional
parameters. The value arrives mangled and produces exactly the same
`SaltParseException`, which sends you hunting for the wrong bug. Read it with
command substitution instead: `H=$(grep '^H=' file | cut -d= -f2-)`.

### 5.6 End-to-end check

Sign in as the **operator** account, run a natural-language search from
«Buscar con Ayuda», and confirm the badge reports the **assisted** origin — not
the degraded lexical path. A degraded badge with results still looks like it
works, which is precisely why it has to be read rather than assumed.

## 6. Moving to a purchased domain

Nothing is rebuilt. The hostname is configuration end to end:

1. Point an `A` record at the elastic IP (`terraform output -raw public_ip`).
2. Set `demo_hostname` in `terraform.tfvars`, `terraform apply` — this updates
   `/jbg-demo/DEMO_HOSTNAME`.
3. Re-run the workflow. The proxy requests a certificate for the new name on the
   first request and keeps serving the old one until it has it.

Do **not** delete `jbg-demo-caddy-data` in the process. See the warning at the
top.

## 7. Tearing it down

```bash
cd terraform/demo && terraform destroy
```

The cost stops, and by construction the shop's account cannot be affected: no
shared state, no shared account, no shared resource.
