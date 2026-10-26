"""Allow ``python -m grade_analytics``."""

import sys

from .cli import main

sys.exit(main())
