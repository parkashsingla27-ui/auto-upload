import logging
try:
    from telegram.ext import Update
    print("SUCCESS: Imported Update from telegram.ext")
except ImportError as e:
    print(f"FAILURE: {e}")

try:
    from telegram import Update
    print("SUCCESS: Imported Update from telegram")
except ImportError as e:
    print(f"FAILURE: {e}")
