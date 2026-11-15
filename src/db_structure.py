"""Чтение описания структуры базы данных из TOML-файла."""

import tomllib
from pathlib import Path
from typing import TypeAlias

TomlTable: TypeAlias = dict[str, object]
TomlTableList: TypeAlias = list[TomlTable]
DbStructure: TypeAlias = tuple[TomlTable, TomlTableList, TomlTableList, TomlTableList]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "db_structure.toml"


def _load_config(file_path: str | Path) -> TomlTable:
    """Загрузить TOML-файл и вернуть его содержимое."""

    path = Path(file_path)
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def _read_table(config: TomlTable, section: str) -> TomlTable:
    """Получить одиночную TOML-таблицу и проверить её тип."""

    value = config.get(section)
    if not isinstance(value, dict):
        raise ValueError(f"Раздел [{section}] отсутствует или имеет неверный формат")
    return value


def _read_table_list(config: TomlTable, section: str) -> TomlTableList:
    """Получить массив TOML-таблиц и проверить его тип."""

    value = config.get(section)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Раздел [[{section}]] отсутствует или имеет неверный формат")
    return value


def read_database(file_path: str | Path = DEFAULT_CONFIG_PATH) -> TomlTable:
    """Прочитать раздел ``database``."""

    return _read_table(_load_config(file_path), "database")


def read_tables(file_path: str | Path = DEFAULT_CONFIG_PATH) -> TomlTableList:
    """Прочитать список ``tables``."""

    return _read_table_list(_load_config(file_path), "tables")


def read_functions(file_path: str | Path = DEFAULT_CONFIG_PATH) -> TomlTableList:
    """Прочитать список ``functions``."""

    return _read_table_list(_load_config(file_path), "functions")


def read_triggers(file_path: str | Path = DEFAULT_CONFIG_PATH) -> TomlTableList:
    """Прочитать список ``triggers``."""

    return _read_table_list(_load_config(file_path), "triggers")


def read_db_structure(file_path: str | Path = DEFAULT_CONFIG_PATH) -> DbStructure:
    """Прочитать все разделы конфигурации за одно обращение к файлу.

    Возвращаемый кортеж содержит ``database``, ``tables``, ``functions`` и
    ``triggers`` в указанном порядке.
    """

    config = _load_config(file_path)
    return (
        _read_table(config, "database"),
        _read_table_list(config, "tables"),
        _read_table_list(config, "functions"),
        _read_table_list(config, "triggers"),
    )
