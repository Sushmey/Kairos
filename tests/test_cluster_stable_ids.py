"""Tests for cluster ID reuse across recluster runs."""

from kairos.bookmarks.index import _match_existing_cluster_id


def test_match_existing_cluster_id_reuses_similar_centroid():
    existing = [
        {
            "cluster_id": "cluster-abc",
            "centroid_embedding": [1.0, 0.0, 0.0],
        }
    ]
    new_centroid = [0.99, 0.01, 0.0]
    matched = _match_existing_cluster_id(new_centroid, existing, threshold=0.88)
    assert matched == "cluster-abc"


def test_match_existing_cluster_id_new_when_different():
    existing = [
        {
            "cluster_id": "cluster-abc",
            "centroid_embedding": [1.0, 0.0, 0.0],
        }
    ]
    new_centroid = [0.0, 1.0, 0.0]
    matched = _match_existing_cluster_id(new_centroid, existing, threshold=0.88)
    assert matched is None
