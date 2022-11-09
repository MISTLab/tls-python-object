from setuptools import setup, find_packages
import sys

from pathlib import Path


if sys.version_info < (3, 7):
    sys.exit('Sorry, Python < 3.7 is not supported, upgrade your python installation to use tlspyo.')


DEFAULT_KEYS_FOLDER = Path.home() / "tlspyo" / "credentials"
if not DEFAULT_KEYS_FOLDER.exists():
    DEFAULT_KEYS_FOLDER.mkdir(parents=True, exist_ok=True)


with open("README.md", "r") as fh:
    long_description = fh.read()


setup(name='tlspyo',
      packages=[package for package in find_packages()],
      version='0.1.1',
      license='MIT',
      description='Secure transport of python objects using TLS encryption',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='Yann Bouteiller, Milo Sobral',
      url='https://github.com/MISTLab/tls-python-object',
      download_url='',
      keywords=['python', 'tls', 'ssl', 'pickle', 'transfer', 'object', 'transport', 'twisted'],
      install_requires=[
        'twisted',
        'pyOpenSSL',
        'service_identity'
        ],
      extras_requires={
        "dev": ['pytest', 'pytest-timeout']
      },
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'Intended Audience :: Education',
          'Intended Audience :: Information Technology',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Topic :: Utilities',
      ],
      )
