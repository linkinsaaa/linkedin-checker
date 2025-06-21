#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinkedIn Link Checker - Production Build
Description: A robust, multi-threaded LinkedIn link validation tool with bulk account
             management, enhanced stealth, and a refined user interface.
Author: A Senior Python Engineer
Version: 14.2 (The Account Management Build - Bugfix 2)
"""

# --- Core Libraries ---
import json
import logging
import queue
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Dynamic Dependency Imports ---
try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.remote.webelement import WebElement
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.wait import WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    import undetected_chromedriver as uc
    UNDETECTED_CHROME_AVAILABLE = True
except ImportError:
    UNDETECTED_CHROME_AVAILABLE = False

try:
    from selenium_stealth import stealth
    SELENIUM_STEALTH_AVAILABLE = True
except ImportError:
    SELENIUM_STEALTH_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, TclError
    import customtkinter as ctk
    from PIL import Image, ImageTk
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


# --- Constants & Application Paths ---
if getattr(sys, "frozen", False):
    APP_PATH = Path(sys.executable).parent
else:
    APP_PATH = Path(__file__).parent

CONFIG_FILE = APP_PATH / "config.json"
LOG_DIR = APP_PATH / "logs"
SESSIONS_DIR = APP_PATH / "sessions"
STATE_FILE = APP_PATH / "checker.state"
DEFAULT_INPUT_FILE = str(APP_PATH / "linkedin_links.txt")
DEFAULT_OUTPUT_DIR = str(APP_PATH / "results")


# --- Enums for Status Tracking ---
class LoginStatus(Enum):
    SUCCESS = auto()
    FAIL_BAD_CREDS = auto()
    FAIL_CAPTCHA = auto()
    FAIL_TIMEOUT = auto()
    FAIL_PAGE_ERROR = auto()
    FAIL_UNKNOWN = auto()


class LinkStatus(Enum):
    WORKING = "WORKING"
    FAILED = "FAILED"
    RATE_LIMIT = "RATE_LIMIT"
    SESSION_LOST = "SESSION_LOST"
    ERROR = "ERROR"


# --- Default Configuration ---
DEFAULT_CONFIG = {
    "settings": {
        "input_file": DEFAULT_INPUT_FILE, "output_dir": DEFAULT_OUTPUT_DIR,
        "delay_min": 3.0, "delay_max": 7.0, "headless": True, "language": "en",
        "theme": "dark", "color_theme": "blue", "num_threads": 2, "window_geometry": "1200x800",
        "account_rest_duration_minutes": 30, "page_load_timeout": 60,
    },
    "accounts_text": "", # Storing raw text to avoid the previous TypeError
    "selectors": {
        "username_field": ["#username", "#session_key"], "password_field": ["#password", "#session_password"],
        "login_submit_button": ["//button[@type='submit']", "button.sign-in-form__submit-button"],
        "login_error_message": [".form__input--error", ".form__message--error", "[data-test-id='error-message']", ".error-for"],
        "login_success_indicator": ["//header[contains(@class, 'global-nav')]", "#global-nav", "[data-test-id='global-nav-search-button']"],
    },
    "markers": {
        "valid": ["start your free", "start premium", "your free trial awaits", "claim your gift", "activate offer", "free month", "linkedin premium"],
        "invalid": ["offer unavailable", "offer is no longer available", "already been redeemed", "link has expired", "page not found", "this page is unavailable", "this page isn't available", "something went wrong"],
        "already_premium": ["you are already a premium member", "manage premium subscription", "your current plan"],
        "rate_limit": ["are you human", "security verification", "captcha", "challenge checkpoint", "unusual activity", "verify you're human"],
        "login_redirect": ["/login", "/authwall", "authentication required"],
    },
    "user_agents": [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    ]
}


# --- Dataclasses for Structured Data ---
@dataclass
class LinkResult:
    link: str; status: LinkStatus; result_details: str = ""
    final_url: Optional[str] = None; line_num: Optional[int] = None
    error: Optional[str] = None; account_email: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Account:
    email: str; password: str
    last_rate_limited_at: Optional[datetime] = field(default=None, repr=False)
    def is_resting(self, duration_minutes: int) -> bool:
        if not self.last_rate_limited_at: return False
        is_resting = datetime.now() < self.last_rate_limited_at + timedelta(minutes=duration_minutes)
        if is_resting:
             main_logger.debug(f"Account {self.email} is resting.")
        return is_resting

@dataclass
class Stats:
    total_processed: int = 0; working_found: int = 0
    failed_or_invalid: int = 0; link_captcha_failures: int = 0
    login_failures: int = 0; errors: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None


# --- Logger & Config Setup ---
class QueueHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue): super().__init__(); self.log_queue = log_queue
    def emit(self, record: logging.LogRecord): self.log_queue.put(self.format(record))

def setup_logging(log_level: int = logging.INFO, log_queue: Optional[queue.Queue] = None) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_format = '%(asctime)s | %(levelname)-8s | %(threadName)-15s | %(message)s'
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
    logging.basicConfig(level=logging.CRITICAL, format=log_format, force=True)
    logger = logging.getLogger("LinkedInChecker")
    logger.setLevel(log_level)
    if logger.hasHandlers(): logger.handlers.clear()
    logger.propagate = False
    stream_handler = logging.StreamHandler(sys.stdout); stream_handler.setFormatter(formatter); logger.addHandler(stream_handler)
    try:
        log_file = LOG_DIR / f'checker_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        file_handler = logging.FileHandler(log_file, encoding='utf-8'); file_handler.setFormatter(formatter); logger.addHandler(file_handler)
    except Exception as e: print(f"Warning: Could not set up file logger: {e}")
    if log_queue:
        queue_handler = QueueHandler(log_queue); queue_handler.setFormatter(formatter); logger.addHandler(queue_handler)
    return logger

main_logger = setup_logging()

class ConfigManager:
    def __init__(self, config_file: Path, default_config: Dict): self.config_file = config_file; self.default_config = default_config
    def load_config(self) -> Dict[str, Any]:
        if not self.config_file.exists(): self.save_config(self.default_config); return self.default_config
        try:
            with self.config_file.open('r', encoding='utf-8') as f: loaded_config = json.load(f)
            return self._merge_configs(self.default_config, loaded_config)
        except (json.JSONDecodeError, IOError) as e: main_logger.error(f"Error loading config, using defaults: {e}"); return self.default_config
    def _merge_configs(self, default, user):
        merged = default.copy()
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict): merged[key] = self._merge_configs(merged[key], value)
            else: merged[key] = value
        return merged
    def save_config(self, data: Dict[str, Any]):
        try:
            with self.config_file.open('w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        except IOError as e: main_logger.error(f"Error saving config file: {e}")


# --- Tooltip Helper ---
class ToolTip(ctk.CTkToplevel):
    def __init__(self, widget, text):
        super().__init__(widget)
        self.withdraw(); self.overrideredirect(True); self.attributes("-topmost", True)
        self.label = ctk.CTkLabel(self, text=text, fg_color="gray20", corner_radius=5, padx=8, pady=4, font=ctk.CTkFont(size=12))
        self.label.pack(); widget.bind("<Enter>", self.show); widget.bind("<Leave>", self.hide)
    def show(self, event):
        x, y, _, _ = event.widget.bbox("insert"); x += event.widget.winfo_rootx() + 25; y += event.widget.winfo_rooty() + 25
        self.geometry(f"+{x}+{y}"); self.deiconify()
    def hide(self, event): self.withdraw()


# --- WebDriver Manager ---
class DriverManager:
    """Handles creating WebDriver instances with advanced stealth."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config; self.settings = config['settings']; self.headless = self.settings.get('headless', True)
        self.user_agents = self.config.get('user_agents', []); SESSIONS_DIR.mkdir(exist_ok=True)

    def _get_cookie_path(self, email: str) -> Path:
        sanitized_email = re.sub(r'[^\w\-_\.]', '_', email); return SESSIONS_DIR / f"{sanitized_email}.json"
    def save_cookies(self, driver: WebDriver, email: str):
        try:
            cookies = driver.get_cookies()
            with self._get_cookie_path(email).open('w') as f: json.dump(cookies, f)
            main_logger.debug(f"Saved session cookies for {email}.")
        except Exception as e: main_logger.error(f"Failed to save cookies for {email}: {e}")
    def load_cookies(self, driver: WebDriver, email: str) -> bool:
        cookie_path = self._get_cookie_path(email)
        if not cookie_path.exists(): return False
        try:
            with cookie_path.open('r') as f: cookies = json.load(f)
            driver.get("https://www.linkedin.com/") # Domain must be visited first
            for cookie in cookies:
                try:
                    if 'expiry' in cookie and cookie['expiry'] is not None: cookie['expiry'] = int(cookie['expiry'])
                    driver.add_cookie(cookie)
                except Exception: continue
            main_logger.info(f"Loaded {len(cookies)} session cookies for {email}.")
            return True
        except Exception as e: main_logger.error(f"Failed to load cookies for {email}: {e}"); return False

    def create_driver(self) -> WebDriver:
        user_agent = random.choice(self.user_agents) if self.user_agents else ""
        options = ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)
        
        # BUGFIX: Removed experimental options that crash newer versions of chromedriver.
        # The undetected_chromedriver library handles these internally now.
        # prefs = {"profile.default_content_setting_values.notifications": 2, "profile.default_content_settings.popups": 0, "profile.managed_default_content_settings.images": 2}
        # options.add_experimental_option("prefs", prefs)
        
        if user_agent: options.add_argument(f"user-agent={user_agent}")
        if self.headless: options.add_argument("--headless=new")
        if UNDETECTED_CHROME_AVAILABLE:
            main_logger.info("Using undetected-chromedriver for enhanced stealth.")
            driver = uc.Chrome(options=options, use_subprocess=True)
        else:
            main_logger.info("Using standard chromedriver.")
            service = ChromeService(ChromeDriverManager().install()); driver = webdriver.Chrome(service=service, options=options)
        if not UNDETECTED_CHROME_AVAILABLE and SELENIUM_STEALTH_AVAILABLE:
            main_logger.info("Applying selenium-stealth patches.")
            stealth(driver, languages=["en-US", "en"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
        timeout = self.settings.get('page_load_timeout', 60); driver.set_page_load_timeout(timeout)
        return driver


# --- Core Checker Class ---
class LinkedInChecker:
    def __init__(self, config: Dict[str, Any], accounts: List[Account], gui_instance: Optional['LinkedInCheckerGUI'] = None):
        self.config = config; self.settings = config['settings']; self.accounts = accounts
        self.gui = gui_instance; self.driver_manager = DriverManager(self.config)
        self.should_stop = threading.Event(); self.pause_event = threading.Event(); self.pause_event.set()
        self.is_paused = False; self.stats = Stats(); self.results: List[LinkResult] = []
        self.links_queue = queue.Queue(); self.processed_links_log = set()
        self.account_pool = queue.Queue(); [self.account_pool.put(acc) for acc in self.accounts]
        self.active_threads = 0; self.lock = threading.Lock()
        main_logger.info(f"Checker initialized with {self.settings.get('num_threads')} threads.")

    def _load_processed_links_state(self):
        if not STATE_FILE.exists(): return
        try:
            with STATE_FILE.open('r', encoding='utf-8') as f: self.processed_links_log = {line.strip() for line in f if line.strip()}
            if self.processed_links_log: main_logger.info(f"Loaded state file. Skipping {len(self.processed_links_log)} already processed links.")
        except Exception as e: main_logger.error(f"Error loading state file: {e}")
    def _log_processed_link(self, link: str):
        self.processed_links_log.add(link)
        try:
            with STATE_FILE.open('a', encoding='utf-8') as f: f.write(f"{link}\n")
        except Exception as e: main_logger.error(f"Error writing to state file: {e}")

    def read_and_queue_links(self) -> int:
        self._load_processed_links_state()
        input_file = Path(self.settings.get('input_file', ''))
        if not input_file.exists(): main_logger.error(f"Input file not found: {str(input_file)}"); return 0
        unique_links = {}
        try:
            with input_file.open('r', encoding='utf-8', errors='ignore') as f: content = f.read()
            url_pattern = re.compile(r'https?://(?:www\.)?linkedin\.com/[^\s\'"<>(),;]+')
            for i, line in enumerate(content.splitlines()):
                for match in url_pattern.finditer(line):
                    url = match.group(0).strip(".,;")
                    if url not in unique_links and url not in self.processed_links_log: unique_links[url] = i + 1
            for url, line_num in unique_links.items(): self.links_queue.put((url, line_num))
            count = self.links_queue.qsize()
            main_logger.info(f"{count} unique, unprocessed links found.")
            return count
        except Exception as e: main_logger.error(f"Error reading links file: {str(e)}"); return 0

    def _find_element(self, driver: WebDriver, selectors: List[str], timeout: int = 10) -> Optional[WebElement]:
        for selector in selectors:
            try:
                by = By.XPATH if selector.startswith(("//", "./")) else By.CSS_SELECTOR
                return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((by, selector)))
            except TimeoutException: continue
        return None
    def _type_like_human(self, element: WebElement, text: str):
        for char in text: element.send_keys(char); time.sleep(random.uniform(0.05, 0.15))

    def setup_and_login(self, account: Account) -> Tuple[Optional[WebDriver], LoginStatus]:
        main_logger.info(f"Attempting to start session for {account.email}.")
        driver = self.driver_manager.create_driver()
        try:
            if self.driver_manager.load_cookies(driver, account.email):
                driver.get("https://www.linkedin.com/feed/")
                if self._find_element(driver, self.config['selectors']['login_success_indicator']):
                    main_logger.info(f"SUCCESS: Resumed session for {account.email} using cookies.")
                    return driver, LoginStatus.SUCCESS
                main_logger.warning(f"Cookie session for {account.email} is invalid. Performing full login.")
                driver.delete_all_cookies()

            driver.get("https://www.linkedin.com/login")
            username_field = self._find_element(driver, self.config['selectors']['username_field'])
            if not username_field: return driver, LoginStatus.FAIL_PAGE_ERROR
            self._type_like_human(username_field, account.email)
            password_field = self._find_element(driver, self.config['selectors']['password_field'])
            if not password_field: return driver, LoginStatus.FAIL_PAGE_ERROR
            self._type_like_human(password_field, account.password)
            submit_button = self._find_element(driver, self.config['selectors']['login_submit_button'])
            if not submit_button: return driver, LoginStatus.FAIL_PAGE_ERROR
            submit_button.click()

            try:
                WebDriverWait(driver, 45).until(EC.any_of(
                    EC.presence_of_element_located((By.XPATH, self.config['selectors']['login_success_indicator'][0])),
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.config['selectors']['login_error_message'][0])),
                    EC.url_contains("checkpoint"), EC.url_contains("challenge")))
            except TimeoutException: main_logger.error(f"TIMEOUT: Login for {account.email} did not result in a known page state."); return driver, LoginStatus.FAIL_TIMEOUT

            current_url = driver.current_url.lower()
            if self._find_element(driver, self.config['selectors']['login_success_indicator'], 5):
                main_logger.info(f"SUCCESS: Full login successful for {account.email}."); self.driver_manager.save_cookies(driver, account.email); return driver, LoginStatus.SUCCESS
            if "checkpoint" in current_url or "challenge" in current_url:
                main_logger.warning(f"Security challenge for {account.email}. Pausing for manual intervention.")
                if self.gui and not self.settings.get('headless'):
                    if self.gui.show_captcha_prompt(account.email):
                        if self._find_element(driver, self.config['selectors']['login_success_indicator'], 5):
                             main_logger.info(f"Security challenge for {account.email} resolved by user. Resuming."); self.driver_manager.save_cookies(driver, account.email); return driver, LoginStatus.SUCCESS
                main_logger.error(f"User skipped or failed the security challenge for {account.email}."); return driver, LoginStatus.FAIL_CAPTCHA
            if self._find_element(driver, self.config['selectors']['login_error_message'], 2):
                main_logger.warning(f"BAD CREDS: Login failed for {account.email}."); return driver, LoginStatus.FAIL_BAD_CREDS
            main_logger.error(f"UNKNOWN: Login failed for {account.email} with an unknown page state. URL: {current_url}"); return driver, LoginStatus.FAIL_UNKNOWN
        except Exception as e: main_logger.critical(f"CRITICAL: Unhandled exception in login for {account.email}: {e}", exc_info=True); return driver, LoginStatus.FAIL_UNKNOWN

    def classify_content(self, html_content: str, current_url: str) -> Tuple[LinkStatus, str]:
        if not html_content or not BS4_AVAILABLE: return LinkStatus.ERROR, "Empty or unparsable content"
        lower_content = html_content.lower(); lower_url = current_url.lower()
        if any(sub in lower_url for sub in self.config['markers']['login_redirect']): return LinkStatus.SESSION_LOST, "Redirected to login/authwall page."
        for marker in self.config['markers']['rate_limit']:
            if marker in lower_content: return LinkStatus.RATE_LIMIT, f"Rate limit / CAPTCHA on link page. Marker: {marker}"
        for marker in self.config['markers']['already_premium']:
            if marker in lower_content: return LinkStatus.FAILED, f"Account is already a Premium member. Marker: {marker}"
        for marker in self.config['markers']['invalid']:
            if marker in lower_content: return LinkStatus.FAILED, f"Offer unavailable/expired. Marker: {marker}"
        for marker in self.config['markers']['valid']:
            if marker in lower_content: return LinkStatus.WORKING, f"Potential trial/gift offer found. Marker: {marker}"
        if "/feed/" in lower_url and not any(k in lower_url for k in ["premium", "sales", "gift"]): return LinkStatus.FAILED, "Redirected to main feed; link likely invalid or expired."
        return LinkStatus.FAILED, "No clear trial indicators found; link likely invalid."

    def analyze_link_page(self, driver: WebDriver, url: str) -> LinkResult:
        try:
            main_logger.debug(f"Navigating to {url}"); timeout = self.settings.get('page_load_timeout', 60); driver.get(url)
            WebDriverWait(driver, timeout).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            classification, reason = self.classify_content(driver.page_source, driver.current_url)
            return LinkResult(link=url, status=classification, result_details=reason, final_url=driver.current_url)
        except TimeoutException: return LinkResult(link=url, status=LinkStatus.ERROR, result_details=f"Page load timed out after {timeout}s.", error="TimeoutException")
        except WebDriverException as e:
            err = str(e).lower()
            status = LinkStatus.SESSION_LOST if any(s in err for s in ["no such window", "invalid session id", "target window already closed"]) else LinkStatus.ERROR
            details = "Session lost." if status == LinkStatus.SESSION_LOST else f"WebDriver error: {str(e)[:100]}"
            return LinkResult(link=url, status=status, result_details=details, error=str(e))
        except Exception as e: return LinkResult(link=url, status=LinkStatus.ERROR, result_details="Unexpected analysis error", error=str(e))

    def worker_thread(self, worker_id: int):
        with self.lock: self.active_threads += 1
        main_logger.info(f"Worker {worker_id} started.")
        while not self.should_stop.is_set():
            self.pause_event.wait();
            if self.links_queue.empty(): break
            try: account = self.account_pool.get(timeout=1)
            except queue.Empty:
                if self.links_queue.empty(): break
                main_logger.debug(f"Worker {worker_id} waiting for an account."); time.sleep(5); continue
            if account.is_resting(self.settings.get('account_rest_duration_minutes', 30)):
                self.account_pool.put(account); time.sleep(1); continue

            driver, login_status = self.setup_and_login(account)
            if login_status != LoginStatus.SUCCESS:
                with self.lock: self.stats.login_failures += 1
                if login_status == LoginStatus.FAIL_CAPTCHA: account.last_rate_limited_at = datetime.now()
                self.account_pool.put(account)
                if driver: driver.quit()
                continue
            
            while not self.should_stop.is_set():
                self.pause_event.wait()
                try: url, line_num = self.links_queue.get_nowait()
                except queue.Empty: break
                with self.lock:
                    total_links = len(self.processed_links_log) + self.links_queue.qsize() + 1
                    current = self.stats.total_processed + 1
                    max_threads = self.settings.get('num_threads')
                if self.gui: self.gui.update_live_status(current, total_links, self.active_threads, max_threads)
                main_logger.info(f"Processing Link {current}/{total_links}: {url} (Line {line_num}) with {account.email}")
                result = self.analyze_link_page(driver, url)
                result.account_email = account.email; result.line_num = line_num
                if result.status == LinkStatus.SESSION_LOST: self.links_queue.put((url, line_num)); break
                with self.lock:
                    self.stats.total_processed += 1; self.results.append(result); self._log_processed_link(url)
                    if result.status == LinkStatus.WORKING: self.stats.working_found += 1
                    elif result.status == LinkStatus.RATE_LIMIT: self.stats.link_captcha_failures += 1
                    elif result.status == LinkStatus.ERROR: self.stats.errors += 1
                    else: self.stats.failed_or_invalid += 1
                if self.gui: self.gui.update_stats_and_progress(self.stats)
                time.sleep(random.uniform(self.settings.get('delay_min', 1.0), self.settings.get('delay_max', 3.0)))
            if driver: driver.quit()
            self.account_pool.put(account) # Return the account to the pool for another worker
        with self.lock: self.active_threads -= 1
        main_logger.info(f"Worker {worker_id} finished.")

    def run(self):
        self.stats = Stats(); self.results.clear()
        if STATE_FILE.exists(): STATE_FILE.unlink(); main_logger.info("New run started. Cleared old state file.")
        total_links = self.read_and_queue_links()
        if self.gui: self.gui.set_total_links(total_links)
        if not total_links or self.account_pool.empty():
            msg = "No unique, unprocessed links found." if not total_links else "No accounts are configured."
            main_logger.error(msg)
            if self.gui: self.gui.show_message_dialog("Input Error", msg, "error")
            if self.gui: self.gui.on_checking_finished(stopped=True)
            return
        num_threads = self.settings.get('num_threads', 1)
        with ThreadPoolExecutor(max_workers=num_threads, thread_name_prefix="LinkChecker") as executor:
            futures = [executor.submit(self.worker_thread, i + 1) for i in range(num_threads)]
            for future in as_completed(futures):
                try: future.result()
                except Exception as e: main_logger.error(f"Worker thread error: {e}", exc_info=True)
        self.stats.end_time = datetime.now(); main_logger.info("All worker threads have completed.")
        self.save_results()
        if self.gui: self.gui.on_checking_finished(stopped=self.should_stop.is_set())

    def save_results(self):
        if not self.results: return
        output_dir = Path(self.settings.get('output_dir', DEFAULT_OUTPUT_DIR)); output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        working_links = [r for r in self.results if r.status == LinkStatus.WORKING]
        if working_links:
            path = output_dir / f"working_links_{timestamp}.txt"
            with path.open('w', encoding='utf-8') as f:
                f.write(f"# LinkedIn Link Checker - Working Links\n# {datetime.now().isoformat()}\n\n")
                for res in sorted(working_links, key=lambda r: r.link): f.write(f"{res.link} | {res.result_details}\n")
            main_logger.info(f"Saved {len(working_links)} working links to: {path}")
        path = output_dir / f"detailed_results_{timestamp}.json"
        with path.open('w', encoding='utf-8') as f:
            serializable_results = [asdict(r, dict_factory=lambda data: {k: v.value if isinstance(v, Enum) else v for k, v in data}) for r in self.results]
            json.dump({"summary": asdict(self.stats), "results": serializable_results}, f, indent=4, default=str)
        main_logger.info(f"Saved detailed JSON results to: {path}")

    def stop(self): self.should_stop.set(); self.pause_event.set()
    def pause(self): self.pause_event.clear(); self.is_paused = True
    def resume(self): self.pause_event.set(); self.is_paused = False


