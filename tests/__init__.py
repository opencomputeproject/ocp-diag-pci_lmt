# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import sys
from pathlib import Path

# add the local lib to sys.path for discovery when running from source
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
