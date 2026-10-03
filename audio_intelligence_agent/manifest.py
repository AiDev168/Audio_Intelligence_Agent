"""Platform-facing manifest definition for the Persian-first Audio Intelligence Agent."""

AGENT_MANIFEST = {
    "id": "audio_intelligence",
    "name": "تحلیلگر هوشمند صوتی",
    "description": (
        "تحلیل فایل‌های صوتی، پیاده‌سازی گفتار، شناسایی گویندگان، موضوعات، "
        "رویدادها و ارائه پاسخ‌های مستند زمانی."
    ),
    "icon": "🎧",
    "color": "#2563eb",
    "version": "0.3.0",
    "tags": ["audio", "speech", "transcription", "diarization", "evidence"],
    "capabilities": ["chat", "file", "media", "audio_intelligence"],
    "params": {
        "type": "object",
        "properties": {
            "audio_file": {
                "type": "string",
                "format": "file",
                "accept": "audio/*",
                "title": "فایل صوتی",
                "description": "یک فایل صوتی را برای تحلیل انتخاب کنید.",
            },
            "operation": {
                "type": "string",
                "enum": [
                    "transcribe",
                    "language",
                    "diarize",
                    "speaker_analysis",
                    "search",
                    "topics",
                    "summary",
                    "entities",
                    "audio_events",
                    "evidence",
                    "ask",
                    "analyze",
                ],
                "enumLabels": {
                    "transcribe": "تبدیل گفتار به متن",
                    "language": "تشخیص زبان",
                    "diarize": "تفکیک گویندگان",
                    "speaker_analysis": "تحلیل گویندگان",
                    "search": "جست‌وجو در متن صوت",
                    "topics": "موضوعات و فصل‌ها",
                    "summary": "خلاصه‌سازی",
                    "entities": "افراد، مکان‌ها و موجودیت‌ها",
                    "audio_events": "رویدادهای صوتی",
                    "evidence": "یافتن شواهد زمانی",
                    "ask": "پرسش و پاسخ مستند",
                    "analyze": "تحلیل کامل",
                },
            },
            "query": {
                "type": "string",
                "default": "",
                "title": "پرسش یا عبارت جست‌وجو",
            },
        },
    },
    "requires": ["agent_file_access", "artifact_store", "media_intelligence_core"],
    "resource_profile": "heavy_audio_gpu",
    "output_types": ["text", "file"],
    "settings": {
        "properties": {
            "profile": {
                "group": "تنظیمات عمومی",
                "type": "string",
                "title": "نوع محتوای صوتی",
                "description": "برای تنظیم پیش‌فرض‌های مناسب تحلیل.",
                "default": "general",
                "enum": ["general", "podcast", "meeting", "lecture", "interview", "call"],
                "enumLabels": {
                    "general": "عمومی",
                    "podcast": "پادکست",
                    "meeting": "جلسه",
                    "lecture": "سخنرانی / کلاس",
                    "interview": "مصاحبه",
                    "call": "تماس / مکالمه",
                },
            },
            "transcription_provider_mode": {
                "group": "تبدیل گفتار به متن — WhisperX / ریموت",
                "type": "string",
                "title": "روش تبدیل گفتار به متن",
                "description": (
                    "برای استفاده از WhisperX محلی یا یک سرویس سازگار با API گفتار‌به‌متن."
                ),
                "default": "local",
                "enum": ["local", "remote", "local-first", "remote-first"],
                "enumLabels": {
                    "local": "WhisperX محلی",
                    "remote": "سرویس ریموت",
                    "local-first": "ابتدا WhisperX، سپس ریموت",
                    "remote-first": "ابتدا ریموت، سپس WhisperX",
                },
            },
            "whisper_model": {
                "type": "string",
                "title": "نام مدل Whisper (اختیاری)",
                "description": (
                    "در صورت وارد کردن مسیر مدل، این گزینه را خالی بگذارید. برای شناسه مدل "
                    "یا کش مدل از این مقدار استفاده کنید."
                ),
                "default": "",
                "showWhen": {
                    "key": "transcription_provider_mode",
                    "values": ["local", "local-first", "remote-first"],
                },
            },
            "whisper_model_path": {
                "type": "string",
                "title": "مسیر مدل WhisperX",
                "description": (
                    "مسیر پوشه یا مدل محلی موجود روی همین سیستم؛ در حالت محلی استفاده "
                    "می‌شود."
                ),
                "default": "",
                "showWhen": {
                    "key": "transcription_provider_mode",
                    "values": ["local", "local-first", "remote-first"],
                },
            },
            "whisper_device": {
                "type": "string",
                "title": "دستگاه پردازش Whisper",
                "description": "معمولاً cuda برای کارت گرافیک و cpu برای پردازنده.",
                "default": "cuda",
                "enum": ["cuda", "cpu"],
                "enumLabels": {"cuda": "کارت گرافیک (CUDA)", "cpu": "پردازنده (CPU)"},
                "showWhen": {
                    "key": "transcription_provider_mode",
                    "values": ["local", "local-first", "remote-first"],
                },
            },
            "whisper_compute_type": {
                "type": "string",
                "title": "نوع محاسبه Whisper",
                "description": (
                    "برای GPU معمولاً float16 مناسب است؛ در CPU می‌توان int8 یا float32 را "
                    "انتخاب کرد."
                ),
                "default": "float16",
                "enum": ["default", "float16", "float32", "int8"],
                "enumLabels": {
                    "default": "خودکار",
                    "float16": "دقت ۱۶ بیتی",
                    "float32": "دقت ۳۲ بیتی",
                    "int8": "۸ بیتی",
                },
                "showWhen": {
                    "key": "transcription_provider_mode",
                    "values": ["local", "local-first", "remote-first"],
                },
            },
            "whisper_batch_size": {
                "type": "integer",
                "title": "اندازه دسته Whisper",
                "description": "عدد بزرگ‌تر سرعت را بیشتر و مصرف حافظه GPU را بالاتر می‌کند.",
                "default": 8,
                "showWhen": {
                    "key": "transcription_provider_mode",
                    "values": ["local", "local-first", "remote-first"],
                },
            },
            "remote_transcription_base_url": {
                "type": "string",
                "title": "نشانی پایه API تبدیل گفتار به متن",
                "description": (
                    "برای سرویس OpenAI-compatible؛ معمولاً مانند https://example.com/v1."
                ),
                "default": "",
                "showWhen": {
                    "key": "transcription_provider_mode",
                    "values": ["remote", "local-first", "remote-first"],
                },
            },
            "remote_transcription_api_key": {
                "type": "string",
                "format": "password",
                "title": "کلید API تبدیل گفتار به متن",
                "description": (
                    "کلید دسترسی سرویس ریموت. در سامانه به‌صورت رمزنگاری‌شده نگهداری "
                    "می‌شود."
                ),
                "default": "",
                "showWhen": {
                    "key": "transcription_provider_mode",
                    "values": ["remote", "local-first", "remote-first"],
                },
            },
            "remote_transcription_model": {
                "type": "string",
                "title": "مدل ریموت تبدیل گفتار به متن",
                "description": "نام مدلی که سرویس ریموت برای تبدیل گفتار به متن ارائه می‌کند.",
                "default": "",
                "showWhen": {
                    "key": "transcription_provider_mode",
                    "values": ["remote", "local-first", "remote-first"],
                },
            },
            "semantic_provider_mode": {
                "group": "مدل زبانی — محلی / ریموت",
                "type": "string",
                "title": "روش مدل زبانی",
                "description": (
                    "برای خلاصه‌سازی، موضوعات، موجودیت‌ها و پرسش‌وپاسخ از مدل زبانی محلی یا "
                    "ریموت استفاده می‌شود."
                ),
                "default": "remote",
                "enum": ["local", "remote", "local-first", "remote-first"],
                "enumLabels": {
                    "local": "مدل زبانی محلی",
                    "remote": "مدل زبانی ریموت",
                    "local-first": "ابتدا محلی، سپس ریموت",
                    "remote-first": "ابتدا ریموت، سپس محلی",
                },
            },
            "local_semantic_base_url": {
                "type": "string",
                "title": "نشانی پایه مدل زبانی محلی",
                "description": (
                    "نشانی سرویس OpenAI-compatible محلی، برای نمونه "
                    "http://127.0.0.1:1234/v1."
                ),
                "default": "http://127.0.0.1:1234/v1",
                "showWhen": {
                    "key": "semantic_provider_mode",
                    "values": ["local", "local-first", "remote-first"],
                },
            },
            "local_semantic_model": {
                "type": "string",
                "title": "مدل زبانی محلی",
                "description": "نام مدل فعال روی سرویس محلی.",
                "default": "",
                "showWhen": {
                    "key": "semantic_provider_mode",
                    "values": ["local", "local-first", "remote-first"],
                },
            },
            "remote_semantic_base_url": {
                "type": "string",
                "title": "Base URL مدل زبانی ریموت",
                "description": (
                    "نشانی پایه API سازگار با OpenAI، برای نمونه "
                    "https://provider.example/v1."
                ),
                "default": "",
                "showWhen": {
                    "key": "semantic_provider_mode",
                    "values": ["remote", "local-first", "remote-first"],
                },
            },
            "remote_semantic_api_key": {
                "type": "string",
                "format": "password",
                "title": "API Key مدل زبانی ریموت",
                "description": "کلید API سرویس ریموت؛ در سامانه رمزنگاری می‌شود.",
                "default": "",
                "showWhen": {
                    "key": "semantic_provider_mode",
                    "values": ["remote", "local-first", "remote-first"],
                },
            },
            "diarization_provider_mode": {
                "group": "تفکیک گویندگان",
                "type": "string",
                "title": "روش تفکیک گویندگان",
                "description": (
                    "در حال حاضر تفکیک محلی با WhisperX و مدل‌های pyannote پشتیبانی می‌شود."
                ),
                "default": "local",
                "enum": ["local"],
                "enumLabels": {"local": "WhisperX + pyannote"},
            },
            "diarization_hf_token": {
                "type": "string",
                "format": "password",
                "title": "کلید Hugging Face برای گویندگان",
                "description": (
                    "برای مدل‌های تفکیک گویندگان در Hugging Face؛ در سامانه رمزنگاری "
                    "می‌شود."
                ),
                "default": "",
            },
            "diarization_model": {
                "type": "string",
                "title": "مدل تفکیک گویندگان",
                "description": (
                    "در صورت استفاده از مقدار پیش‌فرض، مدل pyannote در runtime انتخاب "
                    "می‌شود."
                ),
                "default": "pyannote/speaker-diarization-community-1",
            },
            "remote_semantic_model": {
                "type": "string",
                "title": "مدل ریموت",
                "description": (
                    "نام مدل زبانی ریموت برای خلاصه‌سازی، موضوعات، موجودیت‌ها و پاسخ مستند."
                ),
                "default": "",
                "showWhen": {
                    "key": "semantic_provider_mode",
                    "values": ["remote", "local-first", "remote-first"],
                },
            },
            "cache_enabled": {
                "group": "خروجی و کش",
                "type": "boolean",
                "title": "استفاده از حافظه موقت",
                "description": "نتایج سازگار تحلیل مجدد فایل را دوباره استفاده می‌کند.",
                "default": True,
            },
            "evidence_limit": {
                "type": "integer",
                "title": "تعداد شواهد در پاسخ",
                "description": "حداکثر تعداد بخش‌های زمانی که در حالت مستند برگردانده می‌شود.",
                "default": 20,
            },
        }
    },
    "guide": {
        "title": "تحلیلگر هوشمند صوتی",
        "capabilities": [
            {"name": "تبدیل گفتار به متن", "description": "فایل صوتی را به متن زمان‌بندی‌شده تبدیل می‌کند."},
            {"name": "تشخیص زبان", "description": "زبان گفتار را از نتیجه تحلیل صوت شناسایی می‌کند."},
            {"name": "تفکیک گویندگان", "description": "بخش‌های صوت را به گویندگان مختلف نسبت می‌دهد."},
            {"name": "جست‌وجو و شواهد زمانی", "description": "عبارت یا موضوع را در متن پیدا می‌کند و زمان دقیق آن را نشان می‌دهد."},
            {"name": "موضوعات و فصل‌ها", "description": "ساختار موضوعی فایل را با کمک مدل زبانی استخراج می‌کند."},
            {"name": "خلاصه‌سازی", "description": "محتوای پیاده‌شده را به خلاصه قابل دانلود تبدیل می‌کند."},
            {"name": "افراد و موجودیت‌ها", "description": "نام افراد، مکان‌ها و موجودیت‌های مهم را استخراج می‌کند."},
            {"name": "پرسش و پاسخ مستند", "description": "بر اساس بخش‌های واقعی صوت به سؤال پاسخ می‌دهد."},
        ],
        "summary": "یک ابزار ساده برای تبدیل صوت به متن، خلاصه‌سازی و تحلیل محتوای صوتی.",
        "sections": [
            {
                "title": "شروع سریع",
                "text": (
                    "فایل صوتی را بارگذاری کنید و بنویسید «خلاصه کن» یا یکی از عملیات را "
                    "انتخاب کنید."
                ),
            },
            {
                "title": "آنچه انجام می‌دهد",
                "text": (
                    "تبدیل گفتار به متن، تشخیص زبان، تفکیک گویندگان، جست‌وجو، موضوعات، "
                    "خلاصه، موجودیت‌ها، رویدادهای صوتی، شواهد و پرسش‌وپاسخ مستند."
                ),
            },
            {
                "title": "برای خلاصه‌سازی چه چیزی لازم است؟",
                "text": (
                    "حداقل یک Provider برای تبدیل گفتار به متن و یک مدل زبانی برای "
                    "خلاصه‌سازی لازم است. Whisper فقط متن را تولید می‌کند و به‌تنهایی "
                    "خلاصه‌ساز نیست."
                ),
            },
            {
                "title": "خروجی",
                "text": (
                    "نتایج در پنل نمایش داده می‌شوند و برای خلاصه، فایل متنی قابل دانلود "
                    "نیز ساخته می‌شود."
                ),
            },
        ],
    },
}
