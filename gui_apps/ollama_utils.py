"""
Ollama Utilities

Helper functions for querying the local Ollama installation.
"""

import subprocess


def get_ollama_models() -> list[str]:
    """Return the list of locally installed Ollama model names.

    Runs ``ollama list``, parses the tabular output, and returns the
    model name column.  Returns an empty list if Ollama is not installed,
    not running, or the command times out.

    Returns
    -------
    list[str]
        Installed model names (e.g. ``["gemma3:27b", "llama3.1:8b"]``).
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            return []

        lines = result.stdout.strip().split("\n")
        models = []
        for line in lines[1:]:  # ヘッダー行をスキップ
            parts = line.split()
            if parts:
                models.append(parts[0])  # NAME列
        return models

    except FileNotFoundError:
        return []
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


if __name__ == "__main__":
    models = get_ollama_models()
    if models:
        print("検出されたモデル:")
        for m in models:
            print(f"  {m}")
    else:
        print("Ollama not detected")
