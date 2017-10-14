# -*- coding: utf-8 -*-
"""
Модуль, для написания стихов.

@author: Vladya
"""

import json
from urllib import parse
from requests import Session
from bs4 import BeautifulSoup
from itertools import cycle
from re import compile as re_compile
from os.path import (
    abspath,
    isfile,
    expanduser
)
from MarkovTextGenerator.markov_text_generator import (
    MarkovTextGenerator,
    MarkovTextExcept,
    choices,
    choice
)


class NotVariantExcept(Exception):
    pass


class _SessionParent(Session):

    def __init__(self, file_db):
        super().__init__()
        self.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 6.3; WOW64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/61.0.3163.91 "
            "Safari/537.36 "
            "OPR/48.0.2685.32"
        )
        self.database = {}
        self.file_database = abspath(expanduser("~\\{0}.json".format(file_db)))
        if not isfile(self.file_database):
            self.create_dump()
        self.load_dump()

    def create_dump(self):
        with open(self.file_database, "w", encoding="utf-8") as js_file:
            json.dump(
                self.database,
                js_file,
                ensure_ascii=False,
                indent=4
            )

    def load_dump(self):
        with open(self.file_database, "rb") as js_file:
            self.database = dict(json.load(js_file))


class AccentuationCreator(_SessionParent):

    URL = "http://где-ударение.рф/в-слове-{0}"

    def __init__(self, poet_module):
        super().__init__("accentuations")

        self.poet_module = poet_module

    def get_acc(self, word):
        """
        Возвращает кортеж номеров слогов, где можно поставить ударение.
        В большинстве случаев число будет одно.
        Несколько - в словах, с допуском, как "творог".
        """
        word = word.lower().strip()
        syllable_numbers = self.database.get(word, None)
        if isinstance(syllable_numbers, list):
            return syllable_numbers
        sylls = self.poet_module.syllable_calculate(word)
        if sylls <= 1:
            syllable_numbers = [sylls]
        else:
            syllable_numbers = self.__get_accentuation_from_network(word)
        self.database[word] = syllable_numbers
        self.create_dump()
        return syllable_numbers

    def _get_syllable_num(self, word):
        """
        Возвращает номер слога, по большой букве в написании.
        """
        syllable = 0
        for let in word:
            if let.lower() in self.poet_module.vowels:
                syllable += 1
                if let.isupper():
                    return syllable
        return syllable

    def ask_for_user(self, word):
        """
        Спрашивает про ударение у пользователя,
        на случай, если в сети информации нет.
        """
        q = input(
            (
                "Где ударение в слове {0!r}?\n"
                "(Ответ - номера слогов, цифрой, через запятую)\n"
            ).format(word)
        )
        for part in q.split(","):
            part = part.strip()
            if not part:
                continue
            if part.isdigit():
                yield int(part)

    def __get_format_words(self, answer_page):
        """
        Парсит страницу и возвращает номера слогов ударений.
        """
        acc_rule = answer_page.findChild(attrs={"class": "rule"})
        if acc_rule:
            answer_string = acc_rule.getText().strip()[:-1]
            for part in answer_string.split(","):
                word = part.split(chr(8212))[-1].strip()
                if word:
                    yield self._get_syllable_num(word)

    def __get_accentuation_from_network(self, word):
        """
        Определяет ударения. Сначала ищет информацию в интернете.
        Если безуспешно - спрашивает пользователя.
        Возвращает список чисел.
        """
        _url = self.URL.format(word)
        req = self.get(_url)
        if req.status_code == 200:
            page = BeautifulSoup(req.text, "lxml")
            accs = list(self.__get_format_words(page))
            if accs:
                return accs

        accs = list(self.ask_for_user(word))
        assert accs
        return accs


