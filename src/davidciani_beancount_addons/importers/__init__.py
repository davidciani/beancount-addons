# SPDX-FileCopyrightText: 2025-present David Ciani <dciani@davidciani.com>
#
# SPDX-License-Identifier: MIT
"""_summary_."""

import enum

__all__ = ["BalanceType"]


class BalanceType(enum.Enum):
    """Type of Balance directive to be inserted."""

    NONE = 0  # Don't insert a Balance directive.
    DECLARED = 1  # Insert a Balance directive at the declared date.
    LAST = 2  # Insert a Balance directive at the date following the last
    # extracted transaction.
