import os

# Stockage local des pièces jointes (documents, messages vocaux) — même limitation que la base
# SQLite : disque éphémère sur le plan gratuit Render, acceptable pour une démo (voir README).
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
