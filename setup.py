import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
     name='beancount-addons-davidciani',  
     version='0.1',
     #scripts=['dokr'] ,
     author="David Ciani",
     author_email="dciani@davidciani.com",
     description="My personal collection of beancount addons.",
     long_description=long_description,
     long_description_content_type="text/markdown",
     url="https://github.com/davidciani/beancount-addons",
     packages=setuptools.find_packages(),
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
     ],
     python_requires='>=3.6',
     install_requires=[
         "beancount >= 2.2.3",
     ],
)
