"""File-based storage of one experiment run.

Layout::

    runs/<experiment_id>/
        state.json            # ExperimentState after every orchestrator node
        iterations/iter_XX.json
        arrays/*.npy          # masks, frames, matrices - referenced by data_ref
        llm_calls.jsonl       # one line per LLM call
        final_report.md

Large arrays never travel through contracts or LLM prompts: only their ``data_ref`` (a
path relative to the run directory) does.
"""

import json
import re
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

from experimental_system.schemas.state import ExperimentState, IterationRecord

_SAFE_NAME = re.compile(r"[^a-z0-9_]+")


class StorageError(RuntimeError):
    """Invalid data_ref or unreadable run data."""


class ArrayStore(Protocol):
    """What a backend needs: save an array -> data_ref, load it back."""

    def save_array(self, name: str, array: npt.NDArray[Any]) -> str: ...

    def load_array(self, data_ref: str) -> npt.NDArray[Any]: ...


class RunStore:
    """Implements ``ArrayStore`` plus state / iteration / log / report persistence."""

    def __init__(self, root: Path, experiment_id: str) -> None:
        self.dir = root / experiment_id
        self.arrays_dir = self.dir / "arrays"
        self.iterations_dir = self.dir / "iterations"
        for d in (self.arrays_dir, self.iterations_dir):
            d.mkdir(parents=True, exist_ok=True)
        self._counter = len(list(self.arrays_dir.glob("*.npy")))
        self.prefix = ""  # set by the orchestrator, e.g. "it01"

    # --- arrays -----------------------------------------------------------------------------

    def save_array(self, name: str, array: npt.NDArray[Any]) -> str:
        self._counter += 1
        safe = _SAFE_NAME.sub("_", name.lower()).strip("_") or "array"
        stem = (
            f"{self.prefix}_{self._counter:04d}_{safe}"
            if self.prefix
            else f"{self._counter:04d}_{safe}"
        )
        np.save(self.arrays_dir / f"{stem}.npy", array, allow_pickle=False)
        return f"arrays/{stem}.npy"

    def load_array(self, data_ref: str) -> npt.NDArray[Any]:
        path = (self.dir / data_ref).resolve()
        if self.arrays_dir.resolve() not in path.parents or path.suffix != ".npy":
            raise StorageError(f"data_ref outside the run arrays directory: {data_ref!r}")
        if not path.is_file():
            raise StorageError(f"array not found: {data_ref!r}")
        return np.asarray(np.load(path, allow_pickle=False))

    # --- state, iterations, logs, report ----------------------------------------------------

    def save_state(self, state: ExperimentState) -> None:
        _atomic_write(self.dir / "state.json", state.model_dump_json(indent=2))

    def load_state(self) -> ExperimentState:
        path = self.dir / "state.json"
        if not path.is_file():
            raise StorageError(f"no state.json in {self.dir}")
        return ExperimentState.model_validate_json(path.read_text(encoding="utf-8"))

    def save_iteration(self, record: IterationRecord) -> None:
        path = self.iterations_dir / f"iter_{record.iteration:02d}.json"
        _atomic_write(path, record.model_dump_json(indent=2))

    def append_jsonl(self, name: str, entry: dict[str, Any]) -> None:
        with (self.dir / name).open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def write_text(self, name: str, text: str) -> Path:
        path = self.dir / name
        _atomic_write(path, text)
        return path


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
