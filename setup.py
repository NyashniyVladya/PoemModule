from setuptools import setup, find_packages
from MarkovPoemModule import poem_module

setup(
    name="MarkovPoemModule",
    version=poem_module.__version__,
    author=poem_module.__author__,
    url="https://github.com/NyashniyVladya/PoemModule",
    packages=find_packages(),
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3.6"
    ],
    install_requires=[
        "MarkovTextGenerator>=1.5.8",
        "bs4>=4.5.3",
        "selenium>=3.3.3"
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
