"""
In-memory LRU cache for per-building STEP shapes (Issue #192).

Caches TopoDS_Shape objects keyed by
(gml_id, precision_mode, shape_fix_level, lod_target)
to avoid re-processing the same building when:
- The same building appears in multiple API requests
- A multi-building batch includes duplicates

The cache is bounded (default 128 entries) and uses LRU eviction.
TopoDS_Shape objects are C++ objects managed by OCCT, so this cache
keeps them alive in memory.
"""

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple, Union
import threading

# Cache key: (gml_id, precision_mode, shape_fix_level, lod_target)
CacheKey = Tuple[str, str, str, str]


@dataclass(frozen=True)
class CachedShape:
    shape: Any
    used_lods: Tuple[str, ...]

    @property
    def lod_used(self) -> str:
        if len(self.used_lods) == 1:
            return self.used_lods[0]
        return "mixed" if self.used_lods else "unknown"


class ShapeCache:
    """
    Thread-safe LRU cache for TopoDS_Shape objects.

    Each entry is keyed by (gml_id, precision_mode, shape_fix_level).
    When the cache exceeds max_size, the least recently used entry is evicted.

    Usage:
        cache = ShapeCache(max_size=128)
        key = ("bldg_abc123", "ultra", "minimal", "LOD2")

        # Check cache before expensive computation
        shape = cache.get(key)
        if shape is None:
            shape = expensive_build_shape(...)
            cache.put(key, shape, "LOD2")
    """

    def __init__(self, max_size: int = 128):
        self._max_size = max_size
        self._cache: OrderedDict[CacheKey, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: CacheKey) -> Optional[CachedShape]:
        """
        Look up a cached shape. Returns None on miss.
        Moves the entry to the end (most recently used) on hit.
        """
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(
        self, key: CacheKey, shape: Any, used_lods: Union[str, Iterable[str]]
    ) -> None:
        """
        Store a shape in the cache. Evicts LRU entry if at capacity.
        """
        normalized_lods = (
            (used_lods,)
            if isinstance(used_lods, str)
            else tuple(sorted(set(used_lods)))
        )
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = CachedShape(shape=shape, used_lods=normalized_lods)
            else:
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)  # Evict LRU
                self._cache[key] = CachedShape(shape=shape, used_lods=normalized_lods)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict:
        """Return cache hit/miss statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1f}%",
            }


# Module-level singleton for cross-request caching
_global_cache = ShapeCache(max_size=128)


def get_shape_cache() -> ShapeCache:
    """Return the global shape cache singleton."""
    return _global_cache
