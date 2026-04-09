from setuptools import setup, find_packages

setup(
    name='autodev',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'click',
    ],
    entry_points={
        'console_scripts': [
            'autodev = autodev_cli.cli:cli',
        ],
    },
)
