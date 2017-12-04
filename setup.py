from setuptools import setup, find_packages
import MarkovPoemModule

setup(
    name="MarkovPoemModule",
    version=MarkovPoemModule.__version__,
    author=MarkovPoemModule.__author__,
    url="https://github.com/NyashniyVladya/PoemModule",
    packages=find_packages(),
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3.6"
    ],
    install_requires=[
        "MarkovTextGenerator>=1.5.8",
        "bs4",
        "selenium",
        "shutil"
    ],
    keywords=(
        "vladya markovgenerator markov_generator MarkovPoemModule "
        "markov_chain poem_module poem_generator poem"
    ),
    description=(
        "A poetry generator, based on the text generator on the Markov chains "
        "(MarkovTextGenerator)."
    ),
    long_description=(
        "Генератор стихов, на основе генератора текста по цепям Маркова "
        "(MarkovTextGenerator)."
    )
)
