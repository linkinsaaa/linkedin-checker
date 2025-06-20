# linkedin_checker.py
# -*- coding: utf-8 -*-
"""
LinkURL - Advanced Link Checker
Author: Gemini
Version: 7.0 (The Final Stand)
"""

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
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import os
from enum import Enum, auto

# --- Dynamic Dependency Imports ---
try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        ElementClickInterceptedException,
        NoSuchElementException,
        StaleElementReferenceException,
        TimeoutException,
        WebDriverException,
    )
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.remote.webelement import WebElement
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.wait import WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, TclError
    import customtkinter as ctk

    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


# --- Constants & Paths ---
if getattr(sys, 'frozen', False):
    APP_PATH = Path(sys.executable).parent
else:
    APP_PATH = Path(__file__).parent

CONFIG_FILE = APP_PATH / "config.json"
LOG_DIR = APP_PATH / "logs"
SESSIONS_DIR = APP_PATH / "sessions"
STATE_FILE = APP_PATH / "checker.state"
DEFAULT_INPUT_FILE = str(APP_PATH / "linkedin_links.txt")
DEFAULT_OUTPUT_DIR = str(APP_PATH / "results")

# --- Enums for Statuses ---
class LoginStatus(Enum):
    SUCCESS = auto()
    FAIL_BAD_CREDS = auto()
    FAIL_CAPTCHA = auto()
    FAIL_TIMEOUT = auto()
    FAIL_UNKNOWN = auto()

# --- Default Configuration ---
DEFAULT_CONFIG = {
    "settings": {
        "input_file": DEFAULT_INPUT_FILE,
        "output_dir": DEFAULT_OUTPUT_DIR,
        "delay_min": 3.0,
        "delay_max": 7.0,
        "headless": True,
        "browser_type": "chrome",
        "language": "en",
        "theme": "dark",
        "color_theme": "green",
        "num_threads": 2,
        "window_geometry": "1050x900",
        "account_rest_duration_minutes": 30
    },
    "accounts": [],
    "selectors": {
        "username_field": ["#username", "#session_key"],
        "password_field": ["#password", "#session_password"],
        "login_submit_button": ["//button[@type='submit']", "button.sign-in-form__submit-button"],
        "login_error_message": [".form__input--error", ".form__message--error", "[data-test-id='error-message']", ".error-for"],
        "login_success_indicator": ["//header[contains(@class, 'global-nav')]", "#global-nav"],
        "cookie_accept_button": [
            "//button[@data-control-name='accept_cookies']",
            "//button[contains(., 'Accept')]",
            "//button[contains(., 'Agree')]",
        ],
        "account_chooser_indicator": ["#choose-account-page", "h1.account-chooser__title"],
        "account_chooser_button_template": ["//button[contains(., '{email}')]"],
        "action_buttons": [
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start free trial')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'try premium for free')]",
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start your free month')]",
            "//button[@data-test-id='accept-gift-button']",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'activate')]"
        ]
    },
    "keywords": {
        "rate_limit": ["security verification", "captcha-internal", "are you human", "challenge", "checkpoint", "robot"],
        "unavailable": [
            "offer has already been redeemed", "offer is no longer available",
            "this offer isn't available", "link has expired", "page not found",
            "404", "this page doesn’t exist", "this page is unavailable",
            "an error has occurred", "something went wrong", "offer unavailable"
        ],
        "already_premium": [
            "already a premium member", "your current plan",
            "manage premium subscription", "welcome to premium"
        ],
        "trial_positive": [
            "claim this exclusive offer", "get premium free", "start your free month",
            "free trial", "claim your gift", "redeem your gift", "activate your gift",
            "premium gift", "start premium", "get premium", "unlock premium",
            "your free trial awaits", "special offer for you", "try premium for 0",
            "1-month free trial", "accept your free upgrade", "start my free trial",
            "all you need to do is activate"
        ],
        "payment_form": [
            "card number", "credit card", "payment method", "billing address",
            "paypal", "add a card", "confirm purchase", "review your order", "select payment"
        ]
    },
    "urls": {
        "login": "https://www.linkedin.com/login",
        "feed": "https://www.linkedin.com/feed/",
        "auth_wall_substring": "authwall"
    },
    "user_agents": [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    ]
}

# --- Integrated Translation System (Fallback) ---
try:
    from translations import (
        _, set_language as set_app_language, LANGUAGE_DISPLAY_NAMES
    )
