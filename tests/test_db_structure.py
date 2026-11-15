"""Тесты чтения конфигурации структуры базы данных."""

import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest

from src import db_structure

VALID_CONFIG = """\
format_version = 1

[database]
dialect = "postgresql"
schema = "test_schema"
encoding = "UTF8"

[[tables]]
name = "users"

[[functions]]
name = "update_timestamp"

[[triggers]]
name = "trg_update_timestamp"
"""


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Создать корректный тестовый TOML-файл."""

    path = tmp_path / "db_structure.toml"
    path.write_text(VALID_CONFIG, encoding="utf-8")
    return path


def test_read_db_structure(config_path: Path) -> None:
    """Все разделы загружаются за одно чтение файла."""

    database, tables, functions, triggers = db_structure.read_db_structure(config_path)

    assert database == {
        "dialect": "postgresql",
        "schema": "test_schema",
        "encoding": "UTF8",
    }
    assert tables == [{"name": "users"}]
    assert functions == [{"name": "update_timestamp"}]
    assert triggers == [{"name": "trg_update_timestamp"}]


def test_individual_readers_use_default_config() -> None:
    """Отдельные функции читают нужные разделы из файла по умолчанию."""

    config = db_structure._load_config(db_structure.DEFAULT_CONFIG_PATH)

    assert db_structure.read_database() == config["database"]
    assert db_structure.read_tables() == config["tables"]
    assert db_structure.read_functions() == config["functions"]
    assert db_structure.read_triggers() == config["triggers"]


def test_reader_accepts_string_path(config_path: Path) -> None:
    """В качестве пути можно передать строку."""

    assert db_structure.read_database(str(config_path))["schema"] == "test_schema"


@pytest.mark.parametrize("value", [None, "database", 1, []])
def test_read_table_rejects_missing_or_invalid_section(value: object) -> None:
    """Одиночный раздел должен существовать и быть TOML-таблицей."""

    config = {} if value is None else {"database": value}

    with pytest.raises(
        ValueError,
        match=r"Раздел \[database\] отсутствует или имеет неверный формат",
    ):
        db_structure._read_table(config, "database")


@pytest.mark.parametrize("value", [None, "tables", {}, ["not a table"]])
def test_read_table_list_rejects_missing_or_invalid_section(value: object) -> None:
    """Списочный раздел должен быть массивом TOML-таблиц."""

    config = {} if value is None else {"tables": value}

    with pytest.raises(
        ValueError,
        match=r"Раздел \[\[tables\]\] отсутствует или имеет неверный формат",
    ):
        db_structure._read_table_list(config, "tables")


def test_read_table_list_accepts_empty_list() -> None:
    """Пустой массив TOML-таблиц является корректным разделом."""

    assert db_structure._read_table_list({"tables": []}, "tables") == []


@pytest.mark.parametrize(
    ("reader", "section"),
    [
        (db_structure.read_database, "database"),
        (db_structure.read_tables, "tables"),
        (db_structure.read_functions, "functions"),
        (db_structure.read_triggers, "triggers"),
    ],
)
def test_individual_readers_reject_missing_section(
    tmp_path: Path,
    reader: Callable[[str | Path], object],
    section: str,
) -> None:
    """Публичные функции сообщают об отсутствии запрошенного раздела."""

    path = tmp_path / f"without_{section}.toml"
    path.write_text("format_version = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="отсутствует или имеет неверный формат"):
        reader(path)


def test_missing_file_raises_file_not_found_error(tmp_path: Path) -> None:
    """Ошибка отсутствующего файла не подавляется."""

    with pytest.raises(FileNotFoundError):
        db_structure.read_db_structure(tmp_path / "missing.toml")


def test_invalid_toml_raises_decode_error(tmp_path: Path) -> None:
    """Ошибка синтаксиса TOML не подавляется."""

    path = tmp_path / "invalid.toml"
    path.write_text("[database\n", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        db_structure.read_db_structure(path)
