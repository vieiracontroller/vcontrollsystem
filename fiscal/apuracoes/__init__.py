from __future__ import annotations

from importlib import import_module
import inspect
import pkgutil

from fiscal.apuracoes.base import ApuracaoTributoBase


def carregar_plugins_apuracao() -> list[ApuracaoTributoBase]:
    """Carrega plugins dinamicamente para permitir extensao sem alterar o nucleo."""
    plugins: list[ApuracaoTributoBase] = []

    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name in {"base"}:
            continue

        module = import_module(f"{__name__}.{module_info.name}")

        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate, ApuracaoTributoBase):
                continue
            if candidate is ApuracaoTributoBase:
                continue
            if inspect.isabstract(candidate):
                continue
            plugins.append(candidate())

    return sorted(plugins, key=lambda item: item.nome)
