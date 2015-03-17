from setuptools import setup

setup(
    name='unpacker',
    version='0.1',
    py_modules=['unpacker'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        unpacker=unpacker:cli
    ''',
)
