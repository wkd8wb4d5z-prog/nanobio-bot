import email
from email.header import decode_header
from email.mime.text import MIMEText
import imaplib
import os
import re
import smtplib
import threading
import time
import telebot
from telebot import types

# Чтение переменных из окружения хостинга
TOKEN = os.environ.get("BOT_TOKEN")
EMAIL_ACCOUNT = os.environ.get("EMAIL_ACCOUNT", "bot@nanobiohim.ru")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# Настройки Google Workspace
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

bot = telebot.TeleBot(TOKEN)
bot.remove_webhook()

USERS_FILE = "users.txt"
PDF_FILE_IDS = {}


def save_user(chat_id):
    chat_id_str = str(chat_id)
    users = set()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = set(line.strip() for line in f if line.strip())
    if chat_id_str not in users:
        with open(USERS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{chat_id_str}\n")


def build_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_products = types.InlineKeyboardButton(
        "📦 Продукция", callback_data="products_menu"
    )
    btn_contacts = types.InlineKeyboardButton(
        "📞 Контакты", callback_data="contacts"
    )
    btn_details = types.InlineKeyboardButton(
        "📜 Реквизиты", callback_data="details"
    )
    btn_certs = types.InlineKeyboardButton(
        "📄 Сертификаты", callback_data="certs"
    )
    markup.add(btn_products, btn_contacts, btn_details, btn_certs)
    return markup


def send_banner_or_text(
    chat_id, image_filename, caption_text, reply_markup=None
):
    if os.path.exists(image_filename):
        with open(image_filename, "rb") as photo:
            bot.send_photo(
                chat_id,
                photo=photo,
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    else:
        bot.send_message(
            chat_id,
            text=caption_text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )


def send_email_notification(user_id, username, first_name, user_text):
    if not EMAIL_PASSWORD:
        return
    subject = f"Заявка из Telegram-бота [TG:{user_id}]"
    body = (
        f"📩 Новое обращение из Telegram-бота!\n\n"
        f"Имя: {first_name}\n"
        f"Username: @{username}\n"
        f"ID чата: {user_id}\n\n"
        f"Текст обращения:\n{user_text}\n\n"
        f"--------------------------------------------------\n"
        f"⚠️ Нажмите 'Ответить' в письме/чате, чтобы ваш ответ ушел клиенту в Telegram. "
        f"Не удаляйте метку [TG:{user_id}] из темы письма!"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = EMAIL_ACCOUNT

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Ошибка отправки почты (SMTP): {e}")


def check_email_replies():
    while True:
        try:
            if EMAIL_PASSWORD:
                mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
                mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
                mail.select("inbox")
                status, response = mail.search(None, "UNSEEN")
                mail_ids = response[0].split()

                for m_id in mail_ids:
                    status, data = mail.fetch(m_id, "(RFC822)")
                    for response_part in data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(
                                    encoding if encoding else "utf-8"
                                )

                            match = re.search(r"\[TG:(\d+)\]", subject)
                            if match:
                                target_chat_id = match.group(1)
                                reply_body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        if (
                                            part.get_content_type()
                                            == "text/plain"
                                        ):
                                            reply_body = part.get_payload(
                                                decode=True
                                            ).decode("utf-8")
                                            break
                                else:
                                    reply_body = msg.get_payload(
                                        decode=True
                                    ).decode("utf-8")

                                clean_text = reply_body.split(
                                    "--------------------------------------------------"
                                )[0].strip()
                                if clean_text:
                                    bot.send_message(
                                        target_chat_id,
                                        f"💬 <b>Ответ менеджера:</b>\n\n{clean_text}",
                                        parse_mode="HTML",
                                    )
                mail.logout()
        except Exception:
            pass
        time.sleep(15)


threading.Thread(target=check_email_replies, daemon=True).start()


@bot.message_handler(commands=["start"])
def start(message):
    save_user(message.chat.id)
    caption_text = (
        "<b>Компания НАНОБИОХИМ</b>\n\n"
        "Более 10 лет производит огнебиозащитные составы для древесины, "
        "а также антисептики и продукцию под Вашим СТМ.\n\n"
        "Выберите интересующий раздел ниже:"
    )
    send_banner_or_text(
        message.chat.id, "лого нбх-1.jpg", caption_text, build_main_keyboard()
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    if call.data == "main_menu":
        bot.send_message(
            chat_id,
            "<b>Главное меню ООО «НАНОБИОХИМ»:</b>",
            parse_mode="HTML",
            reply_markup=build_main_keyboard(),
        )
    elif call.data == "products_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton(
            "🔥 ОгнеPROFIT (I и II группа)", callback_data="prod_ogneprofit"
        )
        btn2 = types.InlineKeyboardButton(
            "🛡️ Огнебиозащита (II группа)", callback_data="prod_ognebio"
        )
        btn3 = types.InlineKeyboardButton(
            "🧪 Огнебиозащита Концентрат 1:5", callback_data="prod_koncentrat"
        )
        btn4 = types.InlineKeyboardButton(
            "🌲 Антисептик Биозащита", callback_data="prod_bio"
        )
        btn5 = types.InlineKeyboardButton(
            "🧪 Биозащита Концентрат 1:19", callback_data="prod_bio_koncentrat"
        )
        btn6 = types.InlineKeyboardButton(
            "💧 ХМ-11 Невымываемый антисептик", callback_data="prod_xm11"
        )
        btn7 = types.InlineKeyboardButton(
            "🧴 ХМ-11 Гель", callback_data="prod_xm11_gel"
        )
        btn8 = types.InlineKeyboardButton(
            "🛢️ ДиСепт (ХМ-11 концентрат 1:9)", callback_data="prod_disept"
        )
        btn9 = types.InlineKeyboardButton(
            "✨ Отбеливатель древесины", callback_data="prod_otbelivatel"
        )
        btn10 = types.InlineKeyboardButton(
            "🔬 ДиСепт-Тест (Контроль качества)", callback_data="prod_disepttest"
        )
        btn_back = types.InlineKeyboardButton(
            "⬅️ Назад в главное меню", callback_data="main_menu"
        )
        markup.add(
            btn1,
            btn2,
            btn3,
            btn4,
            btn5,
            btn6,
            btn7,
            btn8,
            btn9,
            btn10,
            btn_back,
        )
        caption_text = (
            "<b>Каталог продукции НАНОБИОХИМ</b>\n\nВыберите интересующую"
            " позицию из списка ниже:"
        )
        send_banner_or_text(chat_id, "ПРОДУКЦИЯ.jpg", caption_text, markup)
    elif call.data.startswith("prod_"):
        send_product_info(chat_id, call.data)
    elif call.data.startswith("pdf_"):
        send_pdf_doc(chat_id, call.data)
    elif call.data == "contacts":
        contacts_text = (
            "<b>📍 Контакты НАНОБИОХИМ:</b>\n\n"
            "📞 <b>Москва:</b> <a href='tel:+74993224378'>+7 (499)"
            " 322-43-78</a>\n"
            "📞 <b>С.-Петербург:</b> <a href='tel:+78123325317'>+7 (812)"
            " 332-53-17</a>\n"
            "✉️ <b>Email:</b> sale@nanobiohim.ru\n"
            "🌐 <b>Сайт:</b> nanobiohim.ru\n\n"
            "✈️ <b>ТГ:</b> @nanobiohim\n\n"
            "<b>📍 Проложить маршрут:</b>"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_yandex = types.InlineKeyboardButton(
            "📍 Яндекс.Карты", url="https://yandex.ru/maps/-/CXuEeFpU"
        )
        btn_2gis = types.InlineKeyboardButton(
            "📍 2ГИС", url="https://2gis.ru/spb/geo/70000001052145542"
        )
        btn_google = types.InlineKeyboardButton(
            "📍 Google Maps", url="https://maps.app.goo.gl/pao4dYFPfYvy2G9f8"
        )
        btn_back = types.InlineKeyboardButton(
            "⬅️ Назад", callback_data="main_menu"
        )
        markup.add(btn_yandex, btn_2gis)
        markup.add(btn_google)
        markup.add(btn_back)
        send_banner_or_text(chat_id, "КОНТАКТЫ.jpg", contacts_text, markup)
    elif call.data == "details":
        details_text = (
            "<b>📜 Реквизиты компании:</b>\n\n"
            "<b>ООО «Торговый Дом Нанобиохим»</b>\n"
            "Собственное производство и лаборатория.\n\n"
            "<b>ИНН/КПП:</b> <code>7816338510/7816338510</code>\n"
            "<b>ОГРН:</b> <code>1077847492067</code>\n\n"
            "📍 <b>Адрес:</b> 192289, г. Санкт-Петербург, пр. 9-го Января, д."
            " 21\n"
            "📞 <b>Тел/факс:</b> +7 (499) 322-43-78, +7 (812) 332-53-17\n"
            "📧 <b>Email:</b> sale@nanobiohim.ru / info@nanobiohim.ru"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        )
        send_banner_or_text(chat_id, "РЕКВИЗИТЫ.jpg", details_text, markup)
    elif call.data == "certs":
        certs_text = (
            "<b>📄 Сертификаты</b>\n\n⏳ Данный раздел находится <b>в"
            " разработке</b>. Скоро файлы сертификатов будут доступны для"
            " скачивания!"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        )
        send_banner_or_text(chat_id, "сертификаты.jpg", certs_text, markup)
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_user_text(message):
    save_user(message.chat.id)
    auto_reply = (
        "Спасибо за обращение! Мы скоро ответим вам, как только сработает VPN."
    )
    bot.reply_to(message, auto_reply)
    username = message.from_user.username or "Не указан"
    first_name = message.from_user.first_name or "Пользователь"
    send_email_notification(
        message.chat.id, username, first_name, message.text
    )


def send_product_info(chat_id, prod_code):
    products = {
        "prod_ogneprofit": {
            "photo": "product-ogneprofit.jpg",
            "text": (
                "<b>🔥 ОгнеPROFIT (I и II группа)</b>\n\n• Максимальная"
                " огнезащита и биозащита по ГОСТ Р 53292-2009.\n• При расходе 1"
                " л на 2 м² — I (высшая) группа огнезащиты.\n• Окрашивает в"
                " малиновый цвет."
            ),
            "pdf_key": "pdf_profit",
        },
        "prod_ognebio": {
            "photo": "product-ognebio.jpg",
            "text": (
                "<b>🛡️ Огнебиозащита (II группа)</b>\n\n• Защита от возгорания"
                " и гниения стропил, обрешетки, стен.\n• Подходит для"
                " внутренних и наружных (под навесом) работ.\n• Тонирует в"
                " розовый цвет."
            ),
            "pdf_key": "pdf_ognebio",
        },
        "prod_koncentrat": {
            "photo": "product-ognebio-koncentrat.jpg",
            "text": (
                "<b>🧪 Огнебиозащита концентрат 1:5 (II группа)</b>\n\n•"
                " Экономичный концентрат — разводится водой 1 к 5.\n•"
                " Обеспечивает II группу огнезащиты по ГОСТ Р 53292-2009."
            ),
            "pdf_key": "pdf_koncentrat",
        },
        "prod_bio": {
            "photo": "product-bio.jpg",
            "text": (
                "<b>🌲 Биозащита (Антисептик)</b>\n\n• Защита от плесени, синевы"
                " и гниения.\n• Бесцветный, без запаха, сохраняет структуру"
                " дерева."
            ),
            "pdf_key": "pdf_bio",
        },
        "prod_bio_koncentrat": {
            "photo": "product-xm11-koncentrat.png",
            "text": (
                "<b>🧪 Биозащита Концентрат 1:19</b>\n\n• Высококонцентрированный"
                " антисептический состав.\n• Из 5 л получается 100 л готового"
                " раствора!\n• Глубокое проникновение, не окрашивает"
                " древесину."
            ),
            "pdf_key": "pdf_bio",
        },
        "prod_xm11": {
            "photo": "product-xm11.jpg",
            "text": (
                "<b>💧 ХМ-11 Невымываемый антисептик (ГОСТ 28815-2018)</b>\n\n•"
                " Для тяжелонагруженных конструкций в контакте с грунтом и"
                " влагой (сваи, столбы, лаги, опоры ЛЭП).\n• IV–XVIII классы"
                " службы по ГОСТ 20022.2-80."
            ),
            "pdf_key": "pdf_xm11",
        },
        "prod_xm11_gel": {
            "photo": "product-xm11-gel.jpg",
            "text": (
                "<b>🧴 ХМ-11 Гель</b>\n\n• Невымываемый гелеобразный антисептик"
                " повышенной вязкости.\n• Не стекает с вертикальных стен,"
                " защищает торцы и нижние венцы."
            ),
            "pdf_key": "pdf_xm11_gel",
        },
        "prod_disept": {
            "photo": "product-xm11 1k9.jpeg",
            "text": (
                "<b>🛢️ ДиСепт трудновымываемый антисептик (Концентрат"
                " 1:9)</b>\n\n• Концентрат (1:9) для заборных столбов, свай,"
                " шпал и лаг.\n• Защищает от гниения, плесени, мхов и"
                " насекомых."
            ),
            "pdf_key": "pdf_xm11_19",
        },
        "prod_otbelivatel": {
            "photo": "product-otbelivatel.jpg",
            "text": (
                "<b>✨ Отбеливатель древесины</b>\n\n• Удаляет застарелую синеву,"
                " плесень и черноту за 30 минут.\n• Возвращает естественный"
                " цвет свежего дерева."
            ),
            "pdf_key": "pdf_otbelivatel",
        },
        "prod_disepttest": {
            "photo": "product-disepttest.jpg",
            "text": (
                "<b>🔬 ДиСепт-Тест (Контроль качества)</b>\n\n• Набор"
                " индикаторов для оценки качества антисептической пропитки (по"
                " СТО ПАО «Россети»).\n• Позволяет определить глубину"
                " проникновения состава."
            ),
            "pdf_key": "pdf_disepttest",
        },
    }
    prod = products.get(prod_code)
    if not prod:
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    if "pdf_key" in prod:
        markup.add(
            types.InlineKeyboardButton(
                "📥 Скачать (PDF)", callback_data=prod["pdf_key"]
            )
        )
    markup.add(
        types.InlineKeyboardButton(
            "⬅️ К списку товаров", callback_data="products_menu"
        )
    )
    photo_path = prod["photo"]
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo:
            bot.send_photo(
                chat_id,
                photo=photo,
                caption=prod["text"],
                parse_mode="HTML",
                reply_markup=markup,
            )
    else:
        bot.send_message(
            chat_id, text=prod["text"], parse_mode="HTML", reply_markup=markup
        )


def send_pdf_doc(chat_id, pdf_code):
    pdf_files = {
        "pdf_profit": ("Profit.pdf", "Технические условия: ОгнеPROFIT"),
        "pdf_ognebio": (
            "ognebio.pdf",
            "Технические условия: Огнебиозащита (II группа)",
        ),
        "pdf_koncentrat": (
            "ognebio-koncentrat.pdf",
            "Технические условия: Огнебиозащита концентрат 1:5",
        ),
        "pdf_bio": (
            "biozaschita.pdf",
            "Технические условия: Антисептик Биозащита",
        ),
        "pdf_xm11": (
            "xm11.pdf",
            "Технические условия: ХМ-11 (ГОСТ 28815-2018)",
        ),
        "pdf_xm11_gel": ("xm11-gel.pdf", "Технические условия: ХМ-11 Гель"),
        "pdf_xm11_19": (
            "xm11 1-9.pdf",
            "Технические условия: ДиСепт Концентрат 1:9",
        ),
        "pdf_otbelivatel": (
            "otbelivatel.pdf",
            "Технические условия: Отбеливатель древесины",
        ),
        "pdf_disepttest": (
            "disepttest.pdf",
            "Инструкция и ТУ: ДиСепт-Тест",
        ),
    }
    item = pdf_files.get(pdf_code)
    if not item:
        return
    filename, caption = item

    if pdf_code in PDF_FILE_IDS:
        file_id = PDF_FILE_IDS[pdf_code]
        bot.send_document(chat_id, file_id, caption=caption)
        return

    if os.path.exists(filename):
        bot.send_chat_action(chat_id, "upload_document")
        with open(filename, "rb") as doc:
            msg = bot.send_document(chat_id, doc, caption=caption)
            if msg and msg.document:
                PDF_FILE_IDS[pdf_code] = msg.document.file_id
    else:
        bot.send_message(chat_id, f"⚠️ Файл {filename} временно недоступен.")


if __name__ == "__main__":
    print("Бот компании НАНОБИОХИМ запущен...")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=15)
        except Exception as e:
            print(f"Сетевой сбой (повтор через 3 сек): {e}")
            time.sleep(3)
