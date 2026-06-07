#  Hybrid Recommender System
here you can search any Anime/Manhwa and find the best recommendations, Get the info by just clicking the poster.

A production-grade recommender system for anime and manhwa, combining **content-based filtering** and **item-based collaborative filtering** using vector similarity search. The system processes 150K+ titles and 90M+ user ratings to deliver hybrid recommendations via a FastAPI backend and a modern JavaScript frontend.

**Live Demo**: [hybrid-recommender-system.vercel.app](https://hybrid-recommender-system.vercel.app)
**Data Files**: [Google Drive](https://drive.google.com/drive/folders/1RHMp0tczMUPr20hibwJzgkUmaJfORzVa?usp=drive_link)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Tech Stack](#tech-stack)
3. [Data Collection](#data-collection)
4. [Data Cleaning & Preprocessing](#data-cleaning--preprocessing)
5. [Feature Engineering & Vectorization](#feature-engineering--vectorization)
6. [Vector Database (Qdrant)](#vector-database-qdrant)
7. [Collaborative Filtering (Ratings Pipeline)](#collaborative-filtering-ratings-pipeline)
8. [Hybrid Recommendation Algorithm (RRF)](#hybrid-recommendation-algorithm-rrf)
9. [Backend API (FastAPI)](#backend-api-fastapi)
10. [Frontend](#frontend)
11. [Deployment](#deployment)
12. [Project Structure](#project-structure)

---

## System Overview

```
AniList GraphQL API ──┐
                       ├──► Raw JSONL Data ──► Metadata Cleaning (Pandas)
Kaggle Ratings ────────┘                   └──► Ratings Cleaning (Dask)
                                                         │
                              ┌──────────────────────────┤
                              │                          │
                    Feature Engineering            Sparse Matrix
                  (OHE + BoW + Embeddings)       (User × Anime)
                              │                          │
                    Qdrant "testing_vector"    Qdrant "collaborative"
                    (Dense, Cosine)            (Sparse, L2 normalized)
                              │                          │
                              └──────────┬───────────────┘
                                         │
                              Reciprocal Rank Fusion
                              content_score + 0.8 × collab_score
                                         │
                                   FastAPI Backend
                                   (Render cloud)
                                         │
                                 JavaScript Frontend
                                   (Vercel cloud)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Data Ingestion | AniList GraphQL API, Kaggle |
| Data Processing | Pandas, Dask, NumPy, SciPy, NLTK |
| ML / Vectorization | scikit-learn, sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector Database | Qdrant Cloud (managed) |
| Backend | FastAPI, Uvicorn, Pydantic |
| Frontend | HTML, CSS, JavaScript (Vanilla) |
| Backend Hosting | Render |
| Frontend Hosting | Vercel |

---

## Data Collection

### `data_input.ipynb`

Data was fetched from two sources:

**AniList GraphQL API**

The AniList public API was queried with a custom paginated GraphQL query to pull all anime and manga entries. The query extracts rich fields including: `id`, `idMal`, `title` (romaji + English), `synonyms`, `stats.scoreDistribution`, `type`, `countryOfOrigin`, `format`, `status`, `episodes`, `chapters`, `volumes`, `averageScore`, `popularity`, `trending`, `description`, `genres`, `studios`, `tags`, `isAdult`, `source`, `coverImage`, `bannerImage`, and `trailer`.

- Pagination: 50 entries per page, iterated until `hasNextPage = false`
- Rate limit handling: tracks `x-ratelimit-remaining` header; sleeps when remaining < 15
- Saves data incrementally to `.jsonl` files (one JSON object per line) to prevent data loss on crash
- Final scale: **~150,000 titles** (anime + manga combined)

**Kaggle — User Ratings**

User interaction data (anime ratings by users) was sourced from Kaggle, providing:
- `userID`: unique user identifier
- `animeID` / `mal_url`: MyAnimeList anime ID
- `rating`: score given by user

- Final scale: **~10 million (10 crore) user rating rows**

---

## Data Cleaning & Preprocessing

### `metadata_preperation.ipynb`

- Merged the base JSONL files (`anilist_anime_complete.jsonl`, `anilist_manga_complete.jsonl`) with patch files that corrected missing/wrong fields
- Merged using inner join on `id`
- Resolved duplicate columns after merge (`idMal_x` / `idMal_y`) by dropping the patch version and renaming the original
- Concatenated anime and manga into a single unified `metadata.csv`

### `Data_cleaning.ipynb` (Metadata)

All cleaning was done with **Pandas**:

**Missing Value Imputation**

- `averageScore`: Calculated from the raw `stats.scoreDistribution` dictionary (weighted average of score buckets × vote counts) and used it to fill NaN values
- `seasonYear`: Extracted from the `startDate.year` field as fallback
- `episodes`, `chapters`, `volumes`: Filled with `0`
- `source`, `format`, `status`: Filled with `"UNKNOWN"`
- `idMal`: Filled with `-1` (sentinel for "no MAL ID")
- `description`: Filled with `""`

**Title Normalization**

- Parsed title dict (`romaji`, `english`) → flat list
- Extracted only English-pattern synonyms using regex: `r'^[a-zA-Z\s\'\-]+$'`
- Appended English synonyms to the title list
- Lowercased all title variants for case-insensitive search

**Tags Filtering**

- Tags each have a `rank` score (0–100) indicating how strongly they apply to the title
- Filtered to only keep tags with `rank > 50` — eliminates weakly-associated tags that would add noise to similarity
- Merged filtered tags into genres list and dropped the separate tags column

**Description NLP Pipeline**

Description text went through a full NLP preprocessing chain:
1. HTML tag removal (`<br/>`, etc.) and URL stripping via regex
2. Lowercasing
3. Tokenization (regex: `[a-zA-Z]+`, removes numbers and punctuation)
4. **Stopword removal** using NLTK's English stopword list
5. **Porter Stemming** — reduces words to root forms (e.g., *running → run*, *genres → genr*) to improve semantic grouping

**Column Cleanup**

- Dropped display-only columns: `startDate`, `endDate`, `duration`, `coverImage`, `bannerImage`, `trailer`, `siteUrl`, `hashtag`, `season`
- `stats` column converted from score distribution dict → total vote count (integer)
- `averageScore` normalized to 0–10 scale (divided by 10)
- Column renames: `averageScore → rating`, `stats → voteCount`, `seasonYear → year`

### `adding_urls.ipynb`

After vectorization was complete, image and trailer URLs were merged back into the dataset (they were excluded during NLP processing to avoid polluting embeddings):

- Extracted `coverImage.large` as a direct CDN URL
- Extracted `trailer.id` and formatted as `https://www.youtube.com/watch?v={id}`
- Merged back into the cleaned metadata on `id`

### `ratings_cleaning.ipynb` (User Ratings)

Ratings data required a multi-step ID mapping due to the Kaggle dataset using internal anime IDs rather than AniList IDs:

1. Extracted MAL IDs from Kaggle's `mal_url` column using regex
2. Merged ratings with a mapping table (`animes.csv`: internal ID → MAL ID)
3. Merged again with cleaned metadata (`idMal` column) to get AniList `id` values — enabling cross-referencing between the rating data and the vector DB
4. **Outlier removal**: Dropped users with > 600 ratings (likely bots or bulk scrapers) using `groupby().transform("count")`
5. **Memory management**: Used explicit `del` + `gc.collect()` after large dataframe operations to prevent RAM overflow
6. Dropped duplicates and NaN rows
7. Downcast dtypes: `userID → int32`, `rating → int8`, `id → int32` to halve memory usage
8. Sampled **1 million unique users** randomly for manageable sparse matrix size

Dask (`dask.dataframe`) was used to load and process the 70M-row ratings file in chunked fashion without loading it all into RAM.

---

## Feature Engineering & Vectorization

### `meta__insertion_in_qdrant.ipynb`

Each title is represented as a **single combined dense vector** by horizontally stacking multiple feature matrices. Each feature group is weighted before concatenation to control its contribution to similarity.

**Feature Groups and Weights**

| Feature Group | Vectorizer | Shape | Weight |
|---|---|---|---|
| Numerical (year, episodes, chapters, volumes) | MinMaxScaler | `(N, 4)` | 1.0 |
| Numerical (rating, popularity, trending, voteCount) | MinMaxScaler | `(N, 4)` | 1.0 |
| Categorical (type, format, status, isAdult, source, countryOfOrigin) | OneHotEncoder | `(N, 31)` | 2.0 |
| Genres + filtered tags | CountVectorizer (BoW, comma-separated) | `(N, 442)` | 1.0 |
| Studios | CountVectorizer (BoW, comma-separated) | `(N, 2384)` | 1.0 |
| Description text | `all-MiniLM-L6-v2` sentence embedding | `(N, 384)` | 3.0 |

**Key design decisions:**

- `MinMaxScaler` is used (not StandardScaler) because it scales all numerics to `[0, 1]`, making them directly compatible with BoW and OHE outputs that are also bounded in this range. StandardScaler would produce negative values that conflict with sparse categorical representations.
- `CountVectorizer` uses `token_pattern=r'[^,]+'` to treat comma-separated multi-word genres (e.g., *"Slice of Life"*) as single tokens, rather than splitting them into meaningless individual words.
- Description embeddings use **`all-MiniLM-L6-v2`** (a 384-dimensional sentence transformer), given the highest weight (3.0) because plot/theme semantic similarity is the strongest signal for a good recommendation.
- Categorical features get weight 2.0 because type/format/country/source are strong hard filters (an ANIME vs MANHWA distinction matters more than minor numerical differences).

**Final combined vector dimensions**: ~3,269 per title (4 + 4 + 31 + 442 + 2384 + 384, each weighted)

The combination is done with `np.hstack` after converting all sparse matrices to dense with `.toarray()`. Stored as `float32` to halve memory vs `float64`.

---

## Vector Database (Qdrant)

Two separate Qdrant cloud collections serve the two arms of the hybrid system.

### Collection: `testing_vector` (Content-Based)

- **Vector type**: Dense, named `"all_vectors"`
- **Distance metric**: Cosine similarity
- **Payload** stored per point: `type`, `format`, `status`, `isAdult`, `countryOfOrigin`
- **Point ID**: AniList `id` (integer)
- **Insertion**: Batched upserts (300 points/batch) with exponential backoff retry (2s → 4s → 8s), using `wait=False` for throughput

### Collection: `collaborative` (Item-Based CF)

- **Vector type**: Sparse, named `"users_ratings"`
- **Distance metric**: Dot product (equivalent to cosine since rows are L2 normalized)
- **Index**: `on_disk=True` — because the user-rating sparse matrix is massive (unique animes × unique users), RAM-only indexing would be infeasible
- **Modifier**: `NONE` (no IDF weighting; raw L2-normalized co-rating vectors)
- **Point ID**: AniList `id`
- **Insertion**: Batched upserts (10 points/batch with `wait=True`) and exponential backoff up to 5 minutes between retries, because sparse vector uploads are heavier

---

## Collaborative Filtering (Ratings Pipeline)

### `ratings_insertion_in_qdrant.ipynb`

**Item-User Sparse Matrix Construction**

After cleaning, ratings were pivoted into an **item-user matrix** using `scipy.sparse.csr_matrix`:

- **Rows** = unique anime IDs (items)
- **Columns** = unique user IDs
- **Values** = rating scores (1–10, `int8`)
- Ratings of `0` are dropped — in the Kaggle dataset, 0 means "watched but not rated" (not a true rating)

This gives each anime a sparse vector in user-space. Two anime that were rated similarly by many of the same users will have high dot product similarity — this is **item-based collaborative filtering**.

**L2 Normalization**

Each row (anime vector) is L2-normalized using `sklearn.preprocessing.normalize`. This means the dot product between two anime vectors equals their cosine similarity — so similarity scores are naturally bounded between 0 and 1 and comparable across animes with very different popularity levels.

**Sparse Vector Truncation at Query Time** (`recommender.py`)

When querying, if a retrieved anime vector has > 15,000 non-zero indices (extremely popular anime with massive rating coverage), it is truncated to the top 5,000 indices by absolute value. This prevents Qdrant from timing out on queries with huge sparse payloads while preserving the strongest signals.

---

## Hybrid Recommendation Algorithm (RRF)

### Reciprocal Rank Fusion

Both the content-based and collaborative systems independently return a ranked list of 100 candidates (`candidate_pool=100`). These two ranked lists are fused using **Reciprocal Rank Fusion (RRF)**:

```
RRF_score(anime) = 1 / (content_rank + K)  +  0.8 × 1 / (collab_rank + K)
```

where `K = 60` (the standard RRF smoothing constant that prevents rank 1 from having disproportionate influence).

**Why RRF instead of score averaging?**

- Content similarity scores and collaborative dot-product scores are on completely different scales and distributions
- RRF normalizes both into rank-based reciprocal scores that are always comparable
- If an anime doesn't appear in one of the lists (e.g., it has no collab data), it contributes `0` from that arm — no penalty for sparse coverage
- The `0.8` multiplier on the collab arm slightly downweights collaborative signal, because the content-based arm is more reliable for niche/new titles with few ratings

**Fallback**: If an anime has no entry in the `collaborative` collection (`has_collab = False`), the system falls back to pure content-based ranking without error.

The top 20 results (by default) are returned, sorted descending by RRF score.

---

## Backend API (FastAPI)

### `main.py`

The API is built with **FastAPI** and loads the full metadata CSV into a Pandas DataFrame at startup for fast in-memory filtering and display name resolution.

**Endpoints**

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Returns top 12 anime and top 12 manhwa sorted by popularity |
| `GET` | `/search?q={query}` | Partial title match search across all title variants |
| `GET` | `/recommend/{id}?limit={n}` | Hybrid recommendations for a given AniList ID |
| `GET` | `/info/{id}` | Full detail record + similar titles |
| `GET` | `/health` | Health check |

**Title Display Logic**

Titles are stored as a list (e.g., `["shingeki no kyojin", "attack on titan"]`). The API always displays the second title if present (English), otherwise falls back to the first (romaji). This is applied consistently across all endpoints.

**Info Endpoint Column Handling**

The `/info/{id}` endpoint drops irrelevant columns based on media type:
- `MANHWA` / `MANGA`: drops `episodes`, `popularity`, `source` (not applicable)
- `ANIME`: drops `chapters`, `volumes`, `popularity`

**Search** (`search_aid.py`)

- `search_all_anime_id`: Partial match — returns all titles where any title variant contains the query string (catches sequels, alternate names, etc.)
- `search_anime_id`: Tries exact match first, falls back to partial
- Results are returned as `{ "Display Title [TYPE]": anilist_id }` dicts; ANIME entries omit the `[TYPE]` suffix for cleaner display

**CORS**: Wildcard allowed (`allow_origins=["*"]`) for frontend flexibility during development and deployment.

---

## Frontend

Built with vanilla **HTML, CSS, and JavaScript** with a dark aesthetic theme:

- Hero search bar with live dropdown results (using the `/search` endpoint)
- Horizontal scroll card rows for anime and manhwa on the home page
- Detail/info page per title with cover art, metadata, and a similar-titles row
- History API navigation (`pushState`) for SPA-like routing without a framework
- Orange accent color scheme with dark background

---

## Deployment

| Component | Platform | Notes |
|---|---|---|
| FastAPI Backend | **Render** | Free-tier web service; loads CSV on startup |
| Frontend | **Vercel** | Static deployment; auto-deploys from repo |
| Vector DB | **Qdrant Cloud** | Two separate managed clusters (content + collab) |

---

## Project Structure

```
project/
├── data/
│   └── fully_final_metadata.csv        # Final cleaned metadata with URLs
│
├── notebooks/
│   ├── data_input.ipynb                # AniList GraphQL scraper
│   ├── metadata_preperation.ipynb      # Merge anime + manga JSONL sources
│   ├── Data_cleaning.ipynb             # Full metadata NLP + cleaning pipeline
│   ├── adding_urls.ipynb               # Merge cover images + trailer URLs
│   ├── ratings_cleaning.ipynb          # Kaggle ratings ID mapping + cleaning
│   ├── meta__insertion_in_qdrant.ipynb # Feature engineering + content vector upsert
│   └── ratings_insertion_in_qdrant.ipynb # Sparse matrix build + collab vector upsert
│
├── recommender_system/
│   ├── recommender.py                  # hybrid_recommend1 + hybrid_recommende2
│   └── search_aid.py                   # search_anime_id + search_all_anime_id
│
└── main.py                             # FastAPI app + endpoint definitions
```

---

## Key Design Decisions Summary

| Decision | Rationale |
|---|---|
| Qdrant over FAISS | Cloud-managed, supports both dense and sparse vectors natively, no infra to manage |
| Sparse vectors for CF | User-rating matrix is extremely sparse (~0.01% density); dense CF vectors would be impossible to store |
| `on_disk=True` for sparse index | Sparse collab index is too large for RAM on free-tier cloud |
| RRF over score fusion | Avoids scale incompatibility between cosine and dot-product scores |
| Dask for ratings | 70M rows cannot be loaded into Pandas in one shot on standard hardware |
| MinMaxScaler not StandardScaler | Keeps numerical features non-negative, compatible with BoW/OHE feature space |
| Description weight = 3.0 | Plot/theme is the strongest semantic similarity signal for recommendations |
| Tags rank > 50 filter | Low-rank tags are editorially disputed and add noise to genre vectors |
| Porter Stemmer on descriptions | Reduces vocabulary size, improves matching across inflected forms |