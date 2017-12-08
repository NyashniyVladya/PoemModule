# -*- coding: utf-8 -*-
"""
Модуль, для написания стихов.

@author: Vladya
"""

import json
from urllib import parse
from requests import Session
from threading import Lock
from bs4 import BeautifulSoup
from itertools import cycle
from re import compile as re_compile
from itertools import count
from shutil import copy2
from os import (
    remove,
    path
)
from random import (
    choices,
    choice,
    shuffle
)
from time import (
    sleep,
    time
)
from os.path import (
    abspath,
    isfile,
    expanduser
)
from MarkovTextGenerator.markov_text_generator import (
    MarkovTextGenerator,
    MarkovTextExcept
)
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.wait import TimeoutException


class NotVariantExcept(Exception):
    pass


class WaitExcept(Exception):
    pass


class NotRightMeter(Exception):
    pass


class StringIsFull(Exception):
    pass


class BrowserClass(Chrome):

    spaces = re_compile("\s+")

    morpherURL = "http://morpher.ru/accentizer"
    morpherTextArea = (
        By.ID,
        "ctl00_ctl00_BodyPlaceHolder_ContentPlaceHolder1_TextBox1"
    )
    morpherButton = (
        By.ID,
        "ctl00_ctl00_BodyPlaceHolder_ContentPlaceHolder1_SubmitButton"
    )

    phoneticURL = "https://vnutrislova.net/выбор-ударения/{0}"
    phonecticResult = (
        By.CSS_SELECTOR,
        "#result > div.phonetic > p.h2.space-top > span"
    )
    phoneticConfirm = (
        By.CSS_SELECTOR,
        "#submit"
    )

    def __init__(self, poet_module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poet_module = poet_module
        self.__browser_lock = Lock()
        self.__wait_object = WebDriverWait(self, 60)

        if self.poet_module.browser is not self:
            self.poet_module.browser = self

    @staticmethod
    def phoneticLetter(letNum):
        return (
            By.XPATH,
            '//*[@id="accent_selection_form"]/div[{0}]/label'.format(letNum)
        )

    def get_phonetic_analysis(self, word):

        word = word.lower().strip()
        letNum = (
            self.poet_module.accentuation_dictionary._get_acc_letter(word)
        )
        _url = self.phoneticURL.format(word)
        with self.__browser_lock:
            self.get(_url)
            letterButton = self._wait_element(self.phoneticLetter(letNum))
            letterButton.click()
            confirmButton = self._wait_element(self.phoneticConfirm)
            confirmButton.click()
            result = self._wait_element(self.phonecticResult)
            result = result.text[1:-1].strip()
            return result

    def format_word(self, word):
        """
        Изменяет символ ударения на большую букву, в месте ударения.
        Если ударения нет - возвращает None.
        """
        word = word.strip().lower()
        if 'ё' in word:
            return self.poet_module.accentuation_dictionary._yo_formatter(word)

        ACCENT = chr(769)
        if (ACCENT not in word):
            return None
        new_word = []
        for s in word.strip():
            if s == ACCENT:
                if new_word:
                    new_word[-1] = new_word[-1].upper()
                continue
            new_word.append(s.lower())
        return "".join(new_word)

    def get_acc(self, word):
        """
        Ищет ударение на сайте. Возвращает либо кортеж вариантов, либо None.
        """
        SPLITTER = chr(124)
        with self.__browser_lock:
            try:
                self.get(self.morpherURL)
                area = self._wait_element(self.morpherTextArea)
                button = self._wait_element(self.morpherButton)

                area.clear()
                area.send_keys(word.strip().lower())
                button.click()

                new_area = self._wait_element(self.morpherTextArea)

                result = tuple(
                    filter(
                        bool,
                        map(self.format_word, new_area.text.split(SPLITTER))
                    )
                )
                return (result or None)
            except TimeoutException:
                return None

    def _wait_element(self, element):
        """
        Ожидает загрузки элемента, указанного в element, и возвращает его.
        """
        return self.__wait_object.until(
            expected_conditions.visibility_of_element_located(element),
            "Превышено время ожидания элемента {0!r}.".format(element)
        )


class UserFeedback(object):

    """
    Класс, для взамодействия с пользователем.
    """

    def __init__(self, poet_module, wait_time=60, try_count=3):

        self.poet_module = poet_module
        self.question = self.answer = None
        self.__lock = Lock()
        self.wait_time = float(wait_time)
        self.try_count = int(try_count)

        self.use_module = self.__get_module_switcher(True)

    def __get_module_switcher(self, use_module=True):
        if use_module:
            if self.poet_module.vk_object:
                if self.poet_module.vk_object.poem_module_testers:
                    return True
        return False

    def ask_to_vk(self, question_text):
        with self.__lock:
            if not self.use_module:
                return ""
            self.question = (
                self.poet_module.vk_object._feedback_text_title + question_text
            )
            self.answer = None
            _user_for_question = choice(
                self.poet_module.vk_object.poem_module_testers
            )
            while True:
                if self.poet_module.vk_object.sent(
                    target=_user_for_question,
                    text=self.question
                ):
                    break
                sleep(1.)

            print("Ожидание ответа...")
            _start_wait_time = time()
            while not self.answer:
                if (time() - _start_wait_time) >= self.wait_time:
                    self.answer = ""
                    print("Время ожидания вышло.")
                    break
                sleep(1.)
            else:
                print("Ответ {0!r} получен.".format(self.answer))
            _answer = self.answer
            self.question = self.answer = None
            return _answer


class _BackupClass(object):

    def __init__(self, file_db):
        self.database = {}
        self.file_database = abspath(expanduser("~\\{0}.json".format(file_db)))
        if not isfile(self.file_database):
            self.create_dump()
        self.load_dump()

    def create_dump(self):
        backup_file = "{0}.backup".format(path.splitext(self.file_database)[0])
        with open(backup_file, "w", encoding="utf-8") as js_file:
            json.dump(self.database, js_file, ensure_ascii=False)
        copy2(backup_file, self.file_database)
        remove(backup_file)

    def load_dump(self):
        with open(self.file_database, "rb") as js_file:
            self.database = dict(json.load(js_file))


class _SessionParent(_BackupClass, Session):

    def __init__(self, file_db):

        _BackupClass.__init__(self, file_db)
        Session.__init__(self)

        self.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 6.3; WOW64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/61.0.3163.91 "
            "Safari/537.36 "
            "OPR/48.0.2685.32"
        )