class RhymeCreator(_SessionParent):

    URL = "http://rifme.net/r/"
    RUS = tuple(map(chr, range(1072, 1106)))

    def __init__(self):
        super().__init__("rhymes")

    def is_rus_word(self, word):
        return all(map(lambda s: (s.lower() in self.RUS), word))

    def get_rhyme(self, word):
        word = word.lower().strip()
        rhymes = self.database.get(word, None)
        if rhymes is not None:
            return rhymes
        rhymes = self.database[word] = list(
            self.__get_rhymes_from_network(word)
        )
        self.create_dump()
        return rhymes

    def __get_rhymes_from_network(self, word):
        _url = parse.urljoin(self.URL, parse.quote(word))
        req = self.get(_url)
        assert (req.status_code == 200)
        page = BeautifulSoup(req.text, "lxml")
        wordsElement = page.findChild(attrs={"class": "rifmypodryad"})
        if wordsElement:
            for element in wordsElement.findAll("li"):
                rhyme = element.getText().lower().strip()
                if self.is_rus_word(rhyme):
                    yield rhyme


class Poem(object):

    def __init__(
        self,
        poet_object,
        verse="abab",
        size=(9, 8),
        meter="10",
        *start_words
    ):

        self.poet = poet_object
        self.verse = verse
        self.start_words = list(start_words)

        self.string_storage = dict.fromkeys(self.verse, [])

        self.sizes = dict(self.__get_size_dict(verse, size, meter))

        self.poem = ""

    def __get_size_dict(self, verse, size, meter):

        _set_verse = set(verse)
        if len(_set_verse) != len(size):
            raise Exception("Ритм и указание размеров не совпадают.")

        for str_name, str_size in zip(sorted(_set_verse), size):
            yield (str_name, (str_size, self.get_re_meter(str_size, meter)))

    def get_re_meter(self, size, meter):
        """
        Возвращает объект регулярного выражения,
        соответствующего нужному метру.
        """
        final_meter = ""
        for ind, part in enumerate(cycle(meter)):
            if ind >= size:
                break
            if part == '1':
                part = "[01]"
            final_meter += part
        return re_compile(final_meter)

    def is_unique_string(self, string):
        for string_list in self.string_storage.values():
            if string in string_list:
                return False
        return True

    def set_rhyme_construct(self, key):
        try_counter = 0
        string_size, string_meter = self.sizes[key]
        while True:
            try_counter += 1
            need_rhymes = ()
            _loop_counter = 0
            self.string_storage[key] = []
            print(
                "{0} попытка генерации строфы {1!r}.".format(
                    try_counter,
                    key
                )
            )
            while True:
                _loop_counter += 1
                if _loop_counter > 5:
                    break

                rhymes = need_rhymes or self.start_words
                try:
                    string = tuple(self.poet._get_generate_tokens(*rhymes))
                except NotVariantExcept:
                    break

                if not string_size:
                    string_size = self.poet._syll_calculate_in_tuple(string)
                    if string_size not in range(5, 11):
                        string_size = 0
                        continue

                if not self.is_unique_string(string):
                    continue
                if self.poet._syll_calculate_in_tuple(string) != string_size:
                    continue

                _need_rhymes = self.poet.get_rhyme_words(string)
                if not _need_rhymes:
                    continue

                _temp_string_meter = self.poet.get_string_meter(string)
                if not string_meter.search(_temp_string_meter):
                    continue

                need_rhymes = _need_rhymes

                _loop_counter = 0
                self.string_storage[key].append(string)
                if len(self.string_storage[key]) >= self.verse.count(key):
                    return

            if self.start_words:
                if try_counter > 15:
                    self.start_words = []

    def tuple_to_string(self, string_tuple):
        out_text = ""
        for token in reversed(string_tuple):
            if token in "$^":
                continue
            if self.poet.ONLY_WORDS.search(token):
                out_text += " "
            out_text += token

        return out_text.strip().capitalize()

    def create_poem(self):
        self.poem = ""
        for key in self.string_storage.copy().keys():
            self.set_rhyme_construct(key)
        for key in self.verse:
            string = self.string_storage[key].pop(0)
            self.poem += self.tuple_to_string(string)
            self.poem += "\r\n"