except ImportError:
    print("Warning: translations.py not found. Using default English strings.")
    LANGUAGE_DISPLAY_NAMES = {"en": "English", "ar": "العربية"}
    _CURRENT_LANGUAGE = "en"
    _TRANSLATIONS = {
        "en": {
            "app_title": "LinkURL - Link Checker v7.0",
            "tab_accounts_and_files": "Accounts & Files",
            "tab_settings": "Settings",
            "email_label": "Accounts (email:password, one per line):",
            "input_file_label": "Input Links File:",
            "output_dir_label": "Output Directory:",
            "browse_button": "Browse...",
            "browser_label": "Browser:",
            "headless_mode_checkbox": "Headless Mode (More Stable)",
            "delay_label": "Delay (sec):",
            "threads_label": "Threads:",
            "delay_to_label": "to",
            "start_button": "Start Checking",
            "pause_button": "Pause",
            "resume_button": "Resume",
            "stop_button": "Stop",
            "status_ready": "Status: Ready",
            "status_starting": "Status: Starting...",
            "status_processing_link": "Status: Processing link {current}/{total} | Threads: {active_threads}",
            "status_paused": "Status: Paused",
            "status_resuming": "Status: Resuming...",
            "status_stopping": "Status: Stopping...",
            "status_completed": "Status: Completed",
            "security_challenge_message": "A security check (like a CAPTCHA) was detected for {email}.\n\nPlease solve it in the browser window.\n\nClick 'Yes' once you have solved it, or 'No' to skip this account.",
            "status_generated_on": "Generated on: {date}",
            "total_found_label": "Total Found: {count}",
            "confidence_label": "Confidence: {confidence}",
            "stats_processed_prefix": "Processed",
            "stats_working_prefix": "Working",
            "stats_failed_prefix": "Failed",
            "stats_link_captcha_prefix": "Link Captcha",
            "stats_errors_prefix": "Errors",
            "stats_login_fails_prefix": "Login Fails",
            "log_section_title": "Live Log",
            "settings_language_label": "Language:",
            "headless_note_label": "Note: Disable Headless Mode to solve login security checks.",
            "confirm_exit_title": "Confirm Exit",
            "confirm_exit_message": "The checker is running. Are you sure you want to stop and exit?",
            "error_dialog_title": "Input Error",
            "missing_email_password_error": "Please provide at least one account in the format 'email:password'.",
            "missing_input_file_error": "Please select an input file.",
            "invalid_delay_error": "Delay values must be valid numbers.",
            "security_challenge_title": "Manual Action Required",
            "security_challenge_detected_log": "Security challenge detected for {email}. Pausing for manual intervention.",
            "security_challenge_solved_log": "Security challenge for {email} appears to be resolved. Resuming.",
            "security_challenge_failed_log": "User skipped or failed to resolve the security challenge for {email}.",
            "checking_complete_dialog_title": "Checking Complete",
            "checking_complete_dialog_message": "Finished checking links.\n\nProcessed: {total_processed}\nWorking Links: {working_found}\nFailed/Invalid: {failed_or_invalid}\nLink Captcha/RL: {link_captcha_failures}\nLogin Fails: {login_failures}\nErrors: {errors}",
            "no_accounts_configured_error": "No accounts configured. Please add accounts.",
            "no_links_to_process_error": "No unique, valid links found in the input file.",
            "processing_link_info": "Processing Link {link_index}/{total_links}: {url} (from Line {line_num}) with {email}",
            "rate_limit_detected_details": "Rate limit / CAPTCHA detected on link page. Keywords: {keywords}",
            "redirected_to_login_details": "Redirected to login/authwall page.",
            "session_lost_details": "Session lost, will attempt to re-login. Re-queueing link.",
            "redirected_to_feed_details": "Redirected to main feed; link is likely invalid.",
            "offer_unavailable_details": "Offer expired, unavailable, or already redeemed. Keywords: {keywords}",
            "already_premium_details": "Account is already a Premium member. Keywords: {keywords}",
            "trial_gift_found_details": "Potential trial/gift offer found.",
            "no_clear_trial_indicators_details": "No clear trial indicators found; link may be invalid.",
            "page_load_timeout_error": "Page load timed out.",
            "webdriver_error_details": "WebDriver error: {error}",
            "saved_working_links_info": "Saved {count} working links to: {file_path}",
            "saved_detailed_results_info": "Saved detailed JSON results to: {file_path}",
            "language_restart_title": "Restart Required",
            "language_restart_message": "Language has been changed. The application will now restart to apply the changes.",
            "input_file_not_found_error": "Input file not found: {file_path}",
            "found_links_to_process_info": "{count} unique links found to process.",
            "error_reading_links_error": "Error reading links: {error}",
            "loaded_state_info": "Loaded state file. Skipped {count} already processed links.",
            "cleared_state_file_info": "New run started. Cleared old state file."
        },
    }
    def _(key: str, **kwargs) -> str:
        lang_dict = _TRANSLATIONS.get(_CURRENT_LANGUAGE, _TRANSLATIONS["en"])
        translation = lang_dict.get(key, key)
        return translation.format(**kwargs) if kwargs else translation
    def set_app_language(lang_code: str):
        global _CURRENT_LANGUAGE
        if lang_code in LANGUAGE_DISPLAY_NAMES:
            _CURRENT_LANGUAGE = lang_code
        else:
            _CURRENT_LANGUAGE = "en"

# --- Dataclasses ---
@dataclass
class LinkResult:
    link: str
    status: str
    result_details: str = ""
    final_url: Optional[str] = None
    line_num: Optional[int] = None
    confidence: Optional[str] = None
    error: Optional[str] = None
    account_email: Optional[str] = None

@dataclass
class Account:
    email: str
    password: str
    last_rate_limited_at: Optional[datetime] = field(default=None, repr=False)
    consecutive_rate_limits: int = field(default=0, repr=False)

    def is_resting(self, duration_minutes: int) -> bool:
        if not self.last_rate_limited_at:
            return False
        return datetime.now() < self.last_rate_limited_at + timedelta(minutes=duration_minutes)

@dataclass
class Stats:
    total_processed: int = 0
    working_found: int = 0
    failed_or_invalid: int = 0
    link_captcha_failures: int = 0
    login_failures: int = 0
    errors: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

# --- Logger Setup ---
class QueueHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord):
        self.log_queue.put(self.format(record))