class ClausesCreator(_BackupClass):

    def __init__(self, poet_module):
        super().__init__("clauses")

        self.poet_module = poet_module

    def get_clause(self, word):
        word = word.lower().strip()
        _clause = self.database.get(word, None)
        if _clause is not None:
            return _clause

        phonems_string = self.poet_module.browser.get_phonetic_analysis(word)
        accentuations = self.poet_module.accentuation_dictionary.get_acc(word)

        syllable = 0
        for ind, symb in enumerate(phonems_string):
            if symb in self.poet_module.vowels:
                syllable += 1
                if syllable in accentuations:
                    _clause = self.database[word] = phonems_string[ind:]
                    self.create_dump()
                    return _clause


class SynonymsCreator(_SessionParent):

    URL = "http://sinonim.org/s/"

    def __init__(self, poet_module):
        super().__init__("synonyms")

        self.poet_module = poet_module

    def get_words(self, page):
        for i in count(1):
            element = page.findChild(attrs={"id": "tr{0}".format(i)})
            if not element:
                break
            word_elem = tuple(element.childGenerator())[-2]
            word = word_elem.getText().lower().strip()
            if self.poet_module.rhyme_dictionary.is_rus_word(word):
                yield word

    def get_synonyms(self, word):
        word = word.strip().lower()
        words = self.database.get(word, None)
        if words:
            return words
        _url = parse.urljoin(self.URL, parse.quote(word))
        req = self.get(_url)
        if req.status_code != 200:
            return []
        page = BeautifulSoup(req.text, "lxml")
        self.database[word] = words = list(self.get_words(page))
        self.create_dump()
        return words


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

        if sylls <= 0:
            syllable_numbers = [0]
        elif sylls == 1:
            syllable_numbers = [1]
        else:
            if 'ё' in word:
                syllable_numbers = [
                    self._get_syllable_num(self._yo_formatter(word))
                ]
            else:
                syllable_numbers = self._get_accentuation(word)
                for ind, n in enumerate(syllable_numbers[:]):
                    if n > sylls:
                        syllable_numbers[ind] = sylls

                syllable_numbers = sorted(set(syllable_numbers))

        self.database[word] = syllable_numbers
        self.create_dump()
        return syllable_numbers

    def _get_acc_letter(self, word):
        """
        Возвращает номер ударной БУКВЫ. Для поиска рифмы на сайте.
        """
        word = word.lower().strip()
        syllable = 0
        syllable_numbers = self.get_acc(word)
        for ind, let in enumerate(word, 1):
            if let in self.poet_module.vowels:
                syllable += 1
            if syllable in syllable_numbers:
                return ind
        raise NotVariantExcept("Ударение не определено.")

    @staticmethod
    def _yo_formatter(word):
        return "".join(
            map(lambda l: (l.upper() if (l == 'ё') else l), word.lower())
        )

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

        question = (
            "[стихомодуль]\r\n"
            "Где ударение в слове {0!r}?\r\n"
            "(Ответ - номера слогов, цифрой, через запятую)\r\n"
        ).format(word)

        answer = self.poet_module.user_feedback.ask_to_vk(question)

        for part in answer.split(","):
            part = part.strip()
            if not part:
                continue
            if part.isdigit():
                yield int(part)

    def __get_format_words(self, answer_page):
        """
        Парсит страницу и возвращает номера слогов ударений.
        """
        SPLITTER = chr(8212)
        acc_rule = answer_page.findChild(attrs={"class": "rule"})
        if acc_rule:
            answer_string = acc_rule.getText().strip()[:-1]
            for part in answer_string.split(","):
                word = part.split(SPLITTER)[-1].strip()
                if word:
                    yield self._get_syllable_num(word)

    def _get_accentuation(self, word):
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

        words = self.poet_module.browser.get_acc(word)
        if words:
            return list(map(self._get_syllable_num, words))

        if not self.poet_module.user_feedback.use_module:
            raise NotVariantExcept("Ударение в сети не найдено.")

        _counter = 0
        while True:
            _counter += 1
            if _counter > self.poet_module.user_feedback.try_count:
                raise NotVariantExcept("Запросы исчерпаны.")
            accs = list(self.ask_for_user(word))
            if accs:
                return accs


