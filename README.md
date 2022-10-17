
# Twidge

Simple terminal widgets for simple people.

This package is mostly intended for my own personal use, but have at it.


## Quick Start

#### Install

```sh
python -m pip install twidge
```

#### Echo Keypresses

```sh
python -m twidge echo
```

```python
from twidge.widgets import echo

echo.run()
```

#### Text Editor

```sh
python -m twidge edit 'Hello World'
```

```python
from twidge.widgets import editstr

content = editstr.run('Hello World!')
```

#### Dictionary Editor

```sh
python -m twidge editdict name,email,username,password
```

```python
from twidge.widgets import editdict

favorite_colors = {'Alice': 'red', 'Bob': 'blue'}
content = editdict.run(favorite_colors)
```

## Issues

Many - known and unknown. Issues welcome.
