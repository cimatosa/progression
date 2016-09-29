 #!/usr/bin/env python
# -*- coding: utf-8 -*-
# To create a distribution package for pip or easy-install:
# python setup.py sdist

from setuptools import setup


author      = u"Richard Hartmann"
authors     = [author]
description = 'A python progress bar in ascii art.'
name        = 'progression'
version     = '0.1.1'

if __name__ == "__main__":
    setup(
        name=name,
        author=author,
        author_email='richard.hartmann@tu-dresden.de',
        url='https://github.com/cimatosa/progression',
        version=version,
        packages=[name],
        package_dir={name: name},
        license="BSD (3 clause)",
        description=description,
        keywords=["progress", "bar", "ascii", "art"],
        classifiers= [
            'Operating System :: Unix',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'License :: OSI Approved :: BSD License',
            'Topic :: Utilities',
            'Intended Audience :: Developers'],
        platforms=['ALL']
        )
