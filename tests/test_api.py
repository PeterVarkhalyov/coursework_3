"""Тесты клиентов внешних API без сетевых запросов."""

import json
from typing import Any
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest

from src import api
from src.api import (
    AbstractAircraftAPI,
    AbstractAPIClient,
    AbstractCountryAPI,
    APIError,
    NominatimAPI,
    OpenSkyAPI,
)
from src.models import AircraftState


class ConcreteClient(AbstractAPIClient):
    """Минимальная реализация абстрактного клиента для тестов."""

    def connect(self) -> bool:
        return True


class FakeResponse:
    """Контекстный менеджер с телом HTTP-ответа."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def nominatim_item(**overrides: Any) -> dict[str, Any]:
    """Создать корректный элемент ответа Nominatim."""

    item: dict[str, Any] = {
        "display_name": "France",
        "address": {"country_code": "fr"},
        "lat": "46.0",
        "lon": "2.0",
        "boundingbox": ["41.0", "51.0", "-5.0", "10.0"],
    }
    item.update(overrides)
    return item


def opensky_item(**overrides: Any) -> list[Any]:
    """Создать корректный элемент ответа OpenSky."""

    values: list[Any] = [
        "abc123",
        " TEST123 ",
        "France",
        1,
        2,
        2.0,
        46.0,
        10_000.0,
        False,
        250.0,
        90.0,
        5.0,
        [1, 2],
        10_100.0,
        "7000",
        False,
        0,
    ]
    for index, value in overrides.items():
        values[int(index)] = value
    return values


def test_abstract_client_initialization_and_abstract_methods() -> None:
    """Базовый клиент нормализует URL, а тела абстрактных методов исполняемы."""

    client = ConcreteClient("https://example.test///", timeout=5)

    assert client.base_url == "https://example.test"
    assert client.timeout == 5
    assert client.connect()
    assert AbstractAPIClient.connect(client) is None  # type: ignore[func-returns-value]
    assert AbstractCountryAPI.get_data(client, "France") is None  # type: ignore[arg-type, func-returns-value]
    assert AbstractAircraftAPI.get_data(client) is None  # type: ignore[arg-type, func-returns-value]


def test_request_json_builds_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP-метод формирует URL, заголовки и разбирает JSON."""

    urlopen = MagicMock(return_value=FakeResponse(b'{"ok": true}'))
    monkeypatch.setattr(api, "urlopen", urlopen)
    client = ConcreteClient("https://example.test/", timeout=7)

    result = client._request_json(
        "/resource",
        {"name": "A B", "limit": 1},
        {"User-Agent": "tests"},
    )

    assert result == {"ok": True}
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://example.test/resource?name=A+B&limit=1"
    assert request.get_header("User-agent") == "tests"
    urlopen.assert_called_once_with(request, timeout=7)


def test_request_json_accepts_empty_options(monkeypatch: pytest.MonkeyPatch) -> None:
    """Параметры и заголовки HTTP-запроса необязательны."""

    urlopen = MagicMock(return_value=FakeResponse(b"[]"))
    monkeypatch.setattr(api, "urlopen", urlopen)

    assert ConcreteClient("https://example.test")._request_json("items") == []
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://example.test/items"
    assert request.headers == {}


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (HTTPError("url", 503, "unavailable", MagicMock(), None), "API вернуло HTTP 503"),
        (URLError("offline"), "Не удалось подключиться к API: offline"),
        (TimeoutError(), "API не ответило или вернуло некорректные данные"),
    ],
)
def test_request_json_converts_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    message: str,
) -> None:
    """Ошибки транспорта преобразуются в APIError с понятным сообщением."""

    monkeypatch.setattr(api, "urlopen", MagicMock(side_effect=error))

    with pytest.raises(APIError, match=message):
        ConcreteClient("https://example.test")._request_json("items")


def test_request_json_converts_json_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Некорректный JSON преобразуется в APIError."""

    monkeypatch.setattr(api, "urlopen", MagicMock(return_value=FakeResponse(b"{")))

    with pytest.raises(APIError, match="некорректные данные"):
        ConcreteClient("https://example.test")._request_json("items")


@pytest.mark.parametrize(
    ("response", "expected"),
    [({"status": 0}, True), ({"status": 1}, False), ([], False)],
)
def test_nominatim_connect(response: object, expected: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверка подключения учитывает структуру и статус ответа."""

    client = NominatimAPI()
    request = MagicMock(return_value=response)
    monkeypatch.setattr(client, "_request", request)

    assert client.connect() is expected
    request.assert_called_once_with("status", {"format": "json"})


