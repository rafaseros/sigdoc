# CI/CD Specification

## Purpose

Define requirements for the GitHub Actions CI pipeline that gates deployments behind a passing test suite.

## Requirements

### Requirement: Test Job in CI Pipeline

The `.github/workflows/deploy.yml` MUST include a `test` job that runs before the `deploy` job.

The `test` job MUST:
- Run on `ubuntu-latest`
- Provision a PostgreSQL 16 service container with a known test database URL
- Check out the repository
- Set up Python 3.12
- Install dependencies via `pip install -e ".[dev]"`
- Execute `pytest --tb=short -q`

#### Scenario: Passing tests allow deploy to proceed

- GIVEN all pytest tests pass in the `test` job
- WHEN the workflow completes the `test` job
- THEN the `deploy` job starts execution

#### Scenario: Failing tests block deploy

- GIVEN at least one pytest test fails in the `test` job
- WHEN the `test` job exits with a non-zero code
- THEN the `deploy` job is NOT started
- AND the workflow run is marked as failed

#### Scenario: CI runs with PostgreSQL service container

- GIVEN the `test` job defines a `postgres:16` service with standard env vars
- WHEN the `test` job runs
- THEN the test suite connects to the service container database
- AND no MinIO service is required (storage is faked in tests)

---

### Requirement: Deploy Job Dependency

The `deploy` job MUST declare `needs: [test]` and SHOULD include `if: success()` to ensure it only runs after the test job completes successfully.

#### Scenario: deploy job skipped on test failure

- GIVEN the `test` job fails
- WHEN GitHub Actions evaluates the `deploy` job condition
- THEN the `deploy` job is skipped or cancelled
- AND the existing SSH-based deploy steps do NOT execute

#### Scenario: deploy job runs on test success

- GIVEN the `test` job succeeds
- WHEN GitHub Actions evaluates the `deploy` job condition
- THEN the `deploy` job executes all existing deploy steps unchanged
