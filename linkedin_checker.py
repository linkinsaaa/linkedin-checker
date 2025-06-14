# -*- coding: utf-8 -*-
"""
LinkedIn Premium Trial Link Checker - Complete Implementation
"""

import json
import logging
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Dynamic imports for Selenium
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
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Global constants
if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).parent

CONFIG_FILE = application_path / 'config.json'
LOG_DIR = application_path / 'logs'
DEFAULT_INPUT_FILE = str(application_path / "linkedin_links.txt")
DEFAULT_OUTPUT_DIR = str(application_path / "results")

# Theme
LINKIN_GREEN_THEME = {
    "CTk": {"fg_color": ["#F0F2F5", "#121A12"]},
    "CTkFrame": {"fg_color": ["#E8F5E9", "#203020"], "border_color": ["#388E3C", "#66BB6A"]},
    "CTkButton": {"fg_color": ["#4CAF50", "#43A047"], "hover_color": ["#66BB6A", "#5CB85C"]},
    "CTkLabel": {"text_color": ["#1B5E20", "#C8E6C9"]},
    "CTkEntry": {"fg_color": ["#FFFFFF", "#1A281A"], "border_color": ["#4CAF50", "#66BB6A"]},
    "CTkTextbox": {"fg_color": ["#FBFEFB", "#1A281A"], "border_color": ["#66BB6A", "#4CAF50"]},
    "CTkProgressBar": {"fg_color": ["#C8E6C9", "#203020"], "progress_color": ["#4CAF50", "#66BB6A"]},
}

# Logger setup
class QueueHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record: logging.LogRecord):
        self.log_queue.put(self.format(record))

