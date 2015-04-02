# mobi

"Mobile garage sale" takes the hassle out of buying and selling stuff on-the-go.

## How to use

Clone this repository. Then, create a Python virtual environment for this project and activate it:

```bash
virtualenv venv
source venv/bin/activate
```

Install the requirements (you may need to install pip and gcc first):

```bash
pip install -r ./requirements.txt
```

Initialize the sqlite database. Call init_db() from the python interpreter:

```python
from mobi import init_db
init_db()
```

Start a local instance:

```bash
python mobi.py
```
