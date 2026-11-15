"""Тесты моделей данных."""

from types import SimpleNamespace
from typing import Any

import pytest

from src.models import AircraftState, BoundingBox, PyCountryData


def make_aircraft(**overrides: Any) -> AircraftState:
    """Создать корректное состояние самолёта с изменяемыми полями."""

    values: dict[str, Any] = {
        "icao24": "ABC123",
        "callsign": " TEST123 ",
        "origin_country": " France ",
        "time_position": 1,
        "last_contact": 2,
        "longitude": 2.0,
        "latitude": 48.0,
        "baro_altitude": 10_000.0,
        "on_ground": False,
        "velocity": 250.0,
        "true_track": 90.0,
        "vertical_rate": 5.0,
        "sensors": [1, 2],
        "geo_altitude": 10_100.0,
        "squawk": " 7000 ",
        "spi": False,
        "position_source": 0,
    }
    values.update(overrides)
    return AircraftState(**values)


def test_bounding_box_operations() -> None:
    """Границы проверяют точки и формируют параметры запроса."""

    box = BoundingBox(south=-10, north=20, west=-30, east=40)

    assert box.contains(0, 0)
    assert not box.contains(-11, 0)
    assert not box.contains(0, 41)
    assert box.to_query_params() == {
        "lamin": "-10",
        "lamax": "20",
        "lomin": "-30",
        "lomax": "40",
    }


@pytest.mark.parametrize(
    ("south", "north"),
    [(-91, 0), (10, 0), (0, 91)],
)
def test_bounding_box_rejects_invalid_latitude(south: float, north: float) -> None:
    """Каждая нарушенная граница широты отклоняется."""

    with pytest.raises(ValueError, match="Некорректные границы широты"):
        BoundingBox(south=south, north=north, west=0, east=1)


@pytest.mark.parametrize(
    ("west", "east"),
    [(-181, 0), (10, 0), (0, 181)],
)
def test_bounding_box_rejects_invalid_longitude(west: float, east: float) -> None:
    """Каждая нарушенная граница долготы отклоняется."""

    with pytest.raises(ValueError, match="Некорректные границы долготы"):
        BoundingBox(south=0, north=1, west=west, east=east)


def test_pycountry_data_normalizes_values() -> None:
    """Строки страны очищаются, а коды переводятся в верхний регистр."""

    country = PyCountryData(
        name=" France ",
        alpha_2="fr",
        alpha_3="fra",
        numeric="250",
        official_name=" French Republic ",
        common_name="  ",
        flag=" flag ",
    )

    assert country.name == "France"
    assert country.alpha_2 == "FR"
    assert country.alpha_3 == "FRA"
    assert country.numeric == "250"
    assert country.official_name == "French Republic"
    assert country.common_name is None
    assert country.flag == "flag"


def test_pycountry_data_from_pycountry() -> None:
    """Модель создаётся из объекта справочника с необязательными полями."""

    source = SimpleNamespace(
        name="France",
        alpha_2="FR",
        alpha_3="FRA",
        numeric="250",
    )

    country = PyCountryData.from_pycountry(source)

    assert country == PyCountryData("France", "FR", "FRA", "250")


def test_pycountry_data_rejects_object_without_required_fields() -> None:
    """Отсутствие обязательных атрибутов преобразуется в ValueError."""

    with pytest.raises(ValueError, match="не содержит обязательные поля"):
        PyCountryData.from_pycountry(SimpleNamespace())


@pytest.mark.parametrize(
    ("kwargs", "error", "message"),
    [
        ({"name": 1}, TypeError, "name должен иметь тип str"),
        ({"name": "  "}, ValueError, "name не может быть пустым"),
        ({"alpha_2": "F"}, ValueError, "alpha_2 должен содержать 2 латинские буквы"),
        ({"alpha_2": "F1"}, ValueError, "alpha_2 должен содержать 2 латинские буквы"),
        ({"alpha_2": "ЯЯ"}, ValueError, "alpha_2 должен содержать 2 латинские буквы"),
        ({"numeric": "25"}, ValueError, "numeric должен содержать три цифры"),
        ({"numeric": "ABC"}, ValueError, "numeric должен содержать три цифры"),
        ({"official_name": 1}, TypeError, "official_name должен иметь тип str или None"),
    ],
)
def test_pycountry_data_rejects_invalid_values(
    kwargs: dict[str, object],
    error: type[Exception],
    message: str,
) -> None:
    """Неверные типы и форматы полей страны отклоняются."""

    values: dict[str, object] = {
        "name": "France",
        "alpha_2": "FR",
        "alpha_3": "FRA",
        "numeric": "250",
    }
    values.update(kwargs)

    with pytest.raises(error, match=message):
        PyCountryData(**values)  # type: ignore[arg-type]


def test_aircraft_state_normalizes_values() -> None:
    """Основные строковые и списочные поля самолёта нормализуются."""

    aircraft = make_aircraft()

    assert aircraft.icao24 == "abc123"
    assert aircraft.callsign == "TEST123"
    assert aircraft.origin_country == "France"
    assert aircraft.squawk == "7000"
    assert aircraft.sensors == (1, 2)


