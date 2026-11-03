"""Explicit trusted telemetry for isolated application fixtures only.

These observations do not establish real runtime/network security coverage.
"""
from project_bots.repository import SQLiteRepository
from project_bots.security import SecurityService, REQUIRED_COVERAGE


def fixture_security(repository):
    security = SecurityService(repository)
    for coverage in REQUIRED_COVERAGE:
        security.observe(coverage, healthy=True, source='isolated application fixture; not live OS telemetry', ttl=60)
    return repository


def fixture_repository(path):
    return fixture_security(SQLiteRepository(path))
