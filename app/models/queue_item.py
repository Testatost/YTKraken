from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import List, Optional

_ID_COUNTER = count(1)


def next_queue_item_id() -> int:
    return next(_ID_COUNTER)


@dataclass
class QueueItem:
    url: str
    title: str = ""
    status: str = "waiting"
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    output: str = ""
    output_dir: str = ""
    error: str = ""
    item_id: int = field(default_factory=next_queue_item_id)
    parent: Optional["QueueItem"] = field(default=None, repr=False, compare=False)
    children: List["QueueItem"] = field(default_factory=list)

    def add_child(self, child: "QueueItem") -> None:
        child.parent = self
        self.children.append(child)

    def is_descendant_of(self, other: "QueueItem") -> bool:
        current = self.parent
        while current is not None:
            if current is other:
                return True
            current = current.parent
        return False
