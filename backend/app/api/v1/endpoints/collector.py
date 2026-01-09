from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.services.collector import collector

router = APIRouter()

@router.post("/stocks", status_code=202)
def update_stock_list_job(background_tasks: BackgroundTasks):
    """
    Trigger background job to update stock list (KOSPI/KOSDAQ).
    """
    background_tasks.add_task(collector.update_stock_list)
    return {"message": "Stock list update job triggered"}

@router.post("/daily", status_code=202)
def collect_daily_candles_job(background_tasks: BackgroundTasks, date: str = None):
    """
    Trigger background job to collect daily candles.
    :param date: YYYYMMDD string. Defaults to today/latest available.
    """
    background_tasks.add_task(collector.fetch_daily_ohlcv, date)
    return {"message": "Daily candle collection job triggered", "target_date": date or "Today"}
