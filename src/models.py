"""Модели данных."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass


@dataclass
class BoundingBox:
    """Объявление прямоугольных границ страны.
    Attributes:
      south, north: координаты широты
      west, east: координаты долготы

    Methods:
      __post_init__(): проверка корректности координат
      contains(): проверка попадпния точки в границы координат
      to_query_params(): подготовка границ для запроса к OpenSky
    """

    south: float
    north: float
    west: float
    east: float

    def __post_init__(self) -> None:
        if not -90 <= self.south <= self.north <= 90:
            raise ValueError("Некорректные границы широты")
        if not -180 <= self.west <= self.east <= 180:
            raise ValueError("Некорректные границы долготы")

    def contains(self, latitude: float, longitude: float) -> bool:
        return self.south <= latitude <= self.north and self.west <= longitude <= self.east

    def to_query_params(self) -> dict[str, str]:
        return {
            "lamin": str(self.south),
            "lamax": str(self.north),
            "lomin": str(self.west),
            "lomax": str(self.east),
        }


@dataclass(frozen=True, slots=True)
class PyCountryData:
    """Структура страны из справочника ``pycountry.countries``.

    Attributes:
        name: краткое название страны.
        alpha_2: двухбуквенный код ISO 3166-1.
        alpha_3: трёхбуквенный код ISO 3166-1.
        numeric: трёхзначный цифровой код ISO 3166-1.
        official_name: официальное название, если оно есть в справочнике.
        common_name: общеупотребительное название, если оно есть в справочнике.
        flag: представление флага страны, возвращаемое ``pycountry``.
    """

    name: str
    alpha_2: str
    alpha_3: str
    numeric: str
    official_name: str | None = None
    common_name: str | None = None
    flag: str | None = None

    def __post_init__(self) -> None:
        """Нормализовать и проверить поля ISO 3166-1."""

        object.__setattr__(self, "name", self._required_text("name", self.name))
        object.__setattr__(self, "alpha_2", self._country_code("alpha_2", self.alpha_2, 2))
        object.__setattr__(self, "alpha_3", self._country_code("alpha_3", self.alpha_3, 3))

        numeric = self._required_text("numeric", self.numeric)
        if len(numeric) != 3 or not numeric.isdigit():
            raise ValueError("numeric должен содержать три цифры")
        object.__setattr__(self, "numeric", numeric)

        for field_name in ("official_name", "common_name", "flag"):
            value = getattr(self, field_name)
            object.__setattr__(self, field_name, self._optional_text(field_name, value))

    @classmethod
    def from_pycountry(cls, country: object) -> "PyCountryData":
        """Создать модель из объекта, возвращённого ``pycountry``."""

        try:
            return cls(
                name=getattr(country, "name"),
                alpha_2=getattr(country, "alpha_2"),
                alpha_3=getattr(country, "alpha_3"),
                numeric=getattr(country, "numeric"),
                official_name=getattr(country, "official_name", None),
                common_name=getattr(country, "common_name", None),
                flag=getattr(country, "flag", None),
            )
        except AttributeError as error:
            raise ValueError("Объект pycountry не содержит обязательные поля страны") from error

    @staticmethod
    def _required_text(name: str, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} должен иметь тип str")
        value = value.strip()
        if not value:
            raise ValueError(f"{name} не может быть пустым")
        return value

    @classmethod
    def _country_code(cls, name: str, value: object, length: int) -> str:
        code = cls._required_text(name, value).upper()
        if len(code) != length or not code.isalpha() or not code.isascii():
            raise ValueError(f"{name} должен содержать {length} латинские буквы")
        return code

    @staticmethod
    def _optional_text(name: str, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{name} должен иметь тип str или None")
        return value.strip() or None


@dataclass
class CountryCoordinates:
    """Название, координаты и границы страны.
    Attributes:
        name: наименование страны, возвращённое Nominatim
        country_code: двухбуквенный код страны по стандарту ISO 3166-1
        latitude: широта центральной точки страны в градусах
        longitude: долгота центральной точки страны в градусах
        bounding_box: объект класса BoundingBox, содержащий прямоугольные границы страны
    """

    name: str
    country_code: str | None
    latitude: float
    longitude: float
    bounding_box: BoundingBox


@dataclass(frozen=True, slots=True)
class AircraftState:
    """Основная информация об одном воздушном судне, полученной от OpenSky.
    Attributes:
        icao24: уникальный 24-битный адрес транспондера воздушного судна в шестнадцатеричном формате
        callsign: позывной воздушного судна
        origin_country: страна, определённая OpenSky по ICAO24-адресу транспондера
        time_position: время последнего обновления позиции в формате UNIX
        last_contact: время последнего контакта в формате UNIX
        longitude: текущая географическая долгота воздушного судна
        latitude: текущая географическая широта воздушного судна
        baro_altitude: барометрическая высота воздушного судна в метрах
        on_ground: находится ли самолёт на земле
        velocity: горизонтальная скорость (м/с)
        true_track: курс (градусы)
        vertical_rate: вертикальная скорость (м/с)
        sensors: ID сенсоров
        geo_altitude: геометрическая высота (м)
        squawk: код ответчика (транспондера)
        spi: специальный сигнал
        position_source: источник позиции

    Methods:
        compare_speed(): сравнивает самолёты по горизонтальной скорости
        compare_altitude(): сравнивает самолёты по высоте
        is_faster_than(): проверяет, быстрее ли текущий самолёт
        is_higher_than(): проверяет, выше ли текущий самолёт

    """

    icao24: str
    callsign: str | None
    origin_country: str
    time_position: int | None
    last_contact: int | None
    longitude: float | None
    latitude: float | None
    baro_altitude: float | None
    on_ground: bool
    velocity: float | None
    true_track: float | None
    vertical_rate: float | None
    sensors: Sequence[int] | None
    geo_altitude: float | None
    squawk: str | None
    spi: bool
    position_source: int | None

    def __post_init__(self) -> None:
        """Нормализовать и проверить значения атрибутов."""

        object.__setattr__(self, "icao24", self._required_text("icao24", self.icao24).lower())
        if len(self.icao24) != 6 or any(symbol not in "0123456789abcdef" for symbol in self.icao24):
            raise ValueError("icao24 должен содержать 6 шестнадцатеричных символов")

        object.__setattr__(self, "origin_country", self._required_text("origin_country", self.origin_country))
        object.__setattr__(self, "callsign", self._optional_text("callsign", self.callsign))
        object.__setattr__(self, "squawk", self._optional_text("squawk", self.squawk))

        self._validate_numeric_attributes()
        self._validate_ranges()
        self._validate_flags_and_sensors()

    def _validate_numeric_attributes(self) -> None:
        """Проверить типы числовых атрибутов."""

        for name in (
            "longitude",
            "latitude",
            "baro_altitude",
            "velocity",
            "true_track",
            "vertical_rate",
            "geo_altitude",
        ):
            self._validate_number(name, getattr(self, name))

        for name in ("time_position", "last_contact", "position_source"):
            self._validate_integer(name, getattr(self, name))

    def _validate_ranges(self) -> None:
        """Проверить допустимые диапазоны числовых значений."""

        if self.longitude is not None and not -180 <= self.longitude <= 180:
            raise ValueError("longitude должен находиться в диапазоне от -180 до 180")
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            raise ValueError("latitude должен находиться в диапазоне от -90 до 90")
        if self.velocity is not None and self.velocity < 0:
            raise ValueError("velocity не может быть отрицательной")
        if self.true_track is not None and not 0 <= self.true_track <= 360:
            raise ValueError("true_track должен находиться в диапазоне от 0 до 360")

    def _validate_flags_and_sensors(self) -> None:
        """Проверить логические признаки и список сенсоров."""

        if not isinstance(self.on_ground, bool):
            raise TypeError("on_ground должен иметь тип bool")
        if not isinstance(self.spi, bool):
            raise TypeError("spi должен иметь тип bool")
        if self.sensors is not None:
            if isinstance(self.sensors, (str, bytes)) or not isinstance(self.sensors, Sequence):
                raise TypeError("sensors должен быть последовательностью целых чисел или None")
            if any(isinstance(sensor, bool) or not isinstance(sensor, int) for sensor in self.sensors):
                raise TypeError("sensors должен быть последовательностью целых чисел или None")
            object.__setattr__(self, "sensors", tuple(self.sensors))

    @property
    def altitude(self) -> float | None:
        """Вернуть геометрическую высоту или барометрическую, если геометрическая неизвестна."""

        return self.geo_altitude if self.geo_altitude is not None else self.baro_altitude

    def compare_speed(self, other: object) -> int:
        """Сравнить скорость двух самолётов и вернуть -1, 0 или 1."""

        aircraft = self._require_aircraft(other)
        if self.velocity is None or aircraft.velocity is None:
            raise ValueError("Нельзя сравнить самолёты без данных о скорости")
        return self._compare_values(self.velocity, aircraft.velocity)

    def compare_altitude(self, other: object) -> int:
        """Сравнить высоту двух самолётов и вернуть -1, 0 или 1."""

        aircraft = self._require_aircraft(other)
        current_altitude = self.altitude
        other_altitude = aircraft.altitude
        if current_altitude is None or other_altitude is None:
            raise ValueError("Нельзя сравнить самолёты без данных о высоте")
        return self._compare_values(current_altitude, other_altitude)

    def is_faster_than(self, other: object) -> bool:
        """Вернуть True, если текущий самолёт быстрее другого."""

        return self.compare_speed(other) > 0

    def is_higher_than(self, other: object) -> bool:
        """Вернуть True, если текущий самолёт находится выше другого."""

        return self.compare_altitude(other) > 0

    def to_dict(self) -> dict[str, object]:
        """Вернуть JSON-совместимое представление воздушного судна."""

        data: dict[str, object] = asdict(self)
        data["sensors"] = list(self.sensors) if self.sensors is not None else None
        return data

    @staticmethod
    def _required_text(name: str, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} должен иметь тип str")
        value = value.strip()
        if not value:
            raise ValueError(f"{name} не может быть пустым")
        return value

    @staticmethod
    def _optional_text(name: str, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{name} должен иметь тип str или None")
        return value.strip() or None

    @staticmethod
    def _validate_number(name: str, value: object) -> None:
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise TypeError(f"{name} должен быть числом или None")

    @staticmethod
    def _validate_integer(name: str, value: object) -> None:
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise TypeError(f"{name} должен иметь тип int или None")
        if isinstance(value, int) and value < 0:
            raise ValueError(f"{name} не может быть отрицательным")

    @staticmethod
    def _require_aircraft(value: object) -> "AircraftState":
        if not isinstance(value, AircraftState):
            raise TypeError("Можно сравнивать только объекты AircraftState")
        return value

    @staticmethod
    def _compare_values(first: float, second: float) -> int:
        return (first > second) - (first < second)
