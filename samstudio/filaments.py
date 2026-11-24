"""Measure visible filament centerlines and user-defined bridges across gaps."""

from dataclasses import dataclass
import math

import numpy as np
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from skimage.morphology import skeletonize


FILAMENT_METRICS = {
    "filament_visible_length": ("Filament visible length", 1, "Arc length of the visible centerline, extended to the visible ends."),
    "filament_gap_length": ("Filament estimated gap length", 1, "Sum of straight-line distances between the visible ends you connect."),
    "filament_total_length": ("Filament estimated total length", 1, "Visible centerline length plus estimated gap length."),
    "filament_width_mean": ("Filament mean width", 1, "Arc-length weighted mean of visible perpendicular cross-sections."),
    "filament_width_min": ("Filament minimum width", 1, "Minimum sampled width across the visible mask."),
    "filament_width_max": ("Filament maximum width", 1, "Maximum sampled width across the visible mask."),
    "filament_width_std": ("Filament width standard deviation", 1, "Arc-length weighted population standard deviation of visible widths."),
    "filament_width_variance": ("Filament width variance", 2, "Arc-length weighted population variance of visible widths, in squared length units."),
}
CONNECTIVITY = np.ones((3, 3), dtype=bool)


@dataclass(frozen=True)
class FilamentLink:
    first_id: str
    second_id: str
    first_anchor: tuple[float, float]
    second_anchor: tuple[float, float]

    def __post_init__(self):
        for name in ("first_anchor", "second_anchor"):
            point = np.asarray(getattr(self, name), dtype=float)
            if point.shape != (2,) or not np.isfinite(point).all():
                raise ValueError("A filament connection needs two finite endpoint locations.")
            object.__setattr__(self, name, tuple(point.tolist()))

    @property
    def ends(self):
        return ((self.first_id, self.first_anchor), (self.second_id, self.second_anchor))


def _chain_root(parents, node):
    while parents[node] != node:
        parents[node] = parents[parents[node]]
        node = parents[node]
    return node


def validate_links(links, objects, groups, background_group_id):
    """A connection joins two area annotations in one filament group, forming a chain."""
    filament_groups = {g.id for g in groups if g.filament and g.id != background_group_id}
    eligible = {o.id: o.group_id for o in objects if o.group_id in filament_groups
                and o.role == "object" and o.mask is not None and o.mask.any()}
    parents = {ident: ident for ident in eligible}
    used = {ident: set() for ident in eligible}
    for link in links:
        a, b = link.first_id, link.second_id
        if a not in eligible or b not in eligible or eligible[a] != eligible[b]:
            raise ValueError("Connect two area annotations in the same Filament group.")
        a_root, b_root = _chain_root(parents, a), _chain_root(parents, b)
        if a_root == b_root:
            raise ValueError("The fragments are already connected. A filament chain cannot make a loop.")
        for ident, anchor in link.ends:
            if len(used[ident]) >= 2 or anchor in used[ident]:
                raise ValueError("Each end of a visible fragment can have one connection.")
            used[ident].add(anchor)
        parents[b_root] = a_root


def filament_chains(objects, links):
    """Return members in document order and links for each measured object."""
    parents = {o.id: o.id for o in objects}
    for link in links:
        a, b = link.first_id, link.second_id
        if a in parents and b in parents:
            parents[_chain_root(parents, b)] = _chain_root(parents, a)
    members = {}
    for obj in objects:
        members.setdefault(_chain_root(parents, obj.id), []).append(obj)
    connections = {}
    for link in links:
        if link.first_id in parents and link.second_id in parents:
            connections.setdefault(_chain_root(parents, link.first_id), []).append(link)
    return [(fragments, connections.get(root, [])) for root, fragments in members.items()]


@dataclass
class FilamentTrace:
    points: np.ndarray
    length: float
    widths: np.ndarray
    weights: np.ndarray
    closed: bool
    branched: bool

    @property
    def endpoints(self):
        return self.points[[0, -1]]