# --- GUI Class ---
class LinkedInCheckerGUI:
    def __init__(self):
        if not GUI_AVAILABLE: raise RuntimeError("GUI libraries not installed.")
        self.config_manager = ConfigManager(CONFIG_FILE, DEFAULT_CONFIG)
        self.app_config = self.config_manager.load_config()
        self.root = ctk.CTk(); self.log_queue = queue.Queue(); self.captcha_response_queue = queue.Queue()
        global main_logger; main_logger = setup_logging(log_queue=self.log_queue)
        ctk.set_appearance_mode(self.app_config.get("settings", {}).get("theme", "dark"))
        ctk.set_default_color_theme(self.app_config.get("settings", {}).get("color_theme", "blue"))
        self.checker: Optional[LinkedInChecker] = None; self.checker_thread: Optional[threading.Thread] = None
        self.is_running = False; self.total_links = 0
        self._setup_ui()
        self.load_settings_to_ui()
        self._start_log_processor()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_ui(self):
        self.root.title("LinkedIn Link Checker v14.2")
        self.root.geometry(self.app_config.get("settings", {}).get("window_geometry", "1200x800"))
        self.root.minsize(1100, 700)
        self.root.grid_columnconfigure(0, weight=1); self.root.grid_rowconfigure(1, weight=1)
        
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(0, weight=1)
        
        self.tab_view = ctk.CTkTabview(main_frame); self.tab_view.grid(row=0, column=0, sticky="nsew", padx=5)
        self._create_main_tab(self.tab_view.add("▶️ Main"))
        self._create_settings_tab(self.tab_view.add("⚙️ Settings"))
        
        self._create_progress_widgets(main_frame).grid(row=1, column=0, sticky="ew", padx=5, pady=(15, 5))
        
        log_frame = ctk.CTkFrame(self.root); log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_frame.grid_columnconfigure(0, weight=1); log_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(log_frame, text="Live Log", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, pady=5, padx=10, sticky="w")
        self.log_textbox = ctk.CTkTextbox(log_frame, wrap="word", state="disabled", font=("Consolas", 12))
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))

    def _create_main_tab(self, parent):
        parent.grid_columnconfigure((0, 1), weight=1, uniform="group1")
        parent.grid_rowconfigure(0, weight=1)
        
        # --- Left Frame for Accounts ---
        left_frame = ctk.CTkFrame(parent); left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_columnconfigure(0, weight=1); left_frame.grid_rowconfigure(1, weight=1)
        
        accounts_header_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        accounts_header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,5))
        ctk.CTkLabel(accounts_header_frame, text="👤 Accounts (email:pass)", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(accounts_header_frame, text="Load from File...", width=120, command=self.load_accounts_from_file).pack(side="right")
        
        self.accounts_textbox = ctk.CTkTextbox(left_frame, wrap="none"); self.accounts_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # --- Right Frame for File Paths ---
        right_frame = ctk.CTkFrame(parent); right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        right_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(right_frame, text="📁 File Paths", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, pady=(10, 5), padx=10, sticky="w")
        
        ctk.CTkLabel(right_frame, text="Links File:").grid(row=1, column=0, sticky="w", padx=(10,5), pady=5)
        self.input_file_entry = ctk.CTkEntry(right_frame); self.input_file_entry.grid(row=1, column=1, sticky="ew", padx=(0,10), pady=5)
        
        ctk.CTkLabel(right_frame, text="Output Dir:").grid(row=2, column=0, sticky="w", padx=(10,5), pady=5)
        self.output_dir_entry = ctk.CTkEntry(right_frame); self.output_dir_entry.grid(row=2, column=1, sticky="ew", padx=(0,10), pady=5)
        
    def load_accounts_from_file(self):
        file_path = filedialog.askopenfilename(title="Select Accounts File", filetypes=[("Text Files", "*.txt"), ("All files", "*.*")])
        if not file_path: return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                accounts_text = f.read()
            self.accounts_textbox.delete("1.0", tk.END)
            self.accounts_textbox.insert("1.0", accounts_text)
            main_logger.info(f"Loaded {len(accounts_text.splitlines())} accounts from {file_path}")
        except Exception as e:
            self.show_message_dialog("Error Reading File", f"Could not read the accounts file.\nError: {e}", "error")

    def _create_settings_tab(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        
        threads_label = ctk.CTkLabel(parent, text="Threads:"); threads_label.grid(row=0, column=0, sticky="w", padx=10, pady=10)
        ToolTip(threads_label, "Number of concurrent browser sessions to run.")
        self.threads_slider = ctk.CTkSlider(parent, from_=1, to=10, number_of_steps=9, command=lambda v: self.threads_value_label.configure(text=str(int(v))))
        self.threads_slider.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        self.threads_value_label = ctk.CTkLabel(parent, text="1", width=20); self.threads_value_label.grid(row=0, column=2, sticky="w", padx=10, pady=10)

        delay_label = ctk.CTkLabel(parent, text="Delay (sec):"); delay_label.grid(row=1, column=0, sticky="w", padx=10, pady=10)
        ToolTip(delay_label, "Random delay range between checking each link.")
        delay_inner = ctk.CTkFrame(parent, fg_color="transparent"); delay_inner.grid(row=1, column=1, columnspan=2, sticky="ew", padx=10)
        self.delay_min_entry = ctk.CTkEntry(delay_inner, width=80); self.delay_min_entry.pack(side="left")
        ctk.CTkLabel(delay_inner, text="to").pack(side="left", padx=10)
        self.delay_max_entry = ctk.CTkEntry(delay_inner, width=80); self.delay_max_entry.pack(side="left")
        
        self.headless_var = ctk.BooleanVar()
        self.headless_check = ctk.CTkCheckBox(parent, text="Headless Mode", variable=self.headless_var)
        self.headless_check.grid(row=2, column=1, sticky='w', padx=10, pady=10)
        ToolTip(self.headless_check, "Run browsers in the background. Disable to see browser windows and solve CAPTCHAs.")

    def _create_progress_widgets(self, parent):
        frame = ctk.CTkFrame(parent); frame.grid_columnconfigure(3, weight=1)
        
        self.start_btn = ctk.CTkButton(frame, text="Start", command=self.start_checking, height=35, font=ctk.CTkFont(weight="bold"))
        self.start_btn.grid(row=0, column=0, rowspan=2, padx=(10, 5), pady=5, sticky="ns")
        self.pause_btn = ctk.CTkButton(frame, text="Pause", command=self.toggle_pause_resume, height=35, state="disabled")
        self.pause_btn.grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky="ns")
        self.stop_btn = ctk.CTkButton(frame, text="Stop", command=self.stop_checking, height=35, state="disabled", fg_color="#C62828", hover_color="#B71C1C")
        self.stop_btn.grid(row=0, column=2, rowspan=2, padx=5, pady=5, sticky="ns")
        
        self.status_label = ctk.CTkLabel(frame, text="Status: Ready", anchor="w"); self.status_label.grid(row=0, column=3, padx=10, sticky="sew")
        self.progress_bar = ctk.CTkProgressBar(frame); self.progress_bar.set(0); self.progress_bar.grid(row=1, column=3, padx=10, pady=(0,5), sticky="new")
        
        stats_frame = ctk.CTkFrame(frame, fg_color="transparent"); stats_frame.grid(row=0, column=4, rowspan=2, padx=10, pady=5, sticky="e")
        stat_font = ctk.CTkFont(size=12);
        self.stats_labels = {
            "processed": ctk.CTkLabel(stats_frame, font=stat_font, text="Processed: 0"), "working": ctk.CTkLabel(stats_frame, font=stat_font, text="Working: 0"),
            "failed": ctk.CTkLabel(stats_frame, font=stat_font, text="Failed: 0"), "rate_limit": ctk.CTkLabel(stats_frame, font=stat_font, text="Rate Limit: 0"),
            "login_fails": ctk.CTkLabel(stats_frame, font=stat_font, text="Login Fails: 0"), "errors": ctk.CTkLabel(stats_frame, font=stat_font, text="Errors: 0")
        }
        self.stats_labels['processed'].grid(row=0, column=0, sticky='w', padx=5); self.stats_labels['working'].grid(row=0, column=1, sticky='w', padx=5)
        self.stats_labels['failed'].grid(row=0, column=2, sticky='w', padx=5); self.stats_labels['rate_limit'].grid(row=1, column=0, sticky='w', padx=5)
        self.stats_labels['login_fails'].grid(row=1, column=1, sticky='w', padx=5); self.stats_labels['errors'].grid(row=1, column=2, sticky='w', padx=5)
        return frame

    def load_settings_to_ui(self):
        s = self.app_config.get("settings", {})
        self.input_file_entry.insert(0, s.get("input_file", DEFAULT_INPUT_FILE))
        self.output_dir_entry.insert(0, s.get("output_dir", DEFAULT_OUTPUT_DIR))
        self.delay_min_entry.insert(0, str(s.get("delay_min", 3.0)))
        self.delay_max_entry.insert(0, str(s.get("delay_max", 7.0)))
        self.headless_var.set(s.get("headless", True))
        num_threads = s.get("num_threads", 2)
        self.threads_slider.set(num_threads); self.threads_value_label.configure(text=str(num_threads))
        # This fixes the bug by loading raw text instead of trying to join a list of dicts
        self.accounts_textbox.insert("1.0", self.app_config.get("accounts_text", ""))

    def save_ui_to_config(self):
        try:
            settings = self.app_config['settings']
            settings["input_file"] = self.input_file_entry.get(); settings["output_dir"] = self.output_dir_entry.get()
            settings["delay_min"] = float(self.delay_min_entry.get()); settings["delay_max"] = float(self.delay_max_entry.get())
            settings["headless"] = self.headless_var.get(); settings["num_threads"] = int(self.threads_slider.get())
            settings["theme"] = ctk.get_appearance_mode().lower(); settings["window_geometry"] = self.root.geometry()
            # This fixes the bug by saving raw text
            self.app_config['accounts_text'] = self.accounts_textbox.get("1.0", tk.END).strip()
            self.config_manager.save_config(self.app_config)
        except (ValueError, TclError) as e: main_logger.warning(f"Could not save UI to config: {e}")

    def validate_inputs(self) -> bool:
        accounts = [line.strip() for line in self.accounts_textbox.get("1.0", tk.END).strip().splitlines() if line.strip() and ':' in line]
        if not accounts: self.show_message_dialog("Input Error", "Please provide at least one account in email:password format.", "error"); return False
        if not Path(self.input_file_entry.get()).is_file(): self.show_message_dialog("Input Error", "Please select a valid input file.", "error"); return False
        try: float(self.delay_min_entry.get()); float(self.delay_max_entry.get())
        except ValueError: self.show_message_dialog("Input Error", "Delay values must be valid numbers.", "error"); return False
        return True

    def _set_ui_state(self, is_running: bool):
        state = "disabled" if is_running else "normal"
        self.start_btn.configure(state=state)
        self.tab_view.configure(state=state)
        self.pause_btn.configure(state="normal" if is_running else "disabled")
        self.stop_btn.configure(state="normal" if is_running else "disabled")
        if not is_running: self.pause_btn.configure(text="Pause")

    def start_checking(self):
        if self.is_running: return
        self.save_ui_to_config()
        if not self.validate_inputs(): return
        self.is_running = True; self._set_ui_state(True)
        
        accounts_text = self.app_config.get('accounts_text', '')
        accounts_data = [line.strip().split(":", 1) for line in accounts_text.splitlines() if line.strip() and ':' in line]
        accounts = [Account(email=e, password=p) for e, p in accounts_data]

        self.checker = LinkedInChecker(self.app_config, accounts, self)
        self.update_status("Status: Starting..."); self.progress_bar.set(0); self.update_stats(Stats())
        self.checker_thread = threading.Thread(target=self.checker.run, name="MainChecker", daemon=True)
        self.checker_thread.start()

    def on_checking_finished(self, stopped: bool = False):
        self.is_running = False; self._set_ui_state(False)
        if stopped: self.status_label.configure(text="Status: Stopped by user.")
        else:
            self.status_label.configure(text="Status: Completed")
            if self.checker:
                 msg = (f"Finished checking links.\n\nProcessed: {self.checker.stats.total_processed}\nWorking Links: {self.checker.stats.working_found}\n"
                       f"Failed/Invalid: {self.checker.stats.failed_or_invalid}\nRate Limited: {self.checker.stats.link_captcha_failures}\n"
                       f"Login Fails: {self.checker.stats.login_failures}\nErrors: {self.checker.stats.errors}")
                 self.show_message_dialog("Checking Complete", msg)

    def toggle_pause_resume(self):
        if not self.is_running or not self.checker: return
        if self.checker.is_paused: self.checker.resume(); self.pause_btn.configure(text="Pause"); self.update_status("Status: Resuming...")
        else: self.checker.pause(); self.pause_btn.configure(text="Resume"); self.update_status("Status: Paused")

    def stop_checking(self):
        if self.is_running and self.checker: self.checker.stop(); self.update_status("Status: Stopping...")

    def on_closing(self):
        if self.is_running:
            if messagebox.askokcancel("Confirm Exit", "The checker is running. Are you sure you want to stop and exit?"):
                self.stop_checking()
                if self.checker_thread: self.checker_thread.join(5)
            else: return
        self.save_ui_to_config(); self.root.destroy()

    def set_total_links(self, total: int): self.total_links = total
    def update_live_status(self, current: int, total: int, active: int, max_threads: int):
        self.root.after(0, self.update_status, f"Status: Processing {current}/{total} | Threads: {active}/{max_threads}")
    def update_stats_and_progress(self, stats: Stats): self.root.after(0, self.update_stats, stats)
    
    def update_status(self, text: str): self.status_label.configure(text=text)
    def update_stats(self, stats: Stats):
        self.stats_labels['processed'].configure(text=f"Processed: {stats.total_processed}")
        self.stats_labels['working'].configure(text=f"Working: {stats.working_found}")
        self.stats_labels['failed'].configure(text=f"Failed: {stats.failed_or_invalid}")
        self.stats_labels['rate_limit'].configure(text=f"Rate Limit: {stats.link_captcha_failures}")
        self.stats_labels['login_fails'].configure(text=f"Login Fails: {stats.login_failures}")
        self.stats_labels['errors'].configure(text=f"Errors: {stats.errors}")
        if self.total_links > 0: self.progress_bar.set(stats.total_processed / self.total_links)

    def show_captcha_prompt(self, email: str) -> bool:
        self.root.after(0, self._ask_captcha_question, email)
        return self.captcha_response_queue.get()
    def _ask_captcha_question(self, email: str):
        msg = (f"A security check (e.g., CAPTCHA) was detected for {email}.\nPlease solve it in the browser window.\n\nClick 'Yes' once logged in, or 'No' to skip.");
        result = messagebox.askyesno("Manual Action Required", msg)
        self.captcha_response_queue.put(result)

    def show_message_dialog(self, title: str, message: str, msg_type: str = "info"):
        def _show():
            if msg_type == "error": messagebox.showerror(title, message)
            elif msg_type == "warning": messagebox.showwarning(title, message)
            else: messagebox.showinfo(title, message)
        self.root.after(0, _show)

    def _start_log_processor(self):
        def process():
            try:
                self.log_textbox.configure(state="normal")
                while True: self.log_textbox.insert(tk.END, self.log_queue.get_nowait() + "\n")
            except queue.Empty: pass
            finally: self.log_textbox.see(tk.END); self.log_textbox.configure(state="disabled")
            self.root.after(250, process)
        self.root.after(100, process)

    def run(self): self.root.mainloop()


# --- Main Execution ---
def check_prerequisites():
    missing = []
    if not SELENIUM_AVAILABLE: missing.append("selenium")
    if not BS4_AVAILABLE: missing.append("beautifulsoup4")
    if not GUI_AVAILABLE: missing.append("customtkinter Pillow") # Added Pillow
    if not UNDETECTED_CHROME_AVAILABLE: print("Warning: 'undetected-chromedriver' not found. Stealth may be reduced. (pip install undetected-chromedriver)")
    if not SELENIUM_STEALTH_AVAILABLE: print("Warning: 'selenium-stealth' not found. Stealth may be reduced. (pip install selenium-stealth)")
    if missing:
        msg = f"ERROR: Missing critical libraries. Please run:\n\npip install {' '.join(missing)}"
        print(msg)
        try: root = tk.Tk(); root.withdraw(); messagebox.showerror("Missing Dependencies", msg)
        except Exception: pass
        sys.exit(1)

def main():
    check_prerequisites()
    app = LinkedInCheckerGUI()
    app.run()

if __name__ == "__main__":
    main()
