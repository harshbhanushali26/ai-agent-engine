import os
import re
import sys
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta





# ═══════════════════════════════════════════════════════════════════════════════
# SESSION MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class SessionManager:
    """
    Docstring for SessionManager:
    - In-Memory session details till session ends.
    - Add each session details to file(session/query logging) persistence
    - Old file cleanup 
    - Summarizes 1 week session/query edtails 
    """


    def __init__(self, log_dir: str = "runtime/telemetry", retention_days: int = 14):
        """
        Initialize SessionManager with persistence and cleanup.
        
        Args:
            log_dir: Directory to store log files (default: "logs")
            retention_days: Number of days to keep raw logs (default: 14)
        """
        self.session_id = datetime.now().isoformat()
        self._session_queries = []
        self.log_dir = Path(log_dir)
        self.retention_days = retention_days

        self._ensure_log_directory()

        self._cleanup_old_logs()


    def log_details(self,  query: str, cache_hit: bool, api_calls: int, response_time_ms: float):
        """
        Log query details to memory and persist to disk.
        
        Args:
            query: The query text
            cache_hit: Whether this was a cache hit
            api_calls: Number of API calls made (0 if cached)
            response_time_ms: Response time in milliseconds
        """

        session_query = {
            "session_id": self.session_id,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "cache_hit": cache_hit,
            "api_calls": api_calls,
            "response_time_ms": response_time_ms
        }

        self._session_queries.append(session_query)

        self._write_to_log(session_query)


    # current session summary 
    def get_session_summary(self):
        """
        Get summary statistics for current session.
        
        Returns:
            Dictionary containing session statistics
        """

        total_queries = len(self._session_queries)
        hits = sum(1 for q in self._session_queries if q["cache_hit"])

        return{
            "session_id": self.session_id,
            "total_queries": total_queries,
            "cache_hits": hits,
            "cache_hit_rate": hits / total_queries if total_queries > 0 else 0,
            "total_api_calls": sum(q["api_calls"] for q in self._session_queries),
            "avg_response_time_ms": (
                sum(q["response_time_ms"] for q in self._session_queries) / total_queries
                if total_queries > 0 else 0
            )
        }


    def save_session_summary(self):
        """
        Save current session summary to daily summary file.
        Called on agent shutdown.
        """
        if not self._session_queries:
            return

        summary = self.get_session_summary()
        self._update_daily_summary(summary)


    def _ensure_log_directory(self):
        """Create log directory if it doesn't exist."""

        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Warning: Could not create log directory: {e}", file=sys.stderr)


    def _get_todays_log_path(self) -> Path:
        """Get path to today's log file."""

        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"agent_{today}.jsonl"


    def _write_to_log(self, entry: Dict):
        """
        Append entry to today's log file.
        
        Args:
            entry: Dictionary containing query details
        """
        try:
            log_path = self._get_todays_log_path()
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except (IOError, OSError) as e:
            print(f"Warning: Could not write to log file: {e}", file=sys.stderr)


    def _get_summary_path(self) -> Path:
        """Get path to daily summary file."""
        return self.log_dir / "summary.json"


    def _load_daily_summary(self) -> Dict:
        """
        Load existing daily summary file.
        
        Returns:
            Dictionary of daily summaries, or empty dict if file doesn't exist
        """
        summary_path = self._get_summary_path()
        
        if not summary_path.exists():
            return {}
        
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load summary file: {e}", file=sys.stderr)
            return {}


    def _update_daily_summary(self, session_summary: Dict):
        """
        Update daily summary with current session data.
        
        Args:
            session_summary: Summary statistics for current session
        """
        try:
            all_summaries = self._load_daily_summary()

            today = datetime.now().strftime("%Y-%m-%d")

            if today not in all_summaries:
                all_summaries[today] = {
                    "sessions": [],
                    "daily_total": {
                        "queries": 0,
                        "cache_hits": 0,
                        "api_calls": 0,
                        "avg_response_time_ms": 0
                    }
                }

            all_summaries[today]["sessions"].append(session_summary)

            sessions = all_summaries[today]["sessions"]
            total_queries = sum(s["total_queries"] for s in sessions)
            total_cache_hits = sum(s["cache_hits"] for s in sessions)
            total_api_calls = sum(s["total_api_calls"] for s in sessions)

            # Weighted average of response times
            total_response_time = sum(
                s["avg_response_time_ms"] * s["total_queries"] 
                for s in sessions
            )

            all_summaries[today]["daily_total"] = {
                "queries": total_queries,
                "cache_hits": total_cache_hits,
                "cache_hit_rate": total_cache_hits / total_queries if total_queries > 0 else 0,
                "api_calls": total_api_calls,
                "avg_response_time_ms": total_response_time / total_queries if total_queries > 0 else 0
            }

            summary_path = self._get_summary_path()
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(all_summaries, f, indent=2)

        except (IOError, OSError) as e:
            print(f"Warning: Could not update summary file: {e}", file=sys.stderr)


    def _get_log_files(self) -> List[Path]:
        """Get list of all agent log files."""
        try:
            return sorted(self.log_dir.glob("agent_*.jsonl"))
        except OSError:
            return []


    def _parse_date_from_filename(self, filepath: Path) -> Optional[datetime]:
        """Extract date from log filename."""
        try:
            filename = filepath.stem
            date_str = filename.replace("agent_", "")
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, AttributeError):
            return None


    def _cleanup_old_logs(self):
        """
        Delete log files older than retention_days.
        Runs on startup.
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)

            for log_file in self._get_log_files():
                file_date = self._parse_date_from_filename(log_file)

                if file_date and file_date < cutoff_date:
                    try:
                        log_file.unlink()
                        print(f"Deleted old log: {log_file.name}")
                    except OSError as e:
                        print(f"Warning: Could not delete {log_file.name}: {e}", file=sys.stderr)

        except Exception as e:
            print(f"Warning: Cleanup failed: {e}", file=sys.stderr)


    def print_session_summary(self):
        """Print formatted session summary to console."""
        summary = self.get_session_summary()

        print("\n" + "="*50)
        print("SESSION SUMMARY")
        print("="*50)
        print(f"Session ID: {summary['session_id']}")
        print(f"Total Queries: {summary['total_queries']}")
        print(f"Cache Hits: {summary['cache_hits']} ({summary['cache_hit_rate']:.1%})")
        print(f"API Calls Used: {summary['total_api_calls']}")
        print(f"Avg Response Time: {summary['avg_response_time_ms']:.0f}ms")
        print("="*50 + "\n")



# ═══════════════════════════════════════════════════════════════════════════════
# HYBRID-CACHE (IN-MEMORY + FILE)
# ═══════════════════════════════════════════════════════════════════════════════


class Cache:
    """
    Hybrid in-memory + persistent cache.
    
    - Fast lookups from in-memory dict
    - Automatic persistence to disk
    - Loads cache on initialization
    - Saves cache on shutdown (manual call)
    - FIFO eviction when max_entries reached
    """

    def __init__(self, max_entries: int, cache_file: str):
        self._cache = {}
        self._max_entries = max_entries
        self._cache_file = cache_file

        # Load existing cache from disk
        self._load()


    def _hash_key(self, raw: str) -> str:
        """
        Generate normalized hash key from raw query string.
        
        Normalization:
        - Strips whitespace
        - Converts to lowercase
        - Collapses multiple spaces
        - Removes spaces around operators (+, -, *, /, =, %, ^, **)
        - Normalizes "mod" keyword
        
        Args:
            raw: Raw query string
            
        Returns:
            16-character hash
        """
        normalized = raw.strip()

        # removed bcz of making every query lower case 
        # normalized = raw.strip().lower()

        # Collapse multiple spaces to single space
        normalized = re.sub(r's\+', ' ', normalized)

        # Remove spaces around single-char operators
        normalized = re.sub(r'\s*([+\-*/=%^])\s*', r'\1', normalized)

        # Handle ** (power operator)
        normalized = re.sub(r'\s*\*\*\s*', '**', normalized)

        # Handle "mod" keyword
        normalized = re.sub(r'\s+mod\s+', 'mod', normalized)

        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


    def get(self, raw_key: str):
        """
        Returns cached value if hit, else None
        """
        key = self._hash_key(raw_key)
        return self._cache.get(key)


    def set(self, raw_key: str, value):
        """
        Cache value ONLY if value is not None
        """
        if value is None:
            return  # None strictly represents cache miss

        # Skip dynamic queries (weather, etc.)
        if self._should_skip_caching(raw_key):
            return

        key = self._hash_key(raw_key)

        # Safety cap to avoid unbounded growth
        if len(self._cache) >= self._max_entries:
            # Remove oldest entry (FIFO eviction)
            self._cache.pop(next(iter(self._cache)))

        self._cache[key] = value


    # def _should_skip_caching(self, query: str) -> bool:
    #     """Check if query should skip caching (dynamic data)."""
    #     query_lower = query.lower()

    #     # Skip weather queries
    #     if 'weather' in query_lower:
    #         return True

    #     # Skip stock/crypto queries (if you add those later)
    #     if any(word in query_lower for word in ['stock', 'price', 'ticker']):
    #         return True
        
    #     # Skip "current" queries (likely dynamic)
    #     if 'current' in query_lower and any(word in query_lower for word in ['price', 'temperature', 'status']):
    #         return True
        
    #     return False


    def _should_skip_caching(self, query: str) -> bool:
        """
        Check if query should skip caching (dynamic data).
        
        Skip if:
        - Weather queries (always dynamic)
        - Datetime queries (changes daily/hourly)
        - Web search queries (external data, can change)
        - Stock/price queries (frequently updated)
        """
        query_lower = query.lower()
        
        # Skip weather queries
        if 'weather' in query_lower or 'temperature' in query_lower:
            return True
        
        # Skip datetime queries (dynamic by nature)
        datetime_indicators = [
            'today', 'tomorrow', 'yesterday',
            'what day is', 'what time is', 'current date', 'current time',
            'what date is', 'days from today', 'days before today',
            'next monday', 'next week'
        ]
        if any(indicator in query_lower for indicator in datetime_indicators):
            return True
        
        # Skip web search queries (external data, can change)
        web_search_indicators = [
            'who is', 'what is', 'where is', 'when was', 'why is', 'how does',
            'search for', 'find', 'look up',
            'latest', 'recent', 'current', 'news about',
            'tell me about', 'information about'
        ]
        if any(indicator in query_lower for indicator in web_search_indicators):
            return True
        
        # Skip stock/crypto/price queries
        if any(word in query_lower for word in ['stock', 'price', 'ticker', 'crypto', 'bitcoin']):
            return True
        
        return False


    def clear(self):
        """Clear all cached entries (in-memory only)."""
        self._cache.clear()


    def size(self) -> int:
        return len(self._cache)


    # persistent cache
    def _load(self):
        """
        Load cache from disk on startup.
        
        - Creates empty cache if file doesn't exist
        - Handles corrupted files gracefully
        - Logs errors to stderr
        """

        try:
            file_path = Path(self._cache_file)

            if not file_path.exists():
                return  # No cache file yet, start empty

            with open (file_path, 'r') as f:
                data = json.load(f)

            if data and isinstance(data, dict):
                self._cache = data

        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load cache from {self._cache_file}: {e}", file=sys.stderr)
            self._cache = {}    # Start fresh if load fails


    def save(self):
        """
        Save cache to disk.
        
        - Creates parent directory if needed
        - Handles write errors gracefully
        - Logs errors to stderr
        """
        try:
            file_path = Path(self._cache_file)

            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open (file_path, 'w') as f:
                json.dump(self._cache, f, indent=2)

        except (IOError, OSError) as e:
            print(f"Warning: Could not save cache to {self._cache_file}: {e}", file=sys.stderr)


