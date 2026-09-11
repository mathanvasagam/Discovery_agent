from __future__ import annotations

import logging
import re
from textwrap import dedent
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from core.llm import call_llm as call_provider_llm


logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["python", "nodejs"]


class AgentDefinition(BaseModel):
    name: str
    system_prompt: str
    tools: List[str]
    workflow_steps: List[str]
    test_scenarios: List[str] = Field(default_factory=list)
    description: Optional[str] = None


def call_llm(prompt: str) -> Dict[str, Any]:
    """
    Hook for model-driven code generation.
    """
    result = call_provider_llm(prompt)
    return result if isinstance(result, dict) else {}


def call_llm_yaml(prompt: str) -> Dict[str, Any]:
    """
    Hook for model-driven agent definition generation.
    """
    result = call_provider_llm(prompt)
    return result if isinstance(result, dict) else {}


def _clean_markdown(code: str) -> str:
    return re.sub(r"```[a-zA-Z0-9_+-]*\n?(.*?)\n?```", r"\1", code, flags=re.DOTALL).strip()


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "generated"


def _python_connector_artifact(system_name: str, auth_method: str, category: str) -> Dict[str, Any]:
    slug = _slugify(system_name)
    class_name = f"{''.join(part.capitalize() for part in slug.split('_'))}Connector"
    code = dedent(
        f"""
        import logging
        import time
        from typing import Any, Dict, List, Optional

        import requests


        logger = logging.getLogger(__name__)


        class ConnectorError(Exception):
            pass


        class {class_name}:
            def __init__(self, base_url: str, token: str, timeout: int = 30, max_retries: int = 3, rate_limit_per_second: float = 5.0):
                self.base_url = base_url.rstrip("/")
                self.token = token
                self.timeout = timeout
                self.max_retries = max_retries
                self.rate_limit_per_second = rate_limit_per_second
                self._last_request_ts = 0.0
                self.session = requests.Session()

            def authenticate(self) -> Dict[str, str]:
                if not self.token:
                    raise ConnectorError("Missing API token")
                return {{
                    "Authorization": f"Bearer {{self.token}}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }}

            def _respect_rate_limit(self) -> None:
                minimum_interval = 1.0 / max(self.rate_limit_per_second, 1.0)
                now = time.monotonic()
                elapsed = now - self._last_request_ts
                if elapsed < minimum_interval:
                    time.sleep(minimum_interval - elapsed)
                self._last_request_ts = time.monotonic()

            def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                url = f"{{self.base_url}}/{{path.lstrip('/')}}"
                headers = self.authenticate()
                errors: List[str] = []
                for attempt in range(1, self.max_retries + 1):
                    self._respect_rate_limit()
                    try:
                        response = self.session.request(
                            method=method.upper(),
                            url=url,
                            headers=headers,
                            params=params,
                            json=payload,
                            timeout=self.timeout,
                        )
                        if response.status_code == 429:
                            retry_after = float(response.headers.get("Retry-After", "1"))
                            logger.warning("Rate limited by {system_name}; sleeping for %s seconds", retry_after)
                            time.sleep(retry_after)
                            continue
                        response.raise_for_status()
                        if not response.content:
                            return {{}}
                        return response.json()
                    except requests.RequestException as exc:
                        errors.append(str(exc))
                        logger.warning("Attempt %s failed for %s %s: %s", attempt, method, url, exc)
                        if attempt == self.max_retries:
                            raise ConnectorError(f"Request failed after {{self.max_retries}} attempts: {{'; '.join(errors)}}") from exc
                        time.sleep(attempt)
                raise ConnectorError("Request unexpectedly exhausted retries")

            def create_record(self, entity: str, payload: Dict[str, Any]) -> Dict[str, Any]:
                return self._request("POST", f"api/{{entity}}", payload=payload)

            def get_record(self, entity: str, record_id: str) -> Dict[str, Any]:
                return self._request("GET", f"api/{{entity}}/{{record_id}}")

            def update_record(self, entity: str, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
                return self._request("PUT", f"api/{{entity}}/{{record_id}}", payload=payload)

            def delete_record(self, entity: str, record_id: str) -> Dict[str, Any]:
                return self._request("DELETE", f"api/{{entity}}/{{record_id}}")

            def list_records(self, entity: str, page_size: int = 100) -> List[Dict[str, Any]]:
                records: List[Dict[str, Any]] = []
                page = 1
                while True:
                    result = self._request("GET", f"api/{{entity}}", params={{"page": page, "page_size": page_size}})
                    batch = result.get("items", [])
                    records.extend(batch)
                    if not result.get("next_page"):
                        break
                    page = int(result["next_page"])
                return records


        __all__ = ["{class_name}", "ConnectorError"]
        """
    ).strip()

    tests = dedent(
        f"""
        import unittest
        from unittest.mock import Mock, patch

        import requests

        from {slug}_connector import {class_name}, ConnectorError


        class {class_name}Tests(unittest.TestCase):
            def setUp(self) -> None:
                self.connector = {class_name}(base_url="https://api.example.com", token="secret-token")

            def test_authenticate_requires_token(self) -> None:
                self.connector.token = ""
                with self.assertRaises(ConnectorError):
                    self.connector.authenticate()

            @patch.object(requests.Session, "request")
            def test_create_record(self, mock_request: Mock) -> None:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.content = b'{{"id":"1"}}'
                mock_response.json.return_value = {{"id": "1"}}
                mock_response.raise_for_status.return_value = None
                mock_request.return_value = mock_response

                result = self.connector.create_record("records", {{"name": "demo"}})
                self.assertEqual(result["id"], "1")

            @patch.object(requests.Session, "request")
            def test_retries_raise_connector_error(self, mock_request: Mock) -> None:
                mock_request.side_effect = requests.RequestException("boom")
                with self.assertRaises(ConnectorError):
                    self.connector.get_record("records", "1")


        if __name__ == "__main__":
            unittest.main()
        """
    ).strip()

    readme = dedent(
        f"""
        # {system_name} Connector

        Generated connector for a {category} system using {auth_method} authentication.

        ## Features

        - authentication
        - CRUD operations
        - pagination
        - retries
        - rate limiting
        - structured logging

        ## Usage

        ```python
        from {slug}_connector import {class_name}

        connector = {class_name}(base_url="https://api.example.com", token="YOUR_TOKEN")
        records = connector.list_records("records")
        print(records)
        ```
        """
    ).strip()

    return {
        "code": code,
        "tests": tests,
        "dependencies": ["requests"],
        "readme": readme,
        "config_files": {"requirements.txt": "requests>=2.31.0\n"},
        "language": "python",
        "filename": f"{slug}_connector.py",
    }


