from typing import Any
from uuid import UUID

import httpx

class TraceroClient:
    def __init__(self, base_url: str, api_key: str| None = None, timeout_seconds: float = 10.0,)-> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def log_trace(self , *,query:dict[str, Any],
                  retrieval: dict[str, Any],
                  generation: dict[str, Any],
                  prompt: dict[str, Any] | None = None,
                  latency: dict[str, Any] | None = None,
                  evaluation: dict[str, Any] | None = None,
                  diagnosis: dict[str, Any] | None = None,
                  project: dict[str, Any]| None = None,
                  metadata: dict[str, Any] | None = None,
            )-> UUID:
                payload = {
                "query": query,
                "retrieval": retrieval,
                "generation": generation,    
                "prompt": prompt or {},
                "latency": latency or {},
                "evaluation": evaluation or {},
                "diagnosis": diagnosis or {},
                "project": project or {},
                "metadata": metadata or {},
                }

                headers= {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                
                response = httpx.post(f"{self.base_url}/v1/traces", json=payload, headers=headers, timeout=self.timeout_seconds,)

                response.raise_for_status()

                data = response.json()
                return UUID(data["trace_id"])
                
                