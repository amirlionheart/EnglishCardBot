from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ORM import Translation, User, UserWord, Word, session_scope


@dataclass(frozen=True)
class WordCard:
    """DTO для работы с карточкой слова в боте."""

    id: int
    russian: str
    english: str
    is_common: bool


class WordService:
    """Сервисный слой для работы с пользовательским словарем."""

    @staticmethod
    def ensure_user(user_id: int) -> None:
        """Создаёт пользователя, если его нет в БД."""

        with session_scope() as session:
            exists = session.query(User).filter(User.id == user_id).first()
            if not exists:
                session.add(User(id=user_id))

    @staticmethod
    def get_training_words(user_id: int) -> list[WordCard]:
        """Возвращает общий и персональный словарь пользователя."""

        with session_scope() as session:
            words = (
                session.query(Word)
                .options(joinedload(Word.translation))
                .outerjoin(
                    UserWord,
                    (UserWord.word_id == Word.id) & (UserWord.user_id == user_id),
                )
                .filter((Word.is_common.is_(True)) | (UserWord.id.is_not(None)))
                .all()
            )

            return [
                WordCard(
                    id=word.id,
                    russian=word.russian,
                    english=word.translation.english,
                    is_common=word.is_common,
                )
                for word in words
                if word.translation
            ]

    @staticmethod
    def get_personal_words(user_id: int) -> list[WordCard]:
        """Возвращает только персональные слова пользователя."""

        with session_scope() as session:
            words = (
                session.query(Word)
                .options(joinedload(Word.translation))
                .join(UserWord)
                .filter(UserWord.user_id == user_id)
                .all()
            )

            return [
                WordCard(
                    id=word.id,
                    russian=word.russian,
                    english=word.translation.english,
                    is_common=word.is_common,
                )
                for word in words
                if word.translation
            ]

    @staticmethod
    def add_personal_word(user_id: int, russian: str, english: str) -> tuple[bool, int]:
        """Добавляет слово в персональный словарь.

        Returns:
            tuple[bool, int]:
                - bool: True если новое слово/связь добавлены, False если дубликат.
                - int: текущее количество персональных слов пользователя.
        """

        ru_norm = russian.strip()
        en_norm = english.strip()

        with session_scope() as session:
            candidates = (
                session.query(Word)
                .join(Translation)
                .filter(func.lower(Translation.english) == en_norm.lower())
                .all()
            )
            existing_word = next(
                (
                    word
                    for word in candidates
                    if word.russian.casefold() == ru_norm.casefold()
                ),
                None,
            )

            if not existing_word:
                existing_word = Word(russian=ru_norm, is_common=False)
                existing_word.translation = Translation(english=en_norm)
                session.add(existing_word)
                session.flush()

            link_exists = (
                session.query(UserWord)
                .filter(
                    UserWord.user_id == user_id,
                    UserWord.word_id == existing_word.id,
                )
                .first()
            )

            if link_exists:
                count = (
                    session.query(UserWord).filter(UserWord.user_id == user_id).count()
                )
                return False, count

            session.add(UserWord(user_id=user_id, word_id=existing_word.id))
            session.flush()

            count = session.query(UserWord).filter(UserWord.user_id == user_id).count()
            return True, count

    @staticmethod
    def delete_personal_word(user_id: int, russian_word: str) -> bool:
        """Удаляет только связь UserWord для конкретного пользователя."""

        with session_scope() as session:
            user_word = (
                session.query(UserWord)
                .join(Word)
                .filter(
                    UserWord.user_id == user_id,
                    Word.russian == russian_word,
                )
                .first()
            )

            if not user_word:
                return False

            session.delete(user_word)
            return True