def _node_connector_artifact(system_name: str, auth_method: str, category: str) -> Dict[str, Any]:
    slug = _slugify(system_name)
    class_name = f"{''.join(part.capitalize() for part in slug.split('_'))}Connector"
    code = dedent(
        f"""
        export class ConnectorError extends Error {{
          constructor(message) {{
            super(message)
            this.name = "ConnectorError"
          }}
        }}

        export class {class_name} {{
          constructor({{ baseUrl, token, timeoutMs = 30000, maxRetries = 3, rateLimitPerSecond = 5 }}) {{
            this.baseUrl = baseUrl.replace(/\\/$/, "")
            this.token = token
            this.timeoutMs = timeoutMs
            this.maxRetries = maxRetries
            this.rateLimitPerSecond = rateLimitPerSecond
            this.lastRequestTs = 0
          }}

          authenticate() {{
            if (!this.token) {{
              throw new ConnectorError("Missing API token")
            }}
            return {{
              "Authorization": `Bearer ${{this.token}}`,
              "Accept": "application/json",
              "Content-Type": "application/json",
            }}
          }}

          async respectRateLimit() {{
            const minimumInterval = 1000 / Math.max(this.rateLimitPerSecond, 1)
            const now = Date.now()
            const elapsed = now - this.lastRequestTs
            if (elapsed < minimumInterval) {{
              await new Promise((resolve) => setTimeout(resolve, minimumInterval - elapsed))
            }}
            this.lastRequestTs = Date.now()
          }}

          async request(method, path, {{ params = null, payload = null }} = {{}}) {{
            const url = new URL(`${{this.baseUrl}}/${{path.replace(/^\\//, "")}}`)
            if (params) {{
              for (const [key, value] of Object.entries(params)) {{
                url.searchParams.set(key, String(value))
              }}
            }}

            const headers = this.authenticate()
            const errors = []

            for (let attempt = 1; attempt <= this.maxRetries; attempt += 1) {{
              await this.respectRateLimit()
              try {{
                const response = await fetch(url, {{
                  method,
                  headers,
                  body: payload ? JSON.stringify(payload) : undefined,
                }})
                if (response.status === 429) {{
                  const retryAfter = Number(response.headers.get("retry-after") || "1")
                  await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000))
                  continue
                }}
                if (!response.ok) {{
                  throw new ConnectorError(`HTTP ${{response.status}}`)
                }}
                const text = await response.text()
                return text ? JSON.parse(text) : {{}}
              }} catch (error) {{
                errors.push(String(error))
                if (attempt === this.maxRetries) {{
                  throw new ConnectorError(`Request failed after retries: ${{errors.join("; ")}}`)
                }}
                await new Promise((resolve) => setTimeout(resolve, attempt * 1000))
              }}
            }}
            throw new ConnectorError("Request unexpectedly exhausted retries")
          }}

          createRecord(entity, payload) {{
            return this.request("POST", `api/${{entity}}`, {{ payload }})
          }}

          getRecord(entity, recordId) {{
            return this.request("GET", `api/${{entity}}/${{recordId}}`)
          }}

          updateRecord(entity, recordId, payload) {{
            return this.request("PUT", `api/${{entity}}/${{recordId}}`, {{ payload }})
          }}

          deleteRecord(entity, recordId) {{
            return this.request("DELETE", `api/${{entity}}/${{recordId}}`)
          }}

          async listRecords(entity, pageSize = 100) {{
            const records = []
            let page = 1
            while (true) {{
              const result = await this.request("GET", `api/${{entity}}`, {{ params: {{ page, page_size: pageSize }} }})
              const items = result.items || []
              records.push(...items)
              if (!result.next_page) {{
                break
              }}
              page = Number(result.next_page)
            }}
            return records
          }}
        }}
        """
    ).strip()

    tests = dedent(
        f"""
        import test from "node:test"
        import assert from "node:assert/strict"

        import {{ {class_name}, ConnectorError }} from "./{slug}_connector.js"

        test("authenticate requires a token", () => {{
          const connector = new {class_name}({{ baseUrl: "https://api.example.com", token: "" }})
          assert.throws(() => connector.authenticate(), ConnectorError)
        }})

        test("authenticate returns bearer headers", () => {{
          const connector = new {class_name}({{ baseUrl: "https://api.example.com", token: "abc" }})
          const headers = connector.authenticate()
          assert.equal(headers.Authorization, "Bearer abc")
        }})
        """
    ).strip()

    readme = dedent(
        f"""
        # {system_name} Connector

        Generated connector for a {category} system using {auth_method} authentication.

        ## Features

        - authentication
        - CRUD operations
        - pagination
        - retries
        - rate limiting
        - structured logging
        """
    ).strip()

    return {
        "code": code,
        "tests": tests,
        "dependencies": [],
        "readme": readme,
        "config_files": {
            "package.json": dedent(
                f"""
                {{
                  "name": "{slug}-connector",
                  "version": "1.0.0",
                  "type": "module",
                  "scripts": {{
                    "test": "node --test"
                  }}
                }}
                """
            ).strip()
        },
        "language": "nodejs",
        "filename": f"{slug}_connector.js",
        "test_filename": f"{slug}_connector.test.js",
    }


