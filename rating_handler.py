"""
Automated Rating Handler for Job Completion
Sends SMS prompts to users, captures ratings, and updates operator metrics.
Implements auto-ban logic for low-performing operators.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from database import DatabaseManager
from rating_calculator import RatingCalculator
from sms_service import SMSService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RatingHandler:
    """Handles automated rating workflows after job completion."""
    
    def __init__(self, db_manager: DatabaseManager, sms_service: SMSService):
        """
        Initialize the rating handler.
        
        Args:
            db_manager: Database manager instance
            sms_service: SMS service instance for sending texts
        """
        self.db = db_manager
        self.sms = sms_service
        self.calculator = RatingCalculator(db_manager)
        self.BAN_THRESHOLD = 3.0  # Average rating below this triggers ban
        self.MIN_TRANSACTIONS = 2  # Minimum transactions before banning
    
    def handle_job_completed(
        self,
        job_id: str,
        user_phone: str,
        operator_phone: str,
        operator_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle job completion and initiate rating workflow.
        
        Args:
            job_id: Unique job identifier
            user_phone: Customer phone number
            operator_phone: Operator's phone number
            operator_id: Operator database ID
            **kwargs: Additional job metadata
            
        Returns:
            Dictionary with workflow status
        """
        try:
            # Validate operator status
            operator = self.db.get_operator(operator_id)
            if not operator:
                logger.error(f"Operator {operator_id} not found")
                return {"status": "error", "message": "Operator not found"}
            
            if operator.get("status") == "Banned":
                logger.info(f"Operator {operator_id} is banned, skipping rating request")
                return {"status": "skipped", "message": "Operator is banned"}
            
            # Record job completion
            self.db.record_job_completion(
                job_id=job_id,
                operator_id=operator_id,
                user_phone=user_phone,
                operator_phone=operator_phone,
                completion_time=datetime.now()
            )
            
            # Create rating request
            request_id = self.db.create_rating_request(
                job_id=job_id,
                user_phone=user_phone,
                operator_id=operator_id,
                status="pending"
            )
            
            # Send SMS prompt
            message = "Reply 1 to 5 to rate this operator"
            success = self.sms.send_sms(
                to_number=user_phone,
                message=message,
                metadata={"request_id": request_id, "job_id": job_id}
            )
            
            if success:
                logger.info(f"Rating prompt sent to {user_phone} for job {job_id}")
                return {
                    "status": "success",
                    "message": "Rating prompt sent",
                    "request_id": request_id
                }
            else:
                logger.error(f"Failed to send rating prompt to {user_phone}")
                return {"status": "error", "message": "SMS send failed"}
                
        except Exception as e:
            logger.error(f"Error in handle_job_completed: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def process_rating_reply(
        self,
        request_id: str,
        rating: int,
        operator_id: str
    ) -> Dict[str, Any]:
        """
        Process inbound rating reply and update metrics.
        
        Args:
            request_id: Rating request ID
            rating: Integer rating (1-5)
            operator_id: Operator ID being rated
            
        Returns:
            Dictionary with processing result
        """
        try:
            # Validate rating
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                logger.warning(f"Invalid rating received: {rating}")
                return {"status": "error", "message": "Rating must be 1-5"}
            
            # Record rating
            self.db.record_rating(
                request_id=request_id,
                operator_id=operator_id,
                rating=rating,
                timestamp=datetime.now()
            )
            
            # Mark request as completed
            self.db.update_rating_request_status(request_id, "completed")
            
            # Calculate new average
            new_average = self.calculator.calculate_average_rating(operator_id)
            transaction_count = self.calculator.get_transaction_count(operator_id)
            
            logger.info(
                f"Rating recorded: Operator {operator_id}, "
                f"Rating {rating}, New Average: {new_average:.2f}, "
                f"Transactions: {transaction_count}"
            )
            
            # Check ban conditions
            ban_result = self._check_and_apply_ban(
                operator_id=operator_id,
                average_rating=new_average,
                transaction_count=transaction_count
            )
            
            return {
                "status": "success",
                "rating": rating,
                "new_average": round(new_average, 2),
                "transaction_count": transaction_count,
                "ban_applied": ban_result["banned"],
                "ban_reason": ban_result["reason"]
            }
            
        except Exception as e:
            logger.error(f"Error processing rating reply: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def _check_and_apply_ban(
        self,
        operator_id: str,
        average_rating: float,
        transaction_count: int
    ) -> Dict[str, Any]:
        """
        Check if operator should be banned and apply ban if conditions met.
        
        Ban Conditions:
        - Average rating < 3.0 stars
        - More than 2 completed transactions
        
        Args:
            operator_id: Operator ID to check
            average_rating: Current average rating
            transaction_count: Total completed transactions
            
        Returns:
            Dictionary with ban decision and reason
        """
        banned = False
        reason = None
        
        if average_rating < self.BAN_THRESHOLD and transaction_count > self.MIN_TRANSACTIONS:
            try:
                # Update operator status to Banned
                self.db.update_operator_status(operator_id, "Banned")
                
                # Block operator from matching queue
                self.db.block_from_queue(operator_id)
                
                banned = True
                reason = (
                    f"Average rating {average_rating:.2f} < {self.BAN_THRESHOLD} "
                    f"across {transaction_count} transactions"
                )
                
                logger.warning(
                    f"Operator {operator_id} BANNED: {reason}"
                )
                
                # Optional: Send notification to operator
                self._notify_operator_ban(operator_id, reason)
                
            except Exception as e:
                logger.error(f"Error applying ban: {str(e)}", exc_info=True)
                reason = f"Ban error: {str(e)}"
        
        return {
            "banned": banned,
            "reason": reason
        }
    
    def _notify_operator_ban(self, operator_id: str, reason: str) -> None:
        """
        Notify operator of their ban status.
        
        Args:
            operator_id: Operator ID
            reason: Ban reason
        """
        try:
            operator = self.db.get_operator(operator_id)
            if operator and operator.get("phone_number"):
                message = (
                    f"Your account has been suspended due to low ratings. "
                    f"Reason: {reason} Contact support for details."
                )
                self.sms.send_sms(operator["phone_number"], message)
        except Exception as e:
            logger.error(f"Error notifying operator of ban: {str(e)}")
    
    def get_operator_stats(self, operator_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive rating statistics for an operator.
        
        Args:
            operator_id: Operator ID
            
        Returns:
            Dictionary with operator statistics or None
        """
        try:
            return self.calculator.get_operator_statistics(operator_id)
        except Exception as e:
            logger.error(f"Error retrieving operator stats: {str(e)}")
            return None


if __name__ == "__main__":
    # Example usage (requires proper initialization)
    print("Rating handler module - for use in your application")
