import pytest

from nova.memory.store import MemoryRecord, MemoryStore, UnknownMemoryKindError


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "memory.db")
    yield s
    s.close()


def test_remember_then_get_round_trips(store):
    record = store.remember("preference", "editor", "VS Code")

    assert isinstance(record, MemoryRecord)
    fetched = store.get("editor")
    assert fetched.value == "VS Code"
    assert fetched.kind == "preference"


def test_get_returns_none_for_unknown_key(store):
    assert store.get("nope") is None


def test_remember_upserts_on_the_same_key(store):
    store.remember("preference", "editor", "Vim")
    store.remember("preference", "editor", "VS Code")

    assert store.get("editor").value == "VS Code"
    assert len(store.all()) == 1


def test_upsert_preserves_created_at_and_moves_updated_at(store):
    first = store.remember("fact", "k", "v1")
    second = store.remember("fact", "k", "v2")

    assert second.created_at == first.created_at
    assert second.updated_at >= first.updated_at


def test_rejects_an_unknown_kind(store):
    with pytest.raises(UnknownMemoryKindError):
        store.remember("nonsense", "k", "v")


def test_forget_removes_the_record(store):
    store.remember("fact", "k", "v")

    assert store.forget("k") is True
    assert store.get("k") is None


def test_forget_returns_false_when_absent(store):
    assert store.forget("never-existed") is False


def test_all_is_sorted_by_key(store):
    store.remember("fact", "zebra", "z")
    store.remember("fact", "apple", "a")

    assert [r.key for r in store.all()] == ["apple", "zebra"]


def test_recall_matches_on_value_text(store):
    store.remember("project", "mri", "Training an MRI segmentation model in PyTorch")
    store.remember("project", "website", "Personal portfolio site in Astro")

    results = store.recall("segmentation pytorch")

    assert [r.key for r in results] == ["mri"]


def test_recall_matches_on_key_text(store):
    store.remember("preference", "editor", "VS Code")
    store.remember("preference", "shell", "PowerShell")

    results = store.recall("editor")

    assert results[0].key == "editor"


def test_recall_ranks_more_overlap_first(store):
    store.remember("fact", "a", "python testing")
    store.remember("fact", "b", "python testing with pytest fixtures")

    results = store.recall("python testing pytest fixtures")

    assert results[0].key == "b"


def test_recall_returns_empty_when_nothing_matches(store):
    store.remember("fact", "a", "completely unrelated")

    assert store.recall("quantum chromodynamics") == []


def test_recall_respects_the_limit(store):
    for i in range(10):
        store.remember("fact", f"k{i}", "shared keyword here")

    assert len(store.recall("shared keyword", limit=3)) == 3


def test_recall_ignores_case_and_punctuation(store):
    store.remember("fact", "k", "The MRI Model, trained nightly.")

    assert store.recall("mri model") != []


def test_store_persists_across_reopen(tmp_path):
    path = tmp_path / "memory.db"
    first = MemoryStore(path)
    first.remember("preference", "editor", "VS Code")
    first.close()

    second = MemoryStore(path)
    try:
        assert second.get("editor").value == "VS Code"
    finally:
        second.close()


def test_creates_parent_directories(tmp_path):
    store = MemoryStore(tmp_path / "deep" / "nested" / "memory.db")
    try:
        store.remember("fact", "k", "v")
        assert (tmp_path / "deep" / "nested" / "memory.db").is_file()
    finally:
        store.close()


def test_describe_for_prompt_is_empty_when_no_matches(store):
    assert store.describe_for_prompt("anything") == ""


def test_describe_for_prompt_lists_matches(store):
    store.remember("preference", "editor", "VS Code")

    text = store.describe_for_prompt("editor")

    assert "editor" in text
    assert "VS Code" in text
    assert "preference" in text