def setup_logging(log_level: int = logging.INFO, log_queue: Optional[queue.Queue] = None) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_format = '%(asctime)s | %(levelname)-8s | %(threadName)-15s | %(message)s'
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
    
    logging.basicConfig(level=log_level, format=log_format, handlers=[logging.StreamHandler(sys.stdout)], force=True)
    
    logger = logging.getLogger("LinkURLChecker")
    logger.propagate = False
    
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.addHandler(logging.StreamHandler(sys.stdout))
        
    try:
        file_handler = logging.FileHandler(LOG_DIR / f'linkurl_checker_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Could not set up file logger: {e}")

    if log_queue:
        queue_handler = QueueHandler(log_queue)
        queue_handler.setFormatter(formatter)
        logger.addHandler(queue_handler)

    return logger

main_logger = setup_logging()

# --- Robust Driver Manager ---
class DriverManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_type = config['settings'].get('browser_type', 'chrome').lower()
        self.headless = config['settings'].get('headless', True)
        self.user_agents = config.get('user_agents', [])
        SESSIONS_DIR.mkdir(exist_ok=True)

    def _get_cookie_path(self, email: str) -> Path:
        sanitized_email = re.sub(r'[^\w\-_\.]', '_', email)
        return SESSIONS_DIR / f"{sanitized_email}.json"

    def save_cookies(self, driver: WebDriver, email: str):
        cookie_path = self._get_cookie_path(email)
        try:
            cookies = driver.get_cookies()
            with cookie_path.open('w') as f:
                json.dump(cookies, f)
            main_logger.debug(f"Saved session cookies for {email} to {cookie_path}")
        except Exception as e:
            main_logger.error(f"Failed to save cookies for {email}: {e}")

    def load_cookies(self, driver: WebDriver, email: str) -> bool:
        cookie_path = self._get_cookie_path(email)
        if not cookie_path.exists():
            return False
        try:
            with cookie_path.open('r') as f:
                cookies = json.load(f)
            base_url = "https://www.linkedin.com/"
            driver.get(base_url)
            loaded_count = 0
            for cookie in cookies:
                try:
                    if 'expiry' in cookie and isinstance(cookie['expiry'], float):
                        cookie['expiry'] = int(cookie['expiry'])
                    if 'domain' in cookie and not base_url.endswith(cookie['domain']):
                         continue
                    driver.add_cookie(cookie)
                    loaded_count += 1
                except WebDriverException:
                    continue
            main_logger.info(f"Loaded {loaded_count}/{len(cookies)} session cookies for {email}.")
            return loaded_count > 0
        except Exception as e:
            main_logger.error(f"Failed to load or process cookies file for {email}: {e}", exc_info=True)
            return False

    def create_driver(self) -> WebDriver:
        user_agent = random.choice(self.user_agents)
        if self.browser_type == "chrome":
            options = ChromeOptions()
            if self.headless: options.add_argument("--headless=new")
            options.add_argument("--disable-gpu"); options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage"); options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument(f"user-agent={user_agent}")
            try:
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            except Exception:
                driver = webdriver.Chrome(options=options)
        else: # Firefox
            options = FirefoxOptions()
            if self.headless: options.add_argument("--headless")
            options.set_preference("general.useragent.override", user_agent)
            options.set_preference("dom.webdriver.enabled", False)
            options.set_preference('useAutomationExtension', False)
            try:
                service = FirefoxService(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=options)
            except Exception:
                driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(60)
        driver.set_window_size(random.randint(1200, 1920), random.randint(800, 1080))
        return driver


# --- Core Checker Class ---
class LinkedInChecker:
    def __init__(self, config: Dict[str, Any], accounts: List[Account], translator: Callable, gui_instance: Optional['LinkedInCheckerGUI'] = None):
        self.config = config
        self.settings = config['settings']
        self.all_accounts = accounts
        self.translate = translator
        self.gui = gui_instance
        self.driver_manager = DriverManager(config)
        self.num_threads = self.settings.get('num_threads', 1)
        self.delay_min = float(self.settings.get('delay_min', 2.0))
        self.delay_max = float(self.settings.get('delay_max', 5.0))
        self.should_stop = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.is_paused = False
        self.stats = Stats()
        self.working_links: List[LinkResult] = []
        self.failed_links: List[LinkResult] = []
        self.links_to_process_queue = queue.Queue()
        self.processed_links_log = set()
        self.results_lock = threading.Lock()
        self.account_manager_lock = threading.Lock()
        self.state_file_lock = threading.Lock()
        self.available_accounts = list(self.all_accounts)
        main_logger.info(f"Checker initialized with {self.num_threads} threads for browser '{self.settings.get('browser_type', 'chrome')}'")

    def read_and_queue_links(self) -> int:
        input_file = Path(self.settings.get('input_file', ''))
        if not input_file.exists():
            main_logger.error(self.translate("input_file_not_found_error", file_path=str(input_file)))
            return 0
        
        unique_links = {}
        try:
            with input_file.open('r', encoding='utf-8', errors='ignore') as f: content = f.read()
            url_pattern = re.compile(r'https?://(?:www\.)?linkedin\.com/(?:premium/|sales/|e/)[^\s\'"<>(),;]+')
            
            for i, line in enumerate(content.splitlines()):
                for match in url_pattern.finditer(line):
                    url = match.group(0).strip(".,;")
                    url = re.sub(r'[?&](trk|trkInfo|trkDetails|session_redirect|lipi|midToken|fromEmail|ut|messageThreadKey|referralCookie|upsellOrderOrigin|anchor|anchorElement)=[^&"]*', '', url, flags=re.IGNORECASE)
                    if url.endswith('?'): url = url[:-1]
                    if url not in unique_links and url not in self.processed_links_log:
                        unique_links[url] = i + 1
            
            for url, line_num in unique_links.items():
                self.links_to_process_queue.put((url, line_num))
            
            count = len(unique_links)
            main_logger.info(self.translate("found_links_to_process_info", count=count))
            return count
        except Exception as e:
            main_logger.error(self.translate("error_reading_links_error", error=str(e)))
            return 0
            
    def _find_element(self, driver: WebDriver, selectors: List[str], timeout: int = 10) -> Optional[WebElement]:
        for selector in selectors:
            try:
                by = By.XPATH if selector.startswith(("//", "./")) else By.CSS_SELECTOR
                return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((by, selector)))
            except TimeoutException:
                continue
        return None

    def _click_element(self, driver: WebDriver, element: Union[WebElement, List[str]], timeout: int = 10):
        target = self._find_element(driver, element, timeout) if isinstance(element, list) else element
        if not target: raise NoSuchElementException(f"Could not find element from selectors: {element}")
        try:
            ActionChains(driver).move_to_element(target).pause(random.uniform(0.1, 0.4)).click().perform()
        except StaleElementReferenceException:
            main_logger.warning("Stale element on click, will retry operation.")
            raise

    def get_account(self) -> Optional[Account]:
        with self.account_manager_lock:
            duration = self.settings.get('account_rest_duration_minutes', 30)
            non_resting = [acc for acc in self.available_accounts if not acc.is_resting(duration)]
            if non_resting:
                account = random.choice(non_resting)
                self.available_accounts.remove(account)
                return account
            elif self.available_accounts:
                main_logger.info("All available accounts are currently resting. Waiting...")
            return None

    def release_account(self, account: Account, should_rest: bool = False):
        with self.account_manager_lock:
            if should_rest:
                account.last_rate_limited_at = datetime.now()
                duration = self.settings.get('account_rest_duration_minutes', 30)
                main_logger.warning(f"Account {account.email} is resting for {duration} mins due to LOGIN CAPTCHA.")
            if account not in self.available_accounts:
                self.available_accounts.append(account)

    def _is_logged_in(self, driver: WebDriver, timeout: int = 7) -> bool:
        try:
            return self._find_element(driver, self.config['selectors']['login_success_indicator'], timeout=timeout) is not None
        except WebDriverException:
            return False

    def setup_and_login(self, account: Account) -> Tuple[Optional[WebDriver], LoginStatus]:
        main_logger.info(f"Setting up WebDriver for account {account.email}...")
        driver = self.driver_manager.create_driver()
        try:
            if self.driver_manager.load_cookies(driver, account.email):
                driver.get(self.config['urls']['feed'])
                if self._is_logged_in(driver):
                    main_logger.info(f"Successfully resumed session for {account.email} using cookies.")
                    return driver, LoginStatus.SUCCESS
                main_logger.warning(f"Cookie session for {account.email} is invalid. Proceeding with full login.")
                driver.delete_all_cookies()

            driver.get(self.config['urls']['login'])
            main_logger.info(f"Attempting full login for {account.email}...")
            
            self._find_element(driver, self.config['selectors']['username_field']).send_keys(account.email)
            self._find_element(driver, self.config['selectors']['password_field']).send_keys(account.password)
            self._click_element(driver, self.config['selectors']['login_submit_button'])

            try:
                wait = WebDriverWait(driver, 45)
                wait.until(EC.any_of(
                    EC.presence_of_element_located((By.XPATH, self.config['selectors']['login_success_indicator'][0])),
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.config['selectors']['login_error_message'][0])),
                    EC.url_contains("checkpoint"), EC.url_contains("challenge")
                ))
            except TimeoutException:
                main_logger.error(f"Login timed out for {account.email}. Page did not transition to a known state.")
                driver.quit()
                return None, LoginStatus.FAIL_TIMEOUT

            current_url = driver.current_url.lower()
            if self._is_logged_in(driver, timeout=5):
                main_logger.info(f"Login successful for {account.email}.")
                self.driver_manager.save_cookies(driver, account.email)
                return driver, LoginStatus.SUCCESS

            elif any(s in current_url for s in self.config['keywords']['rate_limit']):
                main_logger.warning(self.translate("security_challenge_detected_log", email=account.email))
                if self.gui and not self.settings.get('headless', True):
                    if self.gui.show_security_challenge_dialog(account.email) and self._is_logged_in(driver):
                        main_logger.info(self.translate("security_challenge_solved_log", email=account.email))
                        self.driver_manager.save_cookies(driver, account.email)
                        return driver, LoginStatus.SUCCESS
                driver.quit()
                return None, LoginStatus.FAIL_CAPTCHA
            else:
                error_el = self._find_element(driver, self.config['selectors']['login_error_message'], timeout=2)
                reason = error_el.text.strip() if error_el else f"Unexpected page: {current_url}"
                main_logger.warning(f"Login failed for {account.email}. Reason: {reason}")
                driver.quit()
                return None, LoginStatus.FAIL_BAD_CREDS
        except Exception as e:
            main_logger.error(f"Critical error during login for {account.email}: {type(e).__name__}", exc_info=True)
            if driver: driver.quit()
            return None, LoginStatus.FAIL_UNKNOWN

    def analyze_link_page(self, driver: WebDriver, url: str) -> LinkResult:
        try:
            driver.get(url)
            WebDriverWait(driver, 25).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            page_source = driver.page_source.lower()
            current_url = driver.current_url.lower()

            auth_wall_url = self.config['urls'].get('auth_wall_substring', 'authwall')
            if auth_wall_url in current_url or "/login" in current_url:
                return LinkResult(link=url, status="SESSION_LOST", result_details=self.translate("redirected_to_login_details"), final_url=current_url)

            # --- Check for definitive failures ---
            for reason, keywords in {
                "rate_limit": self.config['keywords']['rate_limit'],
                "unavailable": self.config['keywords']['unavailable'],
                "already_premium": self.config['keywords']['already_premium']
            }.items():
                found_keywords = [kw for kw in keywords if kw in page_source or kw in current_url]
                if found_keywords:
                    details_key = f"{reason}_details"
                    status = "RATE_LIMIT" if reason == "rate_limit" else "FAILED"
                    return LinkResult(link=url, status=status, result_details=self.translate(details_key, keywords=', '.join(found_keywords)), final_url=current_url)
            
            if "feed" in current_url and all(s not in url for s in ["premium", "redeem", "gift"]):
                return LinkResult(link=url, status="FAILED", result_details=self.translate("redirected_to_feed_details"), final_url=current_url)

            # --- Score for success ---
            score, details = 0, []
            if any(self._find_element(driver, [xpath], timeout=1) for xpath in self.config['selectors']['action_buttons']):
                score += 50; details.append("Action button")
            if any(kw in page_source for kw in self.config['keywords']['payment_form']):
                score += 30; details.append("Payment form")
            if any(kw in page_source for kw in self.config['keywords']['trial_positive']):
                score += 25; details.append("Trial keyword")
            
            if score >= 40:
                confidence = "HIGH" if score >= 60 else "MEDIUM"
                return LinkResult(link=url, status="WORKING", result_details=f"{self.translate('trial_gift_found_details')} ({', '.join(details)})", confidence=confidence, final_url=current_url)
            
            return LinkResult(link=url, status="FAILED", result_details=self.translate("no_clear_trial_indicators_details"), final_url=current_url)
        except TimeoutException:
            return LinkResult(link=url, status="ERROR", result_details=self.translate("page_load_timeout_error"), error="TimeoutException")
        except WebDriverException as e:
            err_str = str(e).lower()
            if any(msg in err_str for msg in ["no such window", "target window already closed", "invalid session id"]):
                return LinkResult(link=url, status="SESSION_LOST", result_details=self.translate("session_lost_details"), error=str(e))
            return LinkResult(link=url, status="ERROR", result_details=self.translate("webdriver_error_details", error=str(e)[:100]), error=str(e))
        except Exception as e:
            main_logger.error(f"Unexpected error analyzing {url}: {e}", exc_info=True)
            return LinkResult(link=url, status="ERROR", result_details=f"Unexpected error: {str(e)[:100]}", error=str(e))

    def process_link_worker(self, worker_id: int):
        main_logger.info(f"Worker {worker_id} starting.")
        
        while not self.should_stop.is_set():
            self.pause_event.wait()
            if self.should_stop.is_set(): break

            account = self.get_account()
            if not account:
                if self.links_to_process_queue.empty():
                    main_logger.info(f"Worker {worker_id} found no links and no accounts, exiting.")
                    break 
                time.sleep(5) 
                continue

            main_logger.info(f"Worker {worker_id} acquired account {account.email}.")
            driver, login_status = self.setup_and_login(account)
            
            if login_status != LoginStatus.SUCCESS:
                main_logger.warning(f"Login failed for {account.email} with status {login_status.name}. Releasing account.")
                with self.results_lock: self.stats.login_failures += 1
                self.release_account(account, should_rest=(login_status == LoginStatus.FAIL_CAPTCHA))
                continue

            main_logger.info(f"Worker {worker_id} successfully started session for {account.email}.")
            while not self.should_stop.is_set():
                self.pause_event.wait()
                if self.should_stop.is_set(): break
                
                try:
                    url, line_num = self.links_to_process_queue.get_nowait()
                except queue.Empty:
                    main_logger.info(f"Worker {worker_id} found queue empty. Ending session for {account.email}.")
                    break
                
                if not driver or not driver.window_handles:
                    main_logger.warning(f"Browser for {account.email} closed unexpectedly. Re-queuing link {url}.")
                    self.links_to_process_queue.put((url, line_num))
                    break
                
                with self.results_lock:
                    link_index = self.stats.total_processed + 1
                    total_links = link_index + self.links_to_process_queue.qsize()
                if self.gui: self.gui.update_live_status(link_index, total_links)
                main_logger.info(f"Worker {worker_id} processing link {link_index}/{total_links}: {url}")
                
                result = self.analyze_link_page(driver, url)
                main_logger.info(f"Link analysis for {url} returned status: {result.status}. Details: {result.result_details}")
                
                if result.status == "SESSION_LOST":
                    main_logger.warning(f"Session lost for {account.email}. Re-queuing link and restarting session.")
                    self.links_to_process_queue.put((url, line_num))
                    break
                
                with self.results_lock:
                    self.stats.total_processed += 1
                    if result.status == "WORKING": self.stats.working_found += 1; self.working_links.append(result)
                    elif result.status == "RATE_LIMIT": self.stats.link_captcha_failures += 1; self.failed_links.append(result)
                    elif result.status == "ERROR": self.stats.errors += 1; self.failed_links.append(result)
                    else: self.stats.failed_or_invalid += 1; self.failed_links.append(result)
                    if self.gui: self.gui.update_stats_and_progress(self.stats)

                time.sleep(random.uniform(self.delay_min, self.delay_max))
            
            if driver: driver.quit()
            main_logger.info(f"Worker {worker_id} ending session for {account.email}, releasing account.")
            self.release_account(account)
            
        main_logger.info(f"Worker {worker_id} received stop signal and is exiting.")

    def save_results(self):
        if not self.working_links and not self.failed_links: return
        output_dir = Path(self.settings.get('output_dir', DEFAULT_OUTPUT_DIR))
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        self.stats.end_time = datetime.now()
        
        if self.working_links:
            path = output_dir / f"working_links_{timestamp}.txt"
            with path.open('w', encoding='utf-8') as f:
                f.write(f"# {self.translate('app_title')} - {self.translate('stats_working_prefix')}\n")
                f.write(f"# {self.translate('status_generated_on', date=datetime.now().isoformat())}\n\n")
                for res in sorted(self.working_links, key=lambda r: (r.confidence or '', r.link)):
                    f.write(f"{res.link} | {self.translate('confidence_label', confidence=res.confidence)} | {res.result_details}\n")
            main_logger.info(self.translate("saved_working_links_info", count=len(self.working_links), file_path=str(path)))
            
        path = output_dir / f"detailed_results_{timestamp}.json"
        with path.open('w', encoding='utf-8') as f:
            json.dump({
                "summary": {**asdict(self.stats), "duration_seconds": self.stats.end_time.timestamp() - self.stats.start_time.timestamp()},
                "results": {"working": [asdict(r) for r in self.working_links], "failed": [asdict(r) for r in self.failed_links]},
                "config_used": self.config
            }, f, indent=4, ensure_ascii=False, default=str)
        main_logger.info(self.translate("saved_detailed_results_info", file_path=str(path)))

    def run(self):
        self.should_stop.clear(); self.pause_event.set(); self.stats = Stats()
        self.working_links.clear(); self.failed_links.clear()
        self.available_accounts = list(self.all_accounts)
        for acc in self.available_accounts: acc.last_rate_limited_at = None
        while not self.links_to_process_queue.empty(): self.links_to_process_queue.get()
        
        if STATE_FILE.exists():
             STATE_FILE.unlink()
             main_logger.info(self.translate("cleared_state_file_info"))
            
        total_links = self.read_and_queue_links()
        if self.gui: self.gui.set_total_links(total_links)
        if not total_links or not self.all_accounts:
            main_logger.warning("No links or no accounts. Aborting.")
            return

        with ThreadPoolExecutor(max_workers=self.num_threads, thread_name_prefix="LinkChecker") as executor:
            futures = [executor.submit(self.process_link_worker, i + 1) for i in range(self.num_threads)]
            for future in as_completed(futures):
                try: future.result()
                except Exception as e: main_logger.error(f"Worker thread error: {e}", exc_info=True)

        if not self.should_stop.is_set(): main_logger.info("Checking process completed.")
        else: main_logger.info("Checking process was stopped by user.")
        self.save_results()

    def stop(self):
        main_logger.info("Stopping..."); self.should_stop.set(); self.pause_event.set()

