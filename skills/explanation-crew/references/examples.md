# Before / after — worked examples

Real exchanges from one session: explaining how an LLM uses memory (layers, Q/K/V, KV-cache) to a project manager who is strong technically but new to ML. Each pair shows the user's reaction to the "before" and the version that worked. Use them as patterns, not templates.

## Contents

1. Figurative verb → actor's literal action
2. Coined label → what is stored
3. Term dropped in passing → anchor in the user's world
4. Fused phrase → whole first, then parts
5. Description → checkable toy numbers
6. Quoted fragment → continue from that point
7. "One paragraph" → one paragraph

---

## 1. Figurative verb → actor's literal action

**Before:** «Q — что этот токен ищет в тексте до себя.»

**User:** «как токен может вообще что-то искать? как 5120 чисел что-то ищут?» — and after a disclaimer «столбцы ничего не ищут»: «так а нахер ты пишешь слово ищут, если они ничего не ищут?»

**After:**

> В памяти видеокарты есть три вещи:
> 1. Описание каждого токена — список чисел.
> 2. Веса — числа, сохранённые в модели при обучении.
> 3. Программа — она выполняет арифметику над этими числами.
>
> Шаг 1. Программа умножает числа описания «ла» на веса и складывает. Получает три коротких списка: Q, K, V.
> Шаг 2. Программа записывает K и V в память. …

Why it works: the only actor is the program; data only gets read and written. The word «ищет» is gone, not explained away.

## 2. Coined label → what is stored

**Before:** «Карточки на каждый токен ведут 16 слоёв из 64.» / «48 слоёв держат листок.»

**User:** «слово "карточки" я тоже не пойму, это слово сродни "ищу"».

**After:**

> Когда слой посчитал для токена списки K и V, программа записывает их в память видеокарты. Больше ничего не записывается: два списка чисел — K (1 024 числа) и V (1 024 числа).
> Каждое число — 2 байта. 2 048 × 2 = 4 096 байт = 4 КиБ.

Why it works: the label is replaced by its contents and its size; the user can now reason about memory without learning a new noun.

## 3. Term dropped in passing → anchor in the user's world

**Before:** «Для этой части слоя нужны три таблицы: W_Q, W_K и W_V.»

**User:** «ты начинаешь говорить о каких-то таблицах, о которых я нихера не знаю… будто я доменный эксперт».

**After:**

> Вы наверняка видели балльную оценку поставщика:
> `итог = качество × 0,5 + цена × 0,3 + срок × 0,2`
> Числа 0,5, 0,3, 0,2 — это веса. Модель — это миллиарды таких весов. Все расчёты в слое — такие балльные оценки, только их очень много.

Why it works: the kind of thing (a weighted sum) is defined through something the user already uses at work, before the model-specific instance.

## 4. Fused phrase → whole first, then parts

**Before:** «У новой модели K и V пишут только 16 слоёв из 64, остальные 48 держат набор.»

**User:** «почему новой модели нужно меньше слоёв?» and later «почему 48 слоёв? их же в новой тоже 64?»

**After:**

> У обеих моделей по 64 слоя. Разница в том, какого вида эти слои.
> — У старой все 64 слоя одного вида: каждый записывает K и V каждого токена.
> — У новой два вида: 16 слоёв записывают K и V каждого токена, 48 — не записывают.
> 16 + 48 = 64.

Why it works: the whole (64 for both) is stated before the split, so the parts cannot be misread as "fewer".

## 5. Description → checkable toy numbers

**Before:** «Q сравнивается с K прошлых токенов, от похожих берётся больше V.»

**After:**

```
Q «ла» = [2, 1]
«мама»: K [0, 1] → 2×0 + 1×1 = 1
« мы»:  K [2, 1] → 2×2 + 1×1 = 5   ← больше всех
«ла»:   K [1, 0] → 2×1 + 1×0 = 2
доли: 2 % / 93 % / 5 %
смесь V: 2 % × [10, 0] + 93 % × [0, 10] + 5 % × [5, 5] = [0,45; 9,55]
```

Why it works: "attention" stops being a word and becomes five lines the user can recompute. Real sizes (1 024 numbers, 64 layers) come after, separately.

## 6. Quoted fragment → continue from that point

**User quotes:** «> ячейки только …» and asks two questions, adding: «когда я отправляю вопросы с середины текста, ты переобъясняешь и захватываешь объяснение, которое я не дочитал… я не могу читать дальше, пока не понял текущую историю».

**After:** answer the two questions, then re-explain everything that followed the quoted point in the previous message (sizes per token, the second kind of layer, the summary), rewritten with the clarification.

## 7. "One paragraph" → one paragraph

**User:** «слишком много деталей, я даже читать это сообщение не буду. на верхнем уровне абстракции в один абзац».

**After (whole answer):**

> Сначала я объяснял образами («ищет», «карточка», «листок») и терминами без определений, а вы читаете буквально — поэтому образ подменял механизм, а неясный термин блокировал чтение. Стало лучше, когда я перешёл на буквальное описание (есть числа и программа, которая их умножает и складывает), вводил каждое понятие через знакомую вещь до его использования и показывал механизм на маленьком примере с проверяемыми числами.

Why it works: the requested level is the contract. No headings, no table, no list.
