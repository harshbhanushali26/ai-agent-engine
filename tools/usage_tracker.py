from app.config import MAX_CONTEXT_TOKENS, SAFE_LIMIT, WARNING_LIMIT, MODEL_NAME
from datetime import date,datetime, timedelta
import json
from pathlib import Path


USAGE_DIR = Path("runtime/usage")
USAGE_DIR.mkdir(exist_ok=True)

RETENTION_DAYS = 14  # change to 30 if needed

def track_cost(usage):
    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
    else:
        prompt_tokens = getattr(usage, "prompt_tokens", 0)
        completion_tokens = getattr(usage, "completion_tokens", 0)
        total_tokens = getattr(usage, "total_tokens", 0)
    
    token_utilization_ratio = total_tokens / MAX_CONTEXT_TOKENS if MAX_CONTEXT_TOKENS > 0 else 0.0
    budget_state = ""
    
    if token_utilization_ratio < SAFE_LIMIT:
        budget_state = "safe"
    elif token_utilization_ratio <  WARNING_LIMIT:
        budget_state = "warning"
    else:
        budget_state = "danger"

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "token_utilization_ratio": token_utilization_ratio,
        "budget_state": budget_state
    }    


def aggregate_costs(*cost_dicts):
    prompt_tokens = sum(c["prompt_tokens"] for c in cost_dicts)
    completion_tokens = sum(c["completion_tokens"] for c in cost_dicts)
    total_tokens = sum(c["total_tokens"] for c in cost_dicts)

    token_utilization_ratio = (
        total_tokens / MAX_CONTEXT_TOKENS
        if MAX_CONTEXT_TOKENS > 0
        else 0.0
    )

    if token_utilization_ratio < SAFE_LIMIT:
        budget_state = "safe"
    elif token_utilization_ratio < WARNING_LIMIT:
        budget_state = "warning"
    else:
        budget_state = "danger"

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "token_utilization_ratio": token_utilization_ratio,
        "budget_state": budget_state
    }


class QuotaExceeded(Exception):
    pass


class QuotaManager:
    """
    Tracks api calls of each day per model
    - It checks for file.
    - It checks for api calls usage.
    - It decides for next call based on usage.
    """
    def __init__(self, call_limits: dict):
        self.call_limits = call_limits


    # ---------- helper functions ----------
    def _today(self) -> str:
        return date.today().isoformat()

    def _today_file(self) -> Path:
        return USAGE_DIR / f"{self._today()}.json"

    def _load_today(self) -> dict:
        path = self._today_file()

        # create file and structure
        if not path.exists():
            data = {
                "date": self._today(),
                "models": {}
            }
            self._save(data)
            return data

        # file exist -> load data 
        with open(path, "r") as f:
            return json.load(f)

    def _save(self, data: dict):
        with open(self._today_file(), "w") as f:
            json.dump(data, f, indent=2)

    # ---------- main logic ----------
    def can_call(self, model: str):
        data = self._load_today()

        if model not in data["models"]:
            data["models"][model] = {
                "used_calls": 0,
                "call_limit": self.call_limits.get(model, 0)
            }
            self._save(data)

        used = data["models"][model]["used_calls"]
        limit = data["models"][model]["call_limit"]

        return used < limit

    def record_call(self, model: str):
        data = self._load_today()

        if model not in data["models"]:
            data["models"][model] = {
                "used_calls": 0,
                "call_limit": self.call_limits.get(model, 0)
            }

        data["models"][model]["used_calls"] += 1
        self._save(data)

    # ---------- NEW: usage queries ----------
    def get_usage_today(self, model: str) -> int:
        """
        Get number of API calls used today for a specific model.
        
        Args:
            model: Model name
            
        Returns:
            Number of calls made today (0 if none)
        """
        data = self._load_today()
        
        if model not in data["models"]:
            return 0
        
        return data["models"][model]["used_calls"]

    def get_remaining_calls(self, model: str) -> int:
        """
        Get number of API calls remaining today.
        
        Args:
            model: Model name
            
        Returns:
            Number of calls remaining (0 if limit reached)
        """
        data = self._load_today()
        
        if model not in data["models"]:
            return self.call_limits.get(model, 0)

        used = data["models"][model]["used_calls"]
        limit = data["models"][model]["call_limit"]

        return max(0, limit - used)

    def check_and_warn(self, model: str) -> tuple[bool, str | None]:
        """
        Check quota and return warning if threshold crossed.
        
        Returns:
            (can_proceed, warning_message)
        """
        limit = self.call_limits.get(model, float('inf'))
        usage = self.get_usage_today(model)
        percentage = (usage / limit * 100) if limit > 0 else 0

        # 100% - Exhausted
        if percentage >= 100:
            return (False, f"🚫 API quota exhausted for {model}! ({usage}/{limit} calls used)")

        # 80% - High warning
        if percentage >= 80:
            remaining = limit - usage
            return (True, f"⚠️  High usage: {usage}/{limit} calls ({percentage:.0f}%). {remaining} remaining.")

        # 50% - Notice
        if percentage >= 50:
            return (True, f"📊 Usage notice: {usage}/{limit} calls ({percentage:.0f}%).")

        # Under 50% - OK
        return (True, None)


    # ---------- maintenance ----------
    def cleanup_old_files(self):
        cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)

        for file in USAGE_DIR.glob("*.json"):
            try:
                file_date = datetime.strptime(file.stem, "%Y-%m-%d")
                if file_date < cutoff:
                    file.unlink()
            except ValueError:
                continue # ignore invalid filenames

    # ---------- reporting ----------
    def get_usage_summary(self, days: int=7) -> dict:
        summary = {}
        cutoff = datetime.now() - timedelta(days=days)

        for file in USAGE_DIR.glob("*.json"):
            try:
                file_date = datetime.strptime(file.stem, "%Y-%m-%d")
                if file_date < cutoff:
                    continue

                with open(file, "r") as f:
                    data = json.load(f)

                for model, stats in data.get("models", {}).items():
                    summary.setdefault(model, 0)
                    summary[model] += stats.get("used_calls", 0)

            except Exception:
                continue

        return summary




