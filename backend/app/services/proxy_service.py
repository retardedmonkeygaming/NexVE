"""
NexVE Multi-Master Proxy Service
Forwards API requests to other cluster nodes when resources aren't local.
"""
import httpx
import json
from typing import Optional


class ProxyService:
    """Manages cross-node API requests in a cluster."""

    def __init__(self):
        self._nodes_cache = {}
        self._cache_timeout = 30  # seconds

    def get_cluster_nodes(self) -> list:
        """Get list of known cluster nodes with their addresses."""
        try:
            import subprocess
            r = subprocess.run(
                "corosync-cmapctl nodes.nodes 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )
            nodes = []
            current_name = ""
            for line in r.stdout.splitlines():
                if ".name" in line and "=" in line:
                    current_name = line.split("=")[-1].strip().strip("'\"")
                elif ".nodeid" in line and "=" in line and current_name:
                    # Try to resolve the node's IP
                    try:
                        import socket
                        ip = socket.gethostbyname(current_name)
                    except Exception:
                        ip = current_name
                    nodes.append({
                        "name": current_name,
                        "address": ip,
                        "node_id": line.split("=")[-1].strip(),
                    })
                    current_name = ""
            return nodes
        except Exception:
            return []

    def get_local_hostname(self) -> str:
        """Get this node's hostname."""
        import socket
        return socket.gethostname()

    def is_local(self, node_name: str) -> bool:
        """Check if a node name refers to this node."""
        local = self.get_local_hostname()
        if node_name in (local, "localhost", "127.0.0.1"):
            return True
        # Check if IPs match
        try:
            import socket
            local_ip = socket.gethostbyname(local)
            target_ip = socket.gethostbyname(node_name)
            return local_ip == target_ip
        except Exception:
            return False

    async def forward_request(self, method: str, target_node: str, path: str,
                              body: Optional[dict] = None, headers: Optional[dict] = None,
                              timeout: int = 30) -> dict:
        """Forward an API request to another cluster node."""
        try:
            # Ensure target has the correct address
            nodes = self.get_cluster_nodes()
            target_addr = target_node
            for n in nodes:
                if n["name"] == target_node:
                    target_addr = n["address"]
                    break

            url = f"http://{target_addr}:8000{path}"
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "GET":
                    r = await client.get(url, headers=headers or {})
                elif method.upper() == "POST":
                    r = await client.post(url, json=body, headers=headers or {})
                elif method.upper() == "PUT":
                    r = await client.put(url, json=body, headers=headers or {})
                elif method.upper() == "DELETE":
                    r = await client.delete(url, headers=headers or {})
                else:
                    return {"error": f"Unsupported method: {method}"}

                return {
                    "status_code": r.status_code,
                    "data": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text,
                    "node": target_node,
                }
        except httpx.ConnectError:
            return {"error": f"Cannot connect to node {target_node}", "node": target_node}
        except httpx.TimeoutException:
            return {"error": f"Request to {target_node} timed out", "node": target_node}
        except Exception as e:
            return {"error": str(e), "node": target_node}

    async def get_node_status(self, node_name: str) -> dict:
        """Check if a node is reachable and get its basic status."""
        try:
            result = await self.forward_request("GET", node_name, "/api/monitor/current")
            if "error" in result:
                return {"name": node_name, "status": "offline", "error": result["error"]}
            return {
                "name": node_name,
                "status": "online",
                "data": result.get("data", {}),
            }
        except Exception as e:
            return {"name": node_name, "status": "offline", "error": str(e)}

    async def get_all_nodes_status(self) -> list:
        """Get status of all cluster nodes."""
        nodes = self.get_cluster_nodes()
        results = []
        for node in nodes:
            if self.is_local(node["name"]):
                # Get local status directly
                try:
                    import psutil
                    results.append({
                        "name": node["name"],
                        "status": "online",
                        "local": True,
                        "cpu_percent": psutil.cpu_percent(interval=0.1),
                        "memory_percent": psutil.virtual_memory().percent,
                    })
                except Exception:
                    results.append({"name": node["name"], "status": "online", "local": True})
            else:
                status = await self.get_node_status(node["name"])
                status["local"] = False
                results.append(status)
        return results

    async def migrate_vm_to_node(self, vm_name: str, target_node: str, live: bool = True) -> dict:
        """Migrate a VM to another node via the migration API."""
        return await self.forward_request(
            "POST", target_node,
            f"/api/migration/vm/{vm_name}/migrate",
            body={"target_node": "localhost", "live": live}
        )
