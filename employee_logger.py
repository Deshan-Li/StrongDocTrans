"""
Employee Translation Logger
Handles CSV logging of translation activities with weekly file rotation
Author: Claude Code
"""

import csv
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class EmployeeTranslationLogger:
    """Logger for employee translation activities with weekly file rotation"""

    def __init__(self, logs_dir: str = "./log"):
        """
        Initialize the logger

        Args:
            logs_dir: Directory to store log files
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

    def _get_weekly_filename(self) -> str:
        """
        Generate weekly filename in format: YYYY-MM-DD_to_YYYY-MM-DD.csv
        Week starts from Monday
        """
        today = datetime.now()
        # Find Monday of current week
        monday = today - timedelta(days=today.weekday())
        # Find Sunday of current week
        sunday = monday + timedelta(days=6)

        monday_str = monday.strftime("%Y-%m-%d")
        sunday_str = sunday.strftime("%Y-%m-%d")

        return f"{monday_str}_to_{sunday_str}.csv"

    def _ensure_csv_header(self, filepath: Path) -> None:
        """
        Ensure CSV file has proper header

        Args:
            filepath: Path to CSV file
        """
        if not filepath.exists():
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["工号", "姓名", "时间", "文件名"])

    def log_translation(self, employee_id: str, employee_name: str, filename: str) -> bool:
        """
        Log a successful translation

        Args:
            employee_id: Employee ID (工号)
            employee_name: Employee name (姓名)
            filename: Name of translated file

        Returns:
            True if logging successful, False otherwise
        """
        try:
            if not employee_id or not employee_name:
                return False

            weekly_filename = self._get_weekly_filename()
            filepath = self.logs_dir / weekly_filename

            # Ensure file exists with header
            self._ensure_csv_header(filepath)

            # Add new log entry
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([employee_id, employee_name, current_time, filename])

            return True

        except Exception as e:
            # Log error but don't interrupt translation workflow
            print(f"Error logging translation activity: {e}")
            return False

    def get_log_files(self) -> list:
        """
        Get list of all log files

        Returns:
            List of log file paths sorted by date (newest first)
        """
        try:
            csv_files = list(self.logs_dir.glob("*.csv"))
            return sorted(csv_files, reverse=True)
        except Exception:
            return []


# Global logger instance
employee_logger = EmployeeTranslationLogger()