def _skeleton_path(mask, matrix):
    skeleton = skeletonize(mask)
    rows, cols = np.nonzero(skeleton)
    size = len(rows)
    if size < 2:
        return None, False, False
    indices = np.full(skeleton.shape, -1, dtype=int)
    indices[rows, cols] = np.arange(size)
    sources, targets, lengths = [], [], []
    # A diagonal duplicates a corner if either orthogonal step is present.
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        ys, xs = rows + dy, cols + dx  # The component mask has a padding pixel.
        start = np.flatnonzero(skeleton[ys, xs])
        if dx and dy:
            start = start[~(skeleton[ys[start], cols[start]] | skeleton[rows[start], xs[start]])]
        end = indices[ys[start], xs[start]]
        sources.extend((start, end))
        targets.extend((end, start))
        lengths.extend((np.full(len(start), np.linalg.norm(matrix @ [dx, dy])),) * 2)
    graph = coo_matrix((np.concatenate(lengths), (np.concatenate(sources), np.concatenate(targets))),
                       shape=(size, size)).tocsr()
    degrees = np.diff(graph.indptr)
    ends = np.flatnonzero(degrees == 1)
    closed = bool(np.all(degrees == 2))
    branched = bool(np.any(degrees > 2))
    if closed:
        order = [0]
        previous = -1
        for _ in range(size - 1):
            current = order[-1]
            left, right = graph.indices[graph.indptr[current]:graph.indptr[current + 1]]
            order.append(int(right if left == previous else left))
            previous = current
    elif len(ends) >= 2:
        distances = dijkstra(graph, indices=ends[0])
        source = ends[np.argmax(distances[ends])]
        distances, predecessor = dijkstra(graph, indices=source, return_predecessors=True)
        target = ends[np.argmax(distances[ends])]
        order = [target]
        while order[-1] != source:
            order.append(predecessor[order[-1]])
    else:
        return None, closed, branched
    return np.column_stack((cols[order], rows[order])).astype(float), closed, branched


def _ray_distances(mask, points, directions):
    """Trace each ray to its first background pixel cell, in physical distance."""
    cells = np.floor(points + .5).astype(int)
    step = np.sign(directions).astype(int)
    delta = np.divide(1., np.abs(directions), out=np.full_like(directions, np.inf), where=step != 0)
    edge = cells + .5 * step
    crossings = np.divide(edge - points, directions, out=np.full_like(directions, np.inf), where=step != 0)
    active = np.arange(len(points))
    distances = np.zeros(len(points))
    while len(active):
        times = crossings[active]
        nearest = times.min(axis=1)
        crossed = times <= nearest[:, None]
        cells[active] += step[active] * crossed
        crossings[active] = np.where(crossed, times + delta[active], times)
        distances[active] = nearest
        x, y = cells[active].T  # First outside cell is always in the padding.
        active = active[mask[y, x]]
    return distances