class Poem(object):

    meters = {
        "хорей": "10",
        "ямб": "01",
        "дактиль": "100",
        "амфибрахий": "010",
        "анапест": "001"
    }

    presets = {
        "онегинская_строфа":
            {"meter_size": 4, "meter": "ямб", "verse": "AbAb CCdd EffE gg"},
        "децима":
            {"meter_size": 4, "meter": "хорей", "verse": "AbbAA ccDDc"},
        "октава":
            {"meter_size": 5, "meter": "ямб", "verse": "aBaBaBcc"},
        "терцина":
            {"meter_size": 5, "meter": "ямб", "verse": "AbA bCb CdC dAd"}
    }

    def __init__(
        self,
        poet_object,
        time_to_write=0,
        used_words=(),
        preset=None,
        **kwargs
    ):

        preset, preset_setting = self.parse_preset(preset)
        kwargs.update(preset_setting)
        _meter = self.meters[preset_setting["meter"]]

        self.poet = poet_object
        self.__used_words = set(used_words)
        self.used_rhymes = set()
        self.temp_used_words = frozenset()

        self.verse = preset_setting["verse"]
        _verse = preset_setting["verse"].replace(chr(32), "")

        self.string_storage = dict.fromkeys(_verse, [])

        self.sizes = dict(
            self.__get_size_dict(_verse, preset_setting["meter_size"], _meter)
        )

        self.poem = ""

        self.time_to_write = int(time_to_write)

        self.__poem_type_tag = ""
        if preset:
            self.__poem_type_tag += "#{0}\r\n".format(preset)
        self.__poem_type_tag += "#{meter_size}стопный_{meter}".format(
            **preset_setting
        )

    def parse_preset(self, preset=None):
        if preset is None:
            return (None, {})
        if preset == "random":
            preset = choice(tuple(self.presets.keys()))
        pr = self.presets.get(preset, None)
        if not pr:
            return (None, {})
        return (preset, pr)

    def get_meter_and_re(self, string_name, meter_size, meter_one):

        woman_rhyme = string_name.isupper()
        final_meter = ""
        _size_counter = 0
        for part in cycle(meter_one):
            if part == '1':
                _size_counter += 1
            final_meter += part
            if _size_counter >= meter_size:
                if woman_rhyme and (final_meter[-2:] == "10"):
                    break
                elif (not woman_rhyme) and (final_meter[-1] == '1'):
                    break
        result_re_object = re_compile(final_meter.replace('1', "[01]"))
        return (final_meter, result_re_object)

    def __get_size_dict(self, verse, size, meter):

        for str_name in set(verse):
            yield (str_name, self.get_meter_and_re(str_name, size, meter))

    def is_unique_string(self, string):
        for string_list in self.string_storage.values():
            if string in string_list:
                return False
        return True

    def get_string(self, final_meter, rhyme_word=None):
        try:
            for token in self.poet._get_generate_tokens(
                rhyme_word=rhyme_word,
                final_meter=final_meter,
                poem_object=self,
                size=-1
            ):
                yield token
        except StringIsFull:
            pass

    def storage_is_full(self, key):

        for _string_type in (key.lower(), key.upper()):
            _data = self.string_storage.get(_string_type, [])
            if self.verse.count(_string_type) > len(_data):
                return False
        return True

    def get_storage_sum(self, key):
        _sum = 0
        for _string_type in (key.lower(), key.upper()):
            _sum += len(self.string_storage.get(_string_type, []))
        return _sum

    def _get_need_sum(self, key):
        _sum = 0
        for _string_type in (key.lower(), key.upper()):
            _sum += self.verse.count(_string_type)
        return _sum

    def set_rhyme_construct(self, key):

        if self.time_to_write > 0:
            _start_time = time()

        _type_iter = filter(
            lambda x: (x in self.verse),
            cycle((key.lower(), key.upper()))
        )
        string_type = _type_iter.__next__()
        _final_meter, re_string_meter = self.sizes[string_type]
        string_size = len(_final_meter)
        _string_len = self.verse.count(string_type)

        try_counter = 0
        self.temp_used_words = frozenset(
            self.poet._get_synonyms(self.__used_words)
        )

        while True:

            if (self.time_to_write > 0) and _start_time:
                if time() >= (_start_time + self.time_to_write):
                    raise WaitExcept("Вышло время на написание строфы.")

            try_counter += 1
            self.used_rhymes = set()
            word_for_rhyme = None
            _loop_counter = 0
            for _string_type in (key.lower(), key.upper()):
                if _string_type in self.string_storage.keys():
                    self.string_storage[_string_type] = []
            print(
                "{0} попытка генерации строфы {1!r}.".format(
                    try_counter,
                    key
                )
            )
            while True:

                if word_for_rhyme:
                    _loop_counter += 1

                if _loop_counter > 75:
                    break

                try:
                    string = tuple(
                        self.get_string(
                            rhyme_word=word_for_rhyme,
                            final_meter=_final_meter
                        )
                    )
                except NotVariantExcept:
                    break
                except NotRightMeter:
                    continue

                if not self.is_unique_string(string):
                    continue
                if self.poet._syll_calculate_in_tuple(string) != string_size:
                    continue

                try:
                    _temp_string_meter = self.poet.get_string_meter(string)
                except NotVariantExcept:
                    continue

                if not re_string_meter.search(_temp_string_meter):
                    continue

                if (self.get_storage_sum(key) + 1) < self._get_need_sum(key):
                    word_for_rhyme = self.poet.get_rhyme_word(string)
                    if not word_for_rhyme:
                        word_for_rhyme = None
                        continue
                    self.used_rhymes.add(word_for_rhyme)

                _loop_counter = 0
                self.string_storage[string_type].append(string)
                if self.storage_is_full(key):
                    return
                if len(self.string_storage[string_type]) >= _string_len:
                    string_type = _type_iter.__next__()
                    _final_meter, re_string_meter = self.sizes[string_type]
                    string_size = len(_final_meter)
                    _string_len = self.verse.count(string_type)

            if self.temp_used_words:
                _len_before = len(self.temp_used_words)
                self.temp_used_words = frozenset(
                    self.poet._get_synonyms(self.temp_used_words)
                )
                _len_after = len(self.temp_used_words)

                if (_len_before == _len_after) or (try_counter >= 3):
                    self.temp_used_words = frozenset()

    @staticmethod
    def tuple_to_string(string_tuple):
        out_text = ""
        _need_capialize = True
        for token in reversed(string_tuple):

            if (token in "$^") or token.isdigit():
                continue

            if Poet.ONLY_WORDS.search(token):
                out_text += " "
            if _need_capialize:
                _need_capialize = False
                token = token.title()
            out_text += token

            if Poet.END_TOKENS.search(token):
                _need_capialize = True

        return out_text.strip()

    def create_poem(self):
        empty_string_token = chr(32)
        self.poem = self.__poem_type_tag
        self.poem += "\r\n\r\n\r\n"
        for key in set(self.verse.replace(empty_string_token, "").lower()):
            self.set_rhyme_construct(key)
        for key in self.verse:
            if key != empty_string_token:
                string = self.string_storage[key].pop(0)
                self.poem += self.tuple_to_string(string)
            self.poem += "\r\n"


