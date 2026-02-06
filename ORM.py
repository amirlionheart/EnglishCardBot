import sqlalchemy as sq
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import create_engine, ForeignKey

Base = declarative_base()

# Настройка подключения к БД
DSN = "sqlite:///english_bot.db"
engine = create_engine(DSN)
Session = sessionmaker(bind=engine)


class User(Base):
    __tablename__ = "user"
    # Telegram ID может быть очень длинным, используем BigInteger
    id = sq.Column(sq.BigInteger, primary_key=True)
    words = relationship("UserWord", back_populates="user")


class Word(Base):
    __tablename__ = "word"
    id = sq.Column(sq.Integer, primary_key=True)
    russian = sq.Column(sq.String(100), nullable=False)
    # Флаг для отделения стартового набора от личных слов
    is_common = sq.Column(sq.Boolean, default=False)

    # Cascade обеспечивает удаление связанных данных при удалении самого слова
    translation = relationship("Translation", back_populates="word", uselist=False, cascade="all, delete-orphan")
    users = relationship("UserWord", back_populates="word", cascade="all, delete-orphan")


class Translation(Base):
    __tablename__ = "translation"
    id = sq.Column(sq.Integer, primary_key=True)
    english = sq.Column(sq.String(100), nullable=False)
    word_id = sq.Column(sq.Integer, ForeignKey("word.id"))

    word = relationship("Word", back_populates="translation")


class UserWord(Base):
    """Связующая таблица для реализации персональных словарей"""
    __tablename__ = "user_word"
    id = sq.Column(sq.Integer, primary_key=True)
    user_id = sq.Column(sq.BigInteger, ForeignKey("user.id"))
    word_id = sq.Column(sq.Integer, ForeignKey("word.id"))

    user = relationship("User", back_populates="words")
    word = relationship("Word", back_populates="users")


def get_session():
    """Создает и возвращает новую сессию для работы с БД"""
    return Session()


def init_db():
    """Создает таблицы и заполняет базу начальным набором слов"""
    Base.metadata.create_all(engine)
    session = get_session()

    # Проверка на наличие общих слов, чтобы не дублировать их при каждом запуске
    if session.query(Word).filter(Word.is_common == True).count() == 0:
        common_set = [
            ('Красный', 'Red'), ('Синий', 'Blue'), ('Зеленый', 'Green'),
            ('Я', 'I'), ('Ты', 'You'), ('Он', 'He'), ('Она', 'She'),
            ('Мы', 'We'), ('Они', 'They'), ('Собака', 'Dog')
        ]

        for ru, en in common_set:
            new_word = Word(russian=ru, is_common=True)
            new_word.translation = Translation(english=en)
            session.add(new_word)

        session.commit()
        print("База данных инициализирована: добавлено 10 базовых слов.")

    session.close()