#!/usr/bin/env python3
"""
rSpotify Bot - Main Entry Point

A Telegram bot for Spotify track sharing and recommendations.
"""

import asyncio
import logging
import os
import signal
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from rspotify_bot.config import setup_logging, validate_environment, config
from rspotify_bot.bot import RSpotifyBot

logger = logging.getLogger(__name__)

PID_FILE = Path(os.getenv("RS_BOT_PID_FILE", "/tmp/rspotify-bot.pid"))
TERMINATION_TIMEOUT_SECONDS = float(os.getenv("RS_BOT_TERMINATION_TIMEOUT", "10"))


def _is_process_running(pid: int) -> bool:
    """Return True if the provided PID is currently running."""

    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


def _looks_like_rspotify_process(pid: int) -> bool:
    """Best-effort check that the PID appears to be an rSpotify process."""

    proc_path = Path("/proc") / str(pid) / "cmdline"
    try:
        cmdline = proc_path.read_bytes().decode("utf-8", errors="ignore")
    except FileNotFoundError:
        return False
    except Exception:
        logger.debug("Unable to inspect process %s", pid, exc_info=True)
        return False

    return "rspotify" in cmdline or "telegram" in cmdline


def _terminate_process(pid: int, timeout: float) -> None:
    """Terminate an existing process gracefully, escalating if needed."""

    try:
        os.kill(pid, signal.SIGTERM)
        logger.warning("Sent SIGTERM to existing rSpotify process %s", pid)
    except ProcessLookupError:
        return
    except PermissionError:
        logger.warning("Insufficient permissions to terminate process %s", pid)
        return
    except Exception:
        logger.error("Failed to send SIGTERM to process %s", pid, exc_info=True)
        return

    deadline = time.time() + timeout
    while time.time() < deadline and _is_process_running(pid):
        time.sleep(0.25)

    if not _is_process_running(pid):
        logger.info("Existing rSpotify process %s terminated", pid)
        return

    logger.warning("Process %s did not exit after SIGTERM; sending SIGKILL", pid)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception:
        logger.error("Failed to send SIGKILL to process %s", pid, exc_info=True)
        return

    deadline = time.time() + timeout
    while time.time() < deadline and _is_process_running(pid):
        time.sleep(0.25)

    if _is_process_running(pid):
        logger.error("Unable to terminate existing process %s", pid)
    else:
        logger.info("Existing rSpotify process %s terminated after SIGKILL", pid)


@contextmanager
def single_instance(pid_file: Path = PID_FILE, timeout: float = TERMINATION_TIMEOUT_SECONDS) -> Iterator[None]:
    """Ensure only one rSpotify bot instance runs at a time."""

    pid_file = pid_file.expanduser().resolve()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    if pid_file.exists():
        try:
            existing_pid = int(pid_file.read_text().strip())
        except ValueError:
            existing_pid = None
            logger.warning("Found malformed PID file at %s; removing", pid_file)

        if existing_pid and existing_pid != os.getpid():
            if _is_process_running(existing_pid) and _looks_like_rspotify_process(existing_pid):
                _terminate_process(existing_pid, timeout)
            elif _is_process_running(existing_pid):
                logger.warning(
                    "PID %s from %s is running but does not look like rSpotify; leaving untouched",
                    existing_pid,
                    pid_file,
                )
            else:
                logger.info("Removing stale PID file at %s", pid_file)

        try:
            pid_file.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            logger.error("Failed to remove PID file %s", pid_file, exc_info=True)

    pid_file.write_text(str(os.getpid()))
    try:
        yield
    finally:
        try:
            if pid_file.exists() and pid_file.read_text().strip() == str(os.getpid()):
                pid_file.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            logger.warning("Failed to clean up PID file %s", pid_file, exc_info=True)


async def main() -> None:
    """Main application entry point."""
    print("🎵 Starting rSpotify Bot...")

    # Setup logging
    setup_logging()
    logger.info("rSpotify Bot starting up...")

    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed. Exiting.")
        sys.exit(1)

    # Create and start bot
    try:
        bot = RSpotifyBot(config.TELEGRAM_BOT_TOKEN)
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("rSpotify Bot stopped.")


if __name__ == "__main__":
    with single_instance():
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user.")
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            sys.exit(1)
