"""
setup.py — AI Clone Engine of Charles-Earl-Lipshay
"""

from setuptools import setup, find_packages

setup(
    name="lippytmai",
    version="3.0.0",
    description="AI Clone Engine of Charles-Earl-Lipshay (@lippytm)",
    author="lippytm",
    url="https://github.com/lippytm/AI-Clone-of-Charles-Earl-Lipshay-lippytm-lippytm.AI-lippytmai-",
    license="GPL-3.0",
    python_requires=">=3.9",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    package_data={
        "": ["config/*.json"],
    },
    extras_require={
        "openai": ["openai>=1.30.0"],
        "anthropic": ["anthropic>=0.27.0"],
        "hermes": ["requests>=2.31.0"],
        "ollama": ["requests>=2.31.0"],
        "openrouter": ["openai>=1.30.0"],
        "dev": ["pytest>=8.0.0"],
        "all": ["openai>=1.30.0", "anthropic>=0.27.0", "requests>=2.31.0"],
    },
    entry_points={
        "console_scripts": [
            "lippytmai=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
