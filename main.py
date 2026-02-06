import os
import random
from dotenv import load_dotenv
import telebot
from telebot import types
from sqlalchemy.orm import joinedload
from ORM import get_session, User, Word, Translation, UserWord, init_db

load_dotenv()
token = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(token)

init_db()

def main_menu_keyboard():
    """Главное меню"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_quiz = types.KeyboardButton("Викторина 🧠")
    btn_list = types.KeyboardButton("Список слов 📖")  # Новая кнопка
    btn_add = types.KeyboardButton("Добавить слово ➕")
    btn_del = types.KeyboardButton("Удалить слово 🔙")
    markup.add(btn_quiz, btn_list, btn_add, btn_del)
    return markup


def quiz_keyboard(correct_word, all_words):
    """Клавиатура для квиза"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    others = [w.translation.english for w in all_words if w.id != correct_word.id]
    num_options = min(len(others), 3)
    options = random.sample(others, num_options) + [correct_word.translation.english]
    random.shuffle(options)

    markup.add(*[types.KeyboardButton(opt) for opt in options])
    markup.row(types.KeyboardButton('Выйти в меню 🏠'))
    return markup


# --- ЛОГИКА СЛОВ ---

def get_user_words(cid):
    """Общие слова + личные для квиза"""
    session = get_session()
    try:
        common = session.query(Word).options(joinedload(Word.translation)).filter(Word.is_common == True).all()
        user_w = session.query(Word).options(joinedload(Word.translation)).join(UserWord).filter(
            UserWord.user_id == cid).all()
        return list(set(common + user_w))
    finally:
        session.close()


def get_only_personal_words(cid):
    """Только слова, добавленные конкретным пользователем"""
    session = get_session()
    try:
        return session.query(Word).options(joinedload(Word.translation)).join(UserWord).filter(
            UserWord.user_id == cid).all()
    finally:
        session.close()


# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start_bot(message):
    cid = message.chat.id
    bot.clear_step_handler_by_chat_id(cid)

    session = get_session()
    if not session.query(User).filter(User.id == cid).first():
        session.add(User(id=cid))
        session.commit()
    session.close()

    welcome_text = (
        "Привет 👋 Давай попрактикуемся в английском языке.\n\n"
        "Выбери действие в меню ниже ⬇️"
    )
    bot.send_message(cid, welcome_text, reply_markup=main_menu_keyboard())


@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    cid = message.chat.id

    if message.text == "Викторина 🧠":
        send_quiz_question(message)

    elif message.text == "Список слов 📖":
        show_personal_words(message)

    elif message.text == "Добавить слово ➕":
        msg = bot.send_message(cid, "Введите слово на РУССКОМ:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, add_word_ru)

    elif message.text == "Удалить слово 🔙":
        delete_word_start(message)

    else:
        bot.send_message(cid, "Используйте кнопки меню.", reply_markup=main_menu_keyboard())


# --- ЛОГИКА СПИСКА СЛОВ ---

def show_personal_words(message):
    cid = message.chat.id
    words = get_only_personal_words(cid)

    if not words:
        bot.send_message(cid, "Ваш личный список слов пока пуст. Добавьте новые слова кнопкой ➕",
                         reply_markup=main_menu_keyboard())
        return

    text = "📝 **Ваш личный словарь:**\n\n"
    for i, w in enumerate(words, 1):
        text += f"{i}. {w.russian} — {w.translation.english}\n"

    bot.send_message(cid, text, parse_mode='Markdown', reply_markup=main_menu_keyboard())


# --- ЛОГИКА ВИКТОРИНЫ ---

def send_quiz_question(message, prefix=""):
    cid = message.chat.id
    words = get_user_words(cid)

    if len(words) < 4:
        bot.send_message(cid, "Нужно минимум 4 слова в базе! Добавьте свои слова.", reply_markup=main_menu_keyboard())
        return

    target_word = random.choice(words)
    markup = quiz_keyboard(target_word, words)

    full_text = f"{prefix}\n\nКак переводится слово: *{target_word.russian}*?"
    bot.send_message(cid, full_text.strip(), reply_markup=markup, parse_mode='Markdown')
    bot.register_next_step_handler(message, check_quiz_answer, target_word.translation.english)


def check_quiz_answer(message, correct_option):
    cid = message.chat.id
    user_answer = message.text

    if user_answer == 'Выйти в меню 🏠' or user_answer == '/start':
        bot.clear_step_handler_by_chat_id(cid)
        return bot.send_message(cid, "Возвращаюсь в меню...", reply_markup=main_menu_keyboard())

    if user_answer and user_answer.lower() == correct_option.lower():
        send_quiz_question(message, prefix="Отлично! ✨")
    else:
        bot.send_message(cid, "Неверно ❌ Попробуй еще раз!")
        bot.register_next_step_handler(message, check_quiz_answer, correct_option)


# --- ДОБАВЛЕНИЕ СЛОВА ---

def add_word_ru(message):
    ru_word = message.text
    if not ru_word: return
    msg = bot.send_message(message.chat.id, f"Введите перевод для '{ru_word}':")
    bot.register_next_step_handler(msg, add_word_finalize, ru_word)


def add_word_finalize(message, ru_word):
    en_word = message.text
    if not en_word: return
    session = get_session()
    try:
        new_word = Word(russian=ru_word, is_common=False)
        new_word.translation = Translation(english=en_word)
        session.add(new_word)
        session.flush()
        session.add(UserWord(user_id=message.chat.id, word_id=new_word.id))
        session.commit()
        bot.send_message(message.chat.id, f"Слово '{ru_word}' добавлено!", reply_markup=main_menu_keyboard())
    except:
        session.rollback()
        bot.send_message(message.chat.id, "Ошибка сохранения.", reply_markup=main_menu_keyboard())
    finally:
        session.close()


# --- УДАЛЕНИЕ СЛОВА ---

def delete_word_start(message):
    cid = message.chat.id
    words = get_only_personal_words(cid)

    if not words:
        bot.send_message(cid, "Ваш личный словарь пуст!", reply_markup=main_menu_keyboard())
        return

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for w in words: markup.add(types.KeyboardButton(w.russian))
    markup.add(types.KeyboardButton('Отмена'))

    msg = bot.send_message(cid, "Выберите слово из списка для удаления:", reply_markup=markup)
    bot.register_next_step_handler(msg, delete_word_finalize)


def delete_word_finalize(message):
    if message.text == 'Отмена':
        return bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu_keyboard())

    session = get_session()
    try:
        word_obj = session.query(Word).join(UserWord).filter(
            UserWord.user_id == message.chat.id, Word.russian == message.text).first()
        if word_obj:
            session.delete(word_obj)
            session.commit()
            bot.send_message(message.chat.id, f"Слово '{message.text}' удалено!", reply_markup=main_menu_keyboard())
        else:
            bot.send_message(message.chat.id, "Слово не найдено.", reply_markup=main_menu_keyboard())
    finally:
        session.close()


if __name__ == '__main__':
    print("Бот запущен..")
    bot.infinity_polling(skip_pending=True)