def test_nominatim_get_data_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Координаты разбираются, нормализуются и затем берутся из кэша."""

    client = NominatimAPI()
    request = MagicMock(return_value=[nominatim_item()])
    monkeypatch.setattr(client, "_request", request)

    first = client.get_data(" France ")
    second = client.get_data("france")

    assert first is second
    assert first.name == "France"
    assert first.country_code == "FR"
    assert first.latitude == 46.0
    assert first.longitude == 2.0
    assert first.bounding_box.south == 41.0
    request.assert_called_once()


def test_nominatim_get_data_uses_fallback_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """После неудачного структурированного поиска выполняется свободный поиск."""

    client = NominatimAPI()
    request = MagicMock(side_effect=[[], [nominatim_item()]])
    monkeypatch.setattr(client, "_request", request)

    country = client.get_data("Франция")

    assert country.country_code == "FR"
    assert request.call_count == 2
    assert request.call_args_list[0].args[1]["country"] == "Франция"
    assert request.call_args_list[1].args[1]["q"] == "Франция"


def test_nominatim_get_data_accepts_missing_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """Некорректный address и нестроковый код страны дают country_code=None."""

    client = NominatimAPI()
    request = MagicMock(
        side_effect=[
            [nominatim_item(address="invalid")],
            [nominatim_item(address={"country_code": 1})],
        ]
    )
    monkeypatch.setattr(client, "_request", request)

    without_address = client.get_data("First")
    without_code = client.get_data("Second")

    assert without_address.country_code is None
    assert without_code.country_code is None


def test_nominatim_get_data_rejects_empty_name() -> None:
    """Пустое название страны отклоняется до запроса."""

    with pytest.raises(ValueError, match="не может быть пустым"):
        NominatimAPI().get_data("   ")


@pytest.mark.parametrize(
    ("first_response", "second_response"),
    [(None, None), ([], []), ([], ["not a table"])],
)
def test_nominatim_get_data_rejects_missing_country(
    first_response: object,
    second_response: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Все варианты пустого или неверного результата дают ошибку поиска."""

    client = NominatimAPI()
    monkeypatch.setattr(client, "_request", MagicMock(side_effect=[first_response, second_response]))

    with pytest.raises(APIError, match="Страна не найдена"):
        client.get_data("Unknown")


