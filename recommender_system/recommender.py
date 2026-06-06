import numpy as np
import pandas as pd
import os
import time
import ast
from qdrant_client import models , QdrantClient
import warnings
warnings.filterwarnings("ignore")

# connecting with the clients
content_client = QdrantClient(
    url="https://c06b5043-1274-466d-9d2b-69cf16e8b262.us-west-1-0.aws.cloud.qdrant.io",
    api_key= "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6NTYwZmRkZWMtZTU1NC00YjZkLTk1MDctMjUyMGZiYWExNWRjIn0._sfGAjklswSJTcrwAlg4asBRhg3dNI1SsHVUZlQjOH0",
    timeout=60.0
)
collab_client = QdrantClient(
    url= "https://2ac22e98-018d-4349-820e-51e45fe1a5d9.us-west-1-0.aws.cloud.qdrant.io",
    api_key= "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MGU0NGM3MDktZGIzOC00YTEzLWFjOWYtNzE3OTU5N2RlNzFkIn0.rlseqT8NBMyg4AvVaY0liD4U22KkNR8708gb8uvP-Qs",
    timeout=60.0
)


def hybrid_recommend1(anime_id, df, top_k=10, candidate_pool=100):
    anime_id = int(anime_id)

    # ─── STEP 1: get the query anime's dense vector from content-based collection ───
    content_point = content_client.retrieve(
        collection_name="testing_vector",
        ids=[anime_id],
        with_vectors=True
    )
    if not content_point:
        print(f"Anime ID {anime_id} not found in content-based collection")
        return None
    dense_vector = content_point[0].vector["all_vectors"]

    # ─── STEP 2: get the query anime's sparse vector from collaborative collection ───
    collab_point = collab_client.retrieve(
        collection_name="collaborative",
        ids=[anime_id],
        with_vectors=True
    )
    has_collab = bool(collab_point)
    if has_collab:
        sparse_vec = collab_point[0].vector["users_ratings"]
        indices    = sparse_vec.indices
        values     = sparse_vec.values

    # ─── STEP 3: query content-based collection with dense vector ───
    content_results = content_client.query_points(
        collection_name="testing_vector",
        query=dense_vector,
        using="all_vectors",
        limit=candidate_pool,
        with_payload=False
    ).points

    # ─── STEP 4: query collaborative collection with sparse vector ───
    if has_collab:
        # noinspection PyTypeChecker
        collab_results = collab_client.query_points(
            collection_name="collaborative",
            query=models.SparseVector(
                indices=indices,
                values=values
            ),
            using="users_ratings",
            limit=candidate_pool,
            with_payload=False
        ).points

    # ─── STEP 5: build rank dictionaries from both result lists ───
    content_ranks = {hit.id: rank for rank, hit in enumerate(content_results, start=1)}
    collab_ranks  = {hit.id: rank for rank, hit in enumerate(collab_results,  start=1)} if has_collab else {}

    # ─── STEP 6: collect all unique anime ids from both result lists ───
    all_ids = set(content_ranks.keys()) | set(collab_ranks.keys())
    # all_ids.discard(anime_id)

    # ─── STEP 7: apply RRF formula to every candidate ───
    K = 60
    rrf_scores = {}
    for aid in all_ids:
        content_score = 1 / (content_ranks[aid] + K) if aid in content_ranks else 0
        collab_score  = 1 / (collab_ranks[aid]  + K) if aid in collab_ranks  else 0
        rrf_scores[aid] = content_score + collab_score

    # ─── STEP 8: deduplicate by franchise, then take top_k ───
    top_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
    # ─── STEP 9: return matching rows from your metadata dataframe ───
    recommended_df = df[df["id"].isin(top_ids)].copy()
    recommended_df["rrf_score"] = recommended_df["id"].map(rrf_scores)
    recommended_df = recommended_df.sort_values("rrf_score", ascending=False)

    # recommended_df = recommended_df.drop(columns="rrf_score")
    recommended_df = recommended_df[["id","title", "coverImage"]]
    recommended_df["title"] = recommended_df["title"].apply(lambda x: x[1] if len(x) > 1 else x[0])
    return recommended_df


