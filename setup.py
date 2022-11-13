import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md")) as f:
    README = f.read()
with open(os.path.join(here, "CHANGES.txt")) as f:
    CHANGES = f.read()

requires = ["formshare"]

tests_require = ["WebTest >= 1.3.1", "pytest", "pytest-cov"]  # py3 compat

setup(
    name="analytics",
    version="1.0",
    description="FormShare Analytics Plugin",
    long_description=README + "\n\n" + CHANGES,
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    author="QLands Technology Consultants",
    author_email="info@qlands.com",
    url="https://formshare.org",
    keywords="formshare plugin analytics",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    extras_require={"testing": tests_require},
    install_requires=requires,
    entry_points={
        "formshare.plugins": ["analytics = analytics.plugin:Analytics"],
        "formshare.celery.plugins": [
            "analytics_repository = analytics.celery_plugin:AnalyticsRepository"
        ],
    },
)
