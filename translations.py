# translations.py
import logging

# For displaying language names in UI (e.g., in a dropdown)
LANGUAGE_DISPLAY_NAMES = {
    "en": "English",
    "ar": "العربية",
}

# Main dictionary holding all translation strings
LANGUAGES_DATA = {
    "en": {
        "app_title": "LinkURL - Link Checker", # Changed from "LinkedIn Premium Trial Link Checker" for generality
        "tab_accounts_and_files": "Accounts & Files",
        "tab_settings": "Settings",
        "email_label": "Accounts (email:password, one per line):",
        "input_file_label": "Input Links File:",
        "output_dir_label": "Output Directory:",
        "browse_button": "Browse...",
        "browser_label": "Browser:",
        "headless_mode_checkbox": "Headless Mode",
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
        "login_failed_all_accounts_title": "Login Failed",
        "login_failed_all_accounts_message": "Could not log into any of the provided LinkedIn accounts. Please check credentials and connection.",
        "all_accounts_resting_warning": "All accounts are currently rate-limited. Please wait before trying again.",
        "no_accounts_configured_error": "No accounts configured. Please add accounts.",
        "no_links_to_process_error": "No links found in the input file.",
        "processing_link_info": "Processing Link {link_index}/{total_links}: {url} (from Line {line_num}) with {email}",
        "rate_limit_detected_details": "Rate limit / CAPTCHA detected.",
        "redirected_to_login_details": "Redirected to login/authwall page.",
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
        "found_links_to_process_info": "{count} links found to process.",
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
        "headless_mode_checkbox": "الوضع الخفي",
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
        "login_failed_all_accounts_title": "فشل تسجيل الدخول",
        "login_failed_all_accounts_message": "تعذر تسجيل الدخول إلى أي من حسابات LinkedIn المقدمة. يرجى التحقق من بيانات الاعتماد واتصالك بالإنترنت.",
        "all_accounts_resting_warning": "جميع الحسابات مقيدة حاليًا وفي فترة راحة. يرجى الانتظار قبل المحاولة مرة أخرى.",
        "no_accounts_configured_error": "لم يتم تكوين أي حسابات. الرجاء إضافة حسابات في الإعدادات.",
        "no_links_to_process_error": "لم يتم العثور على روابط للمعالجة في ملف الإدخال.",
        "processing_link_info": "معالجة الرابط {link_index}/{total_links}: {url} (من السطر {line_num}) باستخدام {email}",
        "rate_limit_detected_details": "تم اكتشاف تقييد للمعدل / CAPTCHA.",
        "redirected_to_login_details": "تمت إعادة التوجيه إلى صفحة تسجيل الدخول/الجدار المصادقة.",
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
        "found_links_to_process_info": "{count} روابط للمعالجة.",
        "error_reading_links_error": "خطأ في قراءة الروابط: {error}",
    }
}

CURRENT_LANGUAGE = "en"  # Default language
main_logger_instance = None # Placeholder for the main logger

def set_language(lang_code: str):
    global CURRENT_LANGUAGE
    if lang_code in LANGUAGES_DATA: # Check against actual translation data keys
        CURRENT_LANGUAGE = lang_code
    elif main_logger_instance:
        main_logger_instance.warning(f"Language '{lang_code}' not supported. Falling back to 'en'.")
        CURRENT_LANGUAGE = "en"
    else: # Before logger is set
        print(f"Warning: Language '{lang_code}' not supported during early init. Falling back to 'en'.")
        CURRENT_LANGUAGE = "en"


def _(key: str, **kwargs) -> str:
    try:
        translation = LANGUAGES_DATA.get(CURRENT_LANGUAGE, LANGUAGES_DATA["en"]).get(key, key)
        if kwargs:
            return translation.format(**kwargs)
        return translation
    except KeyError: # Should not happen if key is always present in "en"
        translation = LANGUAGES_DATA["en"].get(key, key) # Fallback to English data for the key
        if kwargs:
            return translation.format(**kwargs)
        return translation
    except Exception as e:
        if main_logger_instance:
            main_logger_instance.error(f"Translation error for key '{key}' with args {kwargs}: {e}")
        else:
            print(f"Error: Translation error for key '{key}' with args {kwargs}: {e}")
        return key # Return the key itself as a fallback


class MainLoggerPlaceholder:
    def warning(self, msg): print(f"WARNING (translations): {msg}")
    def error(self, msg): print(f"ERROR (translations): {msg}")
    def info(self, msg): print(f"INFO (translations): {msg}")
    def debug(self, msg): print(f"DEBUG (translations): {msg}")

main_logger_instance = MainLoggerPlaceholder()

def set_main_logger(logger: logging.Logger): # Changed logger_instance to logger
    global main_logger_instance
    main_logger_instance = logger
