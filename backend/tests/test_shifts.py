import pytest
from pydantic import ValidationError

from app.core.errors import DomainError
from app.modules.specialists.account_router import generate_slots
from app.modules.specialists.account_schemas import ShiftBatch


def batch(**changes):
    return ShiftBatch.model_validate(
        dict(
            date_from="2030-01-01",
            date_to="2030-01-01",
            weekdays=list(range(7)),
            start="09:00",
            end="12:00",
            **changes,
        )
    )


def test_dst_and_limits():
    for day in ["2030-03-31", "2030-10-27"]:
        data = ShiftBatch(
            date_from=day, date_to=day, weekdays=list(range(7)), start="01:00", end="04:00"
        )
        with pytest.raises(DomainError):
            generate_slots(data, "Europe/Berlin")
    with pytest.raises(ValidationError):
        batch(breaks=[dict(start="10:00", end="11:00"), dict(start="10:30", end="11:30")])
    with pytest.raises(ValidationError):
        ShiftBatch(
            date_from="2030-01-01", date_to="2030-04-30", weekdays=[0], start="09:00", end="12:00"
        )
    assert len(generate_slots(batch(breaks=[dict(start="10:00", end="11:00")]), "UTC")) == 4
