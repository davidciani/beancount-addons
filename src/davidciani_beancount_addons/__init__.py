# SPDX-FileCopyrightText: 2025-present David Ciani <dciani@davidciani.com>
#
# SPDX-License-Identifier: MIT

import os

import pytz

time_zone = pytz.timezone(os.getenv("DC_BEANCOUNT_TZ") or "Etc/UTC")
