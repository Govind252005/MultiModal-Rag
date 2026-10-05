"""
Minimal, dependency-free Prometheus-compatible metrics registry (brief
§125-§126). Deliberately does not depend on the `prometheus_client`
package — this app targets a local/desktop deployment first and a
"pip install prometheus_client" requirement shouldn't be forced onto that
path just to expose a few counters. If you already use
`prometheus_client` elsewhere, swap this module out; the /metrics route
in main.py only depends on `render()` returning the exposition-format text.

Thread safety: a single lock guards all mutations. This is fine at the
request rates a local/desktop deployment sees; a high-throughput
multi-process production deployment should switch to `prometheus_client`
with its multiprocess mode instead of scaling this module.
"""

from __future__ import annotations

import threading
from typing import Dict, Tuple

_lock = threading.Lock()
_counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
_histogram_buckets: Dict[str, list] = {}
_histogram_values: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], list] = {}

DEFAULT_LATENCY_BUCKETS_MS = [50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000]


def _key(name: str, labels: Dict[str, str]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
    return name, tuple(sorted((labels or {}).items()))


def inc_counter(name: str, labels: Dict[str, str] | None = None, value: float = 1.0) -> None:
    k = _key(name, labels or {})
    with _lock:
        _counters[k] = _counters.get(k, 0.0) + value


def observe_histogram(name: str, value_ms: float, labels: Dict[str, str] | None = None,
                      buckets=None) -> None:
    k = _key(name, labels or {})
    with _lock:
        _histogram_buckets[name] = buckets or DEFAULT_LATENCY_BUCKETS_MS
        _histogram_values.setdefault(k, []).append(value_ms)


def _fmt_labels(labels: Tuple[Tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    parts = ",".join(f'{k}="{v}"' for k, v in labels)
    return "{" + parts + "}"


def render() -> str:
    """Prometheus text exposition format (brief §125)."""
    lines = []
    with _lock:
        counters = dict(_counters)
        hist_values = {k: list(v) for k, v in _histogram_values.items()}
        hist_buckets = dict(_histogram_buckets)

    seen_counter_names = set()
    for (name, labels), value in sorted(counters.items()):
        if name not in seen_counter_names:
            lines.append(f"# TYPE {name} counter")
            seen_counter_names.add(name)
        lines.append(f"{name}{_fmt_labels(labels)} {value}")

    seen_hist_names = set()
    for (name, labels), values in sorted(hist_values.items()):
        if name not in seen_hist_names:
            lines.append(f"# TYPE {name} histogram")
            seen_hist_names.add(name)
        buckets = hist_buckets.get(name, DEFAULT_LATENCY_BUCKETS_MS)
        base_labels = dict(labels)
        cumulative = 0
        for b in buckets:
            cumulative = sum(1 for v in values if v <= b)
            lbls = dict(base_labels, le=str(b))
            lines.append(f"{name}_bucket{_fmt_labels(tuple(sorted(lbls.items())))} {cumulative}")
        lbls_inf = dict(base_labels, le="+Inf")
        lines.append(f"{name}_bucket{_fmt_labels(tuple(sorted(lbls_inf.items())))} {len(values)}")
        lines.append(f"{name}_sum{_fmt_labels(labels)} {sum(values)}")
        lines.append(f"{name}_count{_fmt_labels(labels)} {len(values)}")

    return "\n".join(lines) + "\n"


def reset() -> None:
    """Test-only: clear all recorded metrics."""
    with _lock:
        _counters.clear()
        _histogram_values.clear()
        _histogram_buckets.clear()