def setup_logging(log_level: int = logging.INFO, log_queue: Optional[queue.Queue] = None) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_format = '%(asctime)s|%(levelname)-8s|%(funcName)-20s|%(message)s'
    formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    try:
        file_handler = logging.FileHandler(
            LOG_DIR / f'linkedin_checker_{datetime.now().strftime("%Y%m%d")}.log', 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except Exception as e:
        print(f"Could not set up file logger: {e}")
    
    if log_queue:
        queue_handler = QueueHandler(log_queue)
        queue_handler.setFormatter(formatter)
        handlers.append(queue_handler)
    
    logger = logging.getLogger("LinkedInChecker")
    logger.setLevel(log_level)
    
    if logger.hasHandlers():
        logger.handlers.clear()
    
    for handler in handlers:
        handler.setLevel(log_level)
        logger.addHandler(handler)
    
    logger.propagate = False
    return logger

main_logger = setup_logging()

# Dataclasses
@dataclass
class LinkResult:
    link: str
    status: str
    result_details: str = ""
    final_url: Optional[str] = None
    original_url_from_file: Optional[str] = None
    line_num: Optional[int] = None
    confidence: Optional[str] = None
    error: Optional[str] = None

@dataclass
class Account:
    email: str
    password: str

# Core Checker Class
class LinkedInChecker:
    def __init__(self, **kwargs):
        self.input_file = Path(kwargs.get('input_file', DEFAULT_INPUT_FILE))
        self.output_dir = Path(kwargs.get('output_dir', DEFAULT_OUTPUT_DIR))
        self.delay_min = kwargs.get('delay_min', 2.0)
        self.delay_max = kwargs.get('delay_max', 5.0)
        self.headless = kwargs.get('headless', True)
        self.max_retries = kwargs.get('max_retries', 3)
        self.browser_type = kwargs.get('browser_type', 'chrome').lower()
        self.gui = kwargs.get('gui_instance')
        
        self.accounts = []
        self.current_account_index = 0
        self.driver = None
        self.running = False
        self.should_stop = False
        
        self.stats = {
            'total_processed': 0,
            'working_found': 0,
            'failed_or_invalid': 0,
            'rate_limit_suspected': 0
        }
        
        self.working_links = []
        self.failed_links = []
        
        main_logger.info(f"Checker initialized for input: {self.input_file}")

    def set_credentials(self, email: str, password: str) -> bool:
        if not email or not password:
            return False
        
        self.accounts = [Account(email=email, password=password)]
        return True

    def _setup_driver(self):
        if not SELENIUM_AVAILABLE:
            main_logger.error("Selenium not available")
            return None
        
        main_logger.info(f"Setting up {self.browser_type} WebDriver...")
        
        try:
            if self.browser_type == "chrome":
                options = ChromeOptions()
                if self.headless:
                    options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_experimental_option("prefs", {
                    "profile.managed_default_content_settings.images": 2
                })
                
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                options = FirefoxOptions()
                if self.headless:
                    options.add_argument("--headless")
                options.set_preference("permissions.default.image", 2)
                
                service = FirefoxService(GeckoDriverManager().install())
                self.driver = webdriver.Firefox(service=service, options=options)
            
            if self.driver:
                self.driver.set_page_load_timeout(45)
                main_logger.info("WebDriver setup successful")
                return self.driver
                
        except Exception as e:
            main_logger.error(f"Error setting up WebDriver: {e}")
            return None

    def _login_linkedin(self) -> bool:
        if not self.driver or not self.accounts:
            return False
        
        account = self.accounts[self.current_account_index]
        main_logger.info(f"Attempting to log in as {account.email}...")
        
        try:
            self.driver.get("https://www.linkedin.com/login")
            
            # Wait for login form
            username_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.send_keys(account.email)
            
            password_field = self.driver.find_element(By.ID, "password")
            password_field.send_keys(account.password)
            
            submit_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            submit_button.click()
            
            # Wait for login to complete
            WebDriverWait(self.driver, 30).until(
                lambda driver: "feed" in driver.current_url or "checkpoint" in driver.current_url
            )
            
            if "feed" in self.driver.current_url:
                main_logger.info("Login successful")
                return True
            else:
                main_logger.warning("Login may have failed or requires verification")
                return False
                
        except Exception as e:
            main_logger.error(f"Error during login: {e}")
            return False

    def read_links(self) -> List[Tuple[str, int, str]]:
        links_to_process = []
        
        if not self.input_file.exists():
            main_logger.error(f"Input file not found: {self.input_file}")
            return []
        
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract URL from line
                        url_match = re.search(r'https?://[^\s]+', line)
                        if url_match:
                            url = url_match.group(0)
                            links_to_process.append((url, i + 1, line))
            
            main_logger.info(f"Found {len(links_to_process)} links to process")
            return links_to_process
            
        except Exception as e:
            main_logger.error(f"Error reading links: {e}")
            return []

    def process_single_link(self, url: str, line_num: int, original_line: str) -> LinkResult:
        if self.should_stop:
            return LinkResult(link=url, status="CANCELLED", line_num=line_num)
        
        if not self.driver:
            return LinkResult(link=url, status="ERROR", error="WebDriver unavailable", line_num=line_num)
        
        main_logger.info(f"Processing link {line_num}: {url}")
        
        # Random delay
        time.sleep(random.uniform(self.delay_min, self.delay_max))
        
        try:
            self.driver.get(url)
            time.sleep(random.uniform(3, 6))
            
            current_url = self.driver.current_url
            page_title = (self.driver.title or "").lower()
            page_source = (self.driver.page_source or "").lower()
            
            # Check for rate limiting
            rate_limit_keywords = ["security verification", "are you a human", "too many requests"]
            if any(kw in page_title or kw in page_source for kw in rate_limit_keywords):
                return LinkResult(
                    link=url, 
                    status="RATE_LIMIT", 
                    result_details="Rate limit detected",
                    final_url=current_url,
                    line_num=line_num
                )
            
            # Check if redirected to login
            if "authwall" in current_url or "/login" in current_url:
                return LinkResult(
                    link=url,
                    status="FAILED",
                    result_details="Redirected to login/authwall",
                    final_url=current_url,
                    line_num=line_num
                )
            
            # Check for offer unavailable
            unavailable_keywords = [
                "offer is no longer available", "this offer has expired", 
                "sorry, this offer isn't available", "link has expired"
            ]
            if any(kw in page_source for kw in unavailable_keywords):
                return LinkResult(
                    link=url,
                    status="FAILED",
                    result_details="Offer unavailable/expired",
                    final_url=current_url,
                    line_num=line_num
                )
            
            # Check for working trial indicators
            trial_keywords = [
                "try premium for free", "start your free month", "free trial",
                "claim your gift", "redeem your gift", "activate your gift"
            ]
            
            has_trial_indicators = any(kw in page_source for kw in trial_keywords)
            is_redeem_url = any(p in url.lower() for p in ["/redeem", "/gift", "/claim"])
            
            if has_trial_indicators or is_redeem_url:
                confidence = "HIGH" if is_redeem_url and has_trial_indicators else "MEDIUM"
                return LinkResult(
                    link=url,
                    status="WORKING",
                    result_details="Trial/gift indicators found",
                    confidence=confidence,
                    final_url=current_url,
                    line_num=line_num
                )
            
            return LinkResult(
                link=url,
                status="FAILED",
                result_details="No clear trial indicators",
                final_url=current_url,
                line_num=line_num
            )
            
        except TimeoutException:
            return LinkResult(
                link=url,
                status="ERROR",
                error="Page load timeout",
                line_num=line_num
            )
        except Exception as e:
            return LinkResult(
                link=url,
                status="ERROR",
                error=f"WebDriver error: {str(e)[:100]}",
                line_num=line_num
            )

    def save_results(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save working links
        if self.working_links:
            working_file = self.output_dir / f"working_links_{timestamp}.txt"
            with open(working_file, 'w', encoding='utf-8') as f:
                f.write("# Working LinkedIn Premium Trial Links\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                for result in self.working_links:
                    f.write(f"{result.link}\n")
            main_logger.info(f"Saved {len(self.working_links)} working links to {working_file}")
        
        # Save detailed results
        results_file = self.output_dir / f"detailed_results_{timestamp}.json"
        all_results = self.working_links + self.failed_links
        results_data = {
            "metadata": {
                "timestamp": timestamp,
                "total_processed": len(all_results),
                "working_found": len(self.working_links),
                "failed": len(self.failed_links)
            },
            "results": [asdict(result) for result in all_results]
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        main_logger.info(f"Saved detailed results to {results_file}")

    def run(self):
        self.running = True
        self.should_stop = False
        
        if not self.accounts:
            main_logger.error("No accounts configured")
            self.running = False
            return
        
        # Setup driver
        if not self._setup_driver():
            main_logger.error("Failed to setup WebDriver")
            self.running = False
            return
        
        # Login
        if not self._login_linkedin():
            main_logger.error("Failed to login to LinkedIn")
            self.running = False
            return
        
        # Read links
        links_data = self.read_links()
        if not links_data:
            main_logger.error("No links to process")
            self.running = False
            return
        
        # Process links
        total_links = len(links_data)
        for i, (url, line_num, original_line) in enumerate(links_data):
            if self.should_stop:
                break
            
            # Update GUI progress
            if self.gui:
                self.gui.update_progress(i + 1, total_links)
                self.gui.update_status(f"Processing link {i + 1}/{total_links}")
            
            result = self.process_single_link(url, line_num, original_line)
            
            if result.status == "WORKING":
                self.working_links.append(result)
                self.stats['working_found'] += 1
            else:
                self.failed_links.append(result)
                if result.status == "RATE_LIMIT":
                    self.stats['rate_limit_suspected'] += 1
                else:
                    self.stats['failed_or_invalid'] += 1
            
            self.stats['total_processed'] += 1
            
            # Update GUI
            if self.gui:
                self.gui.update_stats(self.stats)
        
        # Save results
        self.save_results()
        
        # Cleanup
        if self.driver:
            self.driver.quit()
        
        self.running = False
        main_logger.info("Checking process completed")

    def stop(self):
        self.should_stop = True
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

# GUI Implementation
class LinkedInCheckerGUI:
    def __init__(self):
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Setup logging
        self.log_queue = queue.Queue()
        self.gui_logger = setup_logging(log_queue=self.log_queue)
        
        # Main window
        self.root = ctk.CTk()
        self.root.title("LinkedIn Premium Trial Link Checker")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Variables
        self.checker = None
        self.checker_thread = None
        self.is_running = False
        
        self.setup_ui()
        self.start_log_processor()
    
    def setup_ui(self):
        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(
            main_frame, 
            text="LinkedIn Premium Trial Link Checker",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(10, 20))
        
        # Configuration section
        config_frame = ctk.CTkFrame(main_frame)
        config_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        config_label = ctk.CTkLabel(config_frame, text="Configuration", font=ctk.CTkFont(size=16, weight="bold"))
        config_label.pack(pady=(10, 5))
        
        # Credentials
        cred_frame = ctk.CTkFrame(config_frame)
        cred_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(cred_frame, text="LinkedIn Email:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.email_entry = ctk.CTkEntry(cred_frame, width=300)
        self.email_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(cred_frame, text="LinkedIn Password:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.password_entry = ctk.CTkEntry(cred_frame, width=300, show="*")
        self.password_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        cred_frame.grid_columnconfigure(1, weight=1)
        
        # File paths
        file_frame = ctk.CTkFrame(config_frame)
        file_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(file_frame, text="Input File:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.input_file_entry = ctk.CTkEntry(file_frame, width=300)
        self.input_file_entry.insert(0, DEFAULT_INPUT_FILE)
        self.input_file_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        input_browse_btn = ctk.CTkButton(file_frame, text="Browse", width=80, command=self.browse_input_file)
        input_browse_btn.grid(row=0, column=2, padx=(5, 10), pady=5)
        
        ctk.CTkLabel(file_frame, text="Output Directory:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.output_dir_entry = ctk.CTkEntry(file_frame, width=300)
        self.output_dir_entry.insert(0, DEFAULT_OUTPUT_DIR)
        self.output_dir_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        output_browse_btn = ctk.CTkButton(file_frame, text="Browse", width=80, command=self.browse_output_dir)
        output_browse_btn.grid(row=1, column=2, padx=(5, 10), pady=5)
        
        file_frame.grid_columnconfigure(1, weight=1)
        
        # Settings
        settings_frame = ctk.CTkFrame(config_frame)
        settings_frame.pack(fill="x", padx=10, pady=5)
        
        # Browser type
        ctk.CTkLabel(settings_frame, text="Browser:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.browser_var = ctk.StringVar(value="chrome")
        browser_combo = ctk.CTkComboBox(settings_frame, values=["chrome", "firefox"], variable=self.browser_var)
        browser_combo.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        
        # Headless mode
        self.headless_var = ctk.BooleanVar(value=True)
        headless_check = ctk.CTkCheckBox(settings_frame, text="Headless Mode", variable=self.headless_var)
        headless_check.grid(row=0, column=2, padx=10, pady=5, sticky="w")
        
        # Delay settings
        ctk.CTkLabel(settings_frame, text="Delay (seconds):").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        delay_frame = ctk.CTkFrame(settings_frame)
        delay_frame.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        
        self.delay_min_entry = ctk.CTkEntry(delay_frame, width=60)
        self.delay_min_entry.insert(0, "2")
        self.delay_min_entry.pack(side="left", padx=(0, 5))
        
        ctk.CTkLabel(delay_frame, text="to").pack(side="left", padx=5)
        
        self.delay_max_entry = ctk.CTkEntry(delay_frame, width=60)
        self.delay_max_entry.insert(0, "5")
        self.delay_max_entry.pack(side="left", padx=(5, 0))
        
        settings_frame.grid_columnconfigure(1, weight=1)
        
        # Control buttons
        control_frame = ctk.CTkFrame(main_frame)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        self.start_btn = ctk.CTkButton(
            control_frame, 
            text="Start Checking", 
            command=self.start_checking,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.start_btn.pack(side="left", padx=10, pady=10)
        
        self.stop_btn = ctk.CTkButton(
            control_frame, 
            text="Stop Checking", 
            command=self.stop_checking,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=10, pady=10)
        
        # Progress section
        progress_frame = ctk.CTkFrame(main_frame)
        progress_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.status_label = ctk.CTkLabel(progress_frame, text="Ready to start checking", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(10, 5))
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 10))
        self.progress_bar.set(0)
        
        # Stats section
        stats_frame = ctk.CTkFrame(progress_frame)
        stats_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.stats_label = ctk.CTkLabel(
            stats_frame, 
            text="Processed: 0 | Working: 0 | Failed: 0 | Rate Limited: 0",
            font=ctk.CTkFont(size=12)
        )
        self.stats_label.pack(pady=5)
        
        # Log section
        log_frame = ctk.CTkFrame(main_frame)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        log_label = ctk.CTkLabel(log_frame, text="Activity Log", font=ctk.CTkFont(size=14, weight="bold"))
        log_label.pack(pady=(10, 5))
        
        self.log_textbox = ctk.CTkTextbox(log_frame, wrap="word")
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def browse_input_file(self):
        filename = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.input_file_entry.delete(0, tk.END)
            self.input_file_entry.insert(0, filename)
    
    def browse_output_dir(self):
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, directory)
    
    def validate_inputs(self) -> bool:
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        input_file = self.input_file_entry.get().strip()
        
        if not email:
            messagebox.showerror("Error", "Please enter your LinkedIn email")
            return False
        
        if not password:
            messagebox.showerror("Error", "Please enter your LinkedIn password")
            return False
        
        if not input_file or not Path(input_file).exists():
            messagebox.showerror("Error", "Please select a valid input file")
            return False
        
        return True
    
    def start_checking(self):
        if not self.validate_inputs():
            return
        
        if self.is_running:
            return
        
        # Get configuration
        config = {
            'input_file': self.input_file_entry.get().strip(),
            'output_dir': self.output_dir_entry.get().strip(),
            'delay_min': float(self.delay_min_entry.get()),
            'delay_max': float(self.delay_max_entry.get()),
            'headless': self.headless_var.get(),
            'browser_type': self.browser_var.get(),
            'max_retries': 3,
            'gui_instance': self
        }
        
        # Create checker
        self.checker = LinkedInChecker(**config)
        self.checker.set_credentials(
            self.email_entry.get().strip(),
            self.password_entry.get().strip()
        )
        
        # Update UI
        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.update_status("Starting checker...")
        
        # Start checker thread
        self.checker_thread = threading.Thread(target=self.run_checker)
        self.checker_thread.daemon = True
        self.checker_thread.start()
    
    def stop_checking(self):
        if self.checker:
            self.checker.stop()
        
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.update_status("Stopping...")
    
    def run_checker(self):
        try:
            self.checker.run()
        except Exception as e:
            main_logger.error(f"Checker error: {e}")
        finally:
            # Reset UI state
            self.root.after(0, self.on_checking_finished)
    
    def on_checking_finished(self):
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.update_status("Checking completed")
        
        if self.checker:
            stats = self.checker.stats
            messagebox.showinfo(
                "Checking Complete", 
                f"Processed: {stats['total_processed']}\n"
                f"Working links found: {stats['working_found']}\n"
                f"Failed/Invalid: {stats['failed_or_invalid']}\n"
                f"Rate limited: {stats['rate_limit_suspected']}"
            )
    
    def update_progress(self, current: int, total: int):
        if total > 0:
            progress = current / total
            self.progress_bar.set(progress)
    
    def update_status(self, status: str):
        self.status_label.configure(text=status)
    
    def update_stats(self, stats: dict):
        stats_text = (
            f"Processed: {stats['total_processed']} | "
            f"Working: {stats['working_found']} | "
            f"Failed: {stats['failed_or_invalid']} | "
            f"Rate Limited: {stats['rate_limit_suspected']}"
        )
        self.stats_label.configure(text=stats_text)
    
    def set_progress_max_value(self, max_value: int):
        pass  # CTkProgressBar handles this automatically
    
    def show_security_challenge_dialog_modal(self):
        result = messagebox.askyesno(
            "Security Challenge",
            "LinkedIn is showing a security challenge. Please solve it manually in the browser, then click Yes to continue."
        )
        return result
    
    def start_log_processor(self):
        def process_logs():
            try:
                while True:
                    try:
                        log_message = self.log_queue.get_nowait()
                        self.root.after(0, lambda msg=log_message: self.add_log_message(msg))
                    except queue.Empty:
                        break
            except:
                pass
            
            # Schedule next check
            self.root.after(100, process_logs)
        
        process_logs()
    
    def add_log_message(self, message: str):
        self.log_textbox.insert(tk.END, message + "\n")
        self.log_textbox.see(tk.END)
    
    def run(self):
        self.root.mainloop()

# Main execution
def check_prerequisites():
    missing_libs = []
    
    if not SELENIUM_AVAILABLE:
        missing_libs.append("selenium and webdriver-manager")
    
    if not hasattr(ctk, 'CTk'):
        missing_libs.append("customtkinter")
    
    if missing_libs:
        error_msg = (
            f"Required libraries are missing:\n- {', '.join(missing_libs)}\n\n"
            "Please install them using pip:\n"
            "pip install selenium webdriver-manager customtkinter Pillow"
        )
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Missing Dependencies", error_msg)
            root.destroy()
        except:
            print(f"CRITICAL ERROR:\n{error_msg}")
        sys.exit(1)

def main():
    check_prerequisites()
    
    app = LinkedInCheckerGUI()
    app.run()

if __name__ == "__main__":
    main()
