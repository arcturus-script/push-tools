from setuptools import setup, find_packages

setup(
    name="push-tools",
    version="0.0.1",
    keywords=["qmsg", "pushplus", "server", "wechat"],
    description="A tool supports push message.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="MIT Licence",
    url="https://github.com/arcturus-script/push-tools",
    author="ARCTURUS",
    author_email="ice99125@qq.com",
    packages=find_packages(),
    include_package_data=True,
    platforms="any",
    install_requires=["requests"],
)