def _trace_component(mask, matrix, offset):
    points, closed, branched = _skeleton_path(mask, matrix)
    if points is None:
        return None
    inverse = np.linalg.inv(matrix)
    n = len(points)
    index = np.arange(n)
    if closed:
        window = min(2, (n - 1) // 2)
        before, after = (index - window) % n, (index + window) % n
    else:
        before, after = np.maximum(index - 2, 0), np.minimum(index + 2, n - 1)
    tangents = (points[after] - points[before]) @ matrix.T
    tangents /= np.linalg.norm(tangents, axis=1, keepdims=True)
    normals = np.column_stack((-tangents[:, 1], tangents[:, 0])) @ inverse.T
    length_points = np.vstack((points, points[0])) if closed else points
    steps = np.linalg.norm(np.diff(length_points, axis=0) @ matrix.T, axis=1)
    if closed:
        samples = slice(None)
        weights = (steps + np.roll(steps, 1)) / 2
        ends = length_points
        extra_length = 0.
    else:
        samples = slice(1, -1) if n > 2 else slice(None)
        weights = (steps[:-1] + steps[1:]) / 2 if n > 2 else np.repeat(steps[0] / 2, 2)
        outward = (tangents[[0, -1]] * [[-1], [1]]) @ inverse.T
        extension = _ray_distances(mask, points[[0, -1]], outward)
        edges = points[[0, -1]] + outward * extension[:, None]
        ends = np.vstack((edges[0], points, edges[1]))
        extra_length = extension.sum()
    widths = (_ray_distances(mask, points[samples], normals[samples])
              + _ray_distances(mask, points[samples], -normals[samples]))
    return FilamentTrace(ends + offset, float(steps.sum() + extra_length), widths, weights, closed, branched)


def fragment_traces(obj, matrix, mask_key=None):
    """Analyze each visible component. Reuse pixel traces for editing and plots."""
    cache_mask, cache_key, traces = getattr(obj, "_filament_cache", (None, None, {}))
    if cache_mask is not obj.mask or (mask_key is not None and cache_key is not None and cache_key != mask_key):
        traces = {}
        cache_key = None
    if mask_key is not None:
        cache_key = mask_key
    obj._filament_cache = (obj.mask, cache_key, traces)
    key = matrix.tobytes()
    if key not in traces:
        if len(traces) >= 8:
            traces.clear()
        labels, _ = ndi.label(obj.mask, structure=CONNECTIVITY)
        components = ndi.find_objects(labels)
        result = []
        for index, bounds in enumerate(components, start=1):
            cropped = np.pad(labels[bounds] == index, 1)
            offset = np.array([bounds[1].start - 1, bounds[0].start - 1])
            result.append(_trace_component(cropped, matrix, offset))
        traces[key] = result
    return traces[key]


def open_endpoints(traces):
    if len(traces) == 1 and traces[0] is not None and not traces[0].closed and not traces[0].branched:
        return traces[0].endpoints
    return None


def resolve_bridge(link, endpoints):
    """Snap saved anchors to the nearest current visible endpoints."""
    resolved = []
    for ident, anchor in link.ends:
        pair = endpoints.get(ident)
        if pair is None:
            return None
        index = int(np.argmin(np.linalg.norm(pair - anchor, axis=1)))
        resolved.append((ident, index, pair[index]))
    return resolved


def filament_values(members, links, matrix, mask_keys):
    traces = {obj.id: fragment_traces(obj, matrix, mask_keys[obj.id]) for obj in members}
    visible = [trace for pieces in traces.values() for trace in pieces if trace is not None]
    if not visible:
        return {}, "A visible centerline could not be resolved at this pixel resolution."
    notes = []
    if any(len(pieces) > 1 for pieces in traces.values()):
        notes.append("Disconnected components in a mask contribute visible length only.")
    if any(trace is None for pieces in traces.values() for trace in pieces):
        notes.append("Some components were too small or ambiguous to trace.")
    if any(trace.branched for trace in visible):
        notes.append("Branched masks use a principal path between skeleton ends.")

    endpoints = {ident: open_endpoints(pieces) for ident, pieces in traces.items()}
    used = set()
    gap = 0.
    for link in links:
        bridge = resolve_bridge(link, endpoints)
        if bridge is None or any((ident, index) in used for ident, index, _ in bridge):
            gap = None
            notes.append("An endpoint could not be resolved. Disconnect and reconnect the edited fragments.")
            break
        used.update((ident, index) for ident, index, _ in bridge)
        gap += float(np.linalg.norm(matrix @ (bridge[1][2] - bridge[0][2])))

    length = sum(trace.length for trace in visible)
    widths = np.concatenate([trace.widths for trace in visible])
    weights = np.concatenate([trace.weights for trace in visible])
    mean = float(np.average(widths, weights=weights))
    variance = float(np.average((widths - mean) ** 2, weights=weights))
    return {
        "filament_visible_length": length,
        "filament_gap_length": gap,
        "filament_total_length": length + gap if gap is not None else None,
        "filament_width_mean": mean,
        "filament_width_min": float(widths.min()),
        "filament_width_max": float(widths.max()),
        "filament_width_std": math.sqrt(variance),
        "filament_width_variance": variance,
    }, " ".join(notes)
