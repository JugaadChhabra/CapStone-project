from datetime import datetime, timedelta


def get_previous_day_close_date():
        """Calculate the previous trading day date"""
        today = datetime.now()
        
        # If today is Monday (0), go back 3 days to Friday
        if today.weekday() == 0:  # Monday
            target_date = today - timedelta(days=3)
        else:
            target_date = today - timedelta(days=1)
            
        return target_date.strftime("%Y-%m-%d")