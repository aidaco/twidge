
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
from twidge import echoers

echoers.echobytes()
```

#### Text Editor

```sh
python -m twidge edit 'Hello World'
```

```python
from twidge import editors

content = editors.editstr('Hello World!')
```

#### Dictionary Editor

```sh
python -m twidge editdict name,email,username,password
```

```python
from twidge import editors

favorite_colors = {'Alice': 'red', 'Bob': 'blue'}
content = editors.editdict(favorite_colors)
```

## Issues

Many.
