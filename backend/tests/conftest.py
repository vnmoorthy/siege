import os
import tempfile

os.environ["SIEGE_MODE"] = "mock"
os.environ["SIEGE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["ROUND_SECONDS"] = "60"
os.environ["VARIANTS_PER_BREACH"] = "2"
