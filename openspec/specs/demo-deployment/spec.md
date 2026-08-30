# demo-deployment Specification

## Purpose
Isolated demonstration environment for the AI service, deployed in an AWS account of its own and reachable from the Internet: the network boundary that leaves only the reverse proxy exposed, the classification of configuration between encrypted secrets and versioned literals, a deployment pipeline whose verification runs inside the host because the AI service is private by design, the data path that carries the real catalog and its vector index without the shop's staff accounts, and the persistence of data and certificates across redeployments.
## Requirements
### Requirement: Demo environment is isolated from the production account

The demo environment SHALL be provisioned in an AWS account distinct from the one hosting the shop's production system, from an infrastructure module with its own directory and its own state file. The module MUST NOT declare, reference or modify any resource belonging to the production account.

#### Scenario: Infrastructure plan touches no production resource

- **GIVEN** the demo infrastructure module with its own state
- **WHEN** an infrastructure plan is produced
- **THEN** every resource listed for creation, modification or destruction belongs to the demo module
- **AND** no production instance, security group, role, image repository, parameter or database appears in the plan

#### Scenario: Deployment pipeline references no production identifier

- **WHEN** the demo deployment workflow is inspected
- **THEN** it references only the demo role, the demo instance, the demo image repositories and the demo parameter prefix
- **AND** it does not reference the production deploy role, instance, repository or parameter prefix

#### Scenario: Production deployment path is unmodified

- **WHEN** the change is compared against the base branch
- **THEN** the production bundled image definition is unchanged
- **AND** the production deployment workflow is unchanged
- **AND** the production infrastructure module is unchanged
- **AND** the only production-side edits are deprecation headers on unused files and the correction of backend documentation that described an obsolete deployment path

### Requirement: Only the reverse proxy is reachable from the Internet

The demo environment SHALL expose exactly one service to the Internet. The AI service, the business API container and the database container MUST NOT publish host ports. The security group MUST allow inbound traffic only on the ports served by the reverse proxy.

#### Scenario: AI service publishes no port

- **WHEN** the demo composition file is inspected
- **THEN** the AI service declares no published port
- **AND** the database service declares no published port
- **AND** the business API service declares no published port
- **AND** the reverse proxy is the only service declaring published ports

#### Scenario: AI service is unreachable from outside

- **GIVEN** the demo environment is running
- **WHEN** a client outside the environment attempts to reach the AI service on its service port using the public address
- **THEN** the connection is not established

#### Scenario: Security group admits only proxy traffic

- **WHEN** the demo security group is inspected
- **THEN** its inbound rules admit only the ports served by the reverse proxy
- **AND** no inbound rule admits the AI service port or the database port

### Requirement: Transport security is served under a parameterised hostname

The demo environment SHALL serve traffic over TLS with a certificate valid for the configured hostname. The hostname MUST be supplied as configuration, so the environment can be deployed before a dedicated domain exists and migrated to one later without changing any image.

#### Scenario: Public entry point serves valid TLS

- **GIVEN** the demo environment is deployed with a hostname configured
- **WHEN** a browser opens the public URL
- **THEN** the connection is served over TLS with a certificate valid for that hostname
- **AND** no certificate warning is presented

#### Scenario: Hostname changes without rebuilding images

- **GIVEN** the environment is running under an initial hostname
- **WHEN** the configured hostname is changed and the environment is redeployed
- **THEN** the environment serves the new hostname
- **AND** no application image is rebuilt

### Requirement: Secrets reach containers through the process environment only

Values classified as secrets SHALL be read from the encrypted parameter store at deploy time and passed to containers through the deploying process environment. They MUST NOT be written to any file on the host, MUST NOT be baked into any image, and MUST NOT appear in the deployment command output.

#### Scenario: No environment file is written to the host

- **WHEN** the deployment completes
- **THEN** no environment file containing secret values exists next to the composition file
- **AND** no secret value is present in any file on the host outside container runtime state

