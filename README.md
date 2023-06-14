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
```

#### Python
```python
from twidge import widgets

# Echo keypresses
widgets.Echo().run()

# ... as bytes
widgets.EchoBytes().run()

# Edit strings
content = widgets.Close(widgets.EditString('Hello World!')).run()

# Form input
user_info = Close(Form(['Name', 'EMail', 'Username', 'Password'])).run()
```
