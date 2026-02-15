
-- Базовые слова для заполнения общего словаря

INSERT INTO word (russian, is_common)
SELECT v.russian, TRUE
FROM (
    VALUES
        ('Красный'),
        ('Синий'),
        ('Зеленый'),
        ('Я'),
        ('Ты'),
        ('Он'),
        ('Она'),
        ('Мы'),
        ('Они'),
        ('Собака')
) AS v(russian)
LEFT JOIN word w
    ON w.russian = v.russian AND w.is_common = TRUE
WHERE w.id IS NULL;

INSERT INTO translation (english, word_id)
SELECT v.english, w.id
FROM (
    VALUES
        ('Red', 'Красный'),
        ('Blue', 'Синий'),
        ('Green', 'Зеленый'),
        ('I', 'Я'),
        ('You', 'Ты'),
        ('He', 'Он'),
        ('She', 'Она'),
        ('We', 'Мы'),
        ('They', 'Они'),
        ('Dog', 'Собака')
) AS v(english, russian)
JOIN word w ON w.russian = v.russian
LEFT JOIN translation t ON t.word_id = w.id
WHERE t.id IS NULL;
