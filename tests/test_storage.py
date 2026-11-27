"""RunStore: arrays by data_ref, state/iteration persistence, path safety."""

from pathlib import Path

import numpy as np
import pytest

from experimental_system.storage import RunStore, StorageError
from factories import make_state


def test_array_round_trip(tmp_path: Path) -> None:
    store = RunStore(tmp_path, "exp1")
    store.prefix = "it01"
    ref = store.save_array("S1 tm/estimate", np.arange(6).reshape(2, 3) + 1j)
    assert ref.startswith("arrays/it01_0001_s1_tm_estimate")
    assert np.array_equal(store.load_array(ref), np.arange(6).reshape(2, 3) + 1j)
    second = store.save_array("x", np.zeros(1))
    assert second != ref


@pytest.mark.parametrize("ref", ["../../etc/passwd", "state.json", "arrays/missing.npy"])
def test_bad_data_ref(tmp_path: Path, ref: str) -> None:
    store = RunStore(tmp_path, "exp1")
    (store.dir / "state.json").write_text("{}")
    with pytest.raises(StorageError):
        store.load_array(ref)


def test_state_and_iteration_persistence(tmp_path: Path) -> None:
    store = RunStore(tmp_path, "exp1")
    state = make_state()
    store.save_state(state)
    assert store.load_state() == state
    store.save_iteration(state.history[0])
    assert (store.iterations_dir / "iter_00.json").is_file()
    store.append_jsonl("llm_calls.jsonl", {"agent": "scientist"})
    store.append_jsonl("llm_calls.jsonl", {"agent": "analyst"})
    assert len((store.dir / "llm_calls.jsonl").read_text().splitlines()) == 2


def test_counter_continues_after_reopen(tmp_path: Path) -> None:
    first = RunStore(tmp_path, "exp1").save_array("a", np.zeros(1))
    second = RunStore(tmp_path, "exp1").save_array("a", np.zeros(1))
    assert first != second
