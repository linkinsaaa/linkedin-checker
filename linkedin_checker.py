# linkedin_checker.py
# -*- coding: utf-8 -*-
"""
LinkURL - Advanced Link Checker
Author: Gemini
Version: 5.5 - Background Window Stability & Session Self-Healing
Date: 2025-06-19
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
from typing import Any, Callable, Dict, List, Optional, Tuple
import os

# --- Dynamic Dependency Imports ---
try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        NoSuchElementException, TimeoutException, WebDriverException
    )
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
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


# --- Constants ---
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
]

if getattr(sys, 'frozen', False):
    APP_PATH = Path(sys.executable).parent
else:
    APP_PATH = Path(__file__).parent

CONFIG_FILE = APP_PATH / 'config.json'
LOG_DIR = APP_PATH / 'logs'
DEFAULT_INPUT_FILE = str(APP_PATH / "linkedin_links.txt")
DEFAULT_OUTPUT_DIR = str(APP_PATH / "results")
ACCOUNT_REST_DURATION_MINUTES = 30

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
            "app_title": "LinkURL - Link Checker",
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
            "stats_rl_account_prefix": "RL Account",
            "stats_errors_prefix": "Errors",
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
            "checking_complete_dialog_message": "Finished checking links.\n\nProcessed: {total_processed}\nWorking Links: {working_found}\nFailed/Invalid: {failed_or_invalid}\nRate Limited (Account): {rate_limit_suspected_current_account}\nErrors: {errors}",
            "no_accounts_configured_error": "No accounts configured. Please add accounts.",
            "no_links_to_process_error": "No unique, valid links found in the input file.",
            "processing_link_info": "Processing Link {link_index}/{total_links}: {url} (from Line {line_num}) with {email}",
            "rate_limit_detected_details": "Rate limit / CAPTCHA detected.",
            "redirected_to_login_details": "Redirected to login/authwall page.",
            "session_lost_details": "Session lost, redirected to login page. Re-queueing link.",
            "redirected_to_feed_details": "Redirected to main feed; link is likely invalid.",
            "offer_unavailable_details": "Offer expired, unavailable, or already redeemed.",
            "already_premium_details": "Account is already a Premium member.",
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
        },
        "ar": {
            "app_title": "LinkURL - مدقق الروابط",
            "tab_accounts_and_files": "الحسابات والملفات",
            "tab_settings": "الإعدادات",
            "email_label": "الحسابات (البريد الإلكتروني:كلمة المرور، واحد لكل سطر):",
            "input_file_label": "ملف الروابط:",
            "output_dir_label": "مجلد الإخراج:",
            "browse_button": "تصفح...",
            "browser_label": "المتصفح:",
            "headless_mode_checkbox": "الوضع الخفي (أكثر استقرارًا)",
            "delay_label": "التأخير (ثانية):",
            "threads_label": "عدد المسارات:",
            "delay_to_label": "إلى",
            "start_button": "بدء الفحص",
            "pause_button": "إيقاف مؤقت",
            "resume_button": "استئناف",
            "stop_button": "إيقاف",
            "status_ready": "الحالة: جاهز",
            "status_starting": "الحالة: جار البدء...",
            "status_processing_link": "الحالة: معالجة الرابط {current}/{total} | المسارات: {active_threads}",
            "status_paused": "الحالة: متوقف مؤقتاً",
            "status_resuming": "الحالة: جار الاستئناف...",
            "status_stopping": "الحالة: جار الإيقاف...",
            "status_completed": "الحالة: اكتمل",
            "security_challenge_message": "تم اكتشاف تحقق أمني (مثل الكابتشا) للحساب {email}.\n\nالرجاء حله في نافذة المتصفح.\n\nانقر 'نعم' بمجرد الانتهاء، أو 'لا' لتخطي هذا الحساب.",
            "status_generated_on": "تم إنشاؤه في: {date}",
            "total_found_label": "إجمالي ما تم العثور عليه: {count}",
            "confidence_label": "الثقة: {confidence}",
            "stats_processed_prefix": "المعالج",
            "stats_working_prefix": "يعمل",
            "stats_failed_prefix": "فشل",
            "stats_rl_account_prefix": "مقيد (حساب)",
            "stats_errors_prefix": "أخطاء",
            "log_section_title": "السجل المباشر",
            "settings_language_label": "اللغة:",
            "headless_note_label": "ملاحظة: قم بتعطيل الوضع الخفي لحل اختبارات تسجيل الدخول الأمنية.",
            "confirm_exit_title": "تأكيد الخروج",
            "confirm_exit_message": "الفاحص قيد التشغيل. هل أنت متأكد من أنك تريد الإيقاف والخروج؟",
            "error_dialog_title": "خطأ في الإدخال",
            "missing_email_password_error": "الرجاء تقديم حساب واحد على الأقل بالتنسيق 'email:password'.",
            "missing_input_file_error": "الرجاء تحديد ملف إدخال.",
            "invalid_delay_error": "يجب أن تكون قيم التأخير أرقامًا صالحة.",
            "security_challenge_title": "إجراء يدوي مطلوب",
            "security_challenge_detected_log": "تم اكتشاف تحدٍ أمني لـ {email}. يتم الإيقاف المؤقت للتدخل اليدوي.",
            "security_challenge_solved_log": "يبدو أنه تم حل التحدي الأمني لـ {email}. جار الاستئناف.",
            "security_challenge_failed_log": "تخطى المستخدم أو فشل في حل التحدي الأمني لـ {email}.",
            "checking_complete_dialog_title": "اكتمل الفحص",
            "checking_complete_dialog_message": "انتهى فحص الروابط.\n\nالمعالج: {total_processed}\nالروابط العاملة: {working_found}\nالفاشلة/غير صالحة: {failed_or_invalid}\nمقيد (حساب حالي): {rate_limit_suspected_current_account}\nالأخطاء: {errors}",
            "no_accounts_configured_error": "لم يتم تكوين أي حسابات. الرجاء إضافة حسابات في الإعدادات.",
            "no_links_to_process_error": "لم يتم العثور على روابط فريدة وصالحة للمعالجة في ملف الإدخال.",
            "processing_link_info": "معالجة الرابط {link_index}/{total_links}: {url} (من السطر {line_num}) باستخدام {email}",
            "rate_limit_detected_details": "تم اكتشاف تقييد للمعدل / CAPTCHA.",
            "redirected_to_login_details": "تمت إعادة التوجيه إلى صفحة تسجيل الدخول/الجدار المصادقة.",
            "session_lost_details": "تم فقدان الجلسة، إعادة التوجيه إلى صفحة تسجيل الدخول. إعادة إدراج الرابط في قائمة الانتظار.",
            "redirected_to_feed_details": "تمت إعادة التوجيه إلى الصفحة الرئيسية؛ الرابط على الأرجح غير صالح.",
            "offer_unavailable_details": "انتهت صلاحية العرض، أو غير متوفر، أو تم استرداده بالفعل.",
            "already_premium_details": "الحساب عضو بريميوم بالفعل.",
            "trial_gift_found_details": "تم العثور على عرض تجريبي/هدية محتمل.",
            "no_clear_trial_indicators_details": "لم يتم العثور على مؤشرات واضحة للنسخة التجريبية، قد يكون الرابط غير صالح.",
            "page_load_timeout_error": "انتهت مهلة تحميل الصفحة.",
            "webdriver_error_details": "خطأ في WebDriver: {error}",
            "saved_working_links_info": "تم حفظ {count} من الروابط العاملة في: {file_path}",
            "saved_detailed_results_info": "تم حفظ النتائج التفصيلية JSON في: {file_path}",
            "language_restart_title": "إعادة التشغيل مطلوبة",
            "language_restart_message": "تم تغيير اللغة. سيتم الآن إعادة تشغيل التطبيق لتطبيق التغييرات.",
            "input_file_not_found_error": "ملف الإدخال غير موجود: {file_path}",
            "found_links_to_process_info": "{count} روابط فريدة للمعالجة.",
            "error_reading_links_error": "خطأ في قراءة الروابط: {error}",
        }
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

@dataclass
class Account:
    email: str
    password: str
    last_rate_limited_at: Optional[datetime] = field(default=None, repr=False)
    consecutive_rate_limits: int = field(default=0, repr=False)

    def is_resting(self) -> bool:
        if not self.last_rate_limited_at:
            return False
        return datetime.now() < self.last_rate_limited_at + timedelta(minutes=ACCOUNT_REST_DURATION_MINUTES)

@dataclass
class Stats:
    total_processed: int = 0
    working_found: int = 0
    failed_or_invalid: int = 0
    rate_limit_suspected_current_account: int = 0
    errors: int = 0

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
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        file_handler = logging.FileHandler(LOG_DIR / f'linkurl_checker_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except Exception as e:
        print(f"Could not set up file logger: {e}")
    if log_queue:
        queue_handler = QueueHandler(log_queue)
        queue_handler.setFormatter(formatter)
        handlers.append(queue_handler)
    logging.basicConfig(level=log_level, format=log_format, handlers=handlers, force=True)
    logger = logging.getLogger("LinkURLChecker")
    logger.propagate = False
    return logger

main_logger = setup_logging()

# --- Core Checker Class ---
class LinkedInChecker:
    _LOGIN_URL = "https://www.linkedin.com/login"
    _USERNAME_FIELD_ID = "username"
    _PASSWORD_FIELD_ID = "password"
    _LOGIN_SUBMIT_XPATH = "//button[@type='submit']"
    _LOGIN_ERROR_CSS = ".form__input--error, .form__message--error, [data-test-id='error-message']"
    _AUTH_WALL_URL_SUBSTRING = "authwall"
    _LOGIN_SUCCESS_ELEMENT_XPATH = "//header[contains(@class, 'global-nav')]"

    _COOKIE_BUTTON_XPATHS = [
        "//button[contains(., 'Accept')]", "//button[contains(., 'Agree')]",
        "//button[contains(., 'Allow all')]", "//button[@data-control-name='accept_cookies']"
    ]
    
    _RATE_LIMIT_KEYWORDS = ["security verification", "captcha-internal", "are you human", "challenge"]
    _UNAVAILABLE_KEYWORDS = [
        "offer has already been redeemed", "offer is no longer available",
        "this offer isn't available", "link has expired", "page not found",
        "404", "this page doesn’t exist", "this page is unavailable",
        "an error has occurred", "something went wrong", "offer unavailable"
    ]
    _ALREADY_PREMIUM_KEYWORDS = [
        "already a premium member", "your current plan",
        "manage premium subscription", "welcome to premium"
    ]
    _TRIAL_KEYWORDS = [
        "claim this exclusive offer", "get premium free", "start your free month", 
        "free trial", "claim your gift", "redeem your gift", "activate your gift", 
        "premium gift", "start premium", "get premium", "unlock premium", 
        "your free trial awaits", "special offer for you", "try premium for 0", 
        "1-month free trial", "accept your free upgrade", "start my free trial",
        "all you need to do is activate"
    ]
    _PAYMENT_KEYWORDS = [
        "card number", "credit card", "payment method", "billing address",
        "paypal", "add a card", "confirm purchase", "review your order", "select payment"
    ]
    _ACTION_INDICATOR_XPATHS = [
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start free trial')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'try premium for free')]",
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start your free month')]",
        "//button[@data-test-id='accept-gift-button']",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'activate')]"
    ]

    def __init__(self, *, input_file: str, output_dir: str, accounts: List[Account], translator: Callable, num_threads: int = 1, delay_min: float = 2.0, delay_max: float = 5.0, headless: bool = True, browser_type: str = 'chrome', gui_instance: Optional['LinkedInCheckerGUI'] = None):
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        self.all_accounts = accounts
        self.translate = translator
        self.num_threads = max(1, num_threads)
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.headless = headless
        self.browser_type = browser_type.lower()
        self.gui = gui_instance
        
        self.should_stop = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.is_paused = False
        
        self.stats = Stats()
        self.working_links: List[LinkResult] = []
        self.failed_links: List[LinkResult] = []
        
        self.links_to_process_queue = queue.Queue()
        self.results_lock = threading.Lock()
        self.account_manager_lock = threading.Lock()
        self.available_accounts = list(self.all_accounts)
        
        main_logger.info(f"Checker initialized with {self.num_threads} threads for browser '{self.browser_type}'. Headless: {self.headless}")

    def read_links(self) -> int:
        if not self.input_file.exists():
            main_logger.error(self.translate("input_file_not_found_error", file_path=str(self.input_file)))
            return 0
        
        unique_links = {}
        try:
            with self.input_file.open('r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    original_line = line.strip()
                    if not original_line or original_line.startswith('#'): continue
                    for match in re.finditer(r'https?://(?:www\.)?linkedin\.com[^\s\'"]*', original_line):
                        url = match.group(0).strip(".,;")
                        url = re.sub(r'(&?)(trk|trkInfo|trkDetails|session_redirect)=[^&"]*', '', url)
                        if '?' in url and url.endswith('?'): url = url[:-1]
                        if url not in unique_links: unique_links[url] = i + 1
            
            for url, line_num in unique_links.items():
                self.links_to_process_queue.put((url, line_num))
            
            count = len(unique_links)
            main_logger.info(self.translate("found_links_to_process_info", count=count))
            return count
        except Exception as e:
            main_logger.error(self.translate("error_reading_links_error", error=str(e)))
            return 0

    def get_account(self) -> Optional[Account]:
        with self.account_manager_lock:
            non_resting_accounts = [acc for acc in self.available_accounts if not acc.is_resting()]
            if non_resting_accounts:
                account = random.choice(non_resting_accounts)
                self.available_accounts.remove(account)
                return account
            return None

    def release_account(self, account: Account, is_rate_limited: bool = False):
        with self.account_manager_lock:
            if is_rate_limited:
                account.last_rate_limited_at = datetime.now()
                account.consecutive_rate_limits += 1
                main_logger.warning(f"Account {account.email} is resting for {ACCOUNT_REST_DURATION_MINUTES} mins.")
            else:
                account.consecutive_rate_limits = 0
            
            if account not in self.available_accounts:
                self.available_accounts.append(account)

    def _create_webdriver(self) -> WebDriver:
        user_agent = random.choice(USER_AGENTS)
        if self.browser_type == "chrome":
            options = ChromeOptions()
            if self.headless: options.add_argument("--headless=new")
            options.add_argument("--disable-gpu"); options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument(f"user-agent={user_agent}")
            try:
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                main_logger.error(f"Failed to start Chrome with webdriver_manager: {e}. Trying system PATH.")
                driver = webdriver.Chrome(options=options)
        else:
            options = FirefoxOptions()
            if self.headless: options.add_argument("--headless")
            options.set_preference("general.useragent.override", user_agent)
            try:
                service = FirefoxService(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=options)
            except Exception as e:
                main_logger.error(f"Failed to start Firefox with webdriver_manager: {e}. Trying system PATH.")
                driver = webdriver.Firefox(options=options)
            driver.maximize_window()
                
        driver.set_page_load_timeout(45)
        return driver

    def _is_logged_in(self, driver: WebDriver) -> bool:
        """Check if the driver session is still authenticated."""
        try:
            current_url = driver.current_url.lower()
            if self._AUTH_WALL_URL_SUBSTRING in current_url or "/login" in current_url:
                return False
            # Check for a reliable element that only appears when logged in
            driver.find_element(By.XPATH, self._LOGIN_SUCCESS_ELEMENT_XPATH)
            return True
        except (NoSuchElementException, WebDriverException):
            return False

    def setup_and_login(self, account: Account) -> Optional[WebDriver]:
        driver = None
        try:
            main_logger.info(f"Setting up WebDriver for account {account.email}...")
            driver = self._create_webdriver()
            main_logger.info(f"Attempting login for {account.email}...")
            driver.get(self._LOGIN_URL)
            
            WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, self._USERNAME_FIELD_ID))).send_keys(account.email)
            driver.find_element(By.ID, self._PASSWORD_FIELD_ID).send_keys(account.password)
            driver.find_element(By.XPATH, self._LOGIN_SUBMIT_XPATH).click()
            
            wait = WebDriverWait(driver, 30)
            wait.until(EC.any_of(
                EC.presence_of_element_located((By.XPATH, self._LOGIN_SUCCESS_ELEMENT_XPATH)),
                EC.url_contains("checkpoint"),
                EC.url_contains("challenge"),
                EC.presence_of_element_located((By.CSS_SELECTOR, self._LOGIN_ERROR_CSS))
            ))
            
            current_url = driver.current_url.lower()
            if self._is_logged_in(driver):
                main_logger.info(f"Login successful for {account.email}.")
                self._handle_cookie_banner(driver)
                return driver
            elif any(s in current_url for s in ["checkpoint", "challenge", "security-check"]):
                main_logger.warning(self.translate("security_challenge_detected_log", email=account.email))
                if self.gui and not self.headless:
                    user_agreed = self.gui.show_security_challenge_dialog(account.email)
                    if user_agreed and self._is_logged_in(driver):
                        main_logger.info(self.translate("security_challenge_solved_log", email=account.email))
                        return driver
                    else:
                        main_logger.warning(self.translate("security_challenge_failed_log", email=account.email))
                else: main_logger.warning("Security challenge in headless/no-GUI mode.")
            else:
                try:
                    error_msg = driver.find_element(By.CSS_SELECTOR, self._LOGIN_ERROR_CSS).text
                    main_logger.warning(f"Login failed for {account.email}. Reason: {error_msg.strip()}")
                except NoSuchElementException:
                    main_logger.warning(f"Login failed for {account.email}. Unexpected page: {current_url}")

            if driver: driver.quit()
            return None
        except Exception as e:
            main_logger.error(f"Unexpected error during login for {account.email}: {e}", exc_info=True)
            if driver: driver.quit()
            return None

    def _handle_cookie_banner(self, driver: WebDriver):
        try:
            wait = WebDriverWait(driver, 2)
            for selector in self._COOKIE_BUTTON_XPATHS:
                try:
                    button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    button.click(); time.sleep(0.5); return
                except TimeoutException: continue
        except Exception: pass

    def _check_page_state(self, driver: WebDriver, url: str) -> LinkResult:
        try:
            driver.get(url)
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(random.uniform(1.5, 2.5)) # Allow dynamic content to load

            page_source = driver.page_source.lower()
            current_url = driver.current_url.lower()
            
            if any(kw in page_source or kw in current_url for kw in self._RATE_LIMIT_KEYWORDS):
                return LinkResult(link=url, status="RATE_LIMIT", result_details=self.translate("rate_limit_detected_details"), final_url=driver.current_url)
            if self._AUTH_WALL_URL_SUBSTRING in current_url:
                return LinkResult(link=url, status="SESSION_LOST", result_details=self.translate("session_lost_details"), final_url=driver.current_url)
            if current_url.endswith("/feed/") and "premium" not in url and "redeem" not in url:
                return LinkResult(link=url, status="FAILED", result_details=self.translate("redirected_to_feed_details"), final_url=driver.current_url)
            if any(kw in page_source for kw in self._UNAVAILABLE_KEYWORDS):
                return LinkResult(link=url, status="FAILED", result_details=self.translate("offer_unavailable_details"), final_url=driver.current_url)
            if any(kw in page_source for kw in self._ALREADY_PREMIUM_KEYWORDS):
                return LinkResult(link=url, status="FAILED", result_details=self.translate("already_premium_details"), final_url=driver.current_url)

            score, details = 0, []
            if any(driver.find_elements(By.XPATH, xpath) for xpath in self._ACTION_INDICATOR_XPATHS):
                score += 50; details.append("Action button")
            if any(kw in page_source for kw in self._PAYMENT_KEYWORDS):
                score += 30; details.append("Payment form")
            if any(kw in page_source for kw in self._TRIAL_KEYWORDS):
                score += 25; details.append("Trial keyword")
            if any(p in current_url for p in ["/redeem", "/gift", "/claim", "/premium/"]):
                score += 15; details.append("Trial URL")
            
            if score >= 40:
                confidence = "HIGH" if score >= 60 else "MEDIUM"
                result_details_str = f"{self.translate('trial_gift_found_details')} ({', '.join(details)})"
                return LinkResult(link=url, status="WORKING", result_details=result_details_str, confidence=confidence, final_url=driver.current_url)
            
            return LinkResult(link=url, status="FAILED", result_details=self.translate("no_clear_trial_indicators_details"), final_url=driver.current_url)

        except TimeoutException:
            return LinkResult(link=url, status="ERROR", result_details=self.translate("page_load_timeout_error"), error="TimeoutException")
        except WebDriverException as e:
            # Check if session is lost, which is a recoverable state
            if "no such window" in str(e) or "target window already closed" in str(e):
                 return LinkResult(link=url, status="SESSION_LOST", result_details=self.translate("session_lost_details"), error=str(e))
            return LinkResult(link=url, status="ERROR", result_details=self.translate("webdriver_error_details", error=str(e)[:100]), error=str(e))
        except Exception as e:
            main_logger.error(f"Unexpected error in _check_page_state for {url}: {e}", exc_info=True)
            return LinkResult(link=url, status="ERROR", result_details=f"Unexpected error: {str(e)[:100]}", error=str(e))

    def process_link_worker(self, worker_id: int):
        main_logger.info(f"Worker {worker_id} starting.")
        driver: Optional[WebDriver] = None
        account: Optional[Account] = None
        try:
            while not self.should_stop.is_set():
                self.pause_event.wait()
                if self.should_stop.is_set(): break
                
                account = self.get_account()
                if not account:
                    if self.links_to_process_queue.empty(): break
                    time.sleep(5); continue
                
                driver = self.setup_and_login(account)
                if not driver:
                    self.release_account(account)
                    time.sleep(random.uniform(5, 10))
                    continue

                while not self.should_stop.is_set():
                    self.pause_event.wait()
                    if self.should_stop.is_set(): break
                    
                    if not self._is_logged_in(driver):
                        main_logger.warning(f"Session lost for {account.email}. Attempting to re-login.")
                        break # Break inner loop to force re-login

                    try:
                        url, line_num = self.links_to_process_queue.get_nowait()
                    except queue.Empty:
                        break 
                    
                    with self.results_lock:
                        link_index = self.stats.total_processed + 1
                        total_links_overall = link_index + self.links_to_process_queue.qsize()
                    if self.gui: self.gui.update_live_status(link_index, total_links_overall)
                    main_logger.info(self.translate("processing_link_info", link_index=link_index, total_links=total_links_overall, url=url, email=account.email, line_num=line_num))
                    
                    result = self._check_page_state(driver, url)
                    result.line_num = line_num

                    with self.results_lock:
                        is_session_killer = result.status in ("RATE_LIMIT", "SESSION_LOST")
                        if is_session_killer:
                            self.stats.rate_limit_suspected_current_account += 1
                            self.links_to_process_queue.put((url, line_num)) # Re-queue
                            self.release_account(account, is_rate_limited=(result.status == "RATE_LIMIT"))
                            account = None
                            driver.quit(); driver = None
                            break
                        else:
                            self.stats.total_processed += 1
                            if result.status == "WORKING":
                                self.stats.working_found += 1; self.working_links.append(result)
                                main_logger.info(f"SUCCESS: Link {url} is WORKING. Confidence: {result.confidence}.")
                            else:
                                if result.status == "ERROR": self.stats.errors += 1
                                else: self.stats.failed_or_invalid += 1
                                self.failed_links.append(result)
                                main_logger.warning(f"FAILURE: Link {url} is {result.status}. Details: {result.result_details}")
                            
                            if self.gui: self.gui.update_stats_and_progress(self.stats)
                    
                    time.sleep(random.uniform(self.delay_min, self.delay_max))
                
                if driver: driver.quit(); driver = None
                if account: self.release_account(account)

        except Exception as e:
            main_logger.error(f"Unhandled exception in worker {worker_id}: {e}", exc_info=True)
        finally:
            if driver: driver.quit()
            if account: self.release_account(account)
            main_logger.info(f"Worker {worker_id} exiting.")

    def save_results(self):
        if not self.working_links and not self.failed_links: return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        if self.working_links:
            working_file_path = self.output_dir / f"working_links_{timestamp}.txt"
            with working_file_path.open('w', encoding='utf-8') as f:
                f.write(f"# {self.translate('app_title')} - {self.translate('stats_working_prefix')}\n")
                f.write(f"# {self.translate('status_generated_on', date=datetime.now().isoformat())}\n\n")
                for res in sorted(self.working_links, key=lambda r: (r.confidence or '', r.link)):
                    f.write(f"{res.link} | {self.translate('confidence_label', confidence=res.confidence)} | {res.result_details}\n")
            main_logger.info(self.translate("saved_working_links_info", count=len(self.working_links), file_path=str(working_file_path)))
            
        detailed_results = {"summary": asdict(self.stats), "results": { "working": [asdict(r) for r in self.working_links], "failed_or_invalid": [asdict(r) for r in self.failed_links]}}
        json_file_path = self.output_dir / f"detailed_results_{timestamp}.json"
        with json_file_path.open('w', encoding='utf-8') as f: json.dump(detailed_results, f, indent=4, ensure_ascii=False)
        main_logger.info(self.translate("saved_detailed_results_info", file_path=str(json_file_path)))

    def run(self):
        self.should_stop.clear(); self.pause_event.set(); self.stats = Stats(); self.working_links.clear(); self.failed_links.clear()
        self.available_accounts = list(self.all_accounts)
        for acc in self.available_accounts: acc.last_rate_limited_at = None; acc.consecutive_rate_limits = 0
        while not self.links_to_process_queue.empty(): self.links_to_process_queue.get()
            
        total_links = self.read_links()
        if self.gui: self.gui.set_total_links(total_links)
        if not total_links or not self.all_accounts:
            if self.gui:
                if not total_links: self.gui.show_message_dialog(_("error_dialog_title"), _("no_links_to_process_error"), "error")
                if not self.all_accounts: self.gui.show_message_dialog(_("error_dialog_title"), _("no_accounts_configured_error"), "error")
            return
            
        with ThreadPoolExecutor(max_workers=self.num_threads, thread_name_prefix="LinkChecker") as executor:
            futures = [executor.submit(self.process_link_worker, i + 1) for i in range(self.num_threads)]
            for future in as_completed(futures):
                try: future.result()
                except Exception as e: main_logger.error(f"Worker future completed with an exception: {e}", exc_info=True)

        if not self.should_stop.is_set(): main_logger.info("Checking process completed."); self.save_results()
        else: main_logger.info("Checking process was stopped by user.")

    def pause(self):
        if not self.is_paused: self.pause_event.clear(); self.is_paused = True; main_logger.info("Pausing...");
        if self.gui: self.gui.update_status(_("status_paused"))
            
    def resume(self):
        if self.is_paused: self.is_paused = False; self.pause_event.set(); main_logger.info("Resuming...");
        if self.gui: self.gui.update_status(_("status_resuming"))
            
    def stop(self):
        main_logger.info("Stopping..."); self.should_stop.set(); self.pause_event.set()
        if self.gui: self.gui.update_status(_("status_stopping"))

# --- ConfigManager ---
class ConfigManager:
    def __init__(self, config_file: Path):
        self.config_file = config_file

    def load_config(self) -> Dict[str, Any]:
        if not self.config_file.exists(): return {}
        try:
            with self.config_file.open('r', encoding='utf-8') as f: return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            main_logger.error(f"Error loading config file {self.config_file}: {e}. Using defaults.")
            return {}

    def save_config(self, data: Dict[str, Any]):
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with self.config_file.open('w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        except IOError as e: main_logger.error(f"Error saving config file {self.config_file}: {e}")

# --- GUI Class ---
class LinkedInCheckerGUI:
    def __init__(self):
        if not GUI_AVAILABLE: raise RuntimeError("GUI libraries not installed.")
        self.config_manager = ConfigManager(CONFIG_FILE)
        self.app_config = self.config_manager.load_config()
        
        config_lang = self.app_config.get("settings", {}).get("language", "en")
        self.current_lang_code = config_lang if config_lang in LANGUAGE_DISPLAY_NAMES else "en"
        set_app_language(self.current_lang_code)
        
        self.root = ctk.CTk()
        self.log_queue = queue.Queue()
        self.gui_logger = setup_logging(log_queue=self.log_queue)
        
        ctk.set_appearance_mode(self.app_config.get("settings", {}).get("theme", "dark"))
        ctk.set_default_color_theme(self.app_config.get("settings", {}).get("color_theme", "green"))
        
        self.checker: Optional[LinkedInChecker] = None; self.checker_thread: Optional[threading.Thread] = None
        self.is_running = False; self.total_links = 0; self.restart_required = False
        self.challenge_response_queue = queue.Queue()
        self._tab_name_keys = {"accounts_files": "tab_accounts_and_files", "settings": "tab_settings"}
        
        self._setup_ui()
        self.load_settings_to_ui()
        self._start_log_processor()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_ui(self):
        self.root.title(_("app_title"))
        self.root.geometry(self.app_config.get("settings", {}).get("window_geometry", "1000x850"))
        self.root.minsize(850, 750)
        self.root.grid_columnconfigure(0, weight=1); self.root.grid_rowconfigure(1, weight=1)
        top_frame = ctk.CTkFrame(self.root); top_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        top_frame.grid_columnconfigure(0, weight=1)
        log_frame = ctk.CTkFrame(self.root); log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_frame.grid_columnconfigure(0, weight=1); log_frame.grid_rowconfigure(1, weight=1)
        self._create_top_widgets(top_frame); self._create_log_widgets(log_frame); self.update_ui_text()

    def _create_top_widgets(self, parent: ctk.CTkFrame):
        ctk.CTkLabel(parent, text=_("app_title"), font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, pady=(10, 20))
        self.tab_view = ctk.CTkTabview(parent, height=300); self.tab_view.grid(row=1, column=0, sticky="nsew", padx=10)
        self.accounts_files_tab = self.tab_view.add(_(self._tab_name_keys["accounts_files"]))
        self.settings_tab = self.tab_view.add(_(self._tab_name_keys["settings"]))
        self._create_accounts_tab(self.accounts_files_tab); self._create_settings_tab(self.settings_tab)
        self._create_control_widgets(parent).grid(row=2, column=0, sticky="ew", padx=10, pady=(15, 10))
        self._create_progress_widgets(parent).grid(row=3, column=0, sticky="ew", padx=10, pady=5)

    def _create_accounts_tab(self, parent: ctk.CTkFrame):
        parent.grid_columnconfigure(1, weight=1)
        self.accounts_label = ctk.CTkLabel(parent, text="", anchor="w"); self.accounts_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 2))
        self.accounts_textbox = ctk.CTkTextbox(parent, height=120, wrap="word"); self.accounts_textbox.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))
        self.input_file_label = ctk.CTkLabel(parent, text=""); self.input_file_entry = ctk.CTkEntry(parent); self.input_browse_btn = ctk.CTkButton(parent, text="", width=100, command=self.browse_input_file)
        self.output_dir_label = ctk.CTkLabel(parent, text=""); self.output_dir_entry = ctk.CTkEntry(parent); self.output_browse_btn = ctk.CTkButton(parent, text="", width=100, command=self.browse_output_dir)
        self.input_file_label.grid(row=2, column=0, sticky="w", padx=10, pady=5); self.input_file_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=5); self.input_browse_btn.grid(row=2, column=2, sticky="ew", padx=10, pady=5)
        self.output_dir_label.grid(row=3, column=0, sticky="w", padx=10, pady=5); self.output_dir_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5); self.output_browse_btn.grid(row=3, column=2, sticky="ew", padx=10, pady=5)

    def _create_settings_tab(self, parent: ctk.CTkFrame):
        parent.grid_columnconfigure(0, weight=1)
        perf_frame = ctk.CTkFrame(parent); perf_frame.grid(row=0, column=0, sticky="ew", pady=10); perf_frame.grid_columnconfigure(1, weight=1)
        self.threads_label = ctk.CTkLabel(perf_frame, text=""); self.threads_slider = ctk.CTkSlider(perf_frame, from_=1, to=10, number_of_steps=9, command=lambda v: self.threads_value_label.configure(text=str(int(v)))); self.threads_value_label = ctk.CTkLabel(perf_frame, text="1")
        self.threads_label.grid(row=0, column=0, sticky="w", padx=10, pady=5); self.threads_slider.grid(row=0, column=1, sticky="ew", padx=10, pady=5); self.threads_value_label.grid(row=0, column=2, sticky="w", padx=10, pady=5)
        self.delay_label_ui = ctk.CTkLabel(perf_frame, text=""); delay_inner_frame = ctk.CTkFrame(perf_frame, fg_color="transparent"); self.delay_min_entry = ctk.CTkEntry(delay_inner_frame, width=80); self.delay_to_label_ui = ctk.CTkLabel(delay_inner_frame, text=""); self.delay_max_entry = ctk.CTkEntry(delay_inner_frame, width=80)
        self.delay_label_ui.grid(row=1, column=0, sticky="w", padx=10, pady=5); delay_inner_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=10); self.delay_min_entry.pack(side="left"); self.delay_to_label_ui.pack(side="left", padx=10); self.delay_max_entry.pack(side="left")
        browser_frame = ctk.CTkFrame(parent); browser_frame.grid(row=1, column=0, sticky="ew", pady=10)
        self.browser_label_ui = ctk.CTkLabel(browser_frame, text=""); self.browser_var = ctk.StringVar(value="chrome"); self.browser_combo = ctk.CTkComboBox(browser_frame, values=["chrome", "firefox"], variable=self.browser_var); self.headless_var = ctk.BooleanVar(value=True); self.headless_check = ctk.CTkCheckBox(browser_frame, text="", variable=self.headless_var); self.headless_note_label = ctk.CTkLabel(browser_frame, text="", text_color="gray")
        self.browser_label_ui.grid(row=0, column=0, padx=10, pady=5, sticky="w"); self.browser_combo.grid(row=0, column=1, padx=10, pady=5, sticky="w"); self.headless_check.grid(row=0, column=2, padx=20, pady=5, sticky="w"); self.headless_note_label.grid(row=1, column=2, padx=20, pady=(0,5), sticky="w")
        app_frame = ctk.CTkFrame(parent); app_frame.grid(row=2, column=0, sticky="ew", pady=10)
        self.lang_label = ctk.CTkLabel(app_frame, text=""); self.lang_var = ctk.StringVar(value=""); self.lang_combo = ctk.CTkComboBox(app_frame, values=[f"{n} ({c})" for c, n in LANGUAGE_DISPLAY_NAMES.items()], variable=self.lang_var, command=self.change_language)
        self.lang_label.pack(side="left", padx=10); self.lang_combo.pack(side="left", padx=10)

    def _create_control_widgets(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent); frame.grid_columnconfigure((0, 1, 2), weight=1)
        button_font = ctk.CTkFont(size=16, weight="bold")
        self.start_btn = ctk.CTkButton(frame, command=self.start_checking, font=button_font, height=45, fg_color="#2E7D32", hover_color="#1B5E20")
        self.pause_resume_btn = ctk.CTkButton(frame, command=self.toggle_pause_resume, font=button_font, height=45, state="disabled")
        self.stop_btn = ctk.CTkButton(frame, command=self.stop_checking, font=button_font, height=45, state="disabled", fg_color="#C62828", hover_color="#B71C1C")
        self.start_btn.grid(row=0, column=0, padx=8, pady=5, sticky="ew"); self.pause_resume_btn.grid(row=0, column=1, padx=8, pady=5, sticky="ew"); self.stop_btn.grid(row=0, column=2, padx=8, pady=5, sticky="ew")
        return frame

    def _create_progress_widgets(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent); frame.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=13)); self.status_label.grid(row=0, column=0, pady=(8, 5), sticky="w", padx=10)
        self.progress_bar = ctk.CTkProgressBar(frame, height=12); self.progress_bar.set(0); self.progress_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.progress_label = ctk.CTkLabel(self.progress_bar, text="", fg_color="transparent", font=ctk.CTkFont(size=10, weight="bold")); self.progress_label.place(relx=0.5, rely=0.5, anchor="center")
        stats_frame = ctk.CTkFrame(frame); stats_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8)); stats_frame.grid_columnconfigure(list(range(5)), weight=1)
        self.stats_processed_label = ctk.CTkLabel(stats_frame, text=""); self.stats_working_label = ctk.CTkLabel(stats_frame, text="", text_color=("#1B5E20", "#66BB6A")); self.stats_failed_label = ctk.CTkLabel(stats_frame, text="", text_color=("#B71C1C", "#E57373")); self.stats_rl_account_label = ctk.CTkLabel(stats_frame, text="", text_color=("#FF8F00", "#FFC107")); self.stats_errors_label = ctk.CTkLabel(stats_frame, text="", text_color=("#D32F2F", "#EF5350"))
        self.stats_processed_label.grid(row=0, column=0, sticky="w"); self.stats_working_label.grid(row=0, column=1, sticky="w"); self.stats_failed_label.grid(row=0, column=2, sticky="w"); self.stats_rl_account_label.grid(row=0, column=3, sticky="w"); self.stats_errors_label.grid(row=0, column=4, sticky="w")
        return frame

    def _create_log_widgets(self, parent: ctk.CTkFrame):
        self.log_label = ctk.CTkLabel(parent, font=ctk.CTkFont(size=16, weight="bold")); self.log_label.grid(row=0, column=0, pady=(8,5), padx=10, sticky="w")
        self.log_textbox = ctk.CTkTextbox(parent, wrap="word", state="disabled", font=("Consolas", 12)); self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def update_ui_text(self):
        self.root.title(_("app_title"))
        try: self.tab_view._segmented_button.configure(values=[_(self._tab_name_keys["accounts_files"]), _(self._tab_name_keys["settings"])])
        except AttributeError: main_logger.error("Could not rename tabs.")
        self.accounts_label.configure(text=_("email_label")); self.input_file_label.configure(text=_("input_file_label"))
        self.output_dir_label.configure(text=_("output_dir_label")); self.input_browse_btn.configure(text=_("browse_button"))
        self.output_browse_btn.configure(text=_("browse_button")); self.browser_label_ui.configure(text=_("browser_label"))
        self.headless_check.configure(text=_("headless_mode_checkbox")); self.delay_label_ui.configure(text=_("delay_label"))
        self.delay_to_label_ui.configure(text=_("delay_to_label")); self.start_btn.configure(text=_("start_button"))
        self.stop_btn.configure(text=_("stop_button")); self.log_label.configure(text=_("log_section_title"))
        self.lang_label.configure(text=_("settings_language_label")); self.headless_note_label.configure(text=_("headless_note_label"))
        self.threads_label.configure(text=_("threads_label"));
        if not self.is_running: self.update_status(_("status_ready"))
        self.pause_resume_btn.configure(text=_("resume_button") if self.is_running and self.checker and self.checker.is_paused else _("pause_button"))
        self.update_stats(self.checker.stats if self.is_running and self.checker else Stats())
        self.lang_var.set(f"{LANGUAGE_DISPLAY_NAMES.get(self.current_lang_code, 'English')} ({self.current_lang_code})")

    def change_language(self, selected_value: str):
        match = re.search(r'\((\w+)\)', selected_value)
        if not match or match.group(1) == self.current_lang_code: return
        self.current_lang_code = match.group(1); set_app_language(self.current_lang_code); self.save_ui_to_config()
        self.show_message_dialog(_("language_restart_title"), _("language_restart_message"), "info")
        self.restart_required = True; self.on_closing(force=True)

    def browse_input_file(self):
        if filename := filedialog.askopenfilename(title=_("input_file_label"), filetypes=[("Text files", "*.txt"), ("All files", "*.*")]):
            self.input_file_entry.delete(0, tk.END); self.input_file_entry.insert(0, filename)
            
    def browse_output_dir(self):
        if directory := filedialog.askdirectory(title=_("output_dir_label")):
            self.output_dir_entry.delete(0, tk.END); self.output_dir_entry.insert(0, directory)

    def get_accounts_from_ui(self) -> List[Account]:
        text = self.accounts_textbox.get("1.0", tk.END).strip()
        accounts = []
        for line in text.splitlines():
            line = line.strip()
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                    accounts.append(Account(email=parts[0].strip(), password=parts[1].strip()))
        return accounts

    def validate_inputs(self) -> bool:
        if not self.get_accounts_from_ui(): self.show_message_dialog(_("error_dialog_title"), _("missing_email_password_error"), "error"); return False
        if not self.input_file_entry.get().strip(): self.show_message_dialog(_("error_dialog_title"), _("missing_input_file_error"), "error"); return False
        try: float(self.delay_min_entry.get()); float(self.delay_max_entry.get())
        except ValueError: self.show_message_dialog(_("error_dialog_title"), _("invalid_delay_error"), "error"); return False
        return True

    def load_settings_to_ui(self):
        settings = self.app_config.get("settings", {})
        self.input_file_entry.insert(0, settings.get("input_file", DEFAULT_INPUT_FILE))
        self.output_dir_entry.insert(0, settings.get("output_dir", DEFAULT_OUTPUT_DIR))
        self.delay_min_entry.insert(0, str(settings.get("delay_min", 2.0))); self.delay_max_entry.insert(0, str(settings.get("delay_max", 5.0)))
        self.headless_var.set(settings.get("headless", True)); self.browser_var.set(settings.get("browser_type", "chrome"))
        num_threads = settings.get("num_threads", 1); self.threads_slider.set(num_threads); self.threads_value_label.configure(text=str(num_threads))
        if accounts := self.app_config.get("accounts", []): self.accounts_textbox.insert("1.0", "\n".join([f"{acc.get('email', '')}:{acc.get('password', '')}" for acc in accounts]))

    def save_ui_to_config(self):
        try:
            config_data = {"settings": {"input_file": self.input_file_entry.get().strip(),"output_dir": self.output_dir_entry.get().strip(),"delay_min": float(self.delay_min_entry.get()),"delay_max": float(self.delay_max_entry.get()),"headless": self.headless_var.get(),"browser_type": self.browser_var.get(),"language": self.current_lang_code,"theme": ctk.get_appearance_mode().lower(),"color_theme": "green","num_threads": int(self.threads_slider.get())},"accounts": [{"email": acc.email, "password": acc.password} for acc in self.get_accounts_from_ui()]}
            if self.root.state() == "normal": config_data["settings"]["window_geometry"] = self.root.geometry()
            self.config_manager.save_config(config_data)
        except (ValueError, TclError) as e: main_logger.error(f"Could not save UI to config: {e}")

    def _set_ui_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        try: self.tab_view._segmented_button.configure(state=state)
        except AttributeError: main_logger.error("Could not disable tab view.")
        for widget in [self.start_btn, self.accounts_textbox, self.input_file_entry, self.output_dir_entry, self.input_browse_btn, self.output_browse_btn, self.threads_slider, self.delay_min_entry, self.delay_max_entry, self.browser_combo, self.headless_check, self.lang_combo]:
            widget.configure(state=state)
        
    def start_checking(self):
        if not self.validate_inputs() or self.is_running: return
        self.save_ui_to_config()
        self.checker = LinkedInChecker(input_file=self.input_file_entry.get().strip(), output_dir=self.output_dir_entry.get().strip(),accounts=self.get_accounts_from_ui(), translator=_, num_threads=int(self.threads_slider.get()),delay_min=float(self.delay_min_entry.get()), delay_max=float(self.delay_max_entry.get()),headless=self.headless_var.get(), browser_type=self.browser_var.get(), gui_instance=self)
        self.is_running = True; self._set_ui_state(False); self.stop_btn.configure(state="normal"); self.pause_resume_btn.configure(state="normal", text=_("pause_button"))
        self.update_status(_("status_starting")); self.progress_bar.set(0); self.update_stats(Stats())
        self.checker_thread = threading.Thread(target=self._run_checker_thread, name="MainChecker", daemon=True); self.checker_thread.start()

    def _run_checker_thread(self):
        try:
            if self.checker: self.checker.run()
        except Exception as e: main_logger.error(f"Unhandled error in checker thread: {e}", exc_info=True)
        finally:
            if self.root.winfo_exists(): self.root.after(0, self._on_checking_finished)

    def _on_checking_finished(self):
        self.is_running = False; self._set_ui_state(True); self.stop_btn.configure(state="disabled"); self.pause_resume_btn.configure(state="disabled", text=_("pause_button"))
        self.update_status(_("status_completed")); self.progress_label.configure(text="")
        if self.checker and not self.checker.should_stop.is_set(): self.show_message_dialog(_("checking_complete_dialog_title"), _("checking_complete_dialog_message", **asdict(self.checker.stats)),"info")

    def toggle_pause_resume(self):
        if self.checker and self.is_running:
            if self.checker.is_paused: self.checker.resume(); self.pause_resume_btn.configure(text=_("pause_button"))
            else: self.checker.pause(); self.pause_resume_btn.configure(text=_("resume_button"))

    def stop_checking(self):
        if self.checker: self.checker.stop()
        self.pause_resume_btn.configure(state="disabled"); self.stop_btn.configure(state="disabled")

    def on_closing(self, force=False):
        if self.is_running and not force:
            if messagebox.askokcancel(_("confirm_exit_title"), _("confirm_exit_message")):
                if self.checker: self.checker.stop()
                if self.checker_thread: self.checker_thread.join(timeout=5.0)
                self.save_ui_to_config(); self.root.destroy()
        else:
            if not self.restart_required: self.save_ui_to_config()
            self.root.destroy()

    def set_total_links(self, total: int): self.total_links = total; self.update_progress(0)
        
    def update_live_status(self, current: int, total: int):
        active_threads = sum(1 for t in threading.enumerate() if t.name.startswith("LinkChecker") and t.is_alive())
        self.root.after(0, self.update_status, _("status_processing_link", current=current, total=total, active_threads=f"{active_threads}/{self.checker.num_threads if self.checker else 'N/A'}"))
        
    def update_stats_and_progress(self, stats: Stats):
        self.root.after(0, self.update_stats, stats); self.root.after(0, self.update_progress, stats.total_processed)
        
    def update_progress(self, current: int):
        progress = current / self.total_links if self.total_links > 0 else 0
        self.progress_bar.set(progress); self.progress_label.configure(text=f"{_('stats_processed_prefix')}: {current}/{self.total_links}")
        
    def update_status(self, status: str): self.status_label.configure(text=status)
        
    def update_stats(self, stats: Stats):
        self.stats_processed_label.configure(text=f"{_('stats_processed_prefix')}: {stats.total_processed}"); self.stats_working_label.configure(text=f"{_('stats_working_prefix')}: {stats.working_found}")
        self.stats_failed_label.configure(text=f"{_('stats_failed_prefix')}: {stats.failed_or_invalid}"); self.stats_rl_account_label.configure(text=f"{_('stats_rl_account_prefix')}: {stats.rate_limit_suspected_current_account}")
        self.stats_errors_label.configure(text=f"{_('stats_errors_prefix')}: {stats.errors}")

    def show_security_challenge_dialog(self, email: str) -> bool:
        self.root.after(0, self._ask_security_question, email)
        return self.challenge_response_queue.get()
        
    def _ask_security_question(self, email: str):
        result = messagebox.askyesno(_("security_challenge_title"), _("security_challenge_message", email=email))
        self.challenge_response_queue.put(result)
        
    def show_message_dialog(self, title: str, message: str, msg_type: str = "info"):
        if msg_type == "error": messagebox.showerror(title, message)
        elif msg_type == "warning": messagebox.showwarning(title, message)
        else: messagebox.showinfo(title, message)

    def _start_log_processor(self):
        def process_queue():
            if not self.root.winfo_exists(): return
            self.log_textbox.configure(state="normal")
            try:
                while not self.log_queue.empty(): self.log_textbox.insert(tk.END, self.log_queue.get_nowait() + "\n")
            finally:
                self.log_textbox.see(tk.END); self.log_textbox.configure(state="disabled")
                self.root.after(250, process_queue)
        self.root.after(100, process_queue)
        
    def run(self) -> bool:
        self.root.mainloop()
        return self.restart_required

# --- Main Execution ---
def check_prerequisites():
    missing = []
    if not SELENIUM_AVAILABLE: missing.append("selenium webdriver-manager")
    if not GUI_AVAILABLE: missing.append("customtkinter Pillow")
    if missing:
        msg = f"Required libraries are missing:\n- {', '.join(missing)}\n\nPlease install them using pip:\n\npip install {' '.join(missing)}"
        try: root = tk.Tk(); root.withdraw(); messagebox.showerror("Missing Dependencies", msg)
        except Exception: print(f"CRITICAL ERROR:\n{msg}")
        sys.exit(1)

def main():
    check_prerequisites()
    restart = True
    while restart:
        app = LinkedInCheckerGUI()
        restart = app.run()

if __name__ == "__main__":
    main()