@pytest.mark.parametrize("bounding_box", [None, ["1", "2"]])
def test_nominatim_get_data_rejects_invalid_bounding_box(
    bounding_box: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Границы должны быть списком из четырёх значений."""

    client = NominatimAPI()
    monkeypatch.setattr(client, "_request", MagicMock(return_value=[nominatim_item(boundingbox=bounding_box)]))

    with pytest.raises(APIError, match="не вернул границы"):
        client.get_data("France")


@pytest.mark.parametrize(
    "changes",
    [
        {"lat": None},
        {"lat": "invalid"},
        {"boundingbox": ["91", "92", "0", "1"]},
    ],
)
def test_nominatim_get_data_rejects_invalid_coordinates(
    changes: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Отсутствующие и неверные координаты преобразуются в APIError."""

    client = NominatimAPI()
    monkeypatch.setattr(client, "_request", MagicMock(return_value=[nominatim_item(**changes)]))

    with pytest.raises(APIError, match="некорректные координаты"):
        client.get_data("France")


def test_nominatim_get_data_rejects_missing_coordinate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Отсутствующая обязательная координата преобразуется в APIError."""

    item = nominatim_item()
    del item["lon"]
    client = NominatimAPI()
    monkeypatch.setattr(client, "_request", MagicMock(return_value=[item]))

    with pytest.raises(APIError, match="некорректные координаты"):
        client.get_data("France")


def test_nominatim_request_without_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Запрос без ограничения частоты не вызывает sleep и обновляет время."""

    client = NominatimAPI()
    request_json = MagicMock(return_value={"ok": True})
    sleep = MagicMock()
    monkeypatch.setattr(client, "_request_json", request_json)
    monkeypatch.setattr(api.time, "monotonic", MagicMock(side_effect=[2.0, 3.0]))
    monkeypatch.setattr(api.time, "sleep", sleep)

    assert client._request("status", {"format": "json"}) == {"ok": True}
    sleep.assert_not_called()
    assert client._last_request_time == 3.0


def test_nominatim_request_with_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Слишком ранний запрос ждёт остаток обязательной секунды."""

    client = NominatimAPI()
    sleep = MagicMock()
    monkeypatch.setattr(client, "_request_json", MagicMock(return_value=[]))
    monkeypatch.setattr(api.time, "monotonic", MagicMock(side_effect=[0.25, 0.5]))
    monkeypatch.setattr(api.time, "sleep", sleep)

    client._request("search", {})

    sleep.assert_called_once_with(0.75)
    assert client._last_request_time == 0.5


def test_nominatim_request_updates_time_after_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Время последнего запроса обновляется также после исключения."""

    client = NominatimAPI()
    monkeypatch.setattr(client, "_request_json", MagicMock(side_effect=APIError("failed")))
    monkeypatch.setattr(api.time, "monotonic", MagicMock(side_effect=[2.0, 4.0]))

    with pytest.raises(APIError, match="failed"):
        client._request("status", {})
    assert client._last_request_time == 4.0


def test_opensky_connect() -> None:
    """Анонимный клиент OpenSky всегда готов к запросу."""

    assert OpenSkyAPI().connect()


def test_opensky_get_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Снимок OpenSky содержит время и только корректные самолёты."""

    client = OpenSkyAPI()
    request = MagicMock(return_value={"time": 100, "states": [opensky_item(), ["short"]]})
    monkeypatch.setattr(client, "_request_json", request)

    server_time, aircraft = client.get_data()

    assert server_time == 100
    assert len(aircraft) == 1
    assert isinstance(aircraft[0], AircraftState)
    assert aircraft[0].callsign == "TEST123"
    request.assert_called_once_with("states/all")


def test_opensky_get_data_accepts_missing_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """Отсутствующий список states трактуется как пустой."""

    client = OpenSkyAPI()
    monkeypatch.setattr(client, "_request_json", MagicMock(return_value={"time": 100}))

    assert client.get_data() == (100, [])


def test_opensky_get_data_rejects_non_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Корневой ответ OpenSky должен быть словарём."""

    client = OpenSkyAPI()
    monkeypatch.setattr(client, "_request_json", MagicMock(return_value=[]))

    with pytest.raises(APIError, match="неожиданный ответ"):
        client.get_data()


@pytest.mark.parametrize("server_time", [None, True])
def test_opensky_get_data_rejects_invalid_time(server_time: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """Время сервера должно быть целым числом, но не bool."""

    client = OpenSkyAPI()
    monkeypatch.setattr(client, "_request_json", MagicMock(return_value={"time": server_time}))

    with pytest.raises(APIError, match="корректное время"):
        client.get_data()


def test_opensky_get_data_rejects_invalid_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """Непустой states должен быть списком."""

    client = OpenSkyAPI()
    monkeypatch.setattr(client, "_request_json", MagicMock(return_value={"time": 100, "states": "invalid"}))

    with pytest.raises(APIError, match="некорректный список"):
        client.get_data()


@pytest.mark.parametrize(
    "item",
    [
        None,
        ["short"],
        opensky_item(**{"0": 123}),
        opensky_item(**{"2": 123}),
        opensky_item(**{"8": 0}),
    ],
)
def test_parse_aircraft_rejects_invalid_structure(item: object) -> None:
    """Элемент OpenSky проверяется до построения модели."""

    assert OpenSkyAPI._parse_aircraft(item) is None


def test_parse_aircraft_normalizes_optional_fields() -> None:
    """Необязательные поля ответа OpenSky безопасно нормализуются."""

    item = opensky_item(**{"1": 1, "14": 1, "15": 1})

    aircraft = OpenSkyAPI._parse_aircraft(item)

    assert aircraft is not None
    assert aircraft.callsign is None
    assert aircraft.squawk is None
    assert aircraft.spi is False


def test_parse_aircraft_converts_empty_callsign() -> None:
    """Пустой после strip позывной преобразуется в None."""

    aircraft = OpenSkyAPI._parse_aircraft(opensky_item(**{"1": "  "}))

    assert aircraft is not None
    assert aircraft.callsign is None


def test_parse_aircraft_ignores_invalid_model() -> None:
    """Ошибка валидации AircraftState делает элемент пропущенным."""

    assert OpenSkyAPI._parse_aircraft(opensky_item(**{"0": "invalid"})) is None


def test_parse_aircraft_ignores_type_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ошибка типа при построении AircraftState также делает элемент пропущенным."""

    monkeypatch.setattr(OpenSkyAPI, "_to_int", MagicMock(return_value="invalid"))

    assert OpenSkyAPI._parse_aircraft(opensky_item()) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), (True, None), ("1.5", 1.5), ("invalid", None), (object(), None)],
)
def test_to_float(value: object, expected: float | None) -> None:
    """Преобразование float безопасно для всех типов входа."""

    assert OpenSkyAPI._to_float(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), (True, None), ("12", 12), ("invalid", None), (object(), None)],
)
def test_to_int(value: object, expected: int | None) -> None:
    """Преобразование int безопасно для всех типов входа."""

    assert OpenSkyAPI._to_int(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ([1, "2", True], [1, 2]),
        (["invalid"], None),
        ([object()], None),
    ],
)
def test_to_int_list(value: object, expected: list[int] | None) -> None:
    """Список сенсоров преобразуется в int без логических значений."""

    assert OpenSkyAPI._to_int_list(value) == expected


def test_json_decode_error_is_expected_type() -> None:
    """Проверка тестовой предпосылки для обработчика JSONDecodeError."""

    with pytest.raises(json.JSONDecodeError):
        json.loads("{")
