"""Entraînement du classifieur de fraude par SMS.

Pipeline : union de TF-IDF (mots 1-2 grammes + caractères 3-5 grammes) suivie
d'une régression logistique. Le mélange mots/caractères rend le modèle robuste
au bilinguisme (FR/EN) et aux fautes/obfuscations volontaires des fraudeurs.

Usage :
    python -m sentinelle.ml.train \
        --data sentinelle/ml/data/seed_dataset.csv \
        --output data/model.joblib
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Console Windows (cp1252) : éviter un crash sur les caractères non-ASCII des logs.
try:  # pragma: no cover - dépend de la plateforme
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_DATA = Path(__file__).resolve().parent / "data" / "seed_dataset.csv"


def load_dataset(path: str | Path) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            text = (row.get("text") or "").strip()
            label = (row.get("label") or "").strip().lower()
            if not text or label not in ("fraud", "legit"):
                continue
            texts.append(text)
            labels.append(1 if label == "fraud" else 0)
    if not texts:
        raise ValueError(f"Aucune donnée exploitable dans {path}")
    return texts, labels


def build_pipeline():
    # Imports différés : scikit-learn n'est requis qu'à l'entraînement.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    features = FeatureUnion([
        ("word", TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2), min_df=1,
            sublinear_tf=True, lowercase=True, strip_accents="unicode")),
        ("char", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=1,
            sublinear_tf=True, lowercase=True, strip_accents="unicode")),
    ])
    clf = LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")
    return Pipeline([("features", features), ("clf", clf)])


def train(data_path: str | Path = DEFAULT_DATA, output_path: str | Path = "data/model.joblib",
          *, verbose: bool = True) -> str:
    import joblib

    texts, labels = load_dataset(data_path)
    pipeline = build_pipeline()

    # Évaluation honnête sur jeu de test si l'on a assez d'exemples.
    if len(texts) >= 40 and len(set(labels)) == 2:
        from sklearn.metrics import classification_report
        from sklearn.model_selection import train_test_split

        x_tr, x_te, y_tr, y_te = train_test_split(
            texts, labels, test_size=0.25, random_state=42, stratify=labels)
        pipeline.fit(x_tr, y_tr)
        if verbose:
            preds = pipeline.predict(x_te)
            print("=== Évaluation sur jeu de test ===")
            print(classification_report(y_te, preds, target_names=["legit", "fraud"],
                                        zero_division=0))

    # Modèle livré : réentraîné sur l'ensemble des données.
    pipeline.fit(texts, labels)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, output_path)
    if verbose:
        print(f"Modele entraine sur {len(texts)} exemples -> {output_path}")
    return str(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Entraîne le classifieur de fraude Sentinelle.")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="CSV d'entraînement")
    parser.add_argument("--output", default="data/model.joblib", help="Chemin du modèle")
    parser.add_argument("--quiet", action="store_true", help="Sortie silencieuse")
    args = parser.parse_args()
    train(args.data, args.output, verbose=not args.quiet)


if __name__ == "__main__":
    main()
