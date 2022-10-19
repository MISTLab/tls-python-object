from setuptools import setup, find_packages


with open("README.md", "r") as fh:
    long_description = fh.read()


setup(name='tlspyo',
      packages=[package for package in find_packages()],
      version='0.1',
      license='MIT',
      description='Secure transport of pickled objects',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='Yann Bouteiller, Milo Sobral',
      url='https://github.com/MISTLab/tls-python-object',
      download_url='',
      keywords=['python', 'tls', 'ssl', 'pickle', 'transfer', 'object', 'transport', 'twisted'],
      install_requires=[
        'twisted'
        ],
      classifiers=[
          'DDevelopment Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'Intended Audience :: Education',
          'Intended Audience :: Information Technology',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Topic :: Scientific/Engineering :: Artificial Intelligence',
      ],
      )