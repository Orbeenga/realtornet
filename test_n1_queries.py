#!/usr/bin/env python
"""
N+1 Query Investigation Script
Run with: DEBUG=true python test_n1_queries.py

Captures SQLAlchemy echo output to count queries on /properties and /agencies endpoints.
"""
import os
os.environ["DEBUG"] = "true"
os.environ["ENV"] = "test"
os.environ["SENTRY_DSN"] = ""

from sqlalchemy import event
from sqlalchemy.engine import Engine
from fastapi.testclient import TestClient

# Import after env vars are set
from app.main import app
from app.core.database import engine

# Track queries
query_count = {"count": 0}
queries = []

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    query_count["count"] += 1
    queries.append(statement[:100])  # Store first 100 chars
    print(f"[Query {query_count['count']}] {statement[:150]}")

def test_properties_endpoint():
    """Test GET /properties and count queries"""
    query_count["count"] = 0
    queries.clear()

    with TestClient(app) as client:
        print("\n=== Testing GET /api/v1/properties/ ===")
        response = client.get("/api/v1/properties/?skip=0&limit=10")
        print(f"Status: {response.status_code}")
        print(f"Total queries for /properties: {query_count['count']}")
        print(f"Expected: ~1-3 queries (not N+1)")

    return query_count["count"]

def test_agencies_endpoint():
    """Test GET /agencies and count queries"""
    query_count["count"] = 0
    queries.clear()

    with TestClient(app) as client:
        print("\n=== Testing GET /api/v1/agencies/ ===")
        response = client.get("/api/v1/agencies/?skip=0&limit=10")
        print(f"Status: {response.status_code}")
        print(f"Total queries for /agencies: {query_count['count']}")
        print(f"Expected: ~1-3 queries (not scaling with result count)")

    return query_count["count"]

if __name__ == "__main__":
    print("N+1 Query Investigation")
    print("=" * 60)

    prop_queries = test_properties_endpoint()
    agency_queries = test_agencies_endpoint()

    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Properties endpoint: {prop_queries} queries")
    print(f"  Agencies endpoint: {agency_queries} queries")
    print(f"  ⚠️  If > 5 for either, investigate N+1 pattern")
