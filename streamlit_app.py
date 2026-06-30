"""Entrypoint de compatibilidade para deploy legado no Streamlit Cloud."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    # Executa app.py para manter um unico ponto funcional da interface.
    runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
