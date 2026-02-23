import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agent.commute_agent import trigger_commute_agent
from agent.auto_trigger import morning_bus_check, afternoon_rail_check
from pydantic import BaseModel, model_validator
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scheduler instance
scheduler = AsyncIOScheduler()
auto_trigger_enabled = False  # Will be auto-enabled at 5:45 AM, disabled at 6:30 AM
afternoon_trigger_enabled = False  # Will be auto-enabled at 1:30 PM, disabled at 1:50 PM

def enable_auto_trigger_job():
    """Job to automatically enable morning auto-trigger at start time"""
    global auto_trigger_enabled
    auto_trigger_enabled = True
    logger.info("⏰ Morning auto-trigger automatically ENABLED at scheduled time (5:45 AM)")

def disable_auto_trigger_job():
    """Job to automatically disable morning auto-trigger at end time"""
    global auto_trigger_enabled
    auto_trigger_enabled = False
    logger.info("⏰ Morning auto-trigger automatically DISABLED at scheduled time (6:30 AM)")

def enable_afternoon_trigger_job():
    """Job to automatically enable afternoon rail alert at start time"""
    global afternoon_trigger_enabled
    afternoon_trigger_enabled = True
    logger.info("⏰ Afternoon rail alert automatically ENABLED at scheduled time (1:30 PM)")

def disable_afternoon_trigger_job():
    """Job to automatically disable afternoon rail alert at end time"""
    global afternoon_trigger_enabled
    afternoon_trigger_enabled = False
    logger.info("⏰ Afternoon rail alert automatically DISABLED at scheduled time (1:50 PM)")

async def morning_bus_check_wrapper():
    """Wrapper that passes the auto_trigger_enabled flag to morning_bus_check"""
    await morning_bus_check(auto_trigger_enabled=auto_trigger_enabled)

async def afternoon_rail_check_wrapper():
    """Wrapper that passes the afternoon_trigger_enabled flag to afternoon_rail_check"""
    await afternoon_rail_check(auto_trigger_enabled=afternoon_trigger_enabled)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Start the scheduler
    logger.info("🚀 Starting auto-trigger scheduler (morning bus + afternoon rail)")

    # ===== MORNING BUS ALERTS (5:45 AM - 6:30 AM) =====

    # Auto-enable at 5:45 AM
    scheduler.add_job(
        enable_auto_trigger_job,
        'cron',
        hour=5,
        minute=45,
        id='auto_enable_morning',
        name='Auto-Enable Morning Bus Alerts'
    )

    # Auto-disable at 6:30 AM
    scheduler.add_job(
        disable_auto_trigger_job,
        'cron',
        hour=6,
        minute=30,
        id='auto_disable_morning',
        name='Auto-Disable Morning Bus Alerts'
    )

    # Run morning bus check every 5 minutes during morning hours (5:45 AM - 6:30 AM)
    scheduler.add_job(
        morning_bus_check_wrapper,
        'cron',
        hour='5-6',
        minute='*/5',
        id='morning_bus_check',
        name='Morning Bus Alert Check'
    )

    # ===== AFTERNOON RAIL ALERTS (1:30 PM - 1:50 PM) =====

    # Auto-enable at 1:30 PM
    scheduler.add_job(
        enable_afternoon_trigger_job,
        'cron',
        hour=13,
        minute=30,
        id='auto_enable_afternoon',
        name='Auto-Enable Afternoon Rail Alerts'
    )

    # Auto-disable at 1:50 PM
    scheduler.add_job(
        disable_afternoon_trigger_job,
        'cron',
        hour=13,
        minute=50,
        id='auto_disable_afternoon',
        name='Auto-Disable Afternoon Rail Alerts'
    )

    # Run afternoon rail check every 5 minutes during afternoon window (1:30 PM - 1:50 PM)
    scheduler.add_job(
        afternoon_rail_check_wrapper,
        'cron',
        hour=13,
        minute='30,35,40,45,50',
        id='afternoon_rail_check',
        name='Afternoon Rail Delay Check'
    )

    scheduler.start()
    logger.info("✅ Scheduler started:")
    logger.info("   - Morning bus alerts: 5:45-6:30 AM (every 5 min)")
    logger.info("   - Afternoon rail alerts: 1:30-1:50 PM (every 5 min)")

    yield

    # Shutdown: Stop the scheduler
    logger.info("🛑 Stopping scheduler")
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

