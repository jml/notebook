import os

import setuptools


def local_file(name):
    return os.path.relpath(os.path.join(os.path.dirname(__file__), name))


SOURCE = local_file("src")
README = local_file("README.md")

setuptools.setup(
    name="jmlnotes",
    # Not actually published on pypi
    version='0.0.0',
    author="Jonathan M. Lange",
    author_email="jml@mumak.net",
    packages=setuptools.find_packages(SOURCE),
    package_dir={"": SOURCE},
    url=("https://github.com/jml/notebook/"),
    license="GPL v3",
    description="jml's notebook",
    zip_safe=False,
    install_requires=[
        "attrs>=18.0.0",
        "beautifulsoup4",
        "click",
        "feedgen",
        "mako",
        "markdown",
        "pygments",
    ],
    entry_points={"console_scripts": ["jmlnotes=jmlnotes.__main__:main"]},
    long_description=open(README).read(),
)
