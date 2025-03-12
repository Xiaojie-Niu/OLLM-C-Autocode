from setuptools import setup

setup(
    name="coding_system",
    version="1.0.0",
    author="Your Name",
    description="A coding system for educational text analysis",
    packages=["coding_system"],
    install_requires=[
        "pandas>=1.5.0",
        "numpy>=1.21.0",
        "PyQt6>=6.4.0",
        "openpyxl>=3.0.10",
    ],
    entry_points={
        'console_scripts': [
            'coding_system=main:main',
        ],
    },
)