def hybrid_recommende2(anime_id,df, top_k=20, candidate_pool=100):
    anime_id = int(anime_id)
    # ─── STEP 1: get the query anime's dense vector from content-based collection ───
    # We fetch the stored vector directly from Qdrant instead of recomputing it.
    # This way we don't need combined_embeddings in memory at query time.
    content_point = content_client.retrieve(
        collection_name="testing_vector",
        ids=[anime_id],
        with_vectors=True  # we need the actual vector, not just payload
    )
    # If the anime_id doesn't exist in the collection, exit early
    if not content_point:
        print(f"Anime ID {anime_id} not found in content-based collection")
        return None
    # Extract the dense vector from the retrieved point
    dense_vector = content_point[0].vector["all_vectors"]
    # ─── STEP 2: get the query anime's sparse vector from collaborative collection ───
    collab_point = collab_client.retrieve(
        collection_name="collaborative",
        ids=[anime_id],
        with_vectors=True
    )
    has_collab = bool(collab_point)
    if has_collab:
        sparse_vec = collab_point[0].vector["users_ratings"]
        indices = np.array(sparse_vec.indices)
        values = np.array(sparse_vec.values)
        if len(indices) > 15000:
            top_pos = np.argsort(np.abs(values))[::-1][:5000]
            top_pos = np.sort(top_pos)
            indices = indices[top_pos]
            values = values[top_pos]

    content_results = content_client.query_points(
        collection_name="testing_vector",
        query=dense_vector,
        using="all_vectors",
        limit=candidate_pool,
        with_payload=False
    ).points
    if has_collab:
        collab_results = collab_client.query_points(
            collection_name="collaborative",
            query=models.SparseVector(
                indices=indices.tolist(),
                values=values.tolist()
            ),
            using="users_ratings",
            limit=candidate_pool,
            with_payload=False
        ).points
    # ─── STEP 5: build rank dictionaries from both result lists ───
    # content_ranks = { mal_id: rank_position }  where rank starts at 1
    content_ranks = {hit.id: rank for rank, hit in enumerate(content_results, start=1)}
    collab_ranks = {hit.id: rank for rank, hit in enumerate(collab_results, start=1)} if has_collab else {}
    # ─── STEP 6: collect all unique anime ids from both result lists ───
    all_ids = set(content_ranks.keys()) | set(collab_ranks.keys())
    # Remove the query anime itself from recommendations
    # ─── STEP 7: apply RRF formula to every candidate ───
    # RRF score = 1/(rank + 60) + 1/(rank + 60)
    # If an anime only appears in one list, its rank in the other is treated as infinity → contributes 0
    # k=60 is the standard constant that prevents top ranks from dominating too aggressively
    K = 60
    rrf_scores = {}
    for anime_id in all_ids:
        content_score = 1 / (content_ranks[anime_id] + K) if anime_id in content_ranks else 0
        collab_score = 1 / (collab_ranks[anime_id] + K) if anime_id in collab_ranks else 0
        rrf_scores[anime_id] = content_score + (.8 * collab_score)
    # ─── STEP 8: sort by RRF score descending and take top_k ───
    top_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
    # ─── STEP 9: return matching rows from your metadata dataframe ───
    recommended_df = df[df["id"].isin(top_ids)].copy()
    # Add the rrf score and sort by it so the best recommendation is first
    recommended_df["rrf_score"] = recommended_df["id"].map(rrf_scores)
    recommended_df = recommended_df.sort_values("rrf_score", ascending=False)
    recommended_df = recommended_df[["id", "title", "coverImage"]]
    recommended_df["title"] = recommended_df["title"].apply(lambda x: x[1] if len(x) > 1 else x[0])
    return recommended_df