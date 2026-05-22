"""
Job Completion Trigger - Integration point for job completion events.
Provides convenient functions to trigger the rating workflow.
"""

import logging
from typing import Dict, Any, Optional
from database import SQLiteDatabaseManager
from rating_handler import RatingHandler
from sms_service import get_sms_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global singleton instances
_db_manager: Optional[SQLiteDatabaseManager] = None
_rating_handler: Optional[RatingHandler] = None


def initialize(db_path: str = "nbcco_ratings.db", use_mock_sms: bool = False) -> None:
    """
    Initialize the job completion trigger system.
    Call this once at application startup.
    
    Args:
        db_path: Path to SQLite database
        use_mock_sms: Use mock SMS service for testing
    """
    global _db_manager, _rating_handler
    
    try:
        _db_manager = SQLiteDatabaseManager(db_path)
        sms_service = get_sms_service(use_mock=use_mock_sms)
        _rating_handler = RatingHandler(_db_manager, sms_service)
        
        logger.info("Job completion trigger system initialized")
    except Exception as e:
        logger.error(f"Error initializing trigger system: {str(e)}", exc_info=True)
        raise


def trigger_job_completed(
    job_id: str,
    user_phone: str,
    operator_phone: str,
    operator_id: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Trigger rating workflow for a completed job.
    Call this immediately after a job is completed.
    
    Args:
        job_id: Unique job identifier
        user_phone: Customer phone number
        operator_phone: Operator's phone number
        operator_id: Operator database ID
        **kwargs: Additional job metadata
        
    Returns:
        Dictionary with workflow status
        
    Example:
        from job_completion_trigger import initialize, trigger_job_completed
        
        # At application startup
        initialize()
        
        # When job completes
        result = trigger_job_completed(
            job_id="JOB-12345",
            user_phone="+1234567890",
            operator_phone="+0987654321",
            operator_id="OP-001"
        )
        print(result)
    """
    if _rating_handler is None:
        logger.error("Trigger system not initialized. Call initialize() first.")
        return {"status": "error", "message": "System not initialized"}
    
    try:
        return _rating_handler.handle_job_completed(
            job_id=job_id,
            user_phone=user_phone,
            operator_phone=operator_phone,
            operator_id=operator_id,
            **kwargs
        )
    except Exception as e:
        logger.error(f"Error triggering job completion: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


def get_operator_stats(operator_id: str) -> Optional[Dict[str, Any]]:
    """
    Get statistics for an operator.
    
    Args:
        operator_id: Operator ID
        
    Returns:
        Dictionary with statistics or None
    """
    if _rating_handler is None:
        logger.error("Trigger system not initialized")
        return None
    
    return _rating_handler.get_operator_stats(operator_id)


def get_rating_handler() -> Optional[RatingHandler]:
    """
    Get the rating handler instance (advanced usage).
    
    Returns:
        RatingHandler instance or None
    """
    return _rating_handler


if __name__ == "__main__":
    print("Job completion trigger module - for use in your application")
    print("")
    print("Usage:")
    print("  from job_completion_trigger import initialize, trigger_job_completed")
    print("  initialize()")
    print("  trigger_job_completed(job_id='JOB-1', user_phone='+1111111111', ...")
