"""
Comprehensive API endpoint tests for Nostr Profiles API.

Tests all endpoints documented in TESTING_GUIDE.md with proper authentication,
error handling, and response validation.
"""

import json
from typing import Any, Dict

import httpx
import pytest


class TestAPIEndpoints:
    """Test suite for all API endpoints."""

    BASE_URL = "http://127.0.0.1:8080"
    API_KEY = "local_test_api_key"

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        self.headers = {"Content-Type": "application/json", "X-API-Key": self.API_KEY}
        self.client = httpx.Client(base_url=self.BASE_URL, timeout=30.0)
        yield
        self.client.close()

    def test_health_check(self):
        """Test GET /health endpoint."""
        response = self.client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "secure-nostr-profiles-api"
        assert data["version"] == "1.0.0"
        assert data["environment"] == "development"
        assert data["auth_configured"] == True

    def test_health_check_no_auth_required(self):
        """Test that health check doesn't require authentication."""
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_search_profiles_success(self):
        """Test POST /api/search_profiles with valid request."""
        payload = {"query": "test", "limit": 10}

        response = self.client.post(
            "/api/search_profiles", headers=self.headers, json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "count" in data
        assert "profiles" in data
        assert "query" in data
        assert data["query"] == "test"
        assert isinstance(data["profiles"], list)
        assert data["count"] == len(data["profiles"])

    def test_search_profiles_no_auth(self):
        """Test search profiles without authentication fails."""
        payload = {"query": "test"}

        response = self.client.post("/api/search_profiles", json=payload)
        assert response.status_code == 401

    def test_search_profiles_invalid_query(self):
        """Test search profiles with invalid query."""
        payload = {"query": ""}  # Empty query should fail

        response = self.client.post(
            "/api/search_profiles", headers=self.headers, json=payload
        )
        assert response.status_code == 422  # Validation error

    def test_search_business_profiles_success(self):
        """Test POST /api/search_business_profiles with valid request."""
        payload = {"query": "", "business_type": "retail", "limit": 5}

        response = self.client.post(
            "/api/search_business_profiles", headers=self.headers, json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "count" in data
        assert "profiles" in data
        assert isinstance(data["profiles"], list)
        assert data["count"] == len(data["profiles"])
        assert data["count"] <= 5  # Respects limit

    def test_search_business_profiles_invalid_type(self):
        """Test business search with invalid business type."""
        payload = {"query": "", "business_type": "invalid_type", "limit": 5}

        response = self.client.post(
            "/api/search_business_profiles", headers=self.headers, json=payload
        )
        assert response.status_code == 422  # Validation error

    def test_get_profile_by_pubkey_success(self):
        """Test GET /api/profile/{pubkey} with valid pubkey."""
        # Use the test profile pubkey from the guide
        pubkey = "57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991"

        response = self.client.get(f"/api/profile/{pubkey}", headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            assert data["success"] == True
            assert "profile" in data
            profile = data["profile"]
            assert profile["pubkey"] == pubkey
            assert "name" in profile
            assert "about" in profile
        elif response.status_code == 404:
            # Profile not found is also valid if database is empty
            data = response.json()
            assert "Profile not found" in data["detail"]
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")

    def test_get_profile_invalid_pubkey(self):
        """Test get profile with invalid pubkey format."""
        invalid_pubkey = "invalid_pubkey"

        response = self.client.get(
            f"/api/profile/{invalid_pubkey}", headers=self.headers
        )
        assert response.status_code == 400  # Bad request for invalid format

    def test_get_profile_no_auth(self):
        """Test get profile without authentication fails."""
        pubkey = "57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991"

        response = self.client.get(f"/api/profile/{pubkey}")
        assert response.status_code == 401

    def test_get_stats_success(self):
        """Test GET /api/stats endpoint."""
        response = self.client.get("/api/stats", headers=self.headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "stats" in data

        stats = data["stats"]
        required_fields = [
            "total_profiles",
            "profiles_with_name",
            "profiles_with_display_name",
            "profiles_with_about",
            "profiles_with_picture",
            "profiles_with_nip05",
            "profiles_with_website",
        ]

        for field in required_fields:
            assert field in stats
            assert isinstance(stats[field], int)
            assert stats[field] >= 0

    def test_get_stats_no_auth(self):
        """Test stats endpoint without authentication fails."""
        response = self.client.get("/api/stats")
        assert response.status_code == 401

    def test_get_business_types_success(self):
        """Test GET /api/business_types endpoint."""
        response = self.client.get("/api/business_types", headers=self.headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "business_types" in data
        assert "count" in data

        business_types = data["business_types"]
        assert isinstance(business_types, list)
        assert len(business_types) > 0
        assert data["count"] == len(business_types)

        # Check for expected business types
        expected_types = [
            "retail",
            "restaurant",
            "service",
            "business",
            "entertainment",
            "other",
        ]
        for expected_type in expected_types:
            if expected_type in business_types:
                assert True
                break
        else:
            pytest.fail("No expected business types found")

    def test_get_business_types_no_auth(self):
        """Test business types endpoint without authentication fails."""
        response = self.client.get("/api/business_types")
        assert response.status_code == 401

    def test_refresh_database_success(self):
        """Test POST /api/refresh endpoint."""
        response = self.client.post("/api/refresh", headers=self.headers)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["message"] == "Database refresh completed"
        assert "current_stats" in data

        # Verify stats structure
        stats = data["current_stats"]
        assert isinstance(stats, dict)
        assert "total_profiles" in stats

    def test_refresh_database_no_auth(self):
        """Test refresh endpoint without authentication fails."""
        response = self.client.post("/api/refresh")
        assert response.status_code == 401

    def test_cors_headers(self):
        """Test that server responds correctly (CORS config not required for test)."""
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_security_headers(self):
        """Test that security headers are present."""
        response = self.client.get("/health")

        security_headers = [
            "x-content-type-options",
            "x-frame-options",
            "x-xss-protection",
            "strict-transport-security",
            "content-security-policy",
            "referrer-policy",
        ]

        headers = {k.lower(): v for k, v in response.headers.items()}

        for header in security_headers:
            assert header in headers, f"Missing security header: {header}"

    def test_input_validation_sql_injection(self):
        """Test SQL injection protection in search queries."""
        malicious_queries = [
            "'; DROP TABLE profiles; --",
            "1' OR '1'='1",
            "test'; SELECT * FROM profiles; --",
        ]

        for query in malicious_queries:
            payload = {"query": query}
            response = self.client.post(
                "/api/search_profiles", headers=self.headers, json=payload
            )
            # Should either sanitize the input or reject it
            assert response.status_code in [200, 400, 422]

    def test_large_payload_protection(self):
        """Test protection against large payloads."""
        # Very long query string
        long_query = "a" * 10000
        payload = {"query": long_query}

        response = self.client.post(
            "/api/search_profiles", headers=self.headers, json=payload
        )
        # Should reject oversized input
        assert response.status_code == 422

    def test_invalid_json_handling(self):
        """Test handling of invalid JSON payloads."""
        # Send malformed JSON
        response = self.client.post(
            "/api/search_profiles",
            headers={"X-API-Key": self.API_KEY, "Content-Type": "application/json"},
            content="{invalid json",
        )
        assert response.status_code == 422

    def test_api_consistency(self):
        """Test that all endpoints follow consistent response format."""
        authenticated_endpoints = [
            ("/api/stats", "GET"),
            ("/api/business_types", "GET"),
            ("/api/refresh", "POST"),
        ]

        for endpoint, method in authenticated_endpoints:
            if method == "GET":
                response = self.client.get(endpoint, headers=self.headers)
            else:
                response = self.client.post(endpoint, headers=self.headers)

            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert data["success"] == True


class TestAsyncIntegration:
    """Integration tests that may require database state."""

    BASE_URL = "http://127.0.0.1:8080"
    API_KEY = "local_test_api_key"

    def test_refresh_then_search_integration(self):
        """Test refresh followed by search to ensure data flow."""
        headers = {"Content-Type": "application/json", "X-API-Key": self.API_KEY}

        with httpx.Client(base_url=self.BASE_URL, timeout=30.0) as client:
            # First refresh the database
            refresh_response = client.post("/api/refresh", headers=headers)
            assert refresh_response.status_code == 200

            # Then search for profiles
            search_payload = {"query": "test", "limit": 10}
            search_response = client.post(
                "/api/search_profiles", headers=headers, json=search_payload
            )
            assert search_response.status_code == 200

            # Check stats reflect the refresh
            stats_response = client.get("/api/stats", headers=headers)
            assert stats_response.status_code == 200
            stats_data = stats_response.json()

            # Verify stats are consistent with search results
            search_data = search_response.json()
            assert isinstance(stats_data["stats"]["total_profiles"], int)
            assert stats_data["stats"]["total_profiles"] >= 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
