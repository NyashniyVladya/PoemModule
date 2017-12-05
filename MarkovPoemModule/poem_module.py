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

    MorpherURL = "http://morpher.ru/accentizer"
    MorpherTextAreaID = (
        "ctl00_ctl00_BodyPlaceHolder_ContentPlaceHolder1_TextBox1"
    )
    morpherButtonID = (
        "ctl00_ctl00_BodyPlaceHolder_ContentPlaceHolder1_SubmitButton"
    )

    rifmusURL = "https://rifmus.net/custom/"
    rifmusLetterCSS = (
        "#stressform > table > tbody > tr > td:nth-child({0}) > label"
    )
    rifmusButtonCSS = "#ssub"
    rifmusResult = "#result > div:nth-child(3)"

    def __init__(self, poet_module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poet_module = poet_module
        self.__browser_lock = Lock()
        self.__wait_object = WebDriverWait(self, 60)

        if self.poet_module.browser is not self:
            self.poet_module.browser = self

    def _get_rhymes(self, word):
        """
        Ищет рифмы на сайте, с указанием ударения.
        """
        letNum = (
            self.poet_module.accentuation_dictionary._get_acc_letter(word)
        )
        with self.__browser_lock:
            try:

                _url = parse.urljoin(self.rifmusURL, parse.quote(word))
                self.get(_url)

                elem_name = self.rifmusLetterCSS.format(letNum)
                letter = self._wait_element(elem_name, By.CSS_SELECTOR)
                letter.click()

                button = self._wait_element(
                    self.rifmusButtonCSS,
                    By.CSS_SELECTOR
                )
                button.click()

                result = self._wait_element(self.rifmusResult, By.CSS_SELECTOR)
                result = result.text.strip().lower()

                for wrd in self.spaces.split(result):
                    if self.poet_module.rhyme_dictionary.is_rus_word(wrd):
                        yield wrd

            except TimeoutException:
                pass

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
                self.get(self.MorpherURL)
                area = self._wait_element(self.MorpherTextAreaID)
                button = self._wait_element(self.morpherButtonID)

                area.clear()
                area.send_keys(word.strip().lower())
                button.click()

                new_area = self._wait_element(self.MorpherTextAreaID)

                result = tuple(
                    filter(
                        bool,
                        map(self.format_word, new_area.text.split(SPLITTER))
                    )
                )
                return (result or None)
            except TimeoutException:
                return None

    def _wait_element(self, element, elem_type=By.ID):
        """
        Ожидает загрузки элемента, указанного в element_id, и возвращает его.
        """
        return self.__wait_object.until(
            expected_conditions.visibility_of_element_located(
                (elem_type, element)
            ),
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
        backup_file = "{0}.backup".format(path.splitext(self.file_database)[0])
        with open(backup_file, "w", encoding="utf-8") as js_file:
            json.dump(self.database, js_file, ensure_ascii=False)
        copy2(backup_file, self.file_database)
        remove(backup_file)

    def load_dump(self):
        with open(self.file_database, "rb") as js_file:
            self.database = dict(json.load(js_file))


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

        if self.poet_module.browser:
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


class RhymeCreator(_SessionParent):

    URL = "https://rifmus.net/rifma/"
    RUS = tuple(map(chr, range(1072, 1104))) + ("ё",)

    def __init__(self, poet_module):
        super().__init__("rhymes")
        self.poet_module = poet_module

    def is_rus_word(self, word):
        if not word:
            return False
        return all(map(lambda s: (s.lower() in self.RUS), word))

    def get_rhymes(self, word):
        word = word.lower().strip()
        rhymes = self.database.get(word, None)
        if rhymes is not None:
            return rhymes
        rhymes = self.database[word] = list(
            self.__get_rhymes(word)
        )
        self.create_dump()
        return rhymes

    def ask_for_user(self, word):

        question = (
            "[стихомодуль]\r\n"
            "Какие рифмы у слова {0!r}?\r\n"
            "(Ответ - рифмующиеся слова, через запятую)\r\n"
        ).format(word)

        answer = self.poet_module.user_feedback.ask_to_vk(question)

        for part in answer.split(","):
            part = part.lower().strip()
            if self.is_rus_word(part):
                yield part

    def __get_rhymes(self, word):

        if self.poet_module.browser:
            yield from self.poet_module.browser._get_rhymes(word)

        else:
            _url = parse.urljoin(self.URL, parse.quote(word))
            while True:
                sleep(.5)
                print("Запрос рифмы к слову {0!r}.".format(word))
                req = self.get(_url)
                if req.status_code in (200, 404):
                    break
                print(
                    "Ошибка запроса. Код {0}.\r\n{1!r}".format(
                        req.status_code,
                        req.text
                    )
                )
            if req.status_code == 200:
                page = BeautifulSoup(req.text, "lxml")
                wordsElement = page.findChild(attrs={"class": "multicolumn"})
                if wordsElement:
                    for element in wordsElement.findAll("li"):
                        rhyme = element.getText().lower().strip()
                        if self.is_rus_word(rhyme):
                            yield rhyme

            elif self.poet_module.user_feedback.use_module:
                _counter = 0
                while True:
                    _counter += 1
                    if _counter > self.poet_module.user_feedback.try_count:
                        raise NotVariantExcept("Запросы исчерпаны.")
                    accs = list(self.ask_for_user(word))
                    if accs:
                        yield from accs
                        break


class Poem(object):

    meters = {
        "хорей": "10",
        "ямб": "01",
        "дактиль": "100",
        "амфибрахий": "010",
        "анапест": "001"
    }

    def __init__(
        self,
        poet_object,
        verse="AbAb",
        meter_size=4,
        meter="ямб",
        time_to_write=0,
        *used_words
    ):

        while True:
            _meter = self.meters.get(meter, None)
            if _meter:
                break
            meter = choice(tuple(self.meters.keys()))

        self.poet = poet_object
        self.verse = verse
        self.__used_words = set(used_words)
        self.temp_used_words = frozenset()

        self.string_storage = dict.fromkeys(self.verse, [])

        self.sizes = dict(self.__get_size_dict(verse, meter_size, _meter))

        self.poem = ""

        self.time_to_write = int(time_to_write)

        self.__poem_type_tag = "#{0}стопный_{1}".format(meter_size, meter)

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

    def get_string(self, rhymes, final_meter):
        try:
            for token in self.poet._get_generate_tokens(
                *rhymes,
                final_meter=final_meter,
                poem_object=self,
                size=-1
            ):
                yield token
        except StringIsFull:
            pass

    def set_rhyme_construct(self, key):

        if self.time_to_write > 0:
            _start_time = time()

        try_counter = 0
        _final_meter, re_string_meter = self.sizes[key]
        string_size = len(_final_meter)
        self.temp_used_words = frozenset(
            self.poet._get_synonyms(self.__used_words)
        )
        _string_len = self.verse.count(key)

        while True:

            if (self.time_to_write > 0) and _start_time:
                if time() >= (_start_time + self.time_to_write):
                    raise WaitExcept("Вышло время на написание строфы.")

            try_counter += 1
            need_rhymes = _need_rhymes = ()
            _loop_counter = 0
            self.string_storage[key] = []
            print(
                "{0} попытка генерации строфы {1!r}.".format(
                    try_counter,
                    key
                )
            )
            while True:

                if need_rhymes or self.temp_used_words:
                    _loop_counter += 1

                if _loop_counter > 50:
                    break

                try:
                    string = tuple(
                        self.get_string(
                            rhymes=need_rhymes,
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

                if (len(self.string_storage[key]) + 1) < _string_len:
                    try:
                        _need_rhymes = self.poet.get_rhyme_words(string)
                    except NotVariantExcept:
                        continue
                    if not _need_rhymes:
                        continue

                    need_rhymes = _need_rhymes

                _loop_counter = 0
                self.string_storage[key].append(string)
                if len(self.string_storage[key]) >= _string_len:
                    return

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
                if token in "$^":
                    _need_capialize = True
                continue
            if Poet.ONLY_WORDS.search(token):
                out_text += " "
            if _need_capialize:
                _need_capialize = False
                token = token.title()
            out_text += token

        return out_text.strip()

    def create_poem(self):
        self.poem = self.__poem_type_tag
        self.poem += "\r\n\r\n\r\n"
        for key in self.string_storage.copy().keys():
            self.set_rhyme_construct(key)
        for key in self.verse:
            string = self.string_storage[key].pop(0)
            self.poem += self.tuple_to_string(string)
            self.poem += "\r\n"


class Poet(MarkovTextGenerator):

    vowels = "ауоыиэяюеёaeiouy"
    tokensBase = "poetModuleTokens"

    def __init__(self, chain_order=2, **kwargs):
        super().__init__(chain_order=chain_order, **kwargs)

        self.rhyme_dictionary = RhymeCreator(poet_module=self)
        self.accentuation_dictionary = AccentuationCreator(poet_module=self)
        self.synonyms_dictionary = SynonymsCreator(poet_module=self)
        self.user_feedback = UserFeedback(poet_module=self)
        self.browser = None
        self.poems = []
        self.vocabulars_in_tokens = []
        self._const_fullstring_weight = 50

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

    def get_rhyme_words(self, string_tuple):

        for s in string_tuple:
            if not s.isalpha():
                continue
            if self.syllable_calculate(s):
                return self.rhyme_dictionary.get_rhymes(s)
            break
        return []

    def token_is_correct(self, token):
        """
        Подходит ли токен, для генерации стиха.
        Допускаются русские слова, знаки препинания и символы начала и конца.
        """
        if self.rhyme_dictionary.is_rus_word(token):
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
        need_rhymes,
        final_meter,
        poem_object,
        start_words
    ):
        """
        Перегрузка дефолтной функции,
        для выстраивания ритмической конструкции, во время генерации.

        :need_rhymes:
            Если необходимо найти рифму,
            но не вышло это сделать, при первичной подборке токенов.
            Если True, функция попытается это сделать.

        :start_words:
            Варианты рифм.

        """
        if need_rhymes:
            need_rhymes = bool(start_words)
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
                if need_rhymes:
                    raise NotRightMeter("Рифма не найдена.")
                print(_string_now)
                raise StringIsFull("Строка готова.")
        print(_string_now)
        good_variants = []
        _weights = []
        variants_list = list(frozenset(variants))
        shuffle(variants_list)
        for token in variants_list:
            if len(good_variants) >= 10:
                #  Иначе цикл может затянуться на несколько тысяч итераций.
                break
            if not self.rhyme_dictionary.is_rus_word(token):
                if need_rhymes and (len(current_string) > 5):
                    continue
                if self.token_is_correct(token):
                    good_variants.append(token)
                    _weight = variants.count(token)
                    _weights.append(_weight)
                continue
            if need_rhymes:
                if token not in start_words:
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
            if token in poem_object.temp_used_words:
                _weight *= 10
            _weight *= variants.count(token)
            good_variants.append(token)
            _weights.append(_weight)
        if not good_variants:
            raise NotRightMeter("Не найдено ни одного пригодного варианта.")
        _result_choice = choices(good_variants, weights=_weights, k=1)[0]
        if need_rhymes:
            need_rhymes = (_result_choice not in start_words)
        return (_result_choice, {"need_rhymes": need_rhymes})

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
            return 10
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

    def get_start_array(self, *rhymes):
        """
        Перегрузка стандартной функции.
        Если не находит нужного предложения, бросает исключение.

        Возвращает кортеж вида:
            (
                Стартовый массив -> tuple,
                Зарифмовано ли уже -> bool
            )
        """
        if not self.start_arrays:
            raise MarkovTextExcept("Не с чего начинать генерацию.")
        if not rhymes:
            return (choice(self.start_arrays), False)

        _variants = []
        _weights = []
        for tokens in self.start_arrays:
            for tok in tokens:
                if tok.isalpha():
                    weight = 0
                    for word in rhymes:
                        word = word.strip().lower()
                        for token in self.ONLY_WORDS.finditer(word):
                            if token.group() == tok:
                                weight += 1
                    if weight:
                        weight *= 2
                        _variants.append((tokens, False))
                        _weights.append(weight)
                    break
            else:
                _variants.append((tokens, True))
                _weights.append(1)

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

    def _get_synonyms(self, words_list):
        for word in words_list:
            yield word.strip().lower()
            yield from self.synonyms_dictionary.get_synonyms(word)

    def write_poem(
        self,
        verse="AbAb",
        size=4,
        meter="ямб",
        time_to_write=0,
        *start_words
    ):

        self.browser = BrowserClass(poet_module=self)
        try:
            poem = Poem(
                self,
                verse,
                size,
                meter,
                time_to_write,
                *start_words
            )
            poem.create_poem()
            _poem = poem.poem
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
