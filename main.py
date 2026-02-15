import os
import random

import telebot
from dotenv import load_dotenv
from telebot import types

from ORM import get_dsn, init_db
from db_service import WordCard, WordService

load_dotenv(encoding="utf-8")
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Добавьте его в .env")

bot = telebot.TeleBot(BOT_TOKEN)
init_db()


WELCOME_TEXT = (
    "Привет 👋 Давай попрактикуемся в английском языке. "
    "Тренировки можешь проходить в удобном для себя темпе.\n\n"
    "У тебя есть возможность использовать тренажёр, как конструктор, "
    "и собирать свою собственную базу для обучения. Для этого воспользуйся "
    "инструментами:\n\n"
    "Добавить слово ➕\n"
    "Удалить слово 🔙\n"
    "Начать Викторину 🧠\n"
    "Ну что, начнём ⬇️"
)


def main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    """Возвращает клавиатуру главного меню."""

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("Викторина 🧠"),
        types.KeyboardButton("Список слов 📖"),
        types.KeyboardButton("Добавить слово ➕"),
        types.KeyboardButton("Удалить слово 🔙"),
    )
    return markup


def quiz_keyboard(
    correct_word: WordCard,
    all_words: list[WordCard],
) -> types.ReplyKeyboardMarkup:
    """Возвращает клавиатуру с 4 вариантами ответа."""

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    others = [word.english for word in all_words if word.id != correct_word.id]
    options = random.sample(others, 3) + [correct_word.english]
    random.shuffle(options)

    markup.add(*[types.KeyboardButton(option) for option in options])
    markup.row(types.KeyboardButton("Выйти в меню 🏠"))
    return markup


@bot.message_handler(commands=["start"])
def start_bot(message):
    """Стартовый обработчик: приветствие и регистрация пользователя."""

    user_id = message.chat.id
    bot.clear_step_handler_by_chat_id(user_id)
    WordService.ensure_user(user_id)
    bot.send_message(user_id, WELCOME_TEXT, reply_markup=main_menu_keyboard())


@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    """Обрабатывает нажатия кнопок основного меню."""

    user_id = message.chat.id

    if message.text == "Викторина 🧠":
        send_quiz_question(message)
    elif message.text == "Список слов 📖":
        show_personal_words(message)
    elif message.text == "Добавить слово ➕":
        prompt = bot.send_message(
            user_id,
            "Введите слово на русском:",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(prompt, add_word_ru)
    elif message.text == "Удалить слово 🔙":
        delete_word_start(message)
    else:
        bot.send_message(
            user_id,
            "Используйте кнопки меню.",
            reply_markup=main_menu_keyboard(),
        )


def show_personal_words(message):
    """Показывает персональный словарь пользователя."""

    user_id = message.chat.id
    words = WordService.get_personal_words(user_id)

    if not words:
        bot.send_message(
            user_id,
            "Ваш личный список слов пока пуст. Добавьте новые слова кнопкой ➕",
            reply_markup=main_menu_keyboard(),
        )
        return

    text = "📝 **Ваш личный словарь:**\n\n"
    for index, word in enumerate(words, start=1):
        text += f"{index}. {word.russian} — {word.english}\n"

    bot.send_message(
        user_id,
        text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


def send_quiz_question(message, prefix: str = ""):
    """Отправляет вопрос викторины."""

    user_id = message.chat.id
    words = WordService.get_training_words(user_id)

    if len(words) < 4:
        bot.send_message(
            user_id,
            "Нужно минимум 4 слова в базе! Добавьте свои слова.",
            reply_markup=main_menu_keyboard(),
        )
        return

    target_word = random.choice(words)
    markup = quiz_keyboard(target_word, words)
    text = f"{prefix}\n\nКак переводится слово: *{target_word.russian}*?".strip()

    question_message = bot.send_message(
        user_id,
        text,
        parse_mode="Markdown",
        reply_markup=markup,
    )
    bot.register_next_step_handler(
        question_message,
        check_quiz_answer,
        target_word.english,
    )


def check_quiz_answer(message, correct_option: str):
    """Проверяет ответ пользователя в викторине."""

    user_id = message.chat.id
    user_answer = (message.text or "").strip()

    if user_answer in {"Выйти в меню 🏠", "/start"}:
        bot.clear_step_handler_by_chat_id(user_id)
        bot.send_message(
            user_id,
            "Возвращаюсь в меню...",
            reply_markup=main_menu_keyboard(),
        )
        return

    if user_answer.lower() == correct_option.lower():
        send_quiz_question(message, prefix="Отлично! ✨")
        return

    bot.send_message(user_id, "Неверно ❌ Попробуй еще раз!")
    bot.register_next_step_handler(message, check_quiz_answer, correct_option)


def add_word_ru(message):
    """Запрашивает английский перевод введенного русского слова."""

    ru_word = (message.text or "").strip()
    if not ru_word:
        bot.send_message(
            message.chat.id,
            "Пустое значение. Попробуйте снова через меню.",
            reply_markup=main_menu_keyboard(),
        )
        return

    prompt = bot.send_message(message.chat.id, f"Введите перевод для '{ru_word}':")
    bot.register_next_step_handler(prompt, add_word_finalize, ru_word)


def add_word_finalize(message, ru_word: str):
    """Сохраняет новое персональное слово пользователя."""

    en_word = (message.text or "").strip()
    if not en_word:
        bot.send_message(
            message.chat.id,
            "Пустое значение. Попробуйте снова через меню.",
            reply_markup=main_menu_keyboard(),
        )
        return

    is_added, personal_count = WordService.add_personal_word(
        user_id=message.chat.id,
        russian=ru_word,
        english=en_word,
    )

    if not is_added:
        bot.send_message(
            message.chat.id,
            "Такое слово уже есть в вашем персональном словаре.",
            reply_markup=main_menu_keyboard(),
        )
        return

    bot.send_message(
        message.chat.id,
        (
            f"Слово '{ru_word}' добавлено!\n"
            f"Вы изучаете {personal_count} персональных слов."
        ),
        reply_markup=main_menu_keyboard(),
    )


def delete_word_start(message):
    """Показывает персональные слова для выбора удаления."""

    user_id = message.chat.id
    words = WordService.get_personal_words(user_id)

    if not words:
        bot.send_message(
            user_id,
            "Ваш личный словарь пуст!",
            reply_markup=main_menu_keyboard(),
        )
        return

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for word in words:
        markup.add(types.KeyboardButton(word.russian))
    markup.add(types.KeyboardButton("Отмена"))

    prompt = bot.send_message(
        user_id,
        "Выберите слово из списка для удаления:",
        reply_markup=markup,
    )
    bot.register_next_step_handler(prompt, delete_word_finalize)


def delete_word_finalize(message):
    """Удаляет слово только из персонального списка текущего пользователя."""

    if message.text == "Отмена":
        bot.send_message(
            message.chat.id,
            "Отменено.",
            reply_markup=main_menu_keyboard(),
        )
        return

    deleted = WordService.delete_personal_word(message.chat.id, message.text)
    if not deleted:
        bot.send_message(
            message.chat.id,
            "Слово не найдено.",
            reply_markup=main_menu_keyboard(),
        )
        return

    bot.send_message(
        message.chat.id,
        f"Слово '{message.text}' удалено из вашего словаря!",
        reply_markup=main_menu_keyboard(),
    )


if __name__ == "__main__":
    print(f"Бот запущен.. БД: {get_dsn()}")
    bot.infinity_polling(skip_pending=True)
