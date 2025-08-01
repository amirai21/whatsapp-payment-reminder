REMINDER_STYLES = {
    "mafia": [
        "\U0001F4BC תקשיב {name}, אתה חייב {amount} עבור *{event}*. אל תגרום לי לבקש שוב.",
        "\U0001F52B היי {name}, המשפחה צריכה את ה-{amount} עבור *{event}*. תשלם עכשיו."
    ],
    "grandpa": [
        "\U0001F474 בזמני שילמנו בזמן, {name}. הגיע הזמן לשלוח {amount} עבור *{event}*.",
        "\u2615 {name}, אני זקן מדי לרדוף אחרי תשלומים. בבקשה שלח {amount} עבור *{event}*."
    ],
    "broker": [
        "\U0001F4C8 היי {name}, תחשוב על זה כהשקעה. שלח {amount} עבור *{event}*.",
        "\U0001F4B9 {name}, התיק שלך חסר {amount} עבור *{event}*. הגיע הזמן להסדיר."
    ],
    "default": [
        "\U0001F514 תזכורת: {name}, בבקשה שלם {amount} עבור *{event}*."
    ]
}

admin_confirmation_msg = (
    "\U0001F4CC האירוע *{title}* נוצר (סגנון: {style}).\n"
    "\u23F3 תזכורות כל {frequency_minutes} דקות, מתחיל ב-{start_time}.\n"
    "\U0001F4C7 הדבק את חברי הקבוצה (שם + טלפון):"
)

MAIN_MENU_MSG = (
    "\U0001F44B שלום! מה תרצה לעשות?\n\n"
    "1\u20E3 צור אירוע\n"
    "2\u20E3 הצג את האירועים שלי\n"
    "3\u20E3 עזרה"
)

CREATE_EVENT_INSTRUCT_MSG = (
    "\U0001F389 *בוא ניצור אירוע חדש!*\n\n"
    "השתמש בפורמט הזה:\n"
    "`create event: Title Amount [style] [freq=MINUTES] [delay=MINUTES]`\n\n"
    "\U0001F4CC *הסבר על הפרמטרים:*\n"
    "• *Title* – שם האירוע (לדוג' יום הולדת, פיקניק)\n"
    "• *Amount* – כמה כל אחד צריך לשלם (לדוג' 50)\n"
    "• *Style* – סגנון תזכורת אופציונלי: `mafia`, `grandpa`, `broker` (ברירת מחדל: mafia)\n"
    "• *freq=MINUTES* – כל כמה זמן לשלוח תזכורת (ברירת מחדל: כל 60 דקות)\n"
    "• *delay=MINUTES* – עיכוב לפני התזכורת הראשונה (ברירת מחדל: מיד)\n\n"
    "\u2705 דוגמה:\n"
    "`create event: Picnic 50 mafia freq=120 delay=30`\n"
    "\U0001F449 זה יעשה:\n"
    "- יצירת אירוע *Picnic* עם 50 לכל משתתף\n"
    "- שימוש בסגנון תזכורת *mafia*\n"
    "- שליחת תזכורות כל שעתיים\n"
    "- התחלת תזכורות בעוד 30 דקות\n\n"
    "לאחר יצירת האירוע, תדביק את חברי הקבוצה (שם + טלפון)."
)

HELP_MSG = "\u2139\uFE0F עזרה: כתוב 'create event: Title Amount Style' כדי להתחיל אירוע."