def generate_agent_definition(gap_info: Dict[str, Any]) -> Dict[str, Any]:
    system_name = gap_info.get("system_name", "Unknown")
    use_case = gap_info.get("use_case_title", "General Automation")

    prompt = f"""
    Task: Generate a JSON configuration for an autonomous agent.
    Objective: {use_case} supporting system {system_name}.

    JSON Schema:
    {{
      "name": "lowercase_snake_case_name",
      "system_prompt": "persona instructions",
      "tools": ["tool1", "tool2"],
      "workflow_steps": ["step1", "step2"],
      "test_scenarios": ["scenario1", "scenario2"]
    }}

    Return ONLY valid JSON.
    """

    raw_definition = call_llm_yaml(prompt)
    if not isinstance(raw_definition, dict):
        raw_definition = {{}}

    # Normalize keys
    if "agent_config" in raw_definition:
        raw_definition = raw_definition["agent_config"]
    
    # Ensure mandatory fields
    raw_definition.setdefault("name", f"{_slugify(system_name)}_agent")
    raw_definition.setdefault("system_prompt", f"Integration agent for {system_name}.")
    raw_definition.setdefault("tools", [f"{_slugify(system_name)}_connector"])
    raw_definition.setdefault("workflow_steps", ["authenticate", "fetch", "process"])
    raw_definition.setdefault("test_scenarios", ["success_path"])

    # Clean lists
    for field in ["tools", "workflow_steps", "test_scenarios"]:
        items = raw_definition.get(field)
        if isinstance(items, list):
            raw_definition[field] = [
                item.get("name") or item.get("step") or str(item) if isinstance(item, dict) else str(item)
                for item in items
            ]
        else:
            raw_definition[field] = [str(items)] if items else []

    try:
        validated = AgentDefinition(**raw_definition)
        return validated.model_dump()
    except Exception as e:
        logger.error(f"AgentDefinition validation failed: {e}")
        # Return a safe version
        return raw_definition