#### Scenario: Command output carries no secret

- **WHEN** the output of the remote deployment command is inspected
- **THEN** it contains no secret value
- **AND** shell execution tracing is not enabled for the section that reads secrets

#### Scenario: A missing required value fails the deployment loudly

- **GIVEN** a required configuration value resolves to an empty string
- **WHEN** the deployment script runs
- **THEN** the deployment fails with a message naming the missing value
- **AND** no container is started with that value empty

### Requirement: Shared credentials are derived from a single parameter

Credentials that must match literally across two services — the internal service token secret and the index feed credential — SHALL each be stored as one parameter and read twice at deploy time, rather than stored as two independently editable parameters.

#### Scenario: Internal token secret is identical on both sides

- **WHEN** the deployed environment is inspected
- **THEN** the secret used by the AI service to validate internal tokens and the secret used by the business API to sign them originate from the same stored parameter

#### Scenario: Index feed credential is identical on both sides

- **WHEN** the deployed environment is inspected
- **THEN** the credential the AI service sends to the index feed and the credential the business API accepts originate from the same stored parameter

### Requirement: Behaviour-affecting settings are version controlled, not stored as parameters

Settings that change what the system computes rather than where it runs — the embedding model identifier, the retrieval distance threshold, and the stub response mode — SHALL be declared as literals under version control. They MUST NOT be supplied from the parameter store, so that changing them requires code review.

#### Scenario: Embedding model is a versioned literal

- **WHEN** the demo composition file is inspected
- **THEN** the embedding model identifier appears as a literal value
- **AND** it is not read from the parameter store

#### Scenario: Stub mode is disabled by a versioned literal

- **WHEN** the demo composition file is inspected
- **THEN** stub response mode is declared as a literal and is disabled
- **AND** it is not read from the parameter store

#### Scenario: Retrieval threshold is a versioned literal

- **WHEN** the demo composition file is inspected
- **THEN** the retrieval distance threshold appears as a literal value matching the value the evaluation figures were computed with

### Requirement: Deployment is verified from inside the host

Because the AI service is not reachable from outside the environment, post-deployment verification SHALL execute inside the host through the systems management service. The verification MUST fail the deployment when the index is empty, when the configured embedding model disagrees with the indexed one, when the database is unreachable, or when the provider credential is absent.

#### Scenario: Verification runs inside the host

- **WHEN** the deployment workflow verifies the result
- **THEN** the check is executed inside the host through the systems management service
- **AND** the check does not require the AI service to be reachable from the pipeline runner

#### Scenario: An empty index fails the deployment

- **GIVEN** the environment is deployed but the vector index contains no documents
- **WHEN** post-deployment verification runs
- **THEN** the verification fails
- **AND** the deployment is not reported as successful

#### Scenario: A healthy deployment passes verification

- **GIVEN** the environment is deployed with the corpus loaded
- **WHEN** post-deployment verification runs
- **THEN** the database is reported reachable
- **AND** the indexed document count is greater than zero
- **AND** the configured embedding model matches the indexed one
- **AND** the provider credential is reported as configured

### Requirement: Data and certificates survive a redeployment

Database contents and issued certificates SHALL be held in persistent volumes. The deployment procedure MUST recreate containers in place and MUST NOT remove volumes.

#### Scenario: Corpus survives a redeployment

- **GIVEN** the environment is deployed with the corpus loaded
- **WHEN** the deployment workflow runs again with a new image
- **THEN** the containers are recreated
- **AND** the catalog and the vector index retain their contents

#### Scenario: Certificate survives a redeployment

- **GIVEN** a certificate has been issued for the configured hostname
- **WHEN** the deployment workflow runs again
- **THEN** the certificate is reused from its persistent volume
- **AND** no new certificate is requested from the certificate authority

#### Scenario: Deployment never removes volumes

