"""
AI Agent CLI Interface

Provides interactive command-line interface with:
- Intelligent caching (skips dynamic queries)
- Pattern matching (bypasses LLM for simple queries)
- Quota management
- Session tracking and analytics
"""

import sys
import uuid
import time
from typing import Optional, Tuple

from core.agent import run_agent
from infra.logger import setup_logging, logger_api
from app.config import validate_config, LOG_LEVEL, LOG_FILE_PATH, MODEL_NAME
from infra.ui import type_list, type_out
from core.memory import Cache, SessionManager
from tools.usage_tracker import QuotaManager
from core.routing.datetime_pattern import match as match_datetime
from core.routing.math_pattern import match as match_math
from core.routing.text_pattern import match as match_text


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

class QueryProcessor:
    """
    Handles query processing with intelligent caching.
    
    Strategy:
    1. Check cache (only for cacheable queries)
    2. Try pattern matching (math, text, datetime)
    3. Fall back to LLM agent
    
    Caching rules:
    - Math results: Cached (deterministic)
    - Text results: Cached (deterministic)
    - Datetime results: NOT cached (dynamic)
    - Web search results: NOT cached (dynamic)
    - Weather results: NOT cached (dynamic)
    """

    def __init__(self, cache: Cache, quota: QuotaManager, session_manager: SessionManager):
        self.cache = cache
        self.quota = quota
        self.session_manager = session_manager
        self.session_cache_hits = 0
        self.session_cache_misses = 0
        self.session_pattern_matches = 0


    def process_query(self, query: str, request_id: str) -> Tuple[str, float, int, bool]:
        """
        Process a query through the full pipeline.
        
        Returns:
            (response, duration, api_calls, cache_hit)
        """
        start_time = time.time()

        # Step 1: Check cache
        cached_response = self.cache.get(query)
        if cached_response:
            self.session_cache_hits += 1
            response_time = (time.time() - start_time) * 1000
            # not tokens used for cached
            run_cost = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "token_utilization_ratio": 0,
                "budget_state": "safe"
            }
            return (cached_response, 0.0, 0, True, run_cost)

        self.session_cache_misses += 1

        # Step 2: Try pattern matching
        pattern_response, pattern_type = self._try_pattern_matching(query)
    
        if pattern_response:
            self.session_pattern_matches += 1

            # Cache ONLY if not dynamic pattern
            if self._should_cache_pattern(pattern_type):
                self.cache.set(query, pattern_response)

            response_time = (time.time() - start_time) * 1000
            # not tokens used for pattern match
            run_cost = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "token_utilization_ratio": 0,
                "budget_state": "safe"
            }
            return (pattern_response, 0.0, 0, False, run_cost)

        # Step 3: Fall back to LLM agent
        calls_before = self.quota.get_usage_today(MODEL_NAME)
        agent_response, agent_duration, token_usage = self._run_agent(query, request_id)
        calls_after = self.quota.get_usage_today(MODEL_NAME)
        api_calls = calls_after - calls_before

        # Cache ONLY if not a dynamic query
        if self._should_cache_agent_response(query):
            self.cache.set(query, agent_response)

        return (agent_response, agent_duration, api_calls, False, token_usage)


    def _try_pattern_matching(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Try pattern matching in priority order.
        
        Returns:
            (response, pattern_type) or (None, None)
        """
        # Try datetime (highest priority - most specific)
        datetime_result = match_datetime(query)
        if datetime_result:
            return (datetime_result, "datetime")

        # Try math (medium priority)
        math_result = match_math(query)
        if math_result:
            return (math_result, "math")

        # Try text (lowest priority)
        text_result = match_text(query)
        if text_result:
            return (text_result, "text")

        return (None, None)


    def _should_cache_pattern(self, pattern_type: Optional[str]) -> bool:
        """
        Decide if pattern result should be cached.
        
        Rules:
        - math: Cache (deterministic)
        - text: Cache (deterministic)
        - datetime: DON'T cache (dynamic)
        """
        return pattern_type in ["math", "text"]


    def _should_cache_agent_response(self, query: str) -> bool:
        """
        Decide if agent response should be cached.
        
        Uses heuristics to detect if query likely used dynamic tools.
        """
        query_lower = query.lower()

        # Don't cache datetime queries
        datetime_indicators = [
            'today', 'tomorrow', 'yesterday',
            'what day is', 'what time is', 'current date', 'current time',
            'what date is', 'days from today', 'days before today',
            'next monday', 'next week', 'last week'
        ]
        if any(indicator in query_lower for indicator in datetime_indicators):
            return False

        # Don't cache web search queries
        web_search_indicators = [
            'who is', 'what is', 'where is', 'when was', 'why is', 'how does',
            'search for', 'find', 'look up',
            'latest', 'recent', 'current', 'news about',
            'tell me about', 'information about',
            'capital of', 'president', 'prime minister'
        ]
        if any(indicator in query_lower for indicator in web_search_indicators):
            return False

        # Don't cache weather queries
        if 'weather' in query_lower or 'temperature' in query_lower:
            return False

        # Don't cache stock/crypto queries
        if any(word in query_lower for word in ['stock', 'price', 'ticker', 'crypto']):
            return False

        # Otherwise, cache it
        return True


    def _run_agent(self, query: str, request_id: str) -> Tuple[str, float]:
        """
        Run the LLM agent.
        
        Returns:
            (response, duration)
        """
        try:
            start_time = time.perf_counter()
            response, token_usage = run_agent(query, request_id=request_id, quota=self.quota)
            duration = time.perf_counter() - start_time
            return (response, duration, token_usage)
        except Exception as e:
            logger_api.error(f"QUERY_FAILED | request_id={request_id} | error={str(e)}")
            return (f"❌ Failed to process query: {str(e)}", 0.0)


    def get_session_stats(self) -> dict:
        """Get session statistics."""
        total_queries = self.session_cache_hits + self.session_cache_misses
        cache_hit_rate = (self.session_cache_hits / total_queries * 100) if total_queries > 0 else 0
        pattern_match_rate = (self.session_pattern_matches / total_queries * 100) if total_queries > 0 else 0

        return {
            "total_queries": total_queries,
            "cache_hits": self.session_cache_hits,
            "cache_misses": self.session_cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "pattern_matches": self.session_pattern_matches,
            "pattern_match_rate": pattern_match_rate,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

class CLI:
    """
    Command-line interface for AI agent.
    
    Provides interactive prompt for sending queries to the agent
    and displaying responses with optional formatting effects.
    """
    
    def __init__(self, typing_effect: bool = False):
        """
        Initialize CLI.
        
        Args:
            typing_effect: Enable typing animation for responses
        """
        self.typing_effect = typing_effect
        self.session_queries = 0


    def run(self):
        """Start interactive CLI session"""
        self._print_welcome()

        # Initialize components
        cache = Cache(max_entries=100, cache_file="runtime/cache/cache.json")
        quota = QuotaManager(call_limits={MODEL_NAME: 20})
        session_manager = SessionManager(log_dir="runtime/telemetry", retention_days=14)

        # Query processor (handles caching logic)
        processor = QueryProcessor(cache, quota, session_manager)

        while True:
            try:
                # Get user input
                query = self._get_input()

                if not query:
                    continue

                # Check for exit commands
                if query.lower() in ('exit', 'quit', 'q'):
                    self._handle_exit(cache, session_manager, processor)
                    break

                # Check for help command
                if query.lower() in ('help', 'h', '?'):
                    self._print_help()
                    continue

                # Check for usage command
                if query.lower() == "usage":
                    self._print_usage(quota)
                    continue

                # Check for stats command
                if query.lower() == "stats":
                    self._print_stats(processor)
                    continue

                # Check quota and warn
                can_proceed, warning = quota.check_and_warn(MODEL_NAME)

                if warning:
                    print(f"\n{warning}\n")

                if not can_proceed:
                    print("Please try again tomorrow or upgrade your quota.")
                    continue


                # Process query
                self.session_queries += 1
                request_id = str(uuid.uuid4())[:8]

                response, duration, api_calls, cache_hit, token_usage = processor.process_query(query, request_id)

                session_manager.track_tokens(token_usage)

                # Display response
                self._print_response(response, duration)

                # Display query info
                if cache_hit:
                    stats = processor.get_session_stats()
                    type_out(f"✓ Cache hit ({stats['cache_hits']} total) - 0 API calls")
                elif api_calls == 0:
                    stats = processor.get_session_stats()
                    type_out(f"⚡ Pattern matched ({stats['pattern_matches']} total) - 0 API calls")
                else:
                    stats = processor.get_session_stats()
                    type_out(f"✗ Cache miss ({stats['cache_misses']} total) - {api_calls} API calls")

                # Log to session manager
                session_manager.log_details(
                    query=query,
                    cache_hit=cache_hit,
                    api_calls=api_calls,
                    response_time_ms=duration * 1000 if duration > 0 else 0
                )

            except KeyboardInterrupt:
                print("\n")
                self._handle_exit(cache, session_manager, processor)
                break

            except Exception as e:
                print(f"\n❌ Error: {str(e)}\n")
                logger_api.error(f"CLI_ERROR | error={str(e)}")


    def _handle_exit(self, cache: Cache, session_manager: SessionManager, processor: QueryProcessor):
        """Handle graceful exit."""
        cache.save()
        session_manager.print_session_summary()
        session_manager.save_session_summary()

        # Print enhanced stats
        stats = processor.get_session_stats()
        print(f"\n📊 Session Statistics:")
        print(f"   Total queries: {stats['total_queries']}")
        print(f"   Cache hits: {stats['cache_hits']} ({stats['cache_hit_rate']:.1f}%)")
        print(f"   Pattern matches: {stats['pattern_matches']} ({stats['pattern_match_rate']:.1f}%)")
        print(f"   LLM calls: {stats['cache_misses'] - stats['pattern_matches']}")

        self._print_goodbye()


    def _get_input(self) -> str:
        """Get user input with prompt"""
        try:
            return input("\nYou: ").strip()
        except EOFError:
            return "exit"


    def _print_response(self, response: str, duration: float):
        """
        Print agent response.
        
        Args:
            response: Agent's response
            duration: Query processing time
        """
        print("\n")
        print("Agent: ", end="")

        if self.typing_effect:
            type_out(response, delay=0.02)
        else:
            print(response)

        if duration > 0:
            print(f"⏱️  {duration:.2f}s")
        print()


    def _print_welcome(self):
        """Print welcome message"""
        print("=" * 60)
        print("  AI Agent Engine v3.0")
        print("=" * 60)
        print()
        print("  Ask me anything! I can help with:")
        print()
        type_list([
            "Date and time calculations",
            "Mathematical operations",
            "Web searches and information lookup",
            "Text processing and analysis",
            "Weather forecasts"
        ], delay=0.3 if self.typing_effect else 0)
        print()
        print("  Commands: help | exit | usage | stats")
        print()


    def _print_help(self):
        """Print help message"""
        print()
        print("Available commands:")
        print("  help, h, ?  - Show this help message")
        print("  stats       - Show session statistics")
        print("  usage       - Show API usage")
        print("  exit, quit  - Exit the application")
        print()
        print("Examples:")
        print('  "What date is 5 days from today?"')
        print('  "Calculate 24 * 7"')
        print('  "Who is the current president?"')
        print('  "Convert \'hello\' to uppercase"')
        print()


    def _print_goodbye(self):
        """Print goodbye message"""
        print()
        print(f"Processed {self.session_queries} queries this session.")
        print("Goodbye! 👋")
        print()


    def _print_usage(self, quota: QuotaManager):
        """Print API usage summary"""
        summary = quota.get_usage_summary(days=7)
        print("\n📈 Usage summary (last 7 days):")

        if not summary:
            print("  No usage recorded.")
            return

        for model, calls in summary.items():
            print(f"  - {model}: {calls} calls")

        print()


    def _print_stats(self, processor: QueryProcessor):
        """Print session statistics"""
        stats = processor.get_session_stats()

        print("\n📊 Session Statistics:")
        print(f"  Total queries: {stats['total_queries']}")
        print(f"  Cache hits: {stats['cache_hits']} ({stats['cache_hit_rate']:.1f}%)")
        print(f"  Pattern matches: {stats['pattern_matches']} ({stats['pattern_match_rate']:.1f}%)")
        print(f"  LLM calls needed: {stats['cache_misses'] - stats['pattern_matches']}")

        # Combined bypass rate
        bypass_count = stats['cache_hits'] + stats['pattern_matches']
        bypass_rate = (bypass_count / stats['total_queries'] * 100) if stats['total_queries'] > 0 else 0
        print(f"  Total bypass rate: {bypass_rate:.1f}% (no LLM needed)")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Main entry point for the application.
    
    Sets up logging, validates configuration, and starts the CLI.
    """
    try:
        # Setup logging
        setup_logging(
            level=LOG_LEVEL,
            log_file=LOG_FILE_PATH if hasattr(sys.modules['app.config'], 'ENABLE_FILE_LOGGING') else None
        )

        logger_api.info("=" * 60)
        logger_api.info("AI Agent Engine Starting")
        logger_api.info("=" * 60)

        # Validate configuration
        logger_api.info("Validating configuration...")
        validate_config()
        logger_api.info("Configuration valid [OK]")

        # Start CLI
        logger_api.info("Starting CLI interface...")
        cli = CLI(typing_effect=False)
        cli.run()

        logger_api.info("AI Agent Engine Stopped")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)

    except Exception as e:
        logger_api.error(f"STARTUP_ERROR | error={str(e)}")
        print(f"\n❌ Startup error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