def generate_connector(gap_info: Dict[str, Any], language: str = "python") -> Dict[str, Any]:
    if language not in SUPPORTED_LANGUAGES:
        logger.warning("Unsupported language '%s' requested. Defaulting to python.", language)
        language = "python"

    system_name = gap_info.get("system_name", "Generic")
    category = gap_info.get("category", "Other")
    auth_method = gap_info.get("auth_method", "Unknown")

    prompt = f"""
    Role: Principal Integration Architect
    Objective: Generate a PRODUCTION-READY {language} connector package for {system_name}.

    Context:
    - System Name: {system_name}
    - System Category: {category}
    - Authentication Method: {auth_method}

    Requirements:
    1. SOURCE CODE: A single Python file with a class named '{''.join(part.capitalize() for part in _slugify(system_name).split('_'))}Connector'.
       - Must include: authenticate(), create_record(), get_record(), update_record(), delete_record(), list_records().
       - Must handle: pagination, rate limiting (time.sleep), retries (max 3), and logging.
    2. UNIT TESTS: Using 'unittest' or 'pytest'.
    3. DEPENDENCIES: List of libraries (e.g. ["requests"]).

    Output Format:
    Return ONLY a JSON object with these exact keys:
    {{
      "code": "full source code string",
      "tests": "full test code string",
      "dependencies": ["lib1", "lib2"],
      "readme": "markdown setup guide",
      "language": "{language}",
      "filename": "{_slugify(system_name)}_connector.{'py' if language == 'python' else 'js'}"
    }}
    """

    artifact = call_llm(prompt)
    if artifact and isinstance(artifact, dict) and "code" in artifact:
        artifact["code"] = _clean_markdown(artifact["code"])
        if "tests" in artifact:
            artifact["tests"] = _clean_markdown(artifact["tests"])
        artifact.setdefault("language", language)
        artifact.setdefault("filename", f"{_slugify(system_name)}_connector.{'py' if language == 'python' else 'js'}")
        artifact.setdefault("readme", f"# {system_name} Connector")
        artifact.setdefault("dependencies", [])

        try:
            from core.sandbox import validate_code_in_sandbox
            val_res = validate_code_in_sandbox(artifact)
            if val_res["status"] == "pass":
                return artifact
            logger.warning(
                "LLM-generated code failed sandbox validation: %s. Falling back to deterministic template.",
                val_res.get("errors")
            )
        except Exception as e:
            logger.error("Failed to run sandbox validation on LLM output: %s", e)

    if language == "python":
        return _python_connector_artifact(system_name, auth_method, category)
    return _node_connector_artifact(system_name, auth_method, category)