- **WHEN** the deployment script is inspected
- **THEN** it does not contain any command that removes volumes while stopping the environment

### Requirement: Demo data carries the catalog but not the shop's staff accounts

The demo environment SHALL be populated by restoring the business and vector schemas from the local environment, so the published index is the one the reported figures describe. Personal accounts belonging to the shop's staff MUST be replaced by demonstration accounts before the environment is publicly reachable.

#### Scenario: Vector index is restored rather than recomputed

- **WHEN** the demo environment is populated
- **THEN** the vector index rows are restored from the dump with their existing embeddings
- **AND** the embeddings are not recomputed against the provider

#### Scenario: Reconciliation sync reports no drift

- **GIVEN** the demo environment has been populated from the dump
- **WHEN** a single index synchronisation is executed and the index status is queried
- **THEN** the reported drift count is zero

#### Scenario: Staff accounts are replaced by demonstration accounts

- **WHEN** the demo environment is publicly reachable
- **THEN** no account belonging to the shop's staff can authenticate
- **AND** an administrator demonstration account exists
- **AND** an operator demonstration account exists

### Requirement: The AI container is memory bounded so its failure is contained

The AI service container SHALL declare an explicit memory limit, so that exhausting memory terminates that container alone rather than the host, leaving the business API serving and letting assisted search degrade through the existing circuit breaker.

#### Scenario: Memory limit is declared on the AI service

- **WHEN** the demo composition file is inspected
- **THEN** the AI service declares an explicit memory limit
- **AND** the limit is expressed with a directive that takes effect outside swarm mode

#### Scenario: The environment survives the AI container being terminated

- **GIVEN** the environment is running
- **WHEN** the AI service container is terminated
- **THEN** the reverse proxy and the business API keep serving requests
- **AND** the AI container is restarted by its restart policy
- **AND** assisted search reports the AI as unavailable rather than failing the page

### Requirement: Images and provisioning are reproducible

Application images and host provisioning SHALL pin every external artefact to an explicit version. Moving tags MUST NOT be used, so the same commit produces the same environment on any day and in any account.

#### Scenario: Dependency installer is version pinned

- **WHEN** the AI service image definition is inspected
- **THEN** the dependency installer is copied from an explicitly versioned source
- **AND** no moving tag is used for it

#### Scenario: Composition plugin is version pinned

- **WHEN** the host provisioning script is inspected
- **THEN** the composition plugin is installed from an explicitly versioned release

#### Scenario: Base operating system image is resolved automatically

- **WHEN** the demo infrastructure module is inspected
- **THEN** the base operating system image is resolved from the provider's published parameter
- **AND** no manual image identifier variable must be updated before applying

### Requirement: Host provisioning knows nothing about the application

Host provisioning SHALL be limited to preparing a container host: installing the container engine and the composition plugin, starting the required system services, retrieving the composition file and deployment script, and running the deployment. Application concerns — reverse proxy configuration, hostnames, certificates and application environment variables — MUST live in the composition file, the images and the parameter store.

#### Scenario: Provisioning contains no application configuration

- **WHEN** the host provisioning script is inspected
- **THEN** it contains no reverse proxy configuration
- **AND** it contains no hostname or certificate handling
- **AND** it contains no application environment variable
- **AND** it does not enumerate application services individually

### Requirement: The demo image serves under any hostname

The image built for the demo environment SHALL resolve its API calls relative to the serving origin, so that the same image works under any hostname without rebuilding.

#### Scenario: Interface calls the API on the serving origin

- **GIVEN** the demo image is built with a relative API base
- **WHEN** the interface is served under the demo hostname
- **THEN** its API calls are issued against the same origin
- **AND** image URLs derived from API-relative paths resolve against the same origin

#### Scenario: Production image definition is not reused or altered

- **WHEN** the change is inspected
- **THEN** the demo image is built from its own definition
- **AND** the production bundled image definition is unchanged
