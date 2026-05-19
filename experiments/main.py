#!/usr/bin/env python3
"""
Кластеризация навыков вакансий из raw/processed данных.

Цели:
  - Понять, на какие профессиональные области делятся вакансии (IT, медицина, строительство и т.д.)
  - Использовать кластер как признак для моделей или обучать отдельные модели на каждом кластере
  - Визуализировать структуру данных

Запуск:
  uv run python -m experiments.main [--sample 50000] [--clusters 15] [--output clusters.png]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.manifold import TSNE
from sklearn.feature_extraction.text import TfidfVectorizer


# --- Конфиг ---
PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = int(os.getenv("DB_PORT", "5432"))
PG_USER = os.getenv("DATABASE_USERNAME", "postgres")
PG_PASS = os.getenv("DATABASE_PASSWORD", "admin")
PG_NAME = os.getenv("DATABASE_NAME", "job_vacancy")


def extract_key_skills(skills_val):
    """Извлекает список навыков из skills (JSONB)."""
    if skills_val is None:
        return []
    if isinstance(skills_val, dict):
        ks = skills_val.get("key_skills", [])
    elif isinstance(skills_val, str):
        try:
            data = json.loads(skills_val)
            ks = data.get("key_skills", [])
        except json.JSONDecodeError:
            return []
    else:
        return []
    return ks if isinstance(ks, list) else []


async def load_vacancies_sample(sample_size: int):
    """Загружает вакансии с навыками из processed_vacancies."""
    try:
        import asyncpg
    except ImportError:
        print("Требуется asyncpg: uv add asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(
        f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_NAME}"
    )
    rows = await conn.fetch(
        """
        SELECT raw_vacancy_uuid, skills
        FROM processed_vacancies
        WHERE skills != '{}'::jsonb
        ORDER BY random()
        LIMIT $1
        """,
        sample_size,
    )
    await conn.close()

    records = []
    for r in rows:
        skills = extract_key_skills(r["skills"])
        if skills:
            records.append({"uuid": str(r["raw_vacancy_uuid"]), "skills": skills})
    return records


def skills_to_text(skills: list[str]) -> str:
    """Склеивает навыки в строку для TF-IDF (пробелы между навыками)."""
    return " ".join(s.strip() for s in skills if s.strip())


def fit_clusters(vacancies: list[dict], n_clusters: int = 15):
    """
    Строит матрицу навыков и кластеризует вакансии.

    Returns:
        (X_tfidf, labels, vectorizer, top_skills_per_cluster)
    """
    texts = [skills_to_text(v["skills"]) for v in vacancies]
    vectorizer = TfidfVectorizer(
        max_features=5000,
        min_df=2,
        max_df=0.95,
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b[\w\s\-\.\+]+\b",
    )
    X = vectorizer.fit_transform(texts)

    model = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, n_init=3, batch_size=1000)
    labels = model.fit_predict(X)

    # Топ навыков (токенов) для каждого кластера
    terms = vectorizer.get_feature_names_out()
    top_skills_per_cluster = []
    for i in range(n_clusters):
        center = model.cluster_centers_[i]
        top_idx = np.argsort(center)[-15:][::-1]
        top = [terms[j] for j in top_idx if center[j] > 0]
        top_skills_per_cluster.append(top)

    return X, labels, vectorizer, top_skills_per_cluster


def _short_label(skills: list, max_len: int = 35) -> str:
    """Краткое название кластера из топ-навыков."""
    parts = []
    total = 0
    for s in skills[:5]:
        if total + len(s) + 2 > max_len:
            break
        parts.append(s[:25] if len(s) > 25 else s)
        total += len(parts[-1]) + 2
    return ", ".join(parts) or "—"


def visualize(X, labels, n_clusters: int, top_skills: list, output_path: Path, max_points: int = 5000):
    """Строит 2D визуализацию (t-SNE) с подписями кластеров."""
    labels = np.asarray(labels, dtype=int)
    n = X.shape[0]
    if n > max_points:
        rng = np.random.default_rng(42)
        idx = rng.choice(n, max_points, replace=False)
        X_vis = X[idx].toarray()
        labels_vis = labels[idx]
    else:
        X_vis = X.toarray()
        labels_vis = labels

    print("t-SNE (это может занять 1-2 мин)...")
    tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, n // 4), max_iter=1000)
    X_2d = tsne.fit_transform(X_vis)

    # Цвета кластеров
    cmap = plt.colormaps["tab20"].resampled(n_clusters)
    colors = [cmap(i / max(n_clusters - 1, 1)) for i in range(n_clusters)]

    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.2, 0.8], wspace=0.3)

    ax_scatter = fig.add_subplot(gs[0])
    scatter = ax_scatter.scatter(
        X_2d[:, 0], X_2d[:, 1],
        c=labels_vis,
        cmap="tab20",
        alpha=0.55,
        s=20,
        vmin=0,
        vmax=n_clusters - 1,
        edgecolors="none",
    )

    # Центроиды и подписи кластеров на графике
    for i in range(n_clusters):
        mask = labels_vis == i
        if not np.any(mask):
            continue
        cx = np.median(X_2d[mask, 0])
        cy = np.median(X_2d[mask, 1])
        label = _short_label(top_skills[i], max_len=28)
        ax_scatter.annotate(
            f"{i}: {label}",
            (cx, cy),
            fontsize=8,
            ha="center",
            va="center",
            fontweight="bold",
            color="black",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=colors[i], alpha=0.9, edgecolor="white", linewidth=0.5),
        )

    ax_scatter.set_title("Кластеризация вакансий по навыкам (t-SNE)", fontsize=14)
    ax_scatter.set_xticks([])
    ax_scatter.set_yticks([])
    ax_scatter.spines["top"].set_visible(False)
    ax_scatter.spines["right"].set_visible(False)

    # Легенда справа: полный список навыков по кластерам
    ax_leg = fig.add_subplot(gs[1])
    ax_leg.axis("off")
    legend_lines = []
    for i in range(n_clusters):
        skills_str = ", ".join(top_skills[i][:6]) if top_skills[i] else "—"
        legend_lines.append(f"Кластер {i}:\n{skills_str}")

    leg_text = "\n\n".join(legend_lines)
    ax_leg.text(0.02, 0.98, leg_text, transform=ax_leg.transAxes, fontsize=9,
                verticalalignment="top", fontfamily="sans-serif",
                bbox=dict(boxstyle="round", facecolor="#f5f5f5", alpha=0.9, edgecolor="#ccc"))

    ax_leg.set_title("Топ навыков по кластерам", fontsize=12)

    fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Сохранено: {output_path}")


def print_cluster_summary(top_skills_per_cluster: list, n_clusters: int):
    """Выводит интерпретацию кластеров по топ-навыкам."""
    print("\n--- Топ навыков по кластерам (интерпретация доменов) ---\n")
    for i in range(n_clusters):
        skills = top_skills_per_cluster[i][:10]
        print(f"Кластер {i}: {', '.join(skills) or '(пусто)'}")


async def main_async(
    sample_size: int = 50_000,
    n_clusters: int = 15,
    output: str = "clusters.png",
):
    print("Загрузка вакансий из БД...")
    vacancies = await load_vacancies_sample(sample_size)
    print(f"Загружено {len(vacancies)} вакансий с навыками")

    if len(vacancies) < n_clusters * 10:
        print("Недостаточно данных для кластеризации. Увеличьте --sample.")
        return

    print("Кластеризация (TF-IDF + MiniBatchKMeans)...")
    X, labels, _, top_skills = fit_clusters(vacancies, n_clusters=n_clusters)

    print_cluster_summary(top_skills, n_clusters)

    out_path = ROOT / "experiments" / output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print("Визуализация (PCA 2D)...")
    visualize(X, labels, n_clusters, top_skills, out_path)


def main():
    parser = argparse.ArgumentParser(description="Кластеризация вакансий по навыкам")
    parser.add_argument("--sample", type=int, default=50_000, help="Размер выборки")
    parser.add_argument("--clusters", type=int, default=15, help="Число кластеров")
    parser.add_argument("--output", default="clusters.png", help="Файл для графика")
    args = parser.parse_args()
    asyncio.run(main_async(
        sample_size=args.sample,
        n_clusters=args.clusters,
        output=args.output,
    ))


if __name__ == "__main__":
    main()
