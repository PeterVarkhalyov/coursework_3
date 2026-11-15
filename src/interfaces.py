"""Структурные контракты между слоями приложения."""

from typing import Protocol

from src.models import AircraftState, CountryCoordinates


class CountryProvider(Protocol):
    """Контракт поставщика координат и границ страны."""

    def get_data(self, country_name: str) -> CountryCoordinates:
        """Получить координаты и границы страны по её названию."""


class AircraftProvider(Protocol):
    """Контракт поставщика состояний воздушных судов."""

    def get_data(self) -> tuple[int, list[AircraftState]]:
        """Получить время сервера и все наблюдаемые воздушные суда."""