class Poet(MarkovTextGenerator):

    vowels = "ауоыиэяюеёaeiouy"
    tokensBase = "poetModuleTokens"

    def __init__(self, *ar, **kw):
        super().__init__(*ar, **kw)

        self.rhyme_dictionary = RhymeCreator()
        self.accentuation_dictionary = AccentuationCreator(poet_module=self)
        self.poems = []
        self.vocabulars_in_tokens = []

        self.dump_file = abspath(expanduser("~\\poemModuleDatabase.json"))
        if not isfile(self.dump_file):
            self.create_dump()
        self.load_dump()

    def create_dump(self):
        _dump_data = {
            "poems": self.poems,
            "tokens": self.tokens_array,
            "vocabulars": self.vocabulars_in_tokens
        }
        with open(self.dump_file, "w", encoding="utf-8") as js_file:
            json.dump(_dump_data, js_file, ensure_ascii=False)

    def load_dump(self):
        with open(self.dump_file, "rb") as js_file:
            _dump_data = json.load(js_file)
        self.poems = _dump_data["poems"]
        self.tokens_array = tuple(_dump_data["tokens"])
        self.vocabulars_in_tokens = _dump_data["vocabulars"]
        self.create_base()

    def get_rhyme_words(self, string_tuple):

        for s in string_tuple:
            if not self.rhyme_dictionary.is_rus_word(s):
                continue
            rhyme = self.rhyme_dictionary.get_rhyme(s)
            if rhyme:
                return rhyme
            return []
        return []

    def get_string_meter(self, string_typle):
        """
        Определяет стихотворный метр строки.
        """

        result = ""
        for token in reversed(string_typle):
            if not token.isalpha():
                continue
            accentuations = self.accentuation_dictionary.get_acc(token)
            _syllables = 0
            for let in token:
                if let.lower() in self.vowels:
                    _syllables += 1
                    result += str(int(bool((_syllables in accentuations))))
        print(result)
        return result

    def _syll_calculate_in_tuple(self, string):
        syllables = 0
        for s in string:
            syllables += self.syllable_calculate(s)
        return syllables

    def syllable_calculate(self, string_data):
        """
        Считает количество слогов в строке.
        """
        syllables = 0
        for s in string_data:
            if s.lower() in self.vowels:
                syllables += 1
        return syllables

    def _get_reversed_tokens(self, iterable):
        for token in reversed(tuple(iterable)):
            if token == "$":
                yield "^"
            elif token == "^":
                yield "$"
            else:
                yield token

    def get_start_array(self, *start_words):
        """
        Перегрузка стандартной функции.
        Если не находит нужного предложения, бросает исключение.
        """
        if not self.start_arrays:
            raise MarkovTextExcept("Не с чего начинать генерацию.")
        if not start_words:
            return choice(self.start_arrays)

        _variants = []
        _weights = []
        for tokens in self.start_arrays:
            weight = 0
            for word in start_words:
                word = word.strip().lower()
                for token in self.ONLY_WORDS.finditer(word):
                    token = token.group()
                    if token in tokens:
                        weight += 1
            if weight:
                _variants.append(tokens)
                _weights.append(weight)

        if not _variants:
            raise NotVariantExcept("Варианты не найдены.")

        return choices(_variants, weights=_weights, k=1)[0]

    def update(self, data, fromfile=True):
        """
        Перегрузка функции, с обратным расположением токенов.
        """
        func = (self._parse_from_file if fromfile else self._parse_from_text)
        new_data = tuple(self._get_reversed_tokens(func(data)))
        if new_data:
            self.tokens_array = new_data + self.tokens_array
            self.create_base()
        self.create_dump()

    def write_poem(self, verse="abab", size=(9, 8), meter="10", *start_words):
        poem = Poem(self, verse, size, meter, *start_words)
        poem.create_poem()
        _poem = poem.poem
        self.poems.append(_poem)
        self.create_dump()
        return _poem

    def add_vocabulary(self, peer_id, from_dialogue=None, update=False):
        vocabular_name = "{0}_{1}".format(peer_id, from_dialogue)
        if vocabular_name in self.vocabulars_in_tokens:
            return
        new_data = tuple(
            self._get_reversed_tokens(
                self.get_vocabulary(
                    peer_id,
                    from_dialogue,
                    update
                )
            )
        )
        if new_data:
            self.tokens_array = new_data + self.tokens_array
            self.create_base()
            self.vocabulars_in_tokens.append(vocabular_name)
        self.create_dump()
