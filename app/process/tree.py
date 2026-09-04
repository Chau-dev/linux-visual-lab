from __future__ import annotations

from dataclasses import dataclass, field
from app.process.model import Process


@dataclass
class ProcessTreeNode:
    """
    Represents a node in the real Linux PID/PPID process tree hierarchy.
    """

    process: Process
    children: list[ProcessTreeNode] = field(default_factory=list)
    depth: int = 0


def build_process_tree(processes: dict[int, Process]) -> list[ProcessTreeNode]:
    """
    Construct a real process tree strictly from PID and PPID.

    No simulated relationships:
    - Root nodes: Processes whose PPID is not present in the snapshot or PPID == 0 / PPID == PID.
    - Child nodes: Attached to their real parent where child.ppid == parent.pid.
    """
    if not processes:
        return []

    nodes: dict[int, ProcessTreeNode] = {
        pid: ProcessTreeNode(process=proc, children=[], depth=0)
        for pid, proc in processes.items()
    }

    roots: list[ProcessTreeNode] = []

    for pid, node in nodes.items():
        ppid = node.process.ppid
        if ppid in nodes and ppid != pid:
            nodes[ppid].children.append(node)
        else:
            roots.append(node)

    # Sort roots and children by PID for consistent deterministic layout
    roots.sort(key=lambda n: n.process.pid)

    def _sort_and_set_depth(node: ProcessTreeNode, current_depth: int):
        node.depth = current_depth
        node.children.sort(key=lambda n: n.process.pid)
        for child in node.children:
            _sort_and_set_depth(child, current_depth + 1)

    for root in roots:
        _sort_and_set_depth(root, 0)

    return roots


def flatten_process_tree(roots: list[ProcessTreeNode]) -> list[tuple[Process, int]]:
    """
    Flatten tree hierarchy into (Process, depth) pairs in depth-first order.
    """
    result: list[tuple[Process, int]] = []

    def _traverse(node: ProcessTreeNode):
        result.append((node.process, node.depth))
        for child in node.children:
            _traverse(child)

    for root in roots:
        _traverse(root)

    return result
