import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class BookingBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guest_name: str
    unit_id: str
    check_in_date: datetime.date
    number_of_nights: int


class BookingResponse(BookingBase):
    id: int

    @computed_field
    @property
    def check_out_date(self) -> datetime.date:
        return self.check_in_date + datetime.timedelta(days=self.number_of_nights)


class ExtendStayRequest(BaseModel):
    number_of_nights: int = Field(..., gt=0, description="Desired total number of nights (must be greater than current)")
