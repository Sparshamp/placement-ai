"""Download the embedding model required for the one-off jobs-index rebuild."""

from huggingface_hub import snapshot_download


if __name__ == "__main__":
    print(snapshot_download("BAAI/bge-large-en-v1.5"))
