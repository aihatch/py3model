#!/usr/bin/python3

from setuptools import setup, find_packages

readmeFile = open("README.md", "r", encoding="utf-8")
long_description = readmeFile.read().replace(
    "./docs/", "https://github.com/aihatch/py3model/blob/master/docs/"
)
readmeFile.close()

# https://setuptools.pypa.io/en/latest/setuptools.html

setup(
    name="py3model",
    version="0.1.1",
    description="一行命令在本地启动一个 OpenAI 兼容的 LLM 服务，配套一个极简的可视化管理窗口。",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="zxl20070701",
    author_email="1904314465@qq.com",
    maintainer="zxl20070701",
    maintainer_email="1904314465@qq.com",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    url="https://github.com/aihatch/py3model",
    license="MIT",
    keywords=["gguf","model", "python3"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "llama-cpp-python==0.3.23"
    ],
    entry_points={
        "console_scripts": [
            # 命令名 = 模块路径:函数名，不要加括号！
            # 开发模式安装：pip3 install -e .
            "py3model = py3model.cli:main",
        ]
    }
)