class TriggerBody(BaseModel):
    zone: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    @model_validator(mode="after")
    def check_inputs(self) -> "TriggerBody":
        if not self.zone and (self.lat is None or self.lon is 
                              None):
            raise ValueError("Either zone OR both lat and lon must be provided.")
        return self

async def _safe_trigger_commute_agent(location, lat, lon):
    """Wrapper to catch and log errors from background task"""
    try:
        await trigger_commute_agent(location=location, lat=lat, lon=lon)
    except Exception as e:
        logger.error(f"❌ Background task failed: {e}", exc_info=True)

@app.post("/trigger")
async def trigger_commute(body: TriggerBody, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        _safe_trigger_commute_agent,
        location=body.zone or "triggered_from_phone",
        lat=body.lat,
        lon=body.lon
    )
    return {"status": "✅ Commute agent triggered and running in background."}

@app.post("/auto-trigger/enable")
async def enable_auto_trigger():
    """Enable automatic morning bus notifications"""
    global auto_trigger_enabled
    auto_trigger_enabled = True
    logger.info("✅ Auto-trigger enabled")
    return {"status": "enabled", "message": "Morning bus alerts are now active"}

@app.post("/auto-trigger/disable")
async def disable_auto_trigger():
    """Disable automatic morning bus notifications"""
    global auto_trigger_enabled
    auto_trigger_enabled = False
    logger.info("🛑 Auto-trigger disabled")
    return {"status": "disabled", "message": "Morning bus alerts are now paused"}

@app.get("/auto-trigger/status")
async def auto_trigger_status():
    """Check if auto-trigger is enabled"""
    jobs = scheduler.get_jobs()
    return {
        "enabled": auto_trigger_enabled,
        "scheduler_running": scheduler.running,
        "scheduled_jobs": [{"id": job.id, "name": job.name, "next_run": str(job.next_run_time)} for job in jobs]
    }

@app.post("/auto-trigger/test")
async def test_auto_trigger():
    """Manually trigger the morning bus check (for testing)"""
    logger.info("🧪 Manual test of morning bus check triggered")
    try:
        await morning_bus_check()
        return {"status": "success", "message": "Morning bus check executed"}
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.post("/afternoon-trigger/test")
async def test_afternoon_trigger():
    """Manually trigger the afternoon rail delay check (for testing)"""
    logger.info("🧪 Manual test of afternoon rail check triggered")
    try:
        await afternoon_rail_check()
        return {"status": "success", "message": "Afternoon rail check executed"}
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.post("/afternoon-trigger/enable")
async def enable_afternoon_trigger():
    """Enable automatic afternoon rail delay notifications"""
    global afternoon_trigger_enabled
    afternoon_trigger_enabled = True
    logger.info("✅ Afternoon rail alert enabled")
    return {"status": "enabled", "message": "Afternoon rail alerts are now active"}

@app.post("/afternoon-trigger/disable")
async def disable_afternoon_trigger():
    """Disable automatic afternoon rail delay notifications"""
    global afternoon_trigger_enabled
    afternoon_trigger_enabled = False
    logger.info("🛑 Afternoon rail alert disabled")
    return {"status": "disabled", "message": "Afternoon rail alerts are now paused"}

@app.get("/afternoon-trigger/status")
async def afternoon_trigger_status():
    """Check if afternoon rail alert is enabled"""
    return {
        "enabled": afternoon_trigger_enabled,
        "window": "1:30 PM - 1:50 PM",
        "checks_for": "Rail delays from Penn Station to Newark affecting 3:40 PM commute"
    }