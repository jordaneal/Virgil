#!/usr/bin/env python3
"""
DnD Knowledge Base Importer
Downloads CRD3 (Critical Role) and FIREBALL (filtered utterances only)
and loads them into ChromaDB dnd_knowledge collection.

Run once. Takes a while. Go make coffee.
"""

import os
import sys
import json
import time
import sqlite3
import requests
import threading
from pathlib import Path

DB_PATH = Path('/mnt/virgil_storage/virgil.db')
CHROMA_PATH = Path('/mnt/virgil_storage/chroma_dnd')
DOWNLOAD_DIR = Path('/mnt/virgil_storage/dnd_datasets')
LOG_PATH = Path('/mnt/virgil_storage/digest/dnd_import.log')


def log(msg):
    line = f"[{__import__('datetime').datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass


# ─────────────────────────────────────────────────────────
# ChromaDB setup
# ─────────────────────────────────────────────────────────

def progress_bar(current, total, prefix='', suffix='', stored=0, skipped=0):
    pct = int(current / total * 40) if total else 0
    bar = '█' * pct + '░' * (40 - pct)
    print(f"\r  {prefix} [{bar}] {current}/{total} {suffix} | stored: {stored} skipped: {skipped}", end='', flush=True)
    if current == total:
        print()


def get_chroma_collection():
    import chromadb
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(
        name="dnd_knowledge",
        metadata={"hnsw:space": "cosine"}
    )
    log(f"ChromaDB dnd_knowledge: {collection.count()} existing documents")
    return collection


def embed(text):
    """Get embedding from local Ollama nomic-embed-text."""
    try:
        resp = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": text[:2000]},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json().get("embeddings", [None])[0]
    except Exception as e:
        log(f"embed error: {e}")
    return None


def store_batch(collection, docs, ids, metadatas):
    """Embed and store a batch of documents."""
    embeddings = []
    valid_docs = []
    valid_ids = []
    valid_metas = []

    for doc, doc_id, meta in zip(docs, ids, metadatas):
        emb = embed(doc)
        if emb is not None:
            embeddings.append(emb)
            valid_docs.append(doc)
            valid_ids.append(doc_id)
            valid_metas.append(meta)

    if embeddings:
        try:
            collection.upsert(
                ids=valid_ids,
                embeddings=embeddings,
                documents=valid_docs,
                metadatas=valid_metas
            )
            return len(embeddings)
        except Exception as e:
            log(f"store_batch error: {e}")
    return 0


# ─────────────────────────────────────────────────────────
# CRD3 - Critical Role Dataset
# ─────────────────────────────────────────────────────────