# --- GUI Class ---
class LinkedInCheckerGUI:
    def __init__(self):
        if not GUI_AVAILABLE: raise RuntimeError("GUI libraries not installed.")
        self.config_manager = ConfigManager(CONFIG_FILE, DEFAULT_CONFIG)
        self.app_config = self.config_manager.load_config()
        set_app_language(self.app_config.get("settings", {}).get("language", "en"))
        
        self.root = ctk.CTk()
        self.log_queue = queue.Queue()
        global main_logger; main_logger = setup_logging(log_queue=self.log_queue)
        
        ctk.set_appearance_mode(self.app_config.get("settings", {}).get("theme", "dark"))
        ctk.set_default_color_theme(self.app_config.get("settings", {}).get("color_theme", "green"))
        
        self.checker: Optional[LinkedInChecker] = None
        self.checker_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.total_links = 0
        self.challenge_response_queue = queue.Queue()
        self._tab_name_keys = {"accounts_files": "tab_accounts_and_files", "settings": "tab_settings"}
        
        self._setup_ui()
        self.load_settings_to_ui()
        self._start_log_processor()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_ui(self):
        self.root.title(_("app_title"))
        self.root.geometry(self.app_config.get("settings", {}).get("window_geometry", "1050x900"))
        self.root.minsize(850, 750)
        self.root.grid_columnconfigure(0, weight=1); self.root.grid_rowconfigure(1, weight=1)
        top_frame = ctk.CTkFrame(self.root); top_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        top_frame.grid_columnconfigure(0, weight=1)
        log_frame = ctk.CTkFrame(self.root); log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_frame.grid_columnconfigure(0, weight=1); log_frame.grid_rowconfigure(1, weight=1)
        
        # Create Widgets
        ctk.CTkLabel(top_frame, text=_("app_title"), font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, pady=(10, 20))
        self.tab_view = ctk.CTkTabview(top_frame); self.tab_view.grid(row=1, column=0, sticky="nsew", padx=10)
        self.accounts_tab = self.tab_view.add(_(self._tab_name_keys["accounts_files"]))
        self.settings_tab = self.tab_view.add(_(self._tab_name_keys["settings"]))
        self._create_accounts_tab(self.accounts_tab)
        self._create_settings_tab(self.settings_tab)
        self._create_control_widgets(top_frame).grid(row=2, column=0, sticky="ew", padx=10, pady=(15, 10))
        self._create_progress_widgets(top_frame).grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(log_frame, text=_("log_section_title"), font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, pady=(8,5), padx=10, sticky="w")
        self.log_textbox = ctk.CTkTextbox(log_frame, wrap="word", state="disabled", font=("Consolas", 12)); self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def _create_accounts_tab(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(parent, text=_("email_label"), anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 2))
        self.accounts_textbox = ctk.CTkTextbox(parent, height=120, wrap="word"); self.accounts_textbox.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))
        ctk.CTkLabel(parent, text=_("input_file_label")).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.input_file_entry = ctk.CTkEntry(parent); self.input_file_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        ctk.CTkButton(parent, text=_("browse_button"), width=100, command=self.browse_input_file).grid(row=2, column=2, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(parent, text=_("output_dir_label")).grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.output_dir_entry = ctk.CTkEntry(parent); self.output_dir_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        ctk.CTkButton(parent, text=_("browse_button"), width=100, command=self.browse_output_dir).grid(row=3, column=2, sticky="ew", padx=10, pady=5)

    def _create_settings_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        perf_frame = ctk.CTkFrame(parent); perf_frame.grid(row=0, column=0, sticky="ew", pady=10); perf_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(perf_frame, text=_("threads_label")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.threads_slider = ctk.CTkSlider(perf_frame, from_=1, to=10, number_of_steps=9, command=lambda v: self.threads_value_label.configure(text=str(int(v)))); self.threads_slider.grid(row=0, column=1, sticky="ew", padx=10, pady=5)
        self.threads_value_label = ctk.CTkLabel(perf_frame, text="1"); self.threads_value_label.grid(row=0, column=2, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(perf_frame, text=_("delay_label")).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        delay_inner = ctk.CTkFrame(perf_frame, fg_color="transparent"); delay_inner.grid(row=1, column=1, columnspan=2, sticky="w", padx=10)
        self.delay_min_entry = ctk.CTkEntry(delay_inner, width=80); self.delay_min_entry.pack(side="left")
        ctk.CTkLabel(delay_inner, text=_("delay_to_label")).pack(side="left", padx=10)
        self.delay_max_entry = ctk.CTkEntry(delay_inner, width=80); self.delay_max_entry.pack(side="left")
        
        browser_frame = ctk.CTkFrame(parent); browser_frame.grid(row=1, column=0, sticky="ew", pady=10)
        ctk.CTkLabel(browser_frame, text=_("browser_label")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.browser_var = ctk.StringVar(value="chrome")
        ctk.CTkComboBox(browser_frame, values=["chrome", "firefox"], variable=self.browser_var).grid(row=0, column=1, padx=10, pady=5, sticky="w")
        self.headless_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(browser_frame, text=_("headless_mode_checkbox"), variable=self.headless_var).grid(row=0, column=2, padx=20, pady=5, sticky="w")
        ctk.CTkLabel(browser_frame, text=_("headless_note_label"), text_color="gray").grid(row=1, column=2, padx=20, pady=(0,5), sticky="w")
        
        app_frame = ctk.CTkFrame(parent); app_frame.grid(row=2, column=0, sticky="ew", pady=10)
        ctk.CTkLabel(app_frame, text=_("settings_language_label")).pack(side="left", padx=10)
        self.lang_var = ctk.StringVar()
        ctk.CTkComboBox(app_frame, values=[f"{n} ({c})" for c, n in LANGUAGE_DISPLAY_NAMES.items()], variable=self.lang_var, command=self.change_language).pack(side="left", padx=10)

    def _create_control_widgets(self, parent):
        frame = ctk.CTkFrame(parent); frame.grid_columnconfigure((0, 1, 2), weight=1)
        font = ctk.CTkFont(size=16, weight="bold")
        self.start_btn = ctk.CTkButton(frame, text=_("start_button"), command=self.start_checking, font=font, height=45, fg_color="#2E7D32", hover_color="#1B5E20"); self.start_btn.grid(row=0, column=0, padx=8, pady=5, sticky="ew")
        self.pause_btn = ctk.CTkButton(frame, text=_("pause_button"), command=self.toggle_pause_resume, font=font, height=45, state="disabled"); self.pause_btn.grid(row=0, column=1, padx=8, pady=5, sticky="ew")
        self.stop_btn = ctk.CTkButton(frame, text=_("stop_button"), command=self.stop_checking, font=font, height=45, state="disabled", fg_color="#C62828", hover_color="#B71C1C"); self.stop_btn.grid(row=0, column=2, padx=8, pady=5, sticky="ew")
        return frame

    def _create_progress_widgets(self, parent):
        frame = ctk.CTkFrame(parent); frame.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(frame, text=_("status_ready"), font=ctk.CTkFont(size=13)); self.status_label.grid(row=0, column=0, pady=(8, 5), sticky="w", padx=10)
        self.progress_bar = ctk.CTkProgressBar(frame, height=12); self.progress_bar.set(0); self.progress_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.progress_label = ctk.CTkLabel(self.progress_bar, text="", fg_color="transparent", font=ctk.CTkFont(size=10, weight="bold")); self.progress_label.place(relx=0.5, rely=0.5, anchor="center")
        
        stats_frame = ctk.CTkFrame(frame); stats_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8)); stats_frame.grid_columnconfigure(list(range(5)), weight=1)
        self.stats_labels = {
            "processed": ctk.CTkLabel(stats_frame, text=""),
            "working": ctk.CTkLabel(stats_frame, text="", text_color=("#1B5E20", "#66BB6A")),
            "failed": ctk.CTkLabel(stats_frame, text="", text_color=("#B71C1C", "#E57373")),
            "captcha": ctk.CTkLabel(stats_frame, text="", text_color=("#FF8F00", "#FFC107")),
            "login_fails": ctk.CTkLabel(stats_frame, text="", text_color=("#FFA000", "#FFCA28")),
            "errors": ctk.CTkLabel(stats_frame, text="", text_color=("#D32F2F", "#EF5350"))
        }
        self.stats_labels['processed'].grid(row=0, column=0, sticky="w", padx=5)
        self.stats_labels['working'].grid(row=0, column=1, sticky="w", padx=5)
        self.stats_labels['failed'].grid(row=0, column=2, sticky="w", padx=5)
        self.stats_labels['captcha'].grid(row=0, column=3, sticky="w", padx=5)
        self.stats_labels['login_fails'].grid(row=0, column=4, sticky="w", padx=5)
        self.stats_labels['errors'].grid(row=0, column=5, sticky="w", padx=5)
        return frame

    def load_settings_to_ui(self):
        settings = self.app_config.get("settings", {})
        self.input_file_entry.insert(0, settings.get("input_file", DEFAULT_INPUT_FILE))
        self.output_dir_entry.insert(0, settings.get("output_dir", DEFAULT_OUTPUT_DIR))
        self.delay_min_entry.insert(0, str(settings.get("delay_min", 3.0)))
        self.delay_max_entry.insert(0, str(settings.get("delay_max", 7.0)))
        self.headless_var.set(settings.get("headless", True))
        self.browser_var.set(settings.get("browser_type", "chrome"))
        num_threads = settings.get("num_threads", 2)
        self.threads_slider.set(num_threads)
        self.threads_value_label.configure(text=str(num_threads))
        self.lang_var.set(f"{LANGUAGE_DISPLAY_NAMES.get(self.app_config['settings']['language'], 'English')} ({self.app_config['settings']['language']})")
        
        accounts = self.app_config.get("accounts", [])
        self.accounts_textbox.insert("1.0", "\n".join([f"{a['email']}:{a['password']}" for a in accounts]))
        self.update_stats(Stats())

    def save_ui_to_config(self):
        try:
            settings = self.app_config['settings']
            settings["input_file"] = self.input_file_entry.get().strip()
            settings["output_dir"] = self.output_dir_entry.get().strip()
            settings["delay_min"] = float(self.delay_min_entry.get())
            settings["delay_max"] = float(self.delay_max_entry.get())
            settings["headless"] = self.headless_var.get()
            settings["browser_type"] = self.browser_var.get()
            settings["language"] = self.lang_var.get().split('(')[-1][:-1]
            settings["num_threads"] = int(self.threads_slider.get())
            if self.root.state() == "normal": settings["window_geometry"] = self.root.geometry()
            self.app_config['accounts'] = [{'email': a.email, 'password': a.password} for a in self.get_accounts_from_ui()]
            self.config_manager.save_config(self.app_config)
        except (ValueError, TclError) as e:
            main_logger.error(f"Could not save UI to config: {e}")

    def _set_ui_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        try: self.tab_view.configure(state=state)
        except Exception: pass
        for widget in [self.start_btn, self.accounts_textbox, self.input_file_entry, self.output_dir_entry, self.threads_slider, self.delay_min_entry, self.delay_max_entry, self.browser_var, self.headless_var, self.lang_var]:
            if hasattr(widget, 'configure'): widget.configure(state=state)
        self.stop_btn.configure(state="disabled" if enabled else "normal")
        self.pause_btn.configure(state="disabled" if enabled else "normal")
        if enabled: self.pause_btn.configure(text=_("pause_button"))
    
    def start_checking(self):
        if self.is_running: return
        self.save_ui_to_config()
        if not self.validate_inputs(): return
        self.is_running = True
        self._set_ui_state(False)
        self.checker = LinkedInChecker(config=self.app_config, accounts=self.get_accounts_from_ui(), translator=_, gui_instance=self)
        self.update_status(_("status_starting")); self.progress_bar.set(0); self.update_stats(Stats())
        self.checker_thread = threading.Thread(target=self._run_checker_thread, name="MainChecker", daemon=True); self.checker_thread.start()

    def _run_checker_thread(self):
        try:
            if self.checker: self.checker.run()
        finally:
            if self.root.winfo_exists(): self.root.after(0, self._on_checking_finished)

    def _on_checking_finished(self):
        self.is_running = False
        self._set_ui_state(True)
        self.update_status(_("status_completed")); self.progress_label.configure(text="")
        if self.checker and not self.checker.should_stop.is_set():
            self.show_message_dialog(_("checking_complete_dialog_title"), _("checking_complete_dialog_message", **asdict(self.checker.stats)), "info")

    def toggle_pause_resume(self):
        if not self.is_running or not self.checker: return
        if self.checker.is_paused:
            self.checker.is_paused = False; self.checker.pause_event.set(); main_logger.info("Resuming...")
            self.pause_btn.configure(text=_("pause_button"))
            self.update_status(_("status_resuming"))
        else:
            self.checker.is_paused = True; self.checker.pause_event.clear(); main_logger.info("Pausing...")
            self.pause_btn.configure(text=_("resume_button"))
            self.update_status(_("status_paused"))
            
    def stop_checking(self):
        if self.is_running and self.checker: self.checker.stop()
        self.stop_btn.configure(state="disabled"); self.pause_btn.configure(state="disabled")

    def on_closing(self, force=False):
        if self.is_running and not force:
            if messagebox.askokcancel(_("confirm_exit_title"), _("confirm_exit_message")):
                if self.checker: self.checker.stop()
                if self.checker_thread: self.checker_thread.join(timeout=5.0)
                self.save_ui_to_config(); self.root.destroy()
        else:
            self.save_ui_to_config(); self.root.destroy()

    def set_total_links(self, total: int): self.total_links = total; self.update_progress(0)
        
    def update_live_status(self, current: int, total: int):
        active = sum(1 for t in threading.enumerate() if t.name.startswith("LinkChecker") and t.is_alive())
        if self.checker: self.root.after(0, self.update_status, _("status_processing_link", current=current, total=total, active_threads=f"{active}/{self.checker.num_threads}"))
        
    def update_stats_and_progress(self, stats: Stats):
        self.root.after(0, self.update_stats, stats)
        self.root.after(0, self.update_progress, stats.total_processed)
        
    def update_progress(self, current: int):
        progress = current / self.total_links if self.total_links > 0 else 0
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"{current}/{self.total_links}")
        
    def update_status(self, status: str): self.status_label.configure(text=status)
        
    def update_stats(self, stats: Stats):
        self.stats_labels['processed'].configure(text=f"{_('stats_processed_prefix')}: {stats.total_processed}")
        self.stats_labels['working'].configure(text=f"{_('stats_working_prefix')}: {stats.working_found}")
        self.stats_labels['failed'].configure(text=f"{_('stats_failed_prefix')}: {stats.failed_or_invalid}")
        self.stats_labels['captcha'].configure(text=f"{_('stats_link_captcha_prefix')}: {stats.link_captcha_failures}")
        self.stats_labels['login_fails'].configure(text=f"{_('stats_login_fails_prefix')}: {stats.login_failures}")
        self.stats_labels['errors'].configure(text=f"{_('stats_errors_prefix')}: {stats.errors}")

    def show_security_challenge_dialog(self, email: str) -> bool:
        self.root.after(0, lambda: self.challenge_response_queue.put(messagebox.askyesno(_("security_challenge_title"), _("security_challenge_message", email=email))))
        return self.challenge_response_queue.get()
        
    def show_message_dialog(self, title: str, message: str, msg_type: str = "info"):
        self.root.after(0, lambda: messagebox.showinfo(title, message) if msg_type == "info" else messagebox.showerror(title, message))

    def _start_log_processor(self):
        def process_queue():
            if not self.root.winfo_exists(): return
            self.log_textbox.configure(state="normal")
            try:
                while True: self.log_textbox.insert(tk.END, self.log_queue.get_nowait() + "\n")
            except queue.Empty:
                pass
            finally:
                self.log_textbox.see(tk.END); self.log_textbox.configure(state="disabled")
                self.root.after(250, process_queue)
        self.root.after(100, process_queue)
        
    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_closing(force=True)

# --- Main Execution ---
def check_prerequisites():
    missing = [lib for lib, available in [("selenium webdriver-manager", SELENIUM_AVAILABLE), ("customtkinter Pillow", GUI_AVAILABLE)] if not available]
    if missing:
        msg = f"Required libraries are missing: {', '.join(missing)}\nPlease install them: pip install {' '.join(missing)}"
        try:
            root = tk.Tk(); root.withdraw(); messagebox.showerror("Missing Dependencies", msg)
        except Exception: print(f"CRITICAL ERROR: {msg}")
        sys.exit(1)

def main():
    check_prerequisites()
    app = LinkedInCheckerGUI()
    app.run()

if __name__ == "__main__":
    main()
