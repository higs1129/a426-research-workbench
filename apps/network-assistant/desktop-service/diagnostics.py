from __future__ import annotations

import concurrent.futures
import datetime as dt
import ipaddress
import json
import math
import os
import re
import statistics
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Iterable


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PONG_RE = re.compile(
    r"pong from .+? via (?P<route>.+?) in (?P<value>[0-9.]+)(?P<unit>ms|s)\s*$",
    re.IGNORECASE,
)
DERP_RE = re.compile(r"DERP\((?P<code>[^)]+)\)", re.IGNORECASE)


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    elapsed_ms: int
    timed_out: bool = False

    @property
    def combined(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part).strip()


def _creation_flags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def run_command(args: Iterable[str], timeout: float = 10.0) -> CommandResult:
    command = tuple(str(item) for item in args)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=_creation_flags(),
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return CommandResult(
            args=command,
            returncode=completed.returncode,
            stdout=ANSI_RE.sub("", completed.stdout or "").strip(),
            stderr=ANSI_RE.sub("", completed.stderr or "").strip(),
            elapsed_ms=elapsed_ms,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else exc.stdout
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else exc.stderr
        return CommandResult(
            args=command,
            returncode=None,
            stdout=ANSI_RE.sub("", stdout or "").strip(),
            stderr=ANSI_RE.sub("", stderr or "").strip(),
            elapsed_ms=elapsed_ms,
            timed_out=True,
        )
    except OSError:
        return CommandResult(
            args=command,
            returncode=None,
            stdout="",
            stderr="command_unavailable",
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )


def _load_json(result: CommandResult) -> Any:
    if result.returncode != 0:
        raise RuntimeError(result.combined or f"command exited with {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("command returned invalid JSON") from exc


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _peer_matches(peer: dict[str, Any], selector: str) -> bool:
    wanted = selector.strip().rstrip(".").lower()
    candidates: list[str] = []
    for key in ("ID", "HostName", "DNSName"):
        value = peer.get(key)
        if value:
            candidates.append(str(value).rstrip(".").lower())
    candidates.extend(str(item).lower() for item in peer.get("TailscaleIPs") or [])
    return wanted in candidates


def find_peer(status: dict[str, Any], selector: str) -> dict[str, Any] | None:
    peers = status.get("Peer") or {}
    values = peers.values() if isinstance(peers, dict) else peers
    for peer in values:
        if isinstance(peer, dict) and _peer_matches(peer, selector):
            return peer
    return None


def public_peer_status(peer: dict[str, Any]) -> dict[str, Any]:
    ips = [str(item) for item in (peer.get("TailscaleIPs") or [])]
    return {
        "id": peer.get("ID"),
        "host_name": peer.get("HostName"),
        "dns_name": str(peer.get("DNSName") or "").rstrip("."),
        "control_online": bool(peer.get("Online")),
        "active_recently": bool(peer.get("Active")),
        "last_seen": peer.get("LastSeen"),
        "last_handshake": peer.get("LastHandshake"),
        "tailscale_ipv4": next((item for item in ips if ":" not in item), None),
        "has_tailscale_ipv6": any(":" in item for item in ips),
        "cached_derp": peer.get("Relay") or None,
        "cached_peer_relay": peer.get("PeerRelay") or None,
    }


def _endpoint_family(route: str) -> str | None:
    endpoint = route.strip()
    if endpoint.startswith("["):
        host = endpoint[1:].split("]", 1)[0]
    else:
        host = endpoint.rsplit(":", 1)[0]
    try:
        return "ipv6" if ipaddress.ip_address(host).version == 6 else "ipv4"
    except ValueError:
        return None


def _path_from_route(route: str) -> tuple[str, str | None]:
    derp = DERP_RE.search(route)
    if derp:
        return "derp", derp.group("code").lower()
    if "peer-relay" in route.lower() or "peer relay" in route.lower():
        return "peer_relay", None
    family = _endpoint_family(route)
    if family:
        return f"direct_{family}", None
    return "unknown", None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def _rtt_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p50": None, "p95": None, "max": None, "jitter": None}
    differences = [abs(right - left) for left, right in zip(values, values[1:])]
    return {
        "min": round(min(values), 1),
        "p50": round(statistics.median(values), 1),
        "p95": round(_percentile(values, 0.95) or 0, 1),
        "max": round(max(values), 1),
        "jitter": round(statistics.mean(differences), 1) if differences else 0.0,
    }


def parse_ping_output(output: str, attempted: int) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for line in ANSI_RE.sub("", output).splitlines():
        match = PONG_RE.search(line.strip())
        if not match:
            continue
        value = float(match.group("value"))
        latency_ms = value * 1000 if match.group("unit").lower() == "s" else value
        path, relay = _path_from_route(match.group("route"))
        samples.append({"path": path, "relay": relay, "latency_ms": latency_ms})

    path_names = ("direct_ipv6", "direct_ipv4", "peer_relay", "derp", "unknown")
    counts = {name: sum(sample["path"] == name for sample in samples) for name in path_names}
    # Earlier samples may be DERP/direct warm-up history. The last successful
    # sample is the least stale answer to "what path is in use now?".
    path = samples[-1]["path"] if samples else "unreachable"
    selected = [sample["latency_ms"] for sample in samples if sample["path"] == path]
    relay_codes = [sample["relay"] for sample in samples if sample["path"] == "derp" and sample["relay"]]
    relay = samples[-1]["relay"] if samples and path == "derp" else None
    transitions: list[str] = []
    for sample in samples:
        if not transitions or transitions[-1] != sample["path"]:
            transitions.append(sample["path"])
    received = len(samples)
    attempted = max(attempted, received)
    return {
        "path": path,
        "relay": relay,
        "last_derp_relay": relay_codes[-1] if relay_codes else None,
        "path_transitions": transitions,
        "attempted": attempted,
        "received": received,
        "loss_pct": round((attempted - received) * 100 / attempted, 1) if attempted else None,
        "path_samples": counts,
        "rtt_ms": _rtt_summary(selected),
        "direct_established": path.startswith("direct_"),
        "raw_summary": "direct connection not established" if "direct connection not established" in output.lower() else None,
    }


def _safe_error(result: CommandResult) -> str:
    if result.timed_out:
        return "timeout"
    if result.returncode not in (0, None):
        return f"exit_{result.returncode}"
    return "unavailable"


def _run_ping(peer_ip: str, attempts: int) -> dict[str, Any]:
    result = run_command(
        (
            "tailscale",
            "ping",
            "--verbose",
            "--until-direct=false",
            "--c",
            str(attempts),
            "--timeout",
            "2s",
            peer_ip,
        ),
        timeout=max(8.0, attempts * 2.5 + 3),
    )
    parsed = parse_ping_output(result.combined, attempts)
    parsed["probe_elapsed_ms"] = result.elapsed_ms
    if result.timed_out and not parsed["received"]:
        parsed["error"] = "timeout"
    elif result.returncode not in (0, None) and not parsed["received"]:
        parsed["error"] = _safe_error(result)
    return parsed


def _derp_regions() -> dict[str, dict[str, Any]]:
    result = run_command(("tailscale", "debug", "derp-map"), timeout=5)
    try:
        data = _load_json(result)
    except RuntimeError:
        return {}
    regions = data.get("Regions") or {}
    return {
        str(region_id): {
            "code": value.get("RegionCode"),
            "name": value.get("RegionName"),
        }
        for region_id, value in regions.items()
        if isinstance(value, dict)
    }


def _run_netcheck() -> dict[str, Any]:
    result = run_command(("tailscale", "netcheck", "--format", "json"), timeout=12)
    try:
        data = _load_json(result)
    except RuntimeError:
        return {"ok": False, "error": _safe_error(result)}

    regions = _derp_regions()
    preferred_id = str(data.get("PreferredDERP")) if data.get("PreferredDERP") is not None else None
    latency_raw = data.get("RegionLatency") or {}
    latency = []
    for region_id, nanoseconds in latency_raw.items():
        region = regions.get(str(region_id), {})
        latency.append(
            {
                "id": str(region_id),
                "code": region.get("code"),
                "name": region.get("name"),
                "latency_ms": round(float(nanoseconds) / 1_000_000, 1),
            }
        )
    latency.sort(key=lambda item: item["latency_ms"])
    return {
        "ok": True,
        "udp": bool(data.get("UDP")),
        "ipv4": bool(data.get("IPv4")),
        "ipv6": bool(data.get("IPv6")),
        "mapping_varies_by_destination": bool(data.get("MappingVariesByDestIP")),
        "port_mapping": {
            "upnp": bool(data.get("UPnP")),
            "pmp": bool(data.get("PMP")),
            "pcp": bool(data.get("PCP")),
        },
        "captive_portal": bool(data.get("CaptivePortal")),
        "preferred_derp": next((item for item in latency if item["id"] == preferred_id), None),
        "nearest_derp": latency[:4],
    }


def _dns_query(name: str, record_type: str = "A") -> dict[str, Any]:
    started = time.perf_counter()
    result = run_command(("tailscale", "dns", "query", "--json", name, record_type), timeout=5)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    try:
        data = _load_json(result)
    except RuntimeError:
        return {"ok": False, "name": name, "type": record_type, "elapsed_ms": elapsed_ms, "error": _safe_error(result)}
    response_code = data.get("ResponseCode")
    return {
        "ok": response_code == "RCodeSuccess",
        "name": name,
        "type": record_type,
        "response_code": response_code,
        "elapsed_ms": elapsed_ms,
        "answer_count": len(data.get("Answers") or []),
        "resolver_count": len(data.get("Resolvers") or []),
    }


def _run_dns(dns_name: str | None) -> dict[str, Any]:
    status_result = run_command(("tailscale", "dns", "status", "--all", "--json"), timeout=5)
    try:
        status = _load_json(status_result)
    except RuntimeError:
        status = {}
    public_query = _dns_query("example.com", "A")
    magic_query = _dns_query(dns_name, "A") if dns_name else {"ok": False, "error": "peer_has_no_dns_name"}
    system_dns = status.get("SystemDNS") or {}
    return {
        "tailscale_dns_enabled": bool(status.get("TailscaleDNS")),
        "magic_dns_enabled": bool((status.get("CurrentTailnet") or {}).get("MagicDNSEnabled")),
        "system_nameserver_count": len(system_dns.get("Nameservers") or []),
        "public": public_query,
        "magic": magic_query,
        "ready": bool(public_query.get("ok") and magic_query.get("ok")),
    }


def _version() -> str | None:
    result = run_command(("tailscale", "version"), timeout=3)
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()[0].strip() if result.stdout else None


def collect_diagnostics(peer_selector: str, ping_attempts: int = 6) -> dict[str, Any]:
    started = time.perf_counter()
    status_result = run_command(("tailscale", "status", "--json"), timeout=6)
    try:
        status = _load_json(status_result)
    except RuntimeError:
        return {
            "ok": False,
            "generated_at": _iso_now(),
            "error": "tailscale_status_unavailable",
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    }
    peer = find_peer(status, peer_selector)
    if not peer:
        return {
            "ok": False,
            "generated_at": _iso_now(),
            "error": "peer_not_found",
            "peer_selector": peer_selector,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }

    public_peer = public_peer_status(peer)
    peer_ip = public_peer.get("tailscale_ipv4")
    if not peer_ip:
        return {
            "ok": False,
            "generated_at": _iso_now(),
            "error": "peer_has_no_tailscale_ipv4",
            "peer": public_peer,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }

    attempts = ping_attempts if public_peer["control_online"] else min(3, ping_attempts)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        ping_future = executor.submit(_run_ping, str(peer_ip), attempts)
        netcheck_future = executor.submit(_run_netcheck)
        dns_future = executor.submit(_run_dns, public_peer.get("dns_name"))
        path = ping_future.result()
        local_network = netcheck_future.result()
        dns = dns_future.result()

    warnings: list[str] = []
    if not public_peer["control_online"]:
        warnings.append("phone_control_offline")
    if path.get("path") == "unreachable":
        warnings.append("phone_probe_unreachable")
    elif path.get("path") == "derp":
        warnings.append("using_derp")
    elif path.get("path") == "peer_relay":
        warnings.append("using_peer_relay")
    if not dns.get("ready"):
        warnings.append("a426_dns_not_ready")
    if local_network.get("mapping_varies_by_destination"):
        warnings.append("a426_hard_nat")

    return {
        "ok": True,
        "generated_at": _iso_now(),
        "server": {"name": status.get("Self", {}).get("HostName") or "A426", "tailscale_version": _version()},
        "peer": public_peer,
        "path": path,
        "a426_network": local_network,
        "a426_dns": dns,
        "warnings": warnings,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    }
