"""Safe client-only Supabase configuration for EFOS Streamlit.

This loader handles Streamlit's project-root/cwd differences without ever
falling back to the old local users.txt password database.
"""
from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any
from ui import supabase_bridge as SB


def require_cloud_config(project_root: Path, runtime_secrets: Any = None) -> dict[str, str]:
    """Read PUBLIC credentials from project file or Streamlit Cloud secrets.

    Preference: project-root .streamlit/secrets.toml for local development;
    then Streamlit Cloud secrets or environment variables. No admin keys.
    Never include values in exceptions or log output.
    """
    path = Path(project_root) / '.streamlit' / 'secrets.toml'
    if path.exists():
        if not path.is_file():
            raise SB.CloudError('La ruta .streamlit/secrets.toml existe pero no es un archivo.')
        try:
            with path.open('rb') as handle:
                content = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise SB.CloudError('No se pudo leer .streamlit/secrets.toml. Revisa su sintaxis TOML.') from None
        configured = SB.config(content)
        if configured is not None:
            return configured

    try:
        configured = SB.config(runtime_secrets)
    except FileNotFoundError:
        configured = SB.config()
    if configured is not None:
        return configured

    raise SB.CloudError(
        'No se encontró EFOS_SUPABASE_URL y EFOS_SUPABASE_ANON_KEY. '
        'Configura .streamlit/secrets.toml en la raíz de efos o los Secrets '
        'de Streamlit Cloud. No se utilizará auth/users.txt.'
    )
