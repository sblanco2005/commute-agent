from fastapi import FastAPI, BackgroundTasks
from agent.commute_agent import trigger_commute_agent
from pydantic import BaseModel, model_validator
from typing import Optional

app = FastAPI()

class TriggerBody(BaseModel):
    zone: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    @model_validator(mode="after")
    def check_inputs(self) -> "TriggerBody":
        if not self.zone and (self.lat is None or self.lon is None):
            raise ValueError("Either zone OR both lat and lon must be provided.")
        return self

@app.post("/trigger")
async def trigger_commute(body: TriggerBody, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        trigger_commute_agent,
        location=body.zone or "triggered_from_phone",
        lat=body.lat,
        lon=body.lon
    )
    return {"status": "✅ Commute agent triggered and running in background."}