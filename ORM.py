import os
from contextlib import contextmanager

import sqlalchemy as sq
from dotenv import load_dotenv
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

load_dotenv()

Base = declarative_base()

DSN = os.getenv("DATABASE_URL")
if not DSN:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to .env, for example: "
        "postgresql://user:password@localhost:5432/dbname"
    )

engine = create_engine(DSN)
Session = sessionmaker(bind=engine)


class User(Base):
    """Пользователь Telegram."""

    __tablename__ = "user"

    id = sq.Column(sq.BigInteger, primary_key=True)
    words = relationship("UserWord", back_populates="user")


class Word(Base):
    """Слово на русском языке."""

    __tablename__ = "word"

    id = sq.Column(sq.Integer, primary_key=True)
    russian = sq.Column(sq.String(100), nullable=False)
    is_common = sq.Column(sq.Boolean, default=False)

    translation = relationship(
        "Translation",
        back_populates="word",
        uselist=False,
        cascade="all, delete-orphan",
    )
    users = relationship(
        "UserWord", back_populates="word", cascade="all, delete-orphan"
    )


class Translation(Base):
    """Английский перевод слова."""

    __tablename__ = "translation"

    id = sq.Column(sq.Integer, primary_key=True)
    english = sq.Column(sq.String(100), nullable=False)
    word_id = sq.Column(sq.Integer, ForeignKey("word.id"), unique=True)

    word = relationship("Word", back_populates="translation")


class UserWord(Base):
    """Связь пользователя с персональным словом."""

    __tablename__ = "user_word"

    id = sq.Column(sq.Integer, primary_key=True)
    user_id = sq.Column(sq.BigInteger, ForeignKey("user.id"), nullable=False)
    word_id = sq.Column(sq.Integer, ForeignKey("word.id"), nullable=False)

    user = relationship("User", back_populates="words")
    word = relationship("Word", back_populates="users")


COMMON_SET = [
    ("Красный", "Red"),
    ("Синий", "Blue"),
    ("Зеленый", "Green"),
    ("Я", "I"),
    ("Ты", "You"),
    ("Он", "He"),
    ("Она", "She"),
    ("Мы", "We"),
    ("Они", "They"),
    ("Собака", "Dog"),
]


def get_dsn() -> str:
    """Возвращает текущую строку подключения к БД."""

    return DSN


def get_session():
    """Создает и возвращает новую сессию для работы с БД."""

    return Session()


@contextmanager
def session_scope():
    """Контекстный менеджер сессии SQLAlchemy."""

    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Создает таблицы и заполняет базовый общий словарь."""

    Base.metadata.create_all(engine)

    with session_scope() as session:
        common_exists = session.query(Word).filter(Word.is_common.is_(True)).count()
        if common_exists:
            return

        for russian, english in COMMON_SET:
            word = Word(russian=russian, is_common=True)
            word.translation = Translation(english=english)
            session.add(word)