class Poet(MarkovTextGenerator):

    RUS = tuple(map(chr, range(1072, 1104))) + ("ё",)
    vowels = "ауоыиэяюеёaeiouy"
    tokensBase = "poetModuleTokens"

    def __init__(self, chain_order=2, **kwargs):
        super().__init__(chain_order=chain_order, **kwargs)

        ##  self.rhyme_dictionary = RhymeCreator(poet_module=self)
        self.clauses_dictionary = ClausesCreator(poet_module=self)
        self.accentuation_dictionary = AccentuationCreator(poet_module=self)
        self.synonyms_dictionary = SynonymsCreator(poet_module=self)
        self.user_feedback = UserFeedback(poet_module=self)
        self.browser = None
        self.poems = []
        self.vocabulars_in_tokens = []
        self._const_fullstring_weight = int(1e8)

        self.dump_file = abspath(expanduser("~\\poemModuleDatabase.json"))
        if not isfile(self.dump_file):
            self.create_dump()
        self.load_dump()

    @classmethod
    def is_rus_word(cls, word):
        if not word:
            return False
        return all(map(lambda s: (s.lower() in cls.RUS), word))

    def create_dump(self):
        _dump_data = {
            "poems": self.poems,
            "tokens": self.tokens_array,
            "vocabulars": self.vocabulars_in_tokens
        }
        backup_file = "{0}.backup".format(path.splitext(self.dump_file)[0])
        with open(backup_file, "w", encoding="utf-8") as js_file:
            json.dump(_dump_data, js_file, ensure_ascii=False)
        copy2(backup_file, self.dump_file)
        remove(backup_file)

    def load_dump(self):
        with open(self.dump_file, "rb") as js_file:
            _dump_data = json.load(js_file)
        self.poems = _dump_data["poems"]
        self.tokens_array = tuple(_dump_data["tokens"])
        self.vocabulars_in_tokens = _dump_data["vocabulars"]
        self.create_base()

    def create_base(self):
        super().create_base()
        self.start_arrays = tuple(frozenset(self.get_corrected_start_arrays()))

    def _is_correct_tok(self, tok):
        if self.is_rus_word(tok) and self.syllable_calculate(tok):
            return True
        return False

    def is_rhyme(self, word1, word2):
        """
        Возвращает булевое значение, рифмуются ли два переданных слова.
        """
        if self._is_correct_tok(word1) and self._is_correct_tok(word2):
            clause1 = self.clauses_dictionary.get_clause(word1)
            clause2 = self.clauses_dictionary.get_clause(word2)
            if clause1 == clause2:
                return True
        return False

    def get_rhyme_word(self, string_tuple):
        """
        Возвращает слово, которое рифмуем, или None, если оно неподходящее.
        """

        for s in string_tuple:
            if not s.isalpha():
                continue
            if self._is_correct_tok(s):
                return s
            break
        return None

    def token_is_correct(self, token):
        """
        Подходит ли токен, для генерации стиха.
        Допускаются русские слова, знаки препинания и символы начала и конца.
        """
        if self.is_rus_word(token):
            return True
        elif self.ONLY_MARKS.search(token):
            return True
        elif self.END_TOKENS.search(token):
            return True
        elif token in "$^":
            return True
        return False

    def get_corrected_start_arrays(self):

        for tokens in self.start_arrays:
            if all(map(self.token_is_correct, tokens)):
                yield tokens

    def get_optimal_variant(
        self,
        variants,
        current_string,
        need_rhyme,
        final_meter,
        poem_object,
        start_words,
        rhyme_word

    ):
        """
        Перегрузка дефолтной функции,
        для выстраивания ритмической конструкции, во время генерации.

        :need_rhyme:
            Если необходимо найти рифму,
            но не вышло это сделать, при первичной подборке токенов.
            Если True, функция попытается это сделать.

        :rhyme_word:
            Слово, для рифмовки.

        """
        if need_rhyme:
            need_rhyme = bool(rhyme_word)
        current_string = tuple(current_string)
        if self._syll_calculate_in_tuple(current_string) > len(final_meter):
            raise NotRightMeter("Размер строки больше допустимого.")
        try:
            meter = self.get_string_meter(current_string)
        except NotVariantExcept:
            raise NotRightMeter("Невозможно определить ударение.")
        _string_now = Poem.tuple_to_string(current_string)
        if meter:
            _weight = self.is_good_meter(meter, final_meter)
            if not _weight:
                raise NotRightMeter("Строка не годится, для продолжения.")
            elif _weight == self._const_fullstring_weight:
                if need_rhyme:
                    raise NotRightMeter("Рифма не найдена.")
                print(_string_now)
                raise StringIsFull("Строка готова.")
        good_variants = []
        _weights = []
        variants_list = list(frozenset(variants))
        shuffle(variants_list)
        for token in variants_list:
            if len(good_variants) > 10:
                #  Иначе цикл может затянуться на несколько тысяч итераций.
                break
            if not self.is_rus_word(token):
                if need_rhyme and (len(current_string) >= 3):
                    continue
                if self.token_is_correct(token):
                    good_variants.append(token)
                    _weight = variants.count(token)
                    _weights.append(_weight)
                continue
            _variant = current_string + (token,)
            if self._syll_calculate_in_tuple(_variant) > len(final_meter):
                continue
            try:
                _meter = self.get_string_meter(_variant)
            except NotVariantExcept:
                continue
            _weight = self.is_good_meter(_meter, final_meter)
            if not _weight:
                continue
            if need_rhyme:
                if token in poem_object.used_rhymes:
                    continue
                try:
                    is_rhymes = self.is_rhyme(rhyme_word, token)
                except NotVariantExcept:
                    continue
                if not is_rhymes:
                    continue
            if token in poem_object.temp_used_words:
                _weight *= 1000
            _weight *= variants.count(token)
            good_variants.append(token)
            _weights.append(_weight)
        if not good_variants:
            raise NotRightMeter("Не найдено ни одного пригодного варианта.")
        _result_choice = choices(good_variants, weights=_weights, k=1)[0]
        if need_rhyme:
            if self.is_rus_word(_result_choice):
                need_rhyme = False

        return (_result_choice, {"need_rhyme": need_rhyme})

    def is_good_meter(self, string_meter, full_meter):
        """
        Определяет, годится ли частичный метр, для продолжения генерации.
        Возвращает "вес" ценности следующего токена.
        """
        string_size = len(string_meter)
        if not string_size:
            return 1
        full_size = len(full_meter)
        if string_size > full_size:
            return 0
        string_size *= -1
        current_re = re_compile(full_meter[string_size:].replace('1', "[01]"))
        if current_re.search(string_meter):
            if abs(string_size) == full_size:
                return self._const_fullstring_weight
            return 1
        return 0

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

    def get_start_array(self, *not_used, rhyme_word, final_meter, poem_object):
        """
        Перегрузка стандартной функции.
        Если не находит нужного предложения, бросает исключение.

        Возвращает кортеж вида:
            (
                Стартовый массив -> tuple,
                Нужно ли продолжать поиск рифмы -> bool
            )
        """
        if not self.start_arrays:
            raise MarkovTextExcept("Не с чего начинать генерацию.")
        if not rhyme_word:
            return (choice(self.start_arrays), False)

        _variants = []
        _start_arr_list = list(self.start_arrays)
        shuffle(_start_arr_list)
        for tokens in _start_arr_list:
            if len(_variants) > 10:
                break
            for tok in tokens:
                if tok.isalpha():
                    if self.is_rus_word(tok):
                        if tok not in poem_object.used_rhymes:
                            try:
                                is_rhymes = self.is_rhyme(rhyme_word, tok)
                            except NotVariantExcept:
                                break
                            if is_rhymes:
                                _variants.append((tokens, False))
                    break
            else:
                _variants.append((tokens, True))

        if not _variants:
            raise NotVariantExcept("Варианты не найдены.")

        return choice(_variants)

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

    def _get_synonyms(self, words_list):
        for word in words_list:
            yield word.strip().lower()
            yield from self.synonyms_dictionary.get_synonyms(word)

    def write_poem(self, preset=None, **kwargs):

        self.browser = BrowserClass(poet_module=self)
        try:
            poem = Poem(poet_object=self, preset=preset, **kwargs)
            poem.create_poem()
            _poem = poem.poem
            print(
                "_" * 50,
                _poem,
                "_" * 50,
                sep="\r\n"
            )
            self.poems.append(_poem)
            self.create_dump()
            return _poem
        finally:
            self.browser.quit()
            self.browser = None

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
