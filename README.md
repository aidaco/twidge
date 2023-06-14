# Twidge

Simple terminal widgets for simple people.

This package is mostly intended for my own personal use, but have at it.


## Quick Start

#### Install

```sh
python -m pip install twidge
```

#### CLI

```sh
# Echo keypresses
python -m twidge echo

# ... as bytes
python -m twidge echobytes

# Edit text
python -m twidge edit 'Hello World'

# Form input
python -m twidge form name,email,username,password

# Template input
python -m twidge template "Hello, my name is {name} and I live in {town}. I prefer {language:('Python', 'JavaScript')}"
```

#### Python
```python
from twidge.widgets import *

# Echo keypresses
Echo().run()

# ... as bytes
EchoBytes().run()

# Edit strings
content = Close(EditString('Hello World!')).run()

# Form input
user_info = Close(Form(['Name', 'EMail', 'Username', 'Password'])).run()

# Template input
result = Close(EditTemplate("Hello, my name is {name} and I live in {town}. I prefer {language:('Python', 'JavaScript')}")).run()
```
