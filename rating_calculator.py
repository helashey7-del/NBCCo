"""
Rating Calculator Module
Handles moving average calculations, statistics, and performance analytics.
"""

import logging
from typing import Dict, List, Optional, Any
from statistics import mean, stdev
from database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RatingCalculator:
    """Calculate and manage operator rating statistics."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize rating calculator.
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
    
    def calculate_average_rating(self, operator_id: str) -> float:
        """
        Calculate moving average rating for an operator.
        
        Args:
            operator_id: Operator ID
            
        Returns:
            Average rating as float, or 0.0 if no ratings exist
        """
        try:
            ratings = self.db.get_operator_ratings(operator_id)
            
            if not ratings:
                return 0.0
            
            rating_values = [r["rating"] for r in ratings]
            average = mean(rating_values)
            
            # Update cache in database
            self.db.update_operator_average_rating(operator_id, average)
            
            return average
            
        except Exception as e:
            logger.error(f"Error calculating average rating: {str(e)}")
            return 0.0
    
    def get_transaction_count(self, operator_id: str) -> int:
        """
        Get total number of completed transactions for an operator.
        
        Args:
            operator_id: Operator ID
            
        Returns:
            Number of completed transactions
        """
        try:
            ratings = self.db.get_operator_ratings(operator_id)
            return len(ratings)
        except Exception as e:
            logger.error(f"Error getting transaction count: {str(e)}")
            return 0
    
    def get_operator_statistics(self, operator_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive statistics for an operator.
        
        Args:
            operator_id: Operator ID
            
        Returns:
            Dictionary with statistics or None if operator not found
        """
        try:
            ratings = self.db.get_operator_ratings(operator_id)
            operator = self.db.get_operator(operator_id)
            
            if not operator:
                return None
            
            if not ratings:
                return {
                    "operator_id": operator_id,
                    "total_ratings": 0,
                    "average_rating": 0.0,
                    "min_rating": None,
                    "max_rating": None,
                    "std_deviation": None,
                    "status": operator.get("status"),
                    "queue_blocked": operator.get("queue_blocked", False)
                }
            
            rating_values = [r["rating"] for r in ratings]
            
            stats = {
                "operator_id": operator_id,
                "operator_name": operator.get("name"),
                "phone_number": operator.get("phone_number"),
                "total_ratings": len(rating_values),
                "average_rating": round(mean(rating_values), 2),
                "min_rating": min(rating_values),
                "max_rating": max(rating_values),
                "status": operator.get("status"),
                "queue_blocked": operator.get("queue_blocked", False),
                "created_at": operator.get("created_at"),
                "last_updated": operator.get("last_updated")
            }
            
            # Add standard deviation if more than 1 rating
            if len(rating_values) > 1:
                stats["std_deviation"] = round(stdev(rating_values), 2)
            else:
                stats["std_deviation"] = None
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting operator statistics: {str(e)}")
            return None
    
    def get_top_operators(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top-rated operators.
        
        Args:
            limit: Maximum number of operators to return
            
        Returns:
            List of top operators sorted by rating
        """
        try:
            operators = self.db.get_all_operators()
            
            # Calculate stats for each active operator
            operator_stats = []
            for operator in operators:
                if operator.get("status") != "Banned":
                    stats = self.get_operator_statistics(operator["id"])
                    if stats and stats["total_ratings"] > 0:
                        operator_stats.append(stats)
            
            # Sort by average rating (descending)
            operator_stats.sort(key=lambda x: x["average_rating"], reverse=True)
            
            return operator_stats[:limit]
            
        except Exception as e:
            logger.error(f"Error getting top operators: {str(e)}")
            return []
    
    def get_at_risk_operators(self, threshold: float = 3.0) -> List[Dict[str, Any]]:
        """
        Get operators at risk of being banned (average < threshold).
        
        Args:
            threshold: Rating threshold for risk assessment
            
        Returns:
            List of at-risk operators
        """
        try:
            operators = self.db.get_all_operators()
            at_risk = []
            
            for operator in operators:
                if operator.get("status") != "Banned":
                    stats = self.get_operator_statistics(operator["id"])
                    if stats and stats["total_ratings"] > 2:
                        if stats["average_rating"] < threshold:
                            at_risk.append(stats)
            
            # Sort by rating (ascending)
            at_risk.sort(key=lambda x: x["average_rating"])
            
            return at_risk
            
        except Exception as e:
            logger.error(f"Error getting at-risk operators: {str(e)}")
            return []
    
    def get_rating_distribution(self, operator_id: str) -> Dict[int, int]:
        """
        Get distribution of ratings (1-5) for an operator.
        
        Args:
            operator_id: Operator ID
            
        Returns:
            Dictionary with rating counts: {1: count, 2: count, ...}
        """
        try:
            ratings = self.db.get_operator_ratings(operator_id)
            distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            
            for rating in ratings:
                r_value = rating["rating"]
                if r_value in distribution:
                    distribution[r_value] += 1
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error getting rating distribution: {str(e)}")
            return {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}


if __name__ == "__main__":
    print("Rating calculator module - for use in your application")