def download_crd3():
    """Download CRD3 dataset from HuggingFace."""
    log("Downloading CRD3 (Critical Role Dataset)...")
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    crd3_dir = DOWNLOAD_DIR / "crd3"
    crd3_dir.mkdir(exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
        path = snapshot_download(
            repo_id="microsoft/crd3",
            repo_type="dataset",
            local_dir=str(crd3_dir),
            ignore_patterns=["*.bin", "*.pt"]
        )
        log(f"CRD3 downloaded to {path}")
        return crd3_dir
    except Exception as e:
        log(f"CRD3 download error: {e}")
        return None


def import_crd3(collection, crd3_dir):
    """Import CRD3 transcripts into ChromaDB."""
    log("Importing CRD3 into ChromaDB...")
    imported = 0
    skipped = 0

    # CRD3 files are in 'data/aligned data/c=N/' subdirectories
    aligned_dir = crd3_dir / "data" / "aligned data"
    if aligned_dir.exists():
        data_files = list(aligned_dir.rglob("*.json"))
    else:
        data_files = list(crd3_dir.rglob("*.json"))
    log(f"Found {len(data_files)} CRD3 files")

    batch_docs = []
    batch_ids = []
    batch_metas = []

    total_files = len(data_files)
    for file_idx, fpath in enumerate(data_files, 1):
        progress_bar(file_idx, total_files, 'CRD3', 'files', imported, skipped)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                records = json.load(f)

            if not isinstance(records, list):
                records = [records]

            for i, rec in enumerate(records):
                chunk_id = f"{fpath.stem}_{i}"

                # Store the summary chunk (DM-style narrative description)
                summary = rec.get('CHUNK', '')
                if len(summary) > 30:
                    batch_docs.append(f"DM Summary: {summary[:1500]}")
                    batch_ids.append(f"crd3_sum_{chunk_id}")
                    batch_metas.append({"source": "crd3", "speaker": "summary", "episode": fpath.stem})

                # Store only Matt Mercer (DM) turns — players add volume, not DM behavior
                for j, turn in enumerate(rec.get('TURNS', [])):
                    names = turn.get('NAMES', [])
                    utterances = turn.get('UTTERANCES', [])
                    speaker = names[0] if names else 'Unknown'
                    if speaker.upper() != 'MATT':
                        skipped += 1
                        continue
                    text = ' '.join(utterances) if isinstance(utterances, list) else str(utterances)

                    if len(text.strip()) < 30:
                        skipped += 1
                        continue

                    batch_docs.append(f"{speaker}: {text[:1500]}")
                    batch_ids.append(f"crd3_{chunk_id}_{j}")
                    batch_metas.append({"source": "crd3", "speaker": speaker, "episode": fpath.stem})

                    if len(batch_docs) >= 50:
                        stored = store_batch(collection, batch_docs, batch_ids, batch_metas)
                        imported += stored
                        batch_docs, batch_ids, batch_metas = [], [], []
                        if imported % 500 == 0:
                            log(f"  CRD3: {imported} stored, {skipped} skipped")

        except Exception as e:
            log(f"  Error processing {fpath.name}: {e}")

    if batch_docs:
        imported += store_batch(collection, batch_docs, batch_ids, batch_metas)

    log(f"CRD3 import complete: {imported} documents stored, {skipped} skipped")
    return imported


# ─────────────────────────────────────────────────────────
# FIREBALL - filtered narrative utterances only
# ─────────────────────────────────────────────────────────

def download_fireball():
    """Download FIREBALL dataset - filtered_triples only (smaller, more useful)."""
    log("Downloading FIREBALL filtered triples...")
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    fb_dir = DOWNLOAD_DIR / "fireball"
    fb_dir.mkdir(exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
        # Only download filtered_triples, not raw (raw is huge)
        path = snapshot_download(
            repo_id="lara-martin/FIREBALL",
            repo_type="dataset",
            local_dir=str(fb_dir),
            allow_patterns=["*filtered*", "*.jsonl"],
            ignore_patterns=["raw*", "*.bin", "*.pt"]
        )
        log(f"FIREBALL downloaded to {path}")
        return fb_dir
    except Exception as e:
        log(f"FIREBALL download error: {e}")
        return None


def import_fireball(collection, fb_dir):
    """
    Import FIREBALL filtered triples into ChromaDB.
    Only extracts natural language utterances, not bot commands.
    """
    log("Importing FIREBALL filtered utterances into ChromaDB...")
    imported = 0
    skipped = 0

    jsonl_files = list(fb_dir.rglob("*filtered*.jsonl"))
    if not jsonl_files:
        jsonl_files = list(fb_dir.rglob("*.jsonl"))
    log(f"Found {len(jsonl_files)} FIREBALL files")

    total_files = len(jsonl_files)
    for file_idx, fpath in enumerate(jsonl_files, 1):
        progress_bar(file_idx, total_files, 'FIREBALL', 'files', imported, skipped)
        batch_docs = []
        batch_ids = []
        batch_metas = []
        line_num = 0

        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    line_num += 1

                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue

                    # Extract before_utterances (what players said before the action)
                    utterances = rec.get('before_utterances', [])
                    if not utterances:
                        skipped += 1
                        continue

                    # Combine utterances into a single narrative block
                    text = ' '.join(str(u) for u in utterances if u)
                    text = text.strip()

                    # Skip if too short or looks like a command (starts with !)
                    if len(text) < 40 or text.startswith('!'):
                        skipped += 1
                        continue

                    # Skip lines that are mostly dice notation
                    if text.count('d') > 5 and len(text) < 100:
                        skipped += 1
                        continue

                    doc_id = f"fireball_{fpath.stem}_{line_num}"
                    batch_docs.append(text[:1500])
                    batch_ids.append(doc_id)
                    batch_metas.append({
                        "source": "fireball",
                        "file": fpath.stem,
                        "line": str(line_num)
                    })

                    if len(batch_docs) >= 50:
                        stored = store_batch(collection, batch_docs, batch_ids, batch_metas)
                        imported += stored
                        batch_docs, batch_ids, batch_metas = [], [], []
                        if imported % 1000 == 0:
                            log(f"  FIREBALL: {imported} stored, {skipped} skipped (line {line_num})")

            # Store remaining
            if batch_docs:
                stored = store_batch(collection, batch_docs, batch_ids, batch_metas)
                imported += stored

        except Exception as e:
            log(f"  Error processing {fpath.name}: {e}")

    log(f"FIREBALL import complete: {imported} documents stored, {skipped} skipped")
    return imported


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def main():
    log("=" * 50)
    log("DnD Knowledge Base Importer")
    log("=" * 50)

    collection = get_chroma_collection()
    total = 0

    # ── CRD3 ─────────────────────────────────────────────
    log("\n[1/2] Critical Role Dataset (CRD3)")
    crd3_dir = DOWNLOAD_DIR / "crd3"
    if crd3_dir.exists() and any(crd3_dir.rglob("*.json")):
        log("CRD3 already downloaded, importing...")
    else:
        crd3_dir = download_crd3()

    if crd3_dir:
        total += import_crd3(collection, crd3_dir)
    else:
        log("CRD3 skipped - download failed")

    # ── FIREBALL ──────────────────────────────────────────
    log("\n[2/2] FIREBALL filtered utterances")
    fb_dir = DOWNLOAD_DIR / "fireball"
    if fb_dir.exists() and any(fb_dir.rglob("*.jsonl")):
        log("FIREBALL already downloaded, importing...")
    else:
        fb_dir = download_fireball()

    if fb_dir:
        total += import_fireball(collection, fb_dir)
    else:
        log("FIREBALL skipped - download failed")

    # ── Summary ───────────────────────────────────────────
    log("\n" + "=" * 50)
    log(f"Import complete. Total documents added: {total}")
    log(f"dnd_knowledge collection size: {collection.count()}")
    log("=" * 50)

    # Disk usage
    import shutil
    usage = shutil.disk_usage('/mnt/virgil_storage')
    log(f"Storage used: {usage.used // (1024**3)}GB / {usage.total // (1024**3)}GB")


if __name__ == '__main__':
    main()
