#!/usr/bin/env python

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(name='xrootdtests',
      version='1.0',
      description='XrootD test suite for checking endpoint functionality',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='Albert L. Rossi',
      author_email='arossi@fnal.gov',
      url='https://github.com/alrossi/xrootd-tpc-utils',
      packages=['xrootd.test', 'xrootd.util'],
      scripts=['xrootd_tests'],
      classifiers=[
	"Programming Language :: Python :: 2.7",
	"License :: Fermi National Accelerator Laboratory :: BSD",
	"Operating System :: OS Independent"
     ]
)
