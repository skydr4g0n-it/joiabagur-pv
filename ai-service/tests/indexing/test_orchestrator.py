"""Catalog orchestrator: skip-embed, tombstone, isolation, cursor precedence, hash."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest

from jbg_ai.indexing.feed import FeedCursor
from jbg_ai.indexing.orchestrator import (
    CatalogSyncRequest,
    report_index_status,
    reset_batch_size_warning,
    sync_catalog,
)
from jbg_ai.indexing.repository import SyncCheckpoint
from jbg_ai.indexing.set_hash import of_product_ids
from jbg_ai.indexing.sync_errors import IndexFeedConfigError, ProvenanceMapError
from support.index_fakes import (
    FakeEmbeddingClient,
    FakeIndexFeedClient,
    FakeProductDocumentRepo,
    make_page,
    make_tombstone,
    make_upsert,
)

MAP = {
    "SKU01": {"data_origin": "real", "text_provenance": "ai_assisted"},
    "SKU02": {"data_origin": "real", "text_provenance": "merchant"},
}

A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TS = datetime(2026, 8, 26, 10, 0, tzinfo=UTC)


def _run(coro):
    import asyncio

    return asyncio.run(coro)


async def _sync(feed, embed, repo, provenance=MAP, **kwargs):
    request = kwargs.pop("request", CatalogSyncRequest(full=True))
    return await sync_catalog(
        request,
        feed=feed,
        embed=embed,
        repo=repo,
        provenance_map=provenance,
        **kwargs,
    )


def test_upsert_is_idempotent_for_same_source_hash() -> None:
    item = make_upsert(sku="SKU01", product_id=A, price="48.00", price_band="0-50")
    feed = FakeIndexFeedClient([make_page([item])])
    embed = FakeEmbeddingClient()
    repo = FakeProductDocumentRepo()
    _run(_sync(feed, embed, repo))
    assert len(embed.calls) == 1

    item2 = make_upsert(sku="SKU01", product_id=A, price="72.00", price_band="50-100")
    feed2 = FakeIndexFeedClient([make_page([item2])])
    result = _run(_sync(feed2, embed, repo, request=CatalogSyncRequest(full=True)))
    stored = _run(repo.get_by_product_id(A))
    assert stored is not None
    assert stored.price is not None and str(stored.price) == "72.00"
    assert stored.price_band == "50-100"
    assert result.skipped == 1
    assert result.upserted == 0
    assert len(embed.calls) == 1


def test_family_name_rename_re_embeds() -> None:
    first = make_upsert(sku="SKU01", product_id=A, family_name="Anillo erizo de mar")
    embed = FakeEmbeddingClient()
    repo = FakeProductDocumentRepo()
    _run(_sync(FakeIndexFeedClient([make_page([first])]), embed, repo))
    before = _run(repo.get_by_product_id(A))
    assert before is not None
    assert len(embed.calls) == 1

    renamed = make_upsert(sku="SKU01", product_id=A, family_name="Anillo concha")
    result = _run(
        _sync(
            FakeIndexFeedClient([make_page([renamed])]),
            embed,
            repo,
            request=CatalogSyncRequest(full=True),
        )
    )
    after = _run(repo.get_by_product_id(A))
    assert after is not None
    assert after.source_hash != before.source_hash
    assert after.family_name == "Anillo concha"
    assert result.upserted == 1
    assert result.skipped == 0
    assert len(embed.calls) == 2


def test_tombstone_removes_document_from_index() -> None:
    item = make_upsert(sku="SKU01", product_id=A)
    repo = FakeProductDocumentRepo()
    embed = FakeEmbeddingClient()
    _run(_sync(FakeIndexFeedClient([make_page([item])]), embed, repo))
    assert _run(repo.get_by_product_id(A)) is not None

    first = _run(
        _sync(
            FakeIndexFeedClient([make_page([make_tombstone(A)])]),
            embed,
            repo,
        )
    )
    assert first.deleted == 1
    assert _run(repo.get_by_product_id(A)) is None

    second = _run(
        _sync(
            FakeIndexFeedClient([make_page([make_tombstone(A, reason="unapproved")])]),
            embed,
            repo,
        )
    )
    assert second.deleted == 0
    assert second.failed == 0
    assert repo.failures == []


def test_upsert_leaves_tsv_not_null() -> None:
    item = make_upsert(sku="SKU01", product_id=A)
    repo = FakeProductDocumentRepo()
    embed = FakeEmbeddingClient()
    _run(_sync(FakeIndexFeedClient([make_page([item])]), embed, repo))
    stored = _run(repo.get_by_product_id(A))
    assert stored is not None
    assert stored.embedding is not None
    assert len(stored.embedding) == 1536
    assert stored.tsv
    assert stored.embedding_version == embed.document_version_key


def test_failed_item_recorded_and_does_not_block_others() -> None:
    good = make_upsert(sku="SKU01", product_id=A)
    bad = make_upsert(sku="SKU02", product_id=B)

    class SelectiveEmbed(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            from jbg_ai.indexing.embeddings import EmbedResult

            self.calls.append(list(texts))
            if any("SKU: SKU02" in text for text in texts):
                raise RuntimeError("embed failed")
            vectors = [[0.01] * self.dimension for _ in texts]
            return EmbedResult(
                vectors=vectors,
                embedding_model=self.model_id,
                embedding_version=self.document_version_key,
                cache_hits=0,
            )

    embed = SelectiveEmbed()
    repo = FakeProductDocumentRepo()
    result = _run(
        _sync(FakeIndexFeedClient([make_page([good, bad])]), embed, repo)
    )
    assert result.upserted == 1
    assert result.failed == 1
    assert _run(repo.get_by_product_id(A)) is not None
    assert _run(repo.get_by_product_id(B)) is None
    assert len(repo.failures) == 1
    assert repo.failures[0].product_id == B


def test_embed_failure_keeps_previous_row() -> None:
    first = make_upsert(sku="SKU01", product_id=A, family_name="Anillo erizo de mar")
    repo = FakeProductDocumentRepo()

    class DistinctEmbed(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            from jbg_ai.indexing.embeddings import EmbedResult

            self.calls.append(list(texts))
            vectors = [[0.42] * self.dimension for _ in texts]
            return EmbedResult(
                vectors=vectors,
                embedding_model=self.model_id,
                embedding_version=self.document_version_key,
                cache_hits=0,
            )

    _run(_sync(FakeIndexFeedClient([make_page([first])]), DistinctEmbed(), repo))
    previous = _run(repo.get_by_product_id(A))
    assert previous is not None
    previous_embedding = list(previous.embedding or [])
    previous_hash = previous.source_hash
    assert previous_embedding[:3] == [0.42, 0.42, 0.42]

    class FailOnRename(FakeEmbeddingClient):
        async def embed(self, texts: list[str]):
            from jbg_ai.indexing.embeddings import EmbedResult

            self.calls.append(list(texts))
            if any("Familia: Anillo concha" in text for text in texts):
                raise RuntimeError("embed failed")
            vectors = [[0.01] * self.dimension for _ in texts]
            return EmbedResult(
                vectors=vectors,
                embedding_model=self.model_id,
                embedding_version=self.document_version_key,
                cache_hits=0,
            )

    renamed = make_upsert(sku="SKU01", product_id=A, family_name="Anillo concha")
    sibling = make_upsert(sku="SKU02", product_id=B)
    result = _run(
        _sync(
            FakeIndexFeedClient([make_page([renamed, sibling])]),
            FailOnRename(),
            repo,
        )
    )
    still = _run(repo.get_by_product_id(A))
    assert result.failed == 1
    assert result.upserted == 1
    assert still is not None
    assert still.embedding == previous_embedding
    assert still.source_hash == previous_hash
    assert still.family_name == "Anillo erizo de mar"
    assert _run(repo.get_by_product_id(B)) is not None
    assert repo.failures[-1].product_id == A


def test_orphan_sku_is_sync_failure() -> None:
    orphan = make_upsert(sku="SKU999", product_id=A)
    sibling = make_upsert(sku="SKU01", product_id=B)
    repo = FakeProductDocumentRepo()
    result = _run(
        _sync(
            FakeIndexFeedClient([make_page([orphan, sibling])]),
            FakeEmbeddingClient(),
            repo,
        )
    )
    assert result.failed == 1
    assert result.upserted == 1
    assert _run(repo.get_by_product_id(A)) is None
    assert _run(repo.get_by_product_id(B)) is not None
    assert repo.failures[0].product_id == A


def test_missing_map_writes_nothing() -> None:
    item = make_upsert(sku="SKU01", product_id=A)
    repo = FakeProductDocumentRepo()
    with pytest.raises(ProvenanceMapError):
        _run(
            _sync(
                FakeIndexFeedClient([make_page([item])]),
                FakeEmbeddingClient(),
                repo,
                provenance=None,
            )
        )
    assert repo.documents == {}
    assert repo.failures == []


def test_non_1536_vector_is_not_persisted() -> None:
    item = make_upsert(sku="SKU01", product_id=A)
    repo = FakeProductDocumentRepo()
    result = _run(
        _sync(
            FakeIndexFeedClient([make_page([item])]),
            FakeEmbeddingClient(dimension=384),
            repo,
        )
    )
    assert result.failed == 1
    assert result.upserted == 0
    assert _run(repo.get_by_product_id(A)) is None
    assert repo.failures


def test_catalog_sync_does_not_call_pos_feed() -> None:
    item = make_upsert(sku="SKU01", product_id=A)
    feed = FakeIndexFeedClient([make_page([item])])
    _run(_sync(feed, FakeEmbeddingClient(), FakeProductDocumentRepo()))
    assert feed.pos_calls == []
    assert feed.catalog_calls


def test_full_ignores_body_and_checkpoint() -> None:
    repo = FakeProductDocumentRepo()
    repo.checkpoint = SyncCheckpoint(
        feed="catalog",
        watermark=TS,
        since_id=A,
        last_full_sync_at=None,
        last_incremental_sync_at=None,
        last_aggregate_hash=None,
        indexed_count=0,
    )
    feed = FakeIndexFeedClient([make_page([make_upsert(sku="SKU01", product_id=B)])])
    _run(
        _sync(
            feed,
            FakeEmbeddingClient(),
            repo,
            request=CatalogSyncRequest(full=True, since=TS, since_id=A),
        )
    )
    assert feed.catalog_calls[0] == (None, None)


def test_full_sync_pages_until_next_cursor_is_null() -> None:
    first = make_upsert(sku="SKU01", product_id=A, watermark=TS)
    later = datetime(2026, 8, 26, 11, 0, tzinfo=UTC)
    second = make_upsert(sku="SKU02", product_id=B, watermark=later)
    feed = FakeIndexFeedClient(
        [
            make_page([first], next_cursor=FeedCursor(since=TS, since_id=A)),
            make_page([second], next_cursor=None),
        ]
    )
    repo = FakeProductDocumentRepo()
    result = _run(
        _sync(
            feed,
            FakeEmbeddingClient(),
            repo,
            request=CatalogSyncRequest(full=True),
        )
    )
    assert result.upserted == 2
    assert result.failed == 0
    assert feed.catalog_calls == [(None, None), (TS, A)]
    assert _run(repo.get_by_product_id(A)) is not None
    assert _run(repo.get_by_product_id(B)) is not None
    assert _run(repo.get_by_product_id(A)).embedding is not None
    assert _run(repo.get_by_product_id(B)).embedding is not None


def test_body_keyset_overrides_checkpoint() -> None:
    repo = FakeProductDocumentRepo()
    repo.checkpoint = SyncCheckpoint(
        feed="catalog",
        watermark=TS,
        since_id=A,
        last_full_sync_at=None,
        last_incremental_sync_at=None,
        last_aggregate_hash=None,
        indexed_count=0,
    )
    body_since = datetime(2026, 7, 1, tzinfo=UTC)
    feed = FakeIndexFeedClient([make_page([])])
    _run(
        _sync(
            feed,
            FakeEmbeddingClient(),
            repo,
            request=CatalogSyncRequest(full=False, since=body_since, since_id=B),
        )
    )
    assert feed.catalog_calls[0] == (body_since, B)


def test_incremental_without_body_uses_checkpoint() -> None:
    repo = FakeProductDocumentRepo()
    repo.checkpoint = SyncCheckpoint(
        feed="catalog",
        watermark=TS,
        since_id=A,
        last_full_sync_at=None,
        last_incremental_sync_at=None,
        last_aggregate_hash=None,
        indexed_count=0,
    )
    feed = FakeIndexFeedClient([make_page([])])
    _run(
        _sync(
            feed,
            FakeEmbeddingClient(),
            repo,
            request=CatalogSyncRequest(full=False),
        )
    )
    assert feed.catalog_calls[0] == (TS, A)


def test_time_budget_persists_resume_cursor() -> None:
    first = make_upsert(sku="SKU01", product_id=A, watermark=TS)
    second = make_upsert(
        sku="SKU02",
        product_id=B,
        watermark=datetime(2026, 8, 26, 11, 0, tzinfo=UTC),
    )
    feed = FakeIndexFeedClient([make_page([first, second])])
    repo = FakeProductDocumentRepo()
    result = _run(
        _sync(
            feed,
            FakeEmbeddingClient(),
            repo,
            time_budget_seconds=0,
        )
    )
    assert result.upserted == 1
    assert result.cursor == TS
    assert result.cursor_id == A
    assert repo.checkpoint is not None
    assert repo.checkpoint.watermark == TS
    assert repo.checkpoint.since_id == A
    assert _run(repo.get_by_product_id(B)) is None


def test_set_hash_matches_known_vector() -> None:
    payload = (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert of_product_ids([B, A]) == expected
    assert of_product_ids([A, B]) == expected
    assert of_product_ids([]) == hashlib.sha256(b"").hexdigest()
    assert len(expected) == 64
    assert expected.islower()


def test_set_hash_distinguishes_signed_from_unsigned_order() -> None:
    """El vector de arriba no distingue los dos ordenes posibles. Este si.

    `aaaaaaaa-...` y `bbbbbbbb-...` caen ambos en la mitad alta del rango, donde
    leer el primer campo como entero con signo o sin signo da el mismo orden. La
    prueba pasaba, por tanto, con la implementacion correcta y con la
    incorrecta.

    Estos dos identificadores estan uno a cada lado del bit alto, que es
    exactamente donde las dos lecturas se separan:

      * sin signo (.NET Core, y lo que hace el feed): 0x00000000 < 0xffffffff
      * con signo (.NET Framework):                   0xffffffff = -1 < 0

    C17 descubrio que el feed publica el orden sin signo, midiendo ambos hashes
    sobre los mismos 1200 identificadores del indice real.
    """
    bajo = UUID("00000000-0000-0000-0000-000000000001")
    alto = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    expected = hashlib.sha256((str(bajo) + str(alto)).encode("utf-8")).hexdigest()

    assert of_product_ids([alto, bajo]) == expected
    assert of_product_ids([bajo, alto]) == expected


def test_status_reports_drift_when_counts_diverge() -> None:
    repo = FakeProductDocumentRepo()
    item = make_upsert(sku="SKU01", product_id=A)
    _run(_sync(FakeIndexFeedClient([make_page([item])]), FakeEmbeddingClient(), repo))
    local = of_product_ids(_run(repo.list_product_ids()))
    feed = FakeIndexFeedClient([make_page([], aggregate_hash="ff" * 32)])
    status = _run(report_index_status(feed=feed, repo=repo))
    assert local != "ff" * 32
    assert status.drift_count >= 1
    assert len(feed.catalog_calls) == 1

    matching = FakeIndexFeedClient([make_page([], aggregate_hash=local)])
    zero = _run(report_index_status(feed=matching, repo=repo))
    assert zero.drift_count == 0
    assert len(matching.catalog_calls) == 1


def test_status_feed_down_is_explicit_error() -> None:
    with pytest.raises(IndexFeedConfigError):
        _run(
            report_index_status(
                feed=FakeIndexFeedClient(fail=True),
                repo=FakeProductDocumentRepo(),
            )
        )


def test_batch_size_is_ignored(caplog: pytest.LogCaptureFixture) -> None:
    reset_batch_size_warning()
    item = make_upsert(sku="SKU01", product_id=A)
    feed = FakeIndexFeedClient([make_page([item], page_size=50)])
    with caplog.at_level(logging.WARNING):
        _run(
            _sync(
                feed,
                FakeEmbeddingClient(),
                FakeProductDocumentRepo(),
                request=CatalogSyncRequest(full=True, batch_size=100),
            )
        )
    assert any("batch_size" in record.message for record in caplog.records)
    assert feed.pages[0].page_size == 50