def test_aircraft_state_accepts_optional_values() -> None:
    """Необязательные поля могут принимать None."""

    aircraft = make_aircraft(
        callsign=None,
        squawk=None,
        time_position=None,
        longitude=None,
        sensors=None,
    )

    assert aircraft.callsign is None
    assert aircraft.squawk is None
    assert aircraft.time_position is None
    assert aircraft.longitude is None
    assert aircraft.sensors is None


@pytest.mark.parametrize("icao24", ["ABC12", "ZBC123"])
def test_aircraft_state_rejects_invalid_icao24(icao24: str) -> None:
    """ICAO24 должен содержать ровно шесть шестнадцатеричных символов."""

    with pytest.raises(ValueError, match="icao24 должен содержать 6"):
        make_aircraft(icao24=icao24)


@pytest.mark.parametrize(
    ("field", "value", "error", "message"),
    [
        ("origin_country", 1, TypeError, "origin_country должен иметь тип str"),
        ("origin_country", " ", ValueError, "origin_country не может быть пустым"),
        ("callsign", 1, TypeError, "callsign должен иметь тип str или None"),
        ("squawk", 1, TypeError, "squawk должен иметь тип str или None"),
        ("longitude", True, TypeError, "longitude должен быть числом или None"),
        ("latitude", "48", TypeError, "latitude должен быть числом или None"),
        ("time_position", True, TypeError, "time_position должен иметь тип int или None"),
        ("last_contact", "2", TypeError, "last_contact должен иметь тип int или None"),
        ("position_source", -1, ValueError, "position_source не может быть отрицательным"),
        ("on_ground", 0, TypeError, "on_ground должен иметь тип bool"),
        ("spi", 0, TypeError, "spi должен иметь тип bool"),
    ],
)
def test_aircraft_state_rejects_invalid_types(
    field: str,
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    """Поля самолёта строго проверяют типы."""

    with pytest.raises(error, match=message):
        make_aircraft(**{field: value})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("longitude", -181, "longitude должен находиться"),
        ("longitude", 181, "longitude должен находиться"),
        ("latitude", -91, "latitude должен находиться"),
        ("latitude", 91, "latitude должен находиться"),
        ("velocity", -1, "velocity не может быть отрицательной"),
        ("true_track", -1, "true_track должен находиться"),
        ("true_track", 361, "true_track должен находиться"),
    ],
)
def test_aircraft_state_rejects_out_of_range_values(field: str, value: float, message: str) -> None:
    """Координаты, скорость и курс ограничены допустимыми диапазонами."""

    with pytest.raises(ValueError, match=message):
        make_aircraft(**{field: value})


@pytest.mark.parametrize("sensors", ["1,2", 1, [1, True], [1, "2"]])
def test_aircraft_state_rejects_invalid_sensors(sensors: object) -> None:
    """Сенсоры должны быть последовательностью целых чисел без bool."""

    with pytest.raises(TypeError, match="sensors должен быть последовательностью"):
        make_aircraft(sensors=sensors)


def test_aircraft_altitude_prefers_geo_altitude() -> None:
    """Геометрическая высота имеет приоритет над барометрической."""

    assert make_aircraft(geo_altitude=200, baro_altitude=100).altitude == 200
    assert make_aircraft(geo_altitude=None, baro_altitude=100).altitude == 100


def test_aircraft_comparisons() -> None:
    """Самолёты сравниваются по скорости и доступной высоте."""

    slow = make_aircraft(velocity=100, geo_altitude=None, baro_altitude=100)
    equal = make_aircraft(velocity=100, geo_altitude=None, baro_altitude=100)
    fast = make_aircraft(velocity=200, geo_altitude=200)

    assert slow.compare_speed(fast) == -1
    assert slow.compare_speed(equal) == 0
    assert fast.compare_speed(slow) == 1
    assert fast.is_faster_than(slow)
    assert not slow.is_faster_than(fast)
    assert slow.compare_altitude(fast) == -1
    assert slow.compare_altitude(equal) == 0
    assert fast.compare_altitude(slow) == 1
    assert fast.is_higher_than(slow)
    assert not slow.is_higher_than(fast)


def test_aircraft_comparisons_require_values() -> None:
    """Сравнение невозможно без скорости или высоты у любого участника."""

    aircraft = make_aircraft()
    without_speed = make_aircraft(velocity=None)
    without_altitude = make_aircraft(geo_altitude=None, baro_altitude=None)

    with pytest.raises(ValueError, match="без данных о скорости"):
        without_speed.compare_speed(aircraft)
    with pytest.raises(ValueError, match="без данных о скорости"):
        aircraft.compare_speed(without_speed)
    with pytest.raises(ValueError, match="без данных о высоте"):
        without_altitude.compare_altitude(aircraft)
    with pytest.raises(ValueError, match="без данных о высоте"):
        aircraft.compare_altitude(without_altitude)


def test_aircraft_comparisons_require_aircraft() -> None:
    """Сравнивать можно только экземпляры AircraftState."""

    with pytest.raises(TypeError, match="только объекты AircraftState"):
        make_aircraft().compare_speed(object())


def test_aircraft_to_dict() -> None:
    """Сериализация возвращает JSON-совместимый список сенсоров."""

    with_sensors = make_aircraft().to_dict()
    without_sensors = make_aircraft(sensors=None).to_dict()

    assert with_sensors["sensors"] == [1, 2]
    assert without_sensors["sensors"] is None
