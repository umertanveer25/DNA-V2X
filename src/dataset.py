import os
import numpy as np
from sklearn.model_selection import GroupKFold

DEFAULT_PATHS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Neuro-VeReMi", "results", "authentic_veremi_data.npz")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results", "authentic_veremi_data.npz")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "authentic_veremi_data.npz")),
]


def find_veremi_cache() -> str:
    """Resolves authentic VeReMi dataset npz cache location across repo structures."""
    for p in DEFAULT_PATHS:
        if os.path.exists(p):
            return p
    return DEFAULT_PATHS[0]


CACHE_FILE = find_veremi_cache()


class AuthenticVeReMiParser:
    """
    Directly loads and interfaces authentic VeReMi dataset (SecureComm 2018 / Kamel et al.)
    for DNA-V2X encoding, verification, and classification.
    """
    def __init__(self, cache_path=None, max_samples=None):
        self.cache_path = cache_path or find_veremi_cache()
        self.max_samples = max_samples

    def load_dataset(self):
        if not os.path.exists(self.cache_path):
            raise FileNotFoundError(f"Authentic VeReMi cache not found at: {self.cache_path}")

        print(f"[DNA-V2X] Loading authentic VeReMi dataset from: {self.cache_path}")
        data = np.load(self.cache_path)
        X = data["X"]
        y = data["y"]
        groups = data["groups"]
        attack_types = data["attack_types"]

        if self.max_samples is not None and self.max_samples < len(X):
            X = X[:self.max_samples]
            y = y[:self.max_samples]
            groups = groups[:self.max_samples]
            attack_types = attack_types[:self.max_samples]

        print(f"[DNA-V2X] Successfully loaded {len(X)} authentic records. Benign={np.sum(y==0)}, Malicious={np.sum(y==1)}")
        return X, y, groups, attack_types


def get_grouped_kfold_splits(X, y, groups, n_splits=10):
    gkf = GroupKFold(n_splits=n_splits)
    return list(gkf.split(X, y, groups))


if __name__ == "__main__":
    parser = AuthenticVeReMiParser()
    X, y, groups, atks = parser.load_dataset()
    print("X shape:", X.shape, "y shape:", y.